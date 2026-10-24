import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'aiogram-learning'))
from services.materials import MaterialRepository, ConflictError, LimitedBuffer, MAX_SIZE, parse_number, validate_document

PDF = b'%PDF-1.4\nexample'


def docx():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('word/document.xml', '<document/>')
    return buffer.getvalue()


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = MaterialRepository(Path(self.temp.name))

    def save(self, **kwargs):
        values = dict(subject='МДК', kind='lecture', number=1, extension='.pdf', content=PDF, expected={})
        values.update(kwargs)
        return self.repo.save(**values)

    def test_legacy_and_cross_extension_replacement(self):
        folder = self.repo.folder('МДК', 'lecture')
        folder.mkdir()
        original = folder / 'МДК_1.pdf'
        original.write_bytes(PDF)
        existing = self.repo.numbered('МДК', 'lecture', 1)
        self.assertEqual(existing[0].title, 'Лекция № 1')
        with self.assertRaises(ConflictError):
            self.save()
        self.assertEqual(original.read_bytes(), PDF)
        result = self.save(extension='.docx', content=docx(), expected=self.repo.snapshot(existing))
        self.assertFalse(original.exists())
        self.assertEqual(result.suffix, '.docx')
        self.assertEqual(len(self.repo.list()), 1)

    def test_safe_names_practices_statistics_and_live_listing(self):
        self.assertEqual(self.repo.list(), [])
        extension = validate_document('../../evil.PDF', len(PDF))
        path = self.save(kind='practice', extension=extension)
        self.assertTrue(path.is_relative_to(self.repo.root))
        self.assertEqual(path.name, 'practice_1.pdf')
        self.assertEqual(self.repo.list()[0].title, 'Практика № 1')
        extra = self.repo.root / 'дополнительно'
        extra.mkdir()
        (extra / 'sample.docx').write_bytes(docx())
        (extra / 'backup.pdf.original').write_bytes(PDF)
        self.assertEqual(self.repo.statistics()[1], 1)

    def test_named_material_survives_reload_and_replacement(self):
        path = self.save(title='Введение — часть 2')
        repo = MaterialRepository(self.repo.root)
        item = repo.numbered('МДК', 'lecture', 1)[0]
        self.assertEqual(item.title, 'Лекция № 1 — Введение — часть 2')
        repo.save('МДК', 'lecture', 1, '.docx', docx(), repo.snapshot([item]), item.uid)
        self.assertFalse(path.exists())
        self.assertEqual(repo.list()[0].title, item.title)
        for title in ('../escape', 'a/b', 'a\\b', 'x' * 181):
            with self.assertRaises(ValueError):
                self.save(number=2, title=title)

    def test_revision_conflicts_and_delete(self):
        path = self.save()
        material = self.repo.list()[0]
        path.write_bytes(PDF + b'changed')
        with self.assertRaises(ConflictError):
            self.repo.delete(material.uid, material.revision)
        with self.assertRaises(ConflictError):
            self.save(expected=self.repo.snapshot([material]))
        current = self.repo.get(material.uid)
        self.repo.delete(current.uid, current.revision)
        self.assertEqual(self.repo.list(), [])

    def test_bad_inputs_and_content(self):
        for value in ('0', '-1', '1.5', '²', '1000000', '9' * 5000):
            with self.assertRaises(ValueError):
                parse_number(value)
        for filename, size in [('x.exe', 1), ('x.pdf', 0), ('x.pdf', MAX_SIZE + 1), ('x.pdf', None)]:
            with self.assertRaises(ValueError):
                validate_document(filename, size)
        for extension, content in [('.pdf', b'fake'), ('.docx', b'fake'), ('.docx', b'PK')]:
            with self.assertRaises(ValueError):
                self.save(extension=extension, content=content)
        with self.assertRaises(ValueError):
            self.save(subject='../escape')
        with LimitedBuffer() as buffer:
            buffer.seek(MAX_SIZE)
            with self.assertRaises(ValueError):
                buffer.write(b'x')
        self.assertEqual(self.repo.list(), [])

    def test_failed_replace_preserves_original(self):
        path = self.save()
        existing = self.repo.list()
        original_replace = Path.replace
        def fail_upload(source, target):
            if source.name.startswith('.upload-') and not source.name.endswith('.backup'):
                raise OSError('disk error')
            return original_replace(source, target)
        with patch.object(Path, 'replace', fail_upload):
            with self.assertRaises(OSError):
                self.save(extension='.docx', content=docx(), expected=self.repo.snapshot(existing))
        self.assertEqual(path.read_bytes(), PDF)
        self.assertEqual(len(self.repo.list()), 1)
        self.assertFalse(list(path.parent.glob('.upload-*')))

    def test_unnumbered_and_symlink(self):
        folder = self.repo.folder('ИНО', 'lecture')
        folder.mkdir()
        path = folder / 'Infotech_English_for_Computer_Users_4th_ed-Cambridge.pdf'
        path.write_bytes(PDF)
        material = self.repo.list()[0]
        self.assertIsNone(material.number)
        self.repo.save('ИНО', 'lecture', None, '.docx', docx(), self.repo.snapshot([material]), material.uid)
        self.assertEqual(self.repo.list()[0].path.stem, path.stem)
        self.repo.folder('ОИТ', 'lecture').symlink_to(folder, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.repo.list('ОИТ')

    def test_delete_failure_keeps_file(self):
        path = self.save()
        material = self.repo.list()[0]
        with patch.object(Path, 'unlink', side_effect=PermissionError('read only')):
            with self.assertRaises(PermissionError):
                self.repo.delete(material.uid, material.revision)
        self.assertEqual(path.read_bytes(), PDF)

    def test_duplicate_numbers_require_individual_selection(self):
        path = self.save()
        (path.parent / 'МДК_1.docx').write_bytes(docx())
        materials = self.repo.list()
        with self.assertRaises(ConflictError):
            self.save(expected=self.repo.snapshot(materials))
        self.assertEqual(len(self.repo.list()), 2)

    def test_callbacks_are_stable_and_paginated(self):
        from keyboards.admin import material_list_keyboard
        for number in range(1, 18):
            self.save(number=number)
        materials = self.repo.list()
        keyboard = material_list_keyboard(materials, 'МДК')
        self.assertEqual(len(keyboard.inline_keyboard), 17)
        for row in keyboard.inline_keyboard:
            for button in row:
                self.assertLessEqual(len(button.callback_data.encode()), 64)
        target = materials[-1]
        self.repo.delete(materials[0].uid, materials[0].revision)
        self.assertEqual(self.repo.get(target.uid), target)
