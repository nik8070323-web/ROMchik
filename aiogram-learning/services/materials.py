"""Local material repository. Handlers do not construct storage paths."""
import hashlib
import io
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FOLDERS = {"МДК": "мдк", "ОИТ": "оит", "ИНО": "ИНО"}
SECTIONS = {**FOLDERS, "Дополнительно": "дополнительно"}
KINDS = {"lecture": "Лекция", "practice": "Практика"}
MAX_SIZE = 20 * 1024 * 1024
EXTENSIONS = {".pdf", ".docx"}


class ConflictError(ValueError):
    pass


class LimitedBuffer(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_SIZE:
            raise ValueError("Файл превышает 20 МБ.")
        return super().write(data)


@dataclass(frozen=True)
class Material:
    subject: str
    kind: str
    number: int | None
    path: Path
    uid: str
    revision: str
    size: int

    @property
    def title(self):
        label = f"{KINDS[self.kind]} № {self.number}" if self.number else self.path.stem
        if self.number and " — " in self.path.stem:
            label += " — " + self.path.stem.split(" — ", 1)[1]
        return label


def validate_title(text):
    text = (text or "").strip()
    if not text or len(text.encode("utf-8")) > 180 or any(c in text for c in '/\\') or any(ord(c) < 32 for c in text):
        raise ValueError("Введите название до 180 байт (примерно 90 русских букв), без переносов строк и символов / и \\.")
    return text


def parse_number(text):
    text = (text or "").strip()
    if not re.fullmatch(r"[0-9]{1,6}", text) or int(text) == 0:
        raise ValueError("Введите целый номер от 1 до 999999.")
    return int(text)


def validate_document(filename, size):
    extension = Path(filename or "").suffix.lower()
    if extension not in EXTENSIONS:
        raise ValueError("Отправьте документ PDF или DOCX.")
    if not size or not 0 < size <= MAX_SIZE:
        raise ValueError("Размер файла должен быть от 1 байта до 20 МБ.")
    return extension


def validate_content(content, extension):
    validate_document("file" + extension, len(content))
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("Содержимое файла не соответствует PDF.")
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(archive.namelist()):
                    raise ValueError("Файл не является документом DOCX.")
        except zipfile.BadZipFile as exc:
            raise ValueError("Файл DOCX повреждён.") from exc


class MaterialRepository:
    def __init__(self, root=BASE_DIR / "лекции"):
        self.root = Path(root)

    def folder(self, subject, kind):
        if subject not in SECTIONS or kind not in KINDS:
            raise ValueError("Неизвестный предмет или тип материала.")
        path = self.root / SECTIONS[subject]
        if kind == "practice":
            path /= "практики"
        # Never follow redirected storage directories outside the repository.
        if self.root.is_symlink() or any(p.is_symlink() for p in (path, path.parent)):
            raise ValueError("Папка материалов не должна быть символической ссылкой.")
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Недопустимая папка материалов.")
        return path

    def list(self, subject=None, kind=None):
        result = []
        for sub in ([subject] if subject else SECTIONS):
            for category in ([kind] if kind else KINDS):
                for path in self.folder(sub, category).glob("*"):
                    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                        continue
                    stat = path.stat()
                    match = re.search(r"(?:^|[_ №-])(\d+)$", path.stem.split(" — ", 1)[0])
                    number = int(match[1]) if match and int(match[1]) > 0 else None
                    uid = hashlib.sha256(str(path.relative_to(self.root)).encode()).hexdigest()[:20]
                    revision = f"{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}"
                    result.append(Material(sub, category, number, path, uid, revision, stat.st_size))
        return sorted(result, key=lambda m: (m.subject, m.kind, m.number or 0, m.path.name))

    def get(self, uid):
        return next((m for m in self.list() if m.uid == uid), None)

    def numbered(self, subject, kind, number):
        return [m for m in self.list(subject, kind) if m.number == number]

    @staticmethod
    def snapshot(materials):
        return {m.uid: m.revision for m in materials}

    def save(self, subject, kind, number, extension, content, expected, target_uid=None, title=None):
        validate_content(content, extension)
        folder = self.folder(subject, kind)
        if target_uid:
            target = self.get(target_uid)
            if target is None or target.subject != subject or target.kind != kind:
                raise ConflictError("Материал уже удалён. Откройте список заново.")
            current = [target]
            destination = target.path.with_suffix(extension)
        else:
            number = parse_number(str(number))
            current = self.numbered(subject, kind, number)
            suffix = " — " + validate_title(title) if title else ""
            destination = folder / f"{kind}_{number}{suffix}{extension}"
        if self.snapshot(current) != expected:
            raise ConflictError("Материалы изменились. Повторите выбор и подтвердите актуальную замену.")
        if len(current) > 1:
            raise ConflictError("Найдено несколько файлов с этим номером. Выберите конкретный файл в управлении.")
        old = current[0].path if current else None
        if destination.exists() and destination != old:
            raise ConflictError("Имя файла занято. Выберите файл в управлении.")
        folder.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".upload-", dir=folder)
        temporary = Path(name)
        backup = None
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            if old and old != destination:
                backup = temporary.with_name(temporary.name + ".backup")
                old.replace(backup)
            try:
                temporary.replace(destination)
            except OSError:
                if backup:
                    backup.replace(old)
                raise
            if backup:
                try:
                    backup.unlink()
                except OSError:
                    destination.unlink()
                    backup.replace(old)
                    raise
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def delete(self, uid, revision):
        material = self.get(uid)
        if material is None or material.revision != revision:
            raise ConflictError("Материал изменён или удалён. Откройте список заново.")
        material.path.unlink()

    def statistics(self):
        materials = self.list()
        return ([m for m in materials if m.subject != "Дополнительно"],
                sum(m.subject == "Дополнительно" for m in materials))


repository = MaterialRepository()
