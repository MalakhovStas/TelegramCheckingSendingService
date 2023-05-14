import functools
from datetime import datetime
from types import FunctionType
from typing import Any, Callable

from peewee import Model

from database.db_utils import Tables, db, Contact
from managers.base import BaseSingletonClass

db.create_tables(Tables.all_tables())


class DBManager(BaseSingletonClass):
    """ Класс Singleton надстройка над ORM "peewee" для соблюдения принципа DRY и
        вынесения логики сохранения данных """
    point_db_connection = db
    tables = Tables

    def __new__(cls, *args, **kwargs):
        cls.__instance = super().__new__(cls)
        cls.decorate_methods()
        return cls.__instance

    @staticmethod
    def db_connector(method: Callable) -> Callable:
        """ Единая точка доступа к БД из всех методов класса """

        @functools.wraps(method)
        async def wrapper(*args, **kwargs) -> Any:
            with DBManager.point_db_connection:
                result = await method(*args, **kwargs)
            return result

        return wrapper

    @classmethod
    def decorate_methods(cls):
        """ Оборачивает все методы класса которым нужен доступ БД, декоратором db_connector """

        for attr_name in cls.__dict__:
            if not attr_name.startswith('__') and attr_name not in ['db_connector', 'decorate_methods']:
                method = cls.__getattribute__(cls, attr_name)
                if isinstance(method, FunctionType):
                    # cls.logger.debug(cls.sign + f'decorate_methods -> db_connector wrapper -> method: {attr_name}')
                    setattr(cls, attr_name, cls.db_connector(method))

    async def get_or_create_contact(self, contact: dict, bad_contact: bool = False) -> tuple[Model, bool]:
        """ Если phone не найден в таблице contacts или bad_contacts -> создаёт новую запись """
        if bad_contact:
            db_contact, fact_create = self.tables.bad_contacts.get_or_create(phone=contact.get('phone'))
        else:
            db_contact, fact_create = self.tables.contacts.get_or_create(phone=contact.get('phone'))
        if fact_create:
            db_contact.promo_id = contact.get('promo_id')
            db_contact.var_1 = contact.get('var_1')
            db_contact.var_2 = contact.get('var_2')
            db_contact.var_3 = contact.get('var_3')
            db_contact.date_check = datetime.now()
            db_contact.session_check = contact.get('session_name')
            if bad_contact:
                db_contact.check_result = contact.get('check_result')
            else:
                db_contact.user_id = contact.get('user_id')
                db_contact.username = contact.get('username')
                db_contact.first_name = contact.get('first_name')
                db_contact.last_name = contact.get('last_name')
            db_contact.save()

        text = 'created new contact' if fact_create else 'get contact'
        self.logger.debug(self.sign + f'{bad_contact=} | {text.upper()}: {db_contact.phone=}')
        return db_contact, fact_create

    async def get_or_none_contact_in_contacts(self, phone: int) -> Tables.contacts | None:
        """ Возвращает контакт из таблицы contacts если он там есть """
        contact = self.tables.contacts.get_or_none(phone=phone)
        msg = self.sign + f'{contact=}'
        self.logger.debug(msg) if contact else self.logger.warning(msg)
        return contact

    async def get_or_none_contact_in_bad_contacts(self, phone: int) -> Tables.contacts | None:
        """ Возвращает контакт из таблицы bad_contacts если он там есть """

        contact = self.tables.bad_contacts.get_or_none(phone=phone)
        self.logger.debug(self.sign + f'{contact=}')
        return contact

    # async def update_contact(self, contact: Contact) -> Contact:
    #     """ Обновляет данные контакта в таблице contacts """
    #     db_contact: Contact = self.tables.contacts.get_or_none(phone=contact.phone)

        # if not db_contact:
        #     return False

        # if with_check:
        #     db_contact.date_check = datetime.now()
        #     db_contact.session_check = contact.session_check
        #
        # db_contact.date_last_send = datetime.now()
        # db_contact.session_last_send = contact.session_last_send
        # db_contact.num_sends += 1
        #
        # db_contact.save()
        # return db_contact
        # contact.save()
        # return db_contact

    async def check_contacts_in_all_tables(self, contacts: list[dict]) -> list[dict]:
        """ Проверяет входящий список контактов на наличие каждого контакта в БД и
        возвращает список только тех контактов, которых нет в БД"""

        result_contacts = []
        for contact in contacts:
            phone = contact.get('phone')
            if not self.tables.contacts.get_or_none(phone=phone) \
                    and not self.tables.bad_contacts.get_or_none(phone=phone):
                result_contacts.append(contact)
        self.logger.debug(self.sign + f'Проверено: {len(contacts)} контактов, '
                                      f'из них ранее записано в БД: {len(contacts) - len(result_contacts)}, '
                                      f'к дальнейшей обработке: {len(result_contacts)}')
        return result_contacts

    async def get_contacts_from_promo_id(self, promo_id: str) -> list[Contact]:
        """ Возвращает список контактов соответствующих promo_id """
        # args = [(self.tables.contacts.promo_id == promo_id), (self.tables.contacts.num_sends > 0)]
        # contacts = self.tables.contacts.select().where(*args)
        contacts: Tables.contacts = self.tables.contacts.select().where(self.tables.contacts.promo_id == promo_id)
        return list(contacts)
