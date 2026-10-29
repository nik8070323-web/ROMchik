import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'aiogram-learning'))
from services.materials import ConflictError
from services.drive import DriveRepository, FOLDER, StorageError


class Request:
    def __init__(self, operation):
        self.operation = operation
    def execute(self, **kwargs):
        return self.operation()
    def next_chunk(self, **kwargs):
        return None, self.operation()


class Files:
    def __init__(self):
        self.rows = {'root': dict(id='root', name='ROMchik', mimeType=FOLDER, parents=[])}
        self.contents = {}
    def list(self, q, **kwargs):
        parent = q.split("'")[1]
        return Request(lambda: {'files': [dict(f) for f in self.rows.values() if parent in f.get('parents', []) and not f.get('trashed')]})
    def create(self, body, media_body=None, **kwargs):
        def operation():
            uid = str(len(self.rows))
            row = dict(body, id=uid, version='1')
            if media_body:
                data = Path(media_body._filename).read_bytes()
                self.contents[uid] = data
                row.update(size=str(len(data)), md5Checksum=hashlib.md5(data).hexdigest(), mimeType='application/octet-stream')
            self.rows[uid] = row
            return dict(row)
        return Request(operation)
    def update(self, fileId, body, media_body=None, **kwargs):
        def operation():
            row = self.rows[fileId]
            row.update(body)
            row['version'] = str(int(row['version']) + 1)
            if media_body:
                data = Path(media_body._filename).read_bytes()
                self.contents[fileId] = data
                row.update(size=str(len(data)), md5Checksum=hashlib.md5(data).hexdigest())
            return dict(row)
        return Request(operation)
    def files(self):
        return self


class DriveTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'GOOGLE_DRIVE_ROOT_ID': 'root'})
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.api = Files()
        self.repo = DriveRepository(self.api)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'file.pdf'
        self.path.write_bytes(b'%PDF-1.4 test')

    def upload(self, name='Задание.pdf', **kwargs):
        return self.repo.save_path('МДК', 'practice', 6, self.path, name, kwargs.pop('expected', {}), **kwargs)

    def test_multiple_files_restart_and_subject_isolation(self):
        self.upload(title='Название задания'); self.upload('Таблицы.xlsx')
        rebuilt = DriveRepository(self.api)
        materials = rebuilt.numbered('МДК', 'practice', 6)
        self.assertEqual(len(materials), 2)
        self.assertEqual(rebuilt.numbered('ОИТ', 'practice', 6), [])
        self.assertEqual({m.path.name for m in materials}, {'Задание.pdf', 'Таблицы.xlsx'})
        self.assertTrue(all(m.uid and m.revision for m in materials))
        self.assertTrue(any('Название задания' in m.title for m in materials))

    def test_replace_preserves_id_and_rejects_stale_revision(self):
        uid = self.upload()
        material = self.repo.get(uid)
        self.path.write_bytes(b'%PDF-1.4 new')
        self.upload('new.pdf', target_uid=uid, expected=self.repo.snapshot([material]))
        self.assertEqual(len(self.repo.list()), 1)
        self.assertEqual(self.repo.get(uid).path.name, 'new.pdf')
        with self.assertRaises(ConflictError):
            self.repo.delete(uid, material.revision)
        current = self.repo.get(uid)
        self.repo.delete(uid, current.revision)
        self.assertEqual(self.repo.list(), [])
        self.assertTrue(self.api.rows[uid]['trashed'])

    def test_collision_no_overwrite_and_unknown_id(self):
        uid = self.upload()
        with self.assertRaises(ConflictError):
            self.upload()
        self.assertIsNone(self.repo.get('external-file'))
        self.assertEqual(self.repo.get(uid).number, 6)

    def test_safe_api_error(self):
        with patch.object(self.api, 'list', side_effect=RuntimeError('secret credential')):
            with self.assertRaises(StorageError) as error:
                self.repo.list()
        self.assertNotIn('secret', str(error.exception))

    def test_download_stream_and_cleanup(self):
        uid = self.upload()
        item = self.repo.get(uid)
        class Downloader:
            def __init__(self, output, request, **kwargs):
                self.output = output
            def next_chunk(self, **kwargs):
                self.output.write(b'%PDF-1.4 test')
                return None, True
        with patch.object(self.api, 'get_media', create=True), patch('googleapiclient.http.MediaIoBaseDownload', Downloader):
            with self.repo.local_file(item) as path:
                self.assertEqual(path.read_bytes(), self.path.read_bytes())
            self.assertFalse(path.exists())
