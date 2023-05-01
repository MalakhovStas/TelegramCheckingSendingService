from managers.async_db_manager import DBManager
from managers.session_files_manager import SessionFilesManager
from managers.proxy_manager import ProxyManager
from managers.csv_manager import CSVManager
from managers.checker_manager import Checker
from managers.message_manager import MessageManager
from managers.mailer_manager import Mailer


dbm = DBManager()
sfm = SessionFilesManager()
pm = ProxyManager()
csvm = CSVManager()
mm = MessageManager()
checker = Checker(db_manager=dbm, proxy_manager=pm, session_files_manager=sfm, csv_manager=csvm, message_manager=mm)
mailer = Mailer(db_manager=dbm, proxy_manager=pm, session_files_manager=sfm, csv_manager=csvm, message_manager=mm)
