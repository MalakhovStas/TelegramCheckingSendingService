import os
from datetime import datetime

from managers.base import BaseSingletonClass
from config import INPUT_FILES_DIR
from database.db_utils import Contact


class MessageManager(BaseSingletonClass):
    """ Класс работы с текстами сообщений и переменными контакта из БД """

    async def __call__(self, contact: Contact) -> str:
        return await self.get_message_text(contact=contact)

    @staticmethod
    async def get_message_text(contact: Contact) -> str | None:
        """ Считывает данные из файла с именем promo_id контакта подставляет значения переменных и возвращает текст """

        promo_id = contact.promo_id
        var_1 = contact.var_1
        var_2 = contact.var_2
        var_3 = contact.var_3

        promo_id_text_path = f'{INPUT_FILES_DIR}/{promo_id}.txt'
        text = None
        if promo_id and (os.path.exists(promo_id_text_path) and os.path.isfile(promo_id_text_path)):
            with open(promo_id_text_path, 'r', encoding='utf-8') as file:
                data = file.read()

            text = data.format(var_1=var_1, var_2=var_2, var_3=var_3,
                               var_4=datetime.strftime(datetime.now(), '%d.%m.%Y %H:%M:%S'))

        return text
