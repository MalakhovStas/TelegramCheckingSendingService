import asyncio
import signal
import time
from datetime import datetime

from telethon import TelegramClient
from telethon import functions
from telethon.tl.types import InputPhoneContact, InputPeerUser
from telethon.tl.types.contacts import ImportedContacts

from managers.base import BaseTelegramWorkers
from config import MAX_CONTACTS, DEFAULT_QUARANTINE_TIME, \
    PHONE_CONTACT_test, SESSION_test, MSG_test


class Tester(BaseTelegramWorkers):
    """ Класс для тестирования сессий и текстов сообщений """

    async def __call__(self):
        await self.start_work_with_contacts(contacts=[])

    async def input_data(self) -> tuple:
        """ Ввод начальных данных и проверка их валидности """
        session_name = ''
        session_data = None
        contact = None

        while not session_data:
            await asyncio.sleep(1)
            session_name = SESSION_test if SESSION_test else input('Введите имя сессии(номер): ').strip()
            if await self.session_files.check_exists_session(session_name):
                session_data = await self.session_files.get_session_data(session_name=session_name)
            else:
                if SESSION_test:
                    self.logger.error(self.sign + f"Измените DEF_SESSION_test в config.py и перезапустите приложение")
                    exit()

        while not contact:
            await asyncio.sleep(1)
            phone = PHONE_CONTACT_test if PHONE_CONTACT_test else input('Введите phone контакта из БД: ').strip()
            contact = await self.db_manager.get_or_none_contact_in_contacts(phone=phone)
            if PHONE_CONTACT_test and not contact:
                self.logger.error(self.sign + f"Измените DEF_CONTACT_test в config.py и перезапустите приложение")
                exit()

        await asyncio.sleep(1)
        msg_text = MSG_test if MSG_test else input('Введите сообщение для отправки: ')
        if MSG_test:
            self.logger.debug(self.sign + f'message text: {MSG_test[:50]}...')

        return session_name, session_data, contact, msg_text

    async def start_work_with_contacts(self, contacts: list) -> None:
        """ Для проверки номеров телефонов на наличие Telegram контактов полученных из входного csv файла """
        session_name, session_data, contact, msg_text = await self.input_data()
        contacts = [contact]

        session_data = await self.all_checks_for_one_session(session_name=session_name, mailing=False)
        if not session_data:
            return

        try:
            if client := await self.get_tg_client(session_name=session_name, session_data=session_data):
                self.logger.info(self.sign + f'СТАРТ сессии: {session_name} | '
                                             f'{session_data.get("first_name")} {session_data.get("last_name")}')
            await self.session_files.session_in_work_status(session_name=session_name, action='start')
            await self.start_tg_client(session_name=session_name, session_data=session_data,
                                       client=client, contacts=contacts, msg_text=msg_text)

        except BaseException as base_exc:
            self.logger.error(self.sign + f'Critical ERROR -> {base_exc=}')

        await self.session_files.session_in_work_status(session_name=session_name, action='stop')

    async def start_tg_client(self, session_name: str, session_data: dict,
                              client: TelegramClient, contacts: list, msg_text: str | None = None) -> None:
        """ Подключение к сессии и старт рассылки """
        contact = contacts[0]
        phone_book = await self.session_files.get_session_phone_book(session_name, session_data)
        sent = 'did_not_go'

        async with client:
            signal.alarm(0)
            await self.check_connect_session(client=client)

            if not contact.username:
                if contact.session_check != session_name:
                    if len(phone_book) >= MAX_CONTACTS:
                        self.logger.info(self.sign + f'В телефонной книге этой сессии  сессии: {session_name} | '
                                                     f'больше {MAX_CONTACTS} контактов, выберите другую')
                        return
                check_user_id, access_hash = await self.get_access_hash(phone=str(contact.phone), client=client)
                if check_user_id and access_hash:
                    contact.date_check = datetime.now()
                    contact.session_check = session_name

                    sent = await self.sender_from_user_id(
                        user_id=check_user_id, access_hash=access_hash, client=client, text=msg_text)
                    if sent is True:
                        contact.user_id = check_user_id
            else:
                sent = await self.sender_from_username(username=contact.username, client=client, text=msg_text)

            if sent is True:
                self.sent_messages += 1
                contact.date_last_send = datetime.now()
                contact.session_last_send = session_name
                contact.num_sends += 1
                contact.save()

            elif sent is False:
                error_contact = contacts.pop(-1)
                contacts.insert(0, error_contact)
                await self.session_files.update_key_session_json(
                    session_name, key='quarantine_until', value=int(time.time()) + DEFAULT_QUARANTINE_TIME)
            else:
                self.logger.warning(self.sign + f"недостаточно данных для отправки сообщения {contact.user_id=}")

            msg = self.sign + f'{sent=} | {contact.username=} | {contact.user_id=}'
            self.logger.info(msg) if sent is True else self.logger.warning(msg)

    async def get_access_hash(self, phone: str, client: TelegramClient) -> tuple:
        """ Возвращает user_id Telegram контакта и его access_hash в данной сессии  """
        user_id, access_hash = None, None
        try:
            contact = InputPhoneContact(client_id=0, phone=phone, first_name="", last_name="")
            contacts: ImportedContacts = await client(functions.contacts.ImportContactsRequest([contact]))

            if contacts.to_dict()['imported']:
                user_id = contacts.to_dict()['users'][0]['id']
                access_hash = contacts.to_dict()['users'][0]['access_hash']

                try:
                    await client(functions.contacts.DeleteContactsRequest(id=[user_id]))
                except Exception as exc:
                    self.logger.warning(self.sign + f'ERROR при удалении контакта: {exc=}')

        except Exception as exc:
            self.logger.warning(self.sign + f'{exc=}')

        self.logger.debug(self.sign + f'{user_id=} | {access_hash=}')
        return user_id, access_hash

    @classmethod
    async def sender_from_user_id(cls, user_id, access_hash, client: TelegramClient, text: str) -> bool:
        """ Отправляет сообщение по user_id и access_hash """
        try:
            user = InputPeerUser(user_id=user_id, access_hash=access_hash)
            await client.send_message(user, text, link_preview=False)
            sent = True
        except Exception as exc:
            cls.logger.warning(f'ERROR: {exc=}')
            sent = False
        return sent

    @classmethod
    async def sender_from_username(cls, username: str, client: TelegramClient, text: str) -> bool:
        """ Отправляет сообщение по username """
        try:
            await client.send_message(username, text, link_preview=False)
            sent = True
        except Exception as exc:
            cls.logger.warning(f'ERROR: {exc=}')
            sent = False
        return sent
