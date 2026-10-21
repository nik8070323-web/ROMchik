import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiogram.types import CallbackQuery, Message, User

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'aiogram-learning'))

from handlers import Subjects, admin, start
from keyboards.subject import get_subjects_keyboard, get_additional_keyboard


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    def message(self):
        return Message(
            message_id=1, date=0, chat={'id': 1, 'type': 'private'},
            from_user=User(id=42, is_bot=False, first_name='Тест')
        )

    def callback(self, data):
        message = self.message()
        return CallbackQuery(
            id='test', from_user=message.from_user, chat_instance='test',
            message=message, data=data
        )

    async def test_invalid_lecture_buttons(self):
        for data in ('file:', 'file:МДК', 'file:МДК:-1', 'file:МДК:²', 'file:МДК:999', 'file:нет:0'):
            with self.subTest(data=data):
                with patch.object(CallbackQuery, 'answer', new_callable=AsyncMock) as answer:
                    await Subjects.send_lecture(self.callback(data))
                    answer.assert_awaited_once()
                    self.assertTrue(answer.call_args.kwargs['show_alert'])

    async def test_send_lecture(self):
        with patch.object(CallbackQuery, 'answer', new_callable=AsyncMock) as answer:
            with patch.object(Message, 'answer_document', new_callable=AsyncMock) as document:
                await Subjects.send_lecture(self.callback('file:МДК:0'))
                answer.assert_awaited_once()
                document.assert_awaited_once()
                self.assertTrue(Path(document.call_args.kwargs['document'].path).is_file())

    async def test_missing_additional_file(self):
        with patch.object(Path, 'is_file', return_value=False):
            with patch.object(CallbackQuery, 'answer', new_callable=AsyncMock) as answer:
                await Subjects.send_additional(self.callback('additional:Регламент для реферата'))
                answer.assert_awaited_once_with('Файл не найден', show_alert=True)

    async def test_empty_subject_keeps_navigation(self):
        with patch.object(CallbackQuery, 'answer', new_callable=AsyncMock):
            with patch.object(Message, 'edit_text', new_callable=AsyncMock) as edit:
                await Subjects.open_subject(self.callback('subject:нет'))
                self.assertIsNotNone(edit.call_args.kwargs['reply_markup'])

    async def test_start_without_image(self):
        with patch.object(Path, 'is_file', return_value=False):
            with patch.object(Message, 'answer', new_callable=AsyncMock) as answer:
                await start.start_handler(self.message())
                answer.assert_awaited_once()

    def test_materials_and_buttons(self):
        for subject in Subjects.FOLDERS:
            self.assertTrue(Subjects.get_lecture_files(subject))
        for filename in Subjects.EXTRA_FILES.values():
            self.assertTrue((Subjects.BASE_DIR / 'лекции' / 'дополнительно' / filename).is_file())
        for keyboard in (get_subjects_keyboard(), get_additional_keyboard()):
            for row in keyboard.inline_keyboard:
                for button in row:
                    self.assertLessEqual(len(button.callback_data.encode()), 64)


if __name__ == '__main__':
    unittest.main()
