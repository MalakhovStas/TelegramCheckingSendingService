import asyncio
import json
import os
import shutil
import time
from random import choice
from typing import Any

from config import WORK_SESSIONS_DIR, GOOD_SESSIONS_AFTER_CHECKER_DIR, BAD_SESSIONS_DIR, SESSION_IN_WORK_FILE_PATH
from managers.base import BaseSingletonClass


class SessionFilesManager(BaseSingletonClass):
    """ Класс Singleton для соблюдения принципа DRY и
        вынесения логики работы с файлами сессий """

    work_sessions_dir = WORK_SESSIONS_DIR
    good_sessions_after_checker_dir = GOOD_SESSIONS_AFTER_CHECKER_DIR
    bad_sessions_dir = BAD_SESSIONS_DIR

    def __init__(self):
        super().__init__()
        self.rewrite_session_in_work_file()

    @staticmethod
    def rewrite_session_in_work_file():
        """ Создаёт или перезаписывает данные в файле с информацией о сессиях в работе """
        with open(f'{SESSION_IN_WORK_FILE_PATH}', 'w', encoding='utf-8') as file:
            json.dump([], file, ensure_ascii=False)

    @classmethod
    async def session_in_work_status(cls, session_name: str | None = None,
                                     action: str = 'check', step: int = 1) -> str:
        """ Проверяет не используется ли сессия в данный момент """
        rewrite = True
        try:

            with open(f'{SESSION_IN_WORK_FILE_PATH}', 'r', encoding='utf-8') as file:
                data: list = json.load(file)

            if action == 'stop':
                data.remove(session_name)
                result = 'stop'

            elif action == 'start':
                data.append(session_name)
                result = 'start'

            else:
                rewrite = False
                if session_name in data:
                    result = 'in_work'
                else:
                    result = 'free'

            if rewrite:
                with open(f'{SESSION_IN_WORK_FILE_PATH}', 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False)

        except BaseException as exc:
            cls.logger.error(cls.sign + f'сессия: {session_name} | {action=} | {exc=}')
            if step <= 3:
                result = await cls.session_in_work_status(session_name=session_name, action=action, step=step+1)
            else:
                result = f'ERROR: {exc}'

        cls.logger.debug(cls.sign + f'сессия: {session_name} | {action=} | {step=} | {result=}')
        return result

    @classmethod
    async def get_paths_session_files(cls, session_name: str) -> tuple[str, str]:
        """ Возвращает абсолютные пути к файлам сессии """
        json_file = os.path.abspath(f'{cls.work_sessions_dir}{os.sep}{session_name}.json')
        sql_file = os.path.abspath(f'{cls.work_sessions_dir}{os.sep}{session_name}.session')
        return sql_file, json_file

    @classmethod
    async def get_sessions(cls) -> list:
        """ Возвращает список сессий из рабочей директории """
        inp = 'start'
        while inp.lower() != 'exit':
            if os.listdir(cls.work_sessions_dir):
                for data in os.walk(cls.work_sessions_dir):
                    return list(set(map(lambda f_name: f_name.split('.')[0], data[2])))
            else:
                await asyncio.sleep(2)
                inp = input('\nФайлы сессий не найдены, добавьте сессии и нажмите Enter для продолжения\n'
                            'или введите exit для завершения работы: \n')
        return []

    @classmethod
    async def get_session_name(cls, mailing: bool = False) -> str:
        """ Возвращает имя сессии """
        result = None
        if sessions := await cls.get_sessions():
            if casfq := await cls.check_all_sessions_for_quarantine(sessions):
                cls.logger.warning(cls.sign + f'Все сессии в карантине ожидание: {casfq} сек.')
                await asyncio.sleep(casfq)
            if mailing:
                if casfss := await cls.check_all_sessions_for_stop_sending(sessions):
                    cls.logger.warning(cls.sign + f'Все сессии в stop_sending ожидание: {casfss} сек.')
                    await asyncio.sleep(casfss)
            result = choice(sessions)
        return result

    @classmethod
    async def get_session_data(cls, session_name) -> dict:
        """ Возвращает данные из json файла сессии """
        with open(f'{cls.work_sessions_dir}{os.sep}{session_name}.json', 'r', encoding='utf-8') as file:
            return json.load(file)

    @classmethod
    async def get_key_session_json(cls, session_name: str, key: str) -> Any:
        """ Возвращает значение по ключу key из json файла сессии """
        data = await cls.get_session_data(session_name)
        return data.get(key)

    @classmethod
    async def update_key_session_json(cls, session_name, value, key='phone_book') -> int:
        """ Обновляет значение по ключу key в json файле сессии """
        data = await cls.get_session_data(session_name)
        if key == 'phone_book':
            if data.get(key):
                data.get(key).append(value)
            else:
                data[key] = [value]
        else:
            data[key] = value

        with open(f'{cls.work_sessions_dir}{os.sep}{session_name}.json', 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False)

        cls.logger.info(cls.sign + f'{session_name=} update: {key=} | {value=}')
        return len(data.get(key)) if key == 'phone_book' else value

    @classmethod
    async def move_session_to_bad_sessions(cls, session_name: str) -> bool:
        """ Перемещает сессию в каталог bad_sessions """
        sql_file, json_file = await cls.get_paths_session_files(session_name)
        to_dir = cls.bad_sessions_dir

        if os.path.exists(json_file) and os.path.exists(sql_file):
            shutil.move(json_file, to_dir)
            shutil.move(sql_file, to_dir)
            cls.logger.debug(cls.sign + f'Сессия: {session_name} '
                                        f'перемещена в каталог: {to_dir.split(f"{os.sep}")[-1]}')
            return True
        return False

    @classmethod
    async def check_all_sessions_for_quarantine(cls, sessions):
        """ Проверяет все сессии на карантин """
        quarantine = []
        for session_name in sessions:
            quarantin_session = (await cls.get_session_data(session_name)).get('quarantine_until')
            if not quarantin_session:
                quarantine.append(False)
            elif quarantin_session and isinstance(quarantin_session, int) and quarantin_session < time.time():
                quarantine.append(False)
            else:
                quarantine.append(quarantin_session)
        if all(quarantine):
            return int(min(quarantine) - time.time())
        return False

    @classmethod
    async def check_session_for_quarantine(cls, session_name, session_data) -> bool:
        """ Проверка сессии на карантин """
        result = False
        quarantine = session_data.get('quarantine_until')
        if quarantine:
            if isinstance(quarantine, int) and quarantine > time.time():
                cls.logger.warning(cls.sign + f'сессия: {session_name} '
                                              f'в карантине ещё -> {quarantine - int(time.time())} сек.')
                result = True
            else:
                await cls.update_key_session_json(session_name, key='quarantine_until', value=None)
        return result

    @classmethod
    async def check_all_sessions_for_stop_sending(cls, sessions):
        """ Проверяет все сессии на ограничение рассылки """
        stop_list = []
        for session_name in sessions:
            stop_sending = (await cls.get_session_data(session_name)).get('stop_sending')
            if not stop_sending:
                stop_list.append(False)
            elif stop_sending and isinstance(stop_sending, int) and stop_sending < time.time():
                stop_list.append(False)
            else:
                stop_list.append(stop_sending)
        if all(stop_list):
            return int(min(stop_list) - time.time())
        return False

    @classmethod
    async def check_session_for_stop_sending(cls, session_name, session_data) -> bool:
        """ Проверка сессии на время между отправкой сообщений """
        result = False
        if stop_sending := session_data.get('stop_sending'):
            if isinstance(stop_sending, int) and stop_sending > time.time():
                cls.logger.warning(cls.sign + f'сессия: {session_name} '
                                              f'ограничение рассылки ещё -> {stop_sending - int(time.time())} сек.')
                result = True
            else:
                await cls.update_key_session_json(session_name, key='stop_sending', value=None)
                cls.logger.info(cls.sign + f'сессия: {session_name} | без ограничений рассылки')
        return result

    @classmethod
    async def get_session_phone_book(cls, session_name: str, session_data: dict | None = None) -> list[dict]:
        """ Возвращает телефонную книгу после валидации """
        phone_book = []
        if not session_data:
            session_data = await cls.get_session_data(session_name)

        data = session_data.get('phone_book')
        if data and isinstance(data, list):
            phone_book = data
        cls.logger.info(cls.sign + f'сессия: {session_name} | контактов в телефонной книге: {len(phone_book)}')
        return phone_book
