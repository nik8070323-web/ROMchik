"""Private Drive repository. Drive hierarchy is the durable, rebuildable catalog."""
import hashlib
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory



FOLDER = 'application/vnd.google-apps.folder'
FIELDS = 'id,name,mimeType,size,md5Checksum,version,appProperties,parents'


class StorageError(OSError):
    """Safe message: never include credential or HTTP response contents."""


class DriveRepository:
    def __init__(self, service=None):
        self.root = os.getenv('GOOGLE_DRIVE_ROOT_ID', '12nhmLr5SAhwo04TIZNJdIUSDwEtETxiL')
        self.service = service
        self.lock = threading.RLock()

    def _api(self):
        if self.service is None:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            import httplib2
            from google_auth_httplib2 import AuthorizedHttp
            credentials = Credentials(token=None, refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
                token_uri='https://oauth2.googleapis.com/token', client_id=os.environ['GOOGLE_CLIENT_ID'],
                client_secret=os.environ['GOOGLE_CLIENT_SECRET'])
            self.service = build('drive', 'v3', http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=60)), cache_discovery=False)
        return self.service.files()

    def _execute(self, request):
        return request.execute(num_retries=4)

    def _children(self, parent):
        result, token = [], None
        while True:
            response = self._execute(self._api().list(q=f"'{parent}' in parents and trashed = false",
                fields=f'nextPageToken,files({FIELDS})', pageSize=1000, pageToken=token))
            result.extend(response.get('files', []))
            token = response.get('nextPageToken')
            if not token:
                return result

    @contextmanager
    def _guard(self):
        from services.materials import ConflictError
        # googleapiclient's HTTP transport is not thread safe.
        with self.lock:
            try:
                yield
            except (ValueError, ConflictError, StorageError):
                raise
            except Exception:
                raise StorageError('Google Drive временно недоступен. Попробуйте позже.') from None

    def _folder(self, parent, name):
        matches = [f for f in self._children(parent) if f['name'] == name and f['mimeType'] == FOLDER]
        if len(matches) > 1:
            raise StorageError('Найдены одноимённые папки. Требуется проверка каталога.')
        if matches:
            return matches[0]['id']
        return self._execute(self._api().create(body={'name': name, 'mimeType': FOLDER, 'parents': [parent]}, fields='id'))['id']

    def list(self, subject=None, kind=None):
        from services.materials import Material, SECTIONS, parse_number
        with self._guard():
            result = []
            def walk(parent, sub, category, number=None, depth=0):
                if depth > 12:
                    raise StorageError('Слишком глубокая структура каталога.')
                for f in self._children(parent):
                    name = f['name']
                    match = re.fullmatch(r'(?:PZ|ПЗ|LR|ЛР)[ _-]*(\d+)', name, re.I)
                    n = int(match[1]) if match else number
                    if f['mimeType'] == FOLDER:
                        walk(f['id'], sub, category, n, depth + 1)
                    else:
                        props = f.get('appProperties', {})
                        file_kind = props.get('kind', category)
                        num = props.get('number')
                        if num:
                            n = parse_number(num)
                        elif n is None:
                            m = re.search(r'(?:[_ №-])(\d+)$', Path(name).stem)
                            n = int(m[1]) if m else None
                        if kind is None or file_kind == kind:
                            result.append(Material(sub, file_kind, n, Path(name), f['id'], str(f.get('version', '')), int(f.get('size', 0)), props.get('title') or None))
            for subfolder in self._children(self.root):
                sub = subfolder['name']
                if sub not in SECTIONS or (subject and sub != subject) or subfolder['mimeType'] != FOLDER:
                    continue
                if sub == 'Дополнительно':
                    walk(subfolder['id'], sub, 'lecture')
                else:
                    for section in self._children(subfolder['id']):
                        category = {'Лекции': 'lecture', 'Практики': 'practice', 'Учебники': 'lecture'}.get(section['name'])
                        if category and section['mimeType'] == FOLDER:
                            walk(section['id'], sub, category)
            return sorted(result, key=lambda m: (m.subject, m.kind, m.number or 0, m.path.name))

    def get(self, uid):
        # Resolve only descendants of configured root; never trust callback IDs.
        return next((m for m in self.list() if m.uid == uid), None)

    def numbered(self, subject, kind, number):
        return [m for m in self.list(subject, kind) if m.number == number]

    @staticmethod
    def snapshot(materials):
        return {m.uid: m.revision for m in materials}

    def statistics(self):
        materials = self.list()
        return [m for m in materials if m.subject != 'Дополнительно'], sum(m.subject == 'Дополнительно' for m in materials)

    def save_path(self, subject, kind, number, source, filename, expected, target_uid=None, title=None):
        from services.materials import SECTIONS, KINDS, ConflictError, parse_number
        from googleapiclient.http import MediaFileUpload
        if subject not in SECTIONS or kind not in KINDS:
            raise ValueError('Неизвестный раздел.')
        filename = Path(filename.replace('\\', '/')).name
        if not filename or filename in {'.', '..'} or any(ord(c) < 32 for c in filename):
            raise ValueError('Недопустимое имя файла.')
        with self._guard():
            target = self.get(target_uid) if target_uid else None
            if target_uid and (not target or target.subject != subject or target.kind != kind or self.snapshot([target]) != expected):
                raise ConflictError('Файл изменён. Повторите выбор и подтверждение.')
            parent = self._folder(self.root, subject)
            if subject != 'Дополнительно':
                parent = self._folder(parent, {'lecture': 'Лекции', 'practice': 'Практики'}[kind])
            if number:
                parent = self._folder(parent, ('PZ' if kind == 'practice' else 'Лекция_') + str(parse_number(str(number))))
            body = {'name': filename, 'appProperties': {'subject': subject, 'kind': kind, 'number': str(number or ''), 'title': title or ''}}
            media = MediaFileUpload(str(source), chunksize=1024 * 1024, resumable=True)
            if target:
                # Drive retains the file ID and revision history on replacement.
                request = self._api().update(fileId=target.uid, body=body, media_body=media, fields=FIELDS)
            else:
                matches = [f for f in self._children(parent) if f['name'] == filename]
                if matches:
                    raise ConflictError('Имя файла занято. Для замены выберите файл в управлении.')
                body['parents'] = [parent]
                # Do not blindly retry create: a lost response could create duplicates.
                request = self._api().create(body=body, media_body=media, fields=FIELDS)
            response = None
            while response is None:
                _, response = request.next_chunk(num_retries=4)
            with open(source, 'rb') as stream:
                checksum = hashlib.file_digest(stream, 'md5').hexdigest()
            if response.get('md5Checksum') != checksum:
                raise StorageError('Не удалось подтвердить контрольную сумму. Проверьте каталог перед повторной отправкой.')
            return response['id']

    def delete(self, uid, revision):
        from services.materials import ConflictError
        with self._guard():
            target = self.get(uid)
            if target is None or target.revision != revision:
                raise ConflictError('Файл изменён. Повторите подтверждение.')
            self._execute(self._api().update(fileId=uid, body={'trashed': True}, fields='id'))

    @contextmanager
    def local_file(self, material):
        from googleapiclient.http import MediaIoBaseDownload
        if material.size > 50 * 1024 * 1024:
            raise ValueError('Файл превышает лимит Telegram 50 МБ. Обратитесь к администратору.')
        with TemporaryDirectory(prefix='romchik-') as folder:
            path = Path(folder) / 'document'
            with self._guard(), path.open('wb') as output:
                downloader = MediaIoBaseDownload(output, self._api().get_media(fileId=material.uid), chunksize=1024 * 1024)
                done = False
                while not done:
                    _, done = downloader.next_chunk(num_retries=4)
                    if output.tell() > 50 * 1024 * 1024:
                        raise ValueError('Файл превышает лимит Telegram 50 МБ.')
            yield path
