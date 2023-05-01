import csv
import os.path

from managers.base import BaseSingletonClass
from config import INPUT_CSV_FILE_PATH, INPUT_CSV_FILE_NAME


class CSVManager(BaseSingletonClass):
    """ Класс для вынесения логики получения данных из входящего .csv файла """

    async def __call__(self) -> list:
        result = []

        while not (os.path.exists(INPUT_CSV_FILE_PATH) and os.path.isfile(INPUT_CSV_FILE_PATH)):
            input(f'Не найден файл: {INPUT_CSV_FILE_NAME}, загрузите файл и нажмите Enter для продолжения: ')

        with open(INPUT_CSV_FILE_PATH, newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            for num, row in enumerate(reader, 1):
                try:
                    contact = {
                        'promo_id': row[0],
                        'phone': row[1],
                        'var_1': row[2],
                        'var_2': row[3],
                        'var_3': row[4],
                    }
                except Exception as exc:
                    self.logger.warning(self.sign + f'Невалидная запись в строке: {num} | {row=} | {exc=}')
                    continue
                else:
                    result.append(contact)

        self.logger.debug(self.sign + f'загружено валидных строк: {len(result)} '
                                      f'из {reader.line_num} строк файла {INPUT_CSV_FILE_NAME}')
        return result
