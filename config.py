import ast
import os

from loguru import logger
from python_socks import ProxyType
from dotenv import load_dotenv
load_dotenv()

""" Конфигурация базы данных """
if not os.getenv('PG_DATABASE'):
    DATABASE_CONFIG = ('sqlite', {'database': 'database/database.db',
                                  'pragmas': (('cache_size', -1024 * 64),
                                              ('journal_mode', 'wal'), ('foreign_keys', 1))})
else:
    DATABASE_CONFIG = ('postgres', ast.literal_eval(os.getenv('PG_DATABASE')))

""" Конфигурация логирования """
ERRORS_FORMAT = '{time:DD-MM-YYYY at HH:mm:ss} | {level} | {message}'
DEBUG_FORMAT = '{time:DD-MM-YYYY at HH:mm:ss} | {level} | {message}'

logger_common_args = {
    'diagnose': True,
    'backtrace': False,
    'rotation': '10 Mb',
    'retention': 1,
    'compression': 'zip'
}

PATH_FILE_DEBUG_LOGS = 'logs/debug.log'
PATH_FILE_ERRORS_LOGS = 'logs/errors.log'

LOGGER_DEBUG = {'sink': PATH_FILE_DEBUG_LOGS, 'level': 'DEBUG', 'format': ERRORS_FORMAT} | logger_common_args
LOGGER_ERRORS = {'sink': PATH_FILE_ERRORS_LOGS, 'level': 'WARNING', 'format': DEBUG_FORMAT} | logger_common_args

logger.add(**LOGGER_ERRORS)
logger.add(**LOGGER_DEBUG)

""" Основные пути """
WORKING_FILES_DIR = os.path.abspath('working_files')
WORK_SESSIONS_DIR = os.path.abspath(f'{WORKING_FILES_DIR}{os.sep}work_sessions')
GOOD_SESSIONS_AFTER_CHECKER_DIR = os.path.abspath(f'{WORKING_FILES_DIR}{os.sep}good_sessions_after_checker')
BAD_SESSIONS_DIR = os.path.abspath(f'{WORKING_FILES_DIR}{os.sep}bad_sessions')
INPUT_FILES_DIR = os.path.abspath(f'{WORKING_FILES_DIR}{os.sep}input_files')

INPUT_CSV_FILE_NAME = 'phones.csv'
INPUT_CSV_FILE_PATH = os.path.abspath(f'{INPUT_FILES_DIR}{os.sep}{INPUT_CSV_FILE_NAME}')

SESSION_IN_WORK_FILE_NAME = 'sessions_in_work.json'
SESSION_IN_WORK_FILE_PATH = os.path.abspath(f'{WORKING_FILES_DIR}{os.sep}{SESSION_IN_WORK_FILE_NAME}')

""" Дефолтное время карантина(сек.) для сессии в случае исключения от Телеграм"""
DEFAULT_QUARANTINE_TIME = 60 * 15

""" Диапазон рандомной задержки(сек.) между запросами к Телеграм """
FROM = 1
BEFORE = 5

""" Максимальное количество запросов от одной сессии за одно подключение """
MAX_REQUESTS = 25

""" Максимальное количество контактов в телефонной книге одной сессии """
MAX_CONTACTS = 19

""" Конфигурация прокси, если == None -> используется прокcи указанный в json файле сессии """
# CONFIG_PROXY = None
CONFIG_PROXY = {
    'proxy_type': ProxyType.SOCKS5,
    'addr': '51.79.192.224',
    'port': 10090,
    'rdns': True,
    'username': 'oskosks9221',
    'password': '293aae'
}
# 51.79.192.224:10090|username:oskosks9221|password:293aae  # на выходе динамический ip
