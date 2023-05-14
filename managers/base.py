import asyncio
import functools
import os
import signal
from sqlite3 import OperationalError
from types import FunctionType
from typing import Callable, Any

from telethon import TelegramClient
from telethon.sessions.sqlite import SQLiteSession

from config import logger, MAX_CONTACTS


class BaseSingletonClass:
    """ Базовый класс для вынесения общей логики singleton классов """
    __instance = None
    sign = None
    logger = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
            cls.sign = cls.__name__ + ': '
            cls.logger = logger
        return cls.__instance

    def __init__(self):
        pass


class SignalTimeout(Exception):
    """ Исключение для signal """


def signal_handler(signum, frame):
    """ Обработчик вызовов signal """
    raise SignalTimeout("Прерывание запуска клиента сессии по SignalTimeout")


signal.signal(signal.SIGALRM, signal_handler)


class BaseTelegramWorkers(BaseSingletonClass):
    """ Базовый класс для вынесения общей логики классов: Checker и Mailer """
    default_session_name = None
    total_contacts = 0
    fallen_sessions = 0
    added_contacts = 0
    sent_messages = 0

    def __init__(self, **kwargs):
        super().__init__()
        self.proxy_manager = kwargs.get('proxy_manager')
        self.db_manager = kwargs.get('db_manager')
        self.session_files = kwargs.get('session_files_manager')
        self.csv_manager = kwargs.get('csv_manager')
        self.message_manager = kwargs.get('message_manager')
        self.decorate_call()
        self.decorate_start_tg_client()

    async def __call__(self):
        pass

    async def all_checks_for_one_session(self, session_name: str, mailing: bool) -> bool | dict:
        """ Метод объединяющий все проверки доступности сессии """
        if await self.session_files.session_in_work_status(session_name=session_name) == 'in_work':
            await asyncio.sleep(10)
            return False

        session_data = await self.session_files.get_session_data(session_name)

        if await self.session_files.check_session_for_quarantine(session_name, session_data):
            return False

        if mailing:
            if await self.session_files.check_session_for_stop_sending(session_name, session_data):
                return False
        else:
            if len(await self.session_files.get_session_phone_book(session_name, session_data)) >= MAX_CONTACTS:
                return False

        self.logger.debug(self.sign + f'сессия: {session_name} -> свободна от всех ограничений')
        return session_data

    async def get_and_choice_session_name(self, mailing: bool) -> str:
        """ Выбирает между случайным и установленным ранее именем сессии """
        if mailing and self.default_session_name:
            session_name = self.default_session_name
            self.default_session_name = None
        else:
            session_name = await self.session_files.get_session_name(mailing=mailing)
        return session_name

    async def start_work_with_contacts(self, contacts: list) -> None:
        """ Для проверки номеров телефонов на наличие Telegram контактов полученных из входного csv файла """
        if self.__class__.__name__ == 'Mailer':
            mailing = True
            log_text_1 = 'Рассылка завершена -> ' \
                         'всего контактов: {total_contacts} | ' \
                         'отправлено сообщений: {sent_messages} | ' \
                         'упало сессий: {fallen_sessions}'
            log_text_2 = 'Контактов для рассылки: {contacts}'
        else:
            mailing = False
            log_text_1 = 'Все номера телефонов проверены -> ' \
                         'всего номеров: {total_contacts} | ' \
                         'добавлено контактов: {added_contacts} | ' \
                         'упало сессий: {fallen_sessions}'
            log_text_2 = 'непроверенных номеров: {contacts}'

        while session_name := await self.get_and_choice_session_name(mailing=mailing):
            if not contacts:
                await asyncio.sleep(1)
                self.logger.info(self.sign + log_text_1.format(
                    sent_messages=self.sent_messages, total_contacts=self.total_contacts,
                    fallen_sessions=self.fallen_sessions, added_contacts=self.added_contacts))
                break

            self.logger.info(self.sign + log_text_2.format(contacts=len(contacts)))

            session_data = await self.all_checks_for_one_session(session_name=session_name, mailing=mailing)
            if not session_data:
                continue

            try:
                if client := await self.get_tg_client(session_name=session_name, session_data=session_data):
                    self.logger.info(self.sign + f'СТАРТ сессии: {session_name} | '
                                                 f'{session_data.get("first_name")} {session_data.get("last_name")}')
                    await self.session_files.session_in_work_status(session_name=session_name, action='start')
                    await self.start_tg_client(
                        session_name=session_name, session_data=session_data, client=client, contacts=contacts)

            except BaseException as base_exc:
                self.logger.error(self.sign + f'Critical ERROR -> {base_exc=}')

            await self.session_files.session_in_work_status(session_name=session_name, action='stop')

    async def get_tg_client(self, session_name: str, session_data: dict) -> TelegramClient | None:
        """ Возвращает исходного клиента сессии для подключения """
        client = None
        session_conn = SQLiteSession(session_id=os.path.abspath(
            f'{self.session_files.work_sessions_dir}{os.sep}{session_name}.session'))

        proxy = await self.proxy_manager(session_data)

        if proxy:
            client = TelegramClient(
                session_conn,
                api_id=session_data.get('app_id'),
                api_hash=session_data.get('app_hash'),
                proxy=proxy,
            )

        return client

    async def check_connect_session(self, client: TelegramClient) -> None:
        """ Проверка подключения к сессии """
        user = await client.get_me()
        self.logger.info(self.sign + f'Ok -> подключен к сессии -> '
                                     f'{user.phone=} | {user.first_name} {user.last_name} | {user.id=}')

    @staticmethod
    def wrapper_for_call(method: Callable) -> Callable:
        """ Декоратор для __call__ """

        @functools.wraps(method)
        async def wrapper(self) -> Any:
            try:
                result = await method(self)
            except BaseException as base_exc:
                self.logger.error(self.sign + f'Critical ERROR -> {base_exc=}')
                if self.__class__.__name__ == "Tester":
                    result = None
                else:
                    result = await method(self)
            return result

        return wrapper

    @classmethod
    def decorate_call(cls):
        """ Оборачивает __call__ декоратором wrapper_for_call """
        method = cls.__getattribute__(cls, '__call__')
        if isinstance(method, FunctionType):
            # cls.logger.debug(cls.sign + f'decorate -> {method=}')
            setattr(cls, '__call__', cls.wrapper_for_call(method))

    async def start_tg_client(self, session_name: str, session_data: dict,
                              client: TelegramClient, contacts: list, msg_text: str | None = None) -> None:
        """ Подключение к сессии и старт проверки номеров телефонов на наличие Telegram контактов в классе Checker
        или начало рассылки по контактам в классе Mailer """

    @staticmethod
    def wrapper_for_start_tg_client(method: Callable) -> Callable:
        """ Декоратор для start_tg_client """

        @functools.wraps(method)
        async def wrapper(self, session_name: str, session_data: dict,
                          client: TelegramClient, contacts: list, msg_text: str | None = None) -> None:
            try:
                signal.alarm(30)
                await method(self, session_name, session_data, client, contacts, msg_text)

            except SignalTimeout as exc:
                self.logger.warning(self.sign + f'ERROR ошибка подключения к сессии {exc=}')
                await self.session_files.move_session_to_bad_sessions(session_name=session_name)
                self.fallen_sessions += 1

            except ConnectionError as exc:
                self.logger.warning(
                    self.sign + f'ERROR ошибка подключения к прокси: {exc=}')

            except BaseException as base_exc:
                self.logger.error(self.sign + f'Critical ERROR -> {base_exc=}')

            finally:
                try:
                    signal.alarm(0)
                    await client.__aexit__()
                except OperationalError:
                    pass
                except Exception as exc:
                    self.logger.warning(self.sign + f'{exc=}')
                # self.logger.info(self.sign + f'finally: {client.is_connected()=}')
            return

        return wrapper

    @classmethod
    def decorate_start_tg_client(cls):
        """ Оборачивает start_tg_client декоратором wrapper_for_start_tg_client """
        method = cls.__getattribute__(cls, 'start_tg_client')
        if isinstance(method, FunctionType):
            # cls.logger.debug(cls.sign + f'decorate -> {method=}')
            setattr(cls, 'start_tg_client', cls.wrapper_for_start_tg_client(method))
