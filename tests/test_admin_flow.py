import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.types import Update

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'aiogram-learning'))
from filters import admin as auth
from handlers import admin, Subjects
from services.materials import MaterialRepository
from states.material import AddMaterial
from test_materials import PDF
from main import create_dispatcher


class AdminFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_authorization_fsm_and_catalog(self):
        dp = create_dispatcher()
        bot = Bot('123456:TEST_TOKEN_FOR_OFFLINE_TESTS')
        sequence = 0
        async def feed(text=None, callback=None, user=42, document=None):
            nonlocal sequence
            sequence += 1
            sender = {'id': user, 'is_bot': False, 'first_name': 'Test'}
            message = {'message_id': sequence, 'date': 0, 'chat': {'id': user, 'type': 'private'}, 'from_user': sender}
            if text is not None:
                message['text'] = text
            if document:
                message['document'] = document
            payload = {'update_id': sequence}
            if callback:
                payload['callback_query'] = {'id': str(sequence), 'from_user': sender, 'chat_instance': 'test', 'message': message, 'data': callback}
            else:
                payload['message'] = message
            await asyncio.wait_for(dp.feed_update(bot, Update.model_validate(payload)), timeout=3)
        state = dp.fsm.get_context(bot=bot, chat_id=42, user_id=42)
        async def download(file, destination, **kwargs):
            destination.write(PDF)
        document = {'file_id': 'file', 'file_unique_id': 'unique', 'file_name': '../../lecture.pdf', 'file_size': len(PDF)}
        with tempfile.TemporaryDirectory() as directory:
            repo = MaterialRepository(directory)
            with patch.object(auth, 'ADMIN_IDS', {42}), patch.object(admin, 'repository', repo), patch.object(Subjects, 'repository', repo), patch.object(bot, 'download', side_effect=download), patch.object(bot.session, 'make_request', new_callable=AsyncMock) as requests:
                for action in ('admin:add', 'admin:manage', 'admin:stats', 'admin:save:forged', 'admin:remove:forged'):
                    await feed(callback=action, user=99)
                    self.assertIn('запрещён', requests.call_args.args[1].text)
                await feed(text='/admin', user=99)
                self.assertIn('запрещён', requests.call_args.args[1].text)
                intruder = dp.fsm.get_context(bot=bot, chat_id=99, user_id=99)
                for fsm_state in AddMaterial.__all_states__:
                    await intruder.set_state(fsm_state)
                    await feed(user=99, document=document)
                    self.assertIsNone(await intruder.get_state())
                self.assertEqual(repo.list(), [])
                await feed(text='/admin')
                await feed(callback='admin:add')
                self.assertEqual(await state.get_state(), AddMaterial.subject.state)
                await feed(callback='admin:subject:МДК')
                await feed(callback='admin:kind:practice')
                await feed(text='0')
                self.assertEqual(await state.get_state(), AddMaterial.number.state)
                await feed(callback='admin:to_kind')
                await feed(callback='admin:kind:practice')
                await feed(text='1')
                await feed(callback='admin:skip_title')
                await feed(text='not a document')
                self.assertEqual(await state.get_state(), AddMaterial.file.state)
                await feed(document=document)
                self.assertEqual(await state.get_state(), AddMaterial.confirm.state)
                self.assertEqual(repo.list(), [])
                await feed(callback='admin:save:forged')
                self.assertEqual(repo.list(), [])
                nonce = (await state.get_data())['nonce']
                await feed(callback=f'admin:save:{nonce}')
                self.assertEqual(len(repo.list()), 1)
                self.assertIsNone(await state.get_state())
                await feed(callback=f'admin:save:{nonce}')
                self.assertEqual(len(repo.list()), 1)
                material = repo.list()[0]
                await feed(callback='subject:МДК')
                markup = requests.call_args.args[1].reply_markup
                self.assertIn('Практика № 1', str(markup))
                await feed(callback=f'material:{material.uid}')
                self.assertEqual(requests.call_args.args[1].__api_method__, 'sendDocument')
                await feed(callback=f'admin:replace:{material.uid}')
                await feed(document=document)
                self.assertIn('заменит', requests.call_args.args[1].text)
                await feed(text='/cancel')
                self.assertIsNone(await state.get_state())
                self.assertEqual(material.path.read_bytes(), PDF)
                await feed(callback=f'admin:replace:{material.uid}')
                await feed(document=document)
                nonce = (await state.get_data())['nonce']
                with patch.object(bot, 'download', side_effect=OSError('network failure')):
                    await feed(callback=f'admin:save:{nonce}')
                self.assertEqual(await state.get_state(), AddMaterial.file.state)
                self.assertEqual(material.path.read_bytes(), PDF)
                await feed(document=document)
                nonce = (await state.get_data())['nonce']
                await feed(callback=f'admin:save:{nonce}')
                self.assertEqual(len(repo.list()), 1)
                await feed(callback='admin:add')
                await feed(callback='admin:subject:МДК')
                await feed(callback='admin:kind:practice')
                await feed(text='1')
                await feed(callback='admin:skip_title')
                await feed(document=document)
                self.assertIn('заменит', requests.call_args.args[1].text)
                nonce = (await state.get_data())['nonce']
                with patch.object(auth, 'ADMIN_IDS', set()):
                    await feed(callback=f'admin:save:{nonce}')
                    self.assertIn('запрещён', requests.call_args.args[1].text)
                self.assertIsNone(await state.get_state())
                await feed(callback='admin:stats')
                self.assertIn('Практик: 1', requests.call_args.args[1].text)
                await feed(callback=f'admin:delete:{material.uid}')
                nonce = (await state.get_data())['nonce']
                await feed(callback='admin:remove:wrong')
                self.assertTrue(material.path.exists())
                await feed(callback=f'admin:remove:{nonce}')
                self.assertFalse(material.path.exists())
                for kind in ('lecture', 'practice'):
                    await feed(callback='admin:add')
                    await feed(callback='admin:subject:Дополнительно')
                    await feed(callback=f'admin:kind:{kind}')
                    await feed(text='2')
                    self.assertEqual(await state.get_state(), AddMaterial.title.state)
                    await feed(text='Введение в Python')
                    await feed(document=document)
                    self.assertIn('Введение в Python', requests.call_args.args[1].text)
                    nonce = (await state.get_data())['nonce']
                    await feed(callback=f'admin:save:{nonce}')
                await feed(callback='additional')
                self.assertIn('Введение в Python', str(requests.call_args.args[1].reply_markup))
                self.assertEqual(len(repo.list('Дополнительно')), 2)
                item = repo.list('Дополнительно')[0]
                await feed(callback=f'material:{item.uid}')
                self.assertEqual(requests.call_args.args[1].__api_method__, 'sendDocument')
                await feed(callback='admin:add')
                await feed(text='/start')
                self.assertIsNone(await state.get_state())
        await dp.storage.close()
        await dp.fsm.events_isolation.close()
        await bot.session.close()
