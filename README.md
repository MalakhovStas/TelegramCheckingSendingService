# TelegramCheckingSendingService
Cервис проверки наличия контакта Telegram по номеру телефона и рассылки сообщений.

## Установка
1. Для работы микросервиса нужен Python версии не ниже 3.10
2. Установка виртуального окружения ОС Linux:
    ```shell
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements/base.txt
    ```  

### Если планируете использовать СУБД Postgresql
Все настройки ниже можно не применять тогда по умолчанию будет создан файл базы данных SQLite в 
директории [database](database)  
1. Необходимо установленное ПО для контейнеризации - [Docker](https://docs.docker.com/engine/install/). 
2. Переименуйте файл .env.dist в .env
3. Заполните .env файл. Пример:  
    ```
    PG_DATABASE = '{"database": "tcs_service_db", "host": "localhost", "port": 5432, "user": "my_user", "password": "secret"}'
    ```
4. Установите драйвер для работы с СУБД Postgresql 
   ```shell
   pip install psycopg2-binary
   ```
5. Запуск СУБД Postgresql в [Docker](https://docs.docker.com/engine/install/)
    ```shell
    docker run --name tcs-service-db -e POSTGRES_USER=my_user -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=tcs_service_db -p 5434:5432 -d postgres
    ```

## Начало работы
### Загрузка файлов сессий
1. Файлы сессий загружаются стандартными методами в директорию 
[working_files/work_sessions](working_files/work_sessions), если директория отсутствует - необходимо создать.

### Загрузка контактов в чекер
Файл содержащий номер телефона и данные должен находиться в директории 
[working_files/input_files](working_files/input_files), если директория отсутствует - необходимо создать.
1. Название файла [phones.csv](working_files/Examples/phones.csv). При необходимости название можно изменить в файле config.py
2. Пример структуры файла в директории [working_files/Examples](working_files/Examples):


### Загрузка текстов для рассылки 
Файл содержащий сообщение для рассылки должен находиться в директории 
[working_files/input_files](working_files/input_files), если директория отсутствует - необходимо создать. 
1. Название файла состоит из promo_id и расширения txt. При рассылке по promo_id текст для этой рассылки будет загружен из этого файла.
2. В самом тексте могут содержаться фигурные скобки с названием одной из переменных записанных в БД таким образом
вместо этих скобок будет подставлено значение указаной переменной.
3. Примеры в директории [Examples](working_files/Examples)

## Запуск приложения
Осуществляется после загрузки необходимых файлов(сессии, тексты, phones.txt).

### Чекер
```shell
python start_checker.py
```

### Рассыльщик сообщений
Запускается после заполнения БД Чекером и загрузки текстов, при запуске просит ввести 
promo_id (рассылка будет осуществляться по связанным контактам) и время между отправкой 
сообщений из одной сессии в диапазоне от 1 до 24 часов.
```shell
python start_mailer.py
```
Для повышения эффективности Чекер и Рассыльщик можно запускать одновременно.



