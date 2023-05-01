import asyncio
import signal
import time
from datetime import datetime

from telethon import TelegramClient
from telethon import functions
from telethon.tl.types import InputPhoneContact, InputPeerUser
from telethon.tl.types.contacts import ImportedContacts

from managers.base import BaseTelegramWorkers
from config import MAX_CONTACTS


class Mailer(BaseTelegramWorkers):
    """ Класс для рассылки сообщений по контактам из БД """
    stop_sending_time = 60 * 60
    # stop_sending_time = 60  # минуты для разработки

    async def __call__(self):
        contacts = await self.input_data()
        self.total_contacts = len(contacts)
        await self.start_work_with_contacts(contacts=contacts)

    async def input_data(self) -> list:
        """ Ввод начальных данных и проверка их валидности """
        contacts = []
        input_time = ''

        while not contacts:
            promo_id = input('Введите promo_id: ')
            # promo_id = 'x_promo321'  # для разработки

            contacts = await self.db_manager.get_contacts_from_promo_id(promo_id=promo_id)
            if not contacts:
                self.logger.warning(self.sign + f'контактов с {promo_id=} в БД не зарегистрировано')
                await asyncio.sleep(1)

        while not input_time.isdigit() or not 24 > int(input_time) > 0:
            input_time = input('Введите кол-во часов между отправкой сообщений из одной сессии (от 1 до 24): ')

        self.stop_sending_time *= int(input_time)
        return contacts

    async def start_tg_client(self, session_name: str, session_data: dict,
                              client: TelegramClient, contacts: list) -> None:
        """ Подключение к сессии и старт рассылки """
        contact = contacts[-1]
        text = await self.message_manager(contact)
        phone_book = await self.session_files.get_session_phone_book(session_name, session_data)
        sent = False

        async with client:
            signal.alarm(0)
            await self.check_connect_session(client=client)

            if not contact.username:
                if contact.session_check != session_name:
                    if contact.session_check in await self.session_files.get_sessions():
                        if await self.all_checks_for_one_session(session_name=contact.session_check, mailing=True):
                            self.default_session_name = contact.session_check
                        else:
                            contacts.pop(-1)
                            contacts.insert(0, contact)
                            self.logger.warning(
                                self.sign + f'{contact.phone=} -> перемещён в начало списка')
                        return
                    if len(phone_book) >= MAX_CONTACTS:
                        return

                check_user_id, access_hash = await self.get_access_hash(phone=str(contact.phone), client=client)
                if check_user_id and access_hash:
                    contact.date_check = datetime.now()
                    contact.session_check = session_name

                    if await self.sender_from_user_id(
                            user_id=check_user_id, access_hash=access_hash, client=client, text=text):
                        contact.user_id = check_user_id
                        sent = True

            else:
                if await self.sender_from_username(username=contact.username, client=client, text=text):
                    sent = True
            if sent:
                self.sent_messages += 1
                contact.date_last_send = datetime.now()
                contact.session_last_send = session_name
                contact.num_sends += 1
            contact.save()

            self.logger.debug(self.sign + f'{contact.user_id=} | {contact.username=} | {sent=}')
            await self.session_files.update_key_session_json(
                session_name, key='stop_sending', value=int(time.time()) + self.stop_sending_time)

            contacts.pop(-1)

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
            await client.send_message(user, text)
            sent = True
        except Exception as exc:
            cls.logger.warning(f'ERROR: {exc=}')
            sent = False
        return sent

    @classmethod
    async def sender_from_username(cls, username: str, client: TelegramClient, text: str) -> bool:
        """ Отправляет сообщение по username """
        try:
            await client.send_message(username, text)
            sent = True
        except Exception as exc:
            cls.logger.warning(f'ERROR: {exc=}')
            sent = False
        return sent
