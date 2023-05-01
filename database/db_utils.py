from datetime import datetime

from peewee import ModelBase, Model, CharField, IntegerField, DateTimeField
from playhouse.sqlite_ext import SqliteDatabase, PostgresqlDatabase, MySQLDatabase
from config import DATABASE_CONFIG

databases = {
    'sqlite': SqliteDatabase,
    'postgres': PostgresqlDatabase,
    'mysql': MySQLDatabase
}

db: SqliteDatabase | PostgresqlDatabase | MySQLDatabase = databases[DATABASE_CONFIG[0]](**DATABASE_CONFIG[1])


class Contact(Model):
    """ Модель таблицы номеров имеющих Telegram контакты """
    promo_id = CharField(null=True)
    phone = IntegerField(primary_key=True, unique=True)
    var_1 = CharField(null=True)
    var_2 = CharField(null=True)
    var_3 = CharField(null=True)
    date_check = DateTimeField(default=datetime.now(), null=False)
    session_check = CharField(null=True)

    user_id = IntegerField(null=True)
    username = CharField(null=True)
    first_name = CharField(null=True)
    last_name = CharField(null=True)
    date_last_send = DateTimeField(null=True)
    session_last_send = CharField(null=True)
    num_sends = IntegerField(null=False, default=0)

    class Meta:
        database = db
        order_by = 'id'
        db_table = 'contacts'


class BadContact(Model):
    """ Модель таблицы номеров не имеющих Telegram контакты """
    promo_id = CharField(null=True)
    phone = IntegerField(primary_key=True, unique=True)
    var_1 = CharField(null=True)
    var_2 = CharField(null=True)
    var_3 = CharField(null=True)
    date_check = DateTimeField(default=datetime.now(), null=False)
    session_check = CharField(null=True)
    check_result = CharField(null=True)

    class Meta:
        database = db
        order_by = 'id'
        db_table = 'bad_contacts'


class Tables:
    """ Единая точка доступа ко всем моделям приложения """
    contacts = Contact
    bad_contacts = BadContact

    @classmethod
    def all_tables(cls):
        """ Возвращает список всех моделей приложения """
        return [value for value in cls.__dict__.values() if isinstance(value, ModelBase)]
