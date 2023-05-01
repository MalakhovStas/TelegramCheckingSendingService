import asyncio
import signal
import time
from random import randint

from telethon import TelegramClient
from telethon import functions
from telethon.tl.types import InputPhoneContact
from telethon.tl.types.contacts import ImportedContacts

from config import MAX_REQUESTS, FROM, BEFORE, DEFAULT_QUARANTINE_TIME, MAX_CONTACTS
from managers.base import BaseTelegramWorkers


class Checker(BaseTelegramWorkers):
    """ Класс для проверки наличия контакта Telegram связанного с номером телефона """

    async def __call__(self):
        contacts = await self.db_manager.check_contacts_in_all_tables(await self.csv_manager())
        self.total_contacts = len(contacts)
        await self.start_work_with_contacts(contacts=contacts)

    async def start_tg_client(self, session_name: str, session_data: dict,
                              client: TelegramClient, contacts: list) -> None:
        """ Подключение к сессии и старт проверки номеров телефонов на наличие Telegram контактов """

        async with client:
            signal.alarm(0)
            await self.check_connect_session(client=client)

            step = 0
            while contacts:
                contact = contacts[-1]
                phone = contact.get('phone')
                step += 1

                phone_book = await self.session_files.get_session_phone_book(session_name)
                if any((True for cont in phone_book if cont.get('phone') == phone)):
                    self.logger.warning(
                        self.sign + f'{step}. Номер: {phone} уже в телефонной книге, {len(phone_book)=}')
                    contacts.pop(-1)
                    continue

                result, bad = await self.get_tg_contact(phone=phone, client=client)
                contact.update(result)
                contact.update({'session_name': session_name})

                self.logger.debug(self.sign + f'{step}. {bad=} | {contact=} | {len(phone_book)=}')

                if contact.get('check_result').startswith('ERROR'):
                    contacts.pop(-1)
                    contacts.insert(0, contact)
                    self.logger.warning(self.sign + f'{phone=} | перемещён в начало списка')

                    await self.session_files.update_key_session_json(
                        session_name, key='quarantine_until', value=int(time.time()) + DEFAULT_QUARANTINE_TIME)
                    self.logger.warning(self.sign + f'Сессия: {session_name} -> '
                                                    f'помещена в карантин на {DEFAULT_QUARANTINE_TIME} сек.')
                    break

                await self.db_manager.get_or_create_contact(contact=contact, bad_contact=bad)
                contacts.pop(-1)

                if bad is False:
                    self.added_contacts += 1
                    len_phone_book = await self.session_files.update_key_session_json(session_name,
                                                                                      value=contact)
                    if len_phone_book >= MAX_CONTACTS:
                        break

                if step == MAX_REQUESTS:
                    break

                await asyncio.sleep(randint(FROM, BEFORE))

    async def get_tg_contact(self, phone: str, client: TelegramClient) -> tuple[dict, bool]:
        """ Проверка конкретного номера телефона на наличие Telegram контакта, получение данных контакта """

        bad = False
        result = {
            'check_result': '',
            'user_id': 0,
            'username': '',
            'first_name': '',
            'last_name': '',
        }
        try:
            contact = InputPhoneContact(client_id=0, phone=phone, first_name="", last_name="")
            contacts: ImportedContacts = await client(functions.contacts.ImportContactsRequest([contact]))

            if not contacts.to_dict()['imported']:
                result['check_result'] = 'phone_not_detected'
                bad = True

            else:
                result['check_result'] = 'Ok'
                result['username'] = username = contacts.to_dict()['users'][0]['username']
                result['first_name'] = contacts.to_dict()['users'][0]['first_name']
                result['last_name'] = contacts.to_dict()['users'][0]['first_name']
                result['user_id'] = user_id = contacts.to_dict()['users'][0]['id']

                if not username:
                    try:
                        await client(functions.contacts.DeleteContactsRequest(id=[user_id]))
                    except Exception as exc:
                        self.logger.warning(self.sign + f'ERROR при удалении контакта: {exc=}')
                else:
                    await client(functions.contacts.DeleteContactsRequest(id=[username]))

        except Exception as exc:
            result['check_result'] = check_result = f'ERROR получения контакта: {exc=}'
            self.logger.warning(self.sign + f'{check_result=}')
            bad = True

        self.logger.debug(self.sign + f'{phone=} | {result=}')
        return result, bad
