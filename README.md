# ДЗ2 по курсу "Программирование на Python"

Небольшая консольная база данных на Python. Проект реализован в процедурном стиле: таблицы и записи хранятся в JSON-файлах, команды вводятся в интерактивном режиме.

## Возможности

- создание, просмотр и удаление таблиц;
- типы столбцов `int`, `str`, `bool`;
- автоматическое создание уникального целочисленного `ID`;
- CRUD-операции: `insert`, `select`, `update`, `delete`;
- фильтрация по одному или нескольким условиям `where`;
- отображение записей с помощью PrettyTable;
- JSON-хранение метаданных и данных таблиц;
- подтверждение удаления, централизованная обработка ожидаемых ошибок, замер времени и кэширование `select`.

## Требования

- Python 3.12 или новее;
- [uv](https://docs.astral.sh/uv/).

## Установка и запуск

```bash
uv sync
uv run database
```

Альтернативные варианты запуска:

```bash
uv run project
uv run python -m primitive_db.main
```

После установки собранного wheel-файла команда `database` также будет доступна как CLI-команда:

```bash
uv build
uv tool install dist/*.whl
database
```

## Управление таблицами

Поддерживаемые команды:

| Команда | Назначение |
|---|---|
| `create_table <table> <column:type> ...` | Создать таблицу |
| `list_tables` | Показать список таблиц |
| `drop_table <table>` | Удалить таблицу (требуется подтверждение `y`) |
| `info <table>` | Показать структуру таблицы и количество записей |
| `help` | Показать справку |
| `exit` | Завершить программу |

Пример:

```text
create_table users name:str age:int is_active:bool
Таблица "users" успешно создана со столбцами: ID:int, name:str, age:int, is_active:bool
list_tables
- users
info users
Таблица: users
Столбцы: ID:int, name:str, age:int, is_active:bool
Количество записей: 0
```

Столбец `ID:int` добавляется автоматически. Не указывайте его в команде `create_table`.

## CRUD-операции

### Добавление записи

Строковые значения обязательно заключаются в одинарные или двойные кавычки. Значения `bool` записываются как `true` или `false`.

```text
insert into users values ("Sergei", 28, true)
```

Программа проверит количество и типы значений, автоматически назначит следующий `ID` и сохранит запись.

### Чтение записей

```text
select from users
select from users where age = 28
select from users where name = "Sergei"
```

### Обновление записей

```text
update users set age = 29 where name = "Sergei"
update users set age = 30, is_active = false where ID = 1
```

### Удаление записей

```text
delete from users where ID = 1
```

Перед удалением приложение запросит подтверждение. Введите `y`, чтобы продолжить, или любой другой ответ, чтобы отменить операцию.

## Хранение данных

- `db_meta.json` — метаданные: имена таблиц и описания столбцов;
- `data/<table_name>.json` — записи конкретной таблицы.

## Архитектура

```text
src/primitive_db/
├── __init__.py
├── constants.py   # пути, имена и типы-константы
├── core.py        # управление таблицами и CRUD-логика
├── decorators.py  # ошибки, подтверждение, таймер, кэш
├── engine.py      # интерактивный цикл и диспетчеризация команд
├── main.py        # точка входа
├── parser.py      # разбор значений и условий
└── utils.py       # чтение и запись JSON-файлов
```

## Проверки и сборка

```bash
uv run ruff check .
uv build
uvx twine check dist/*
```

Для установки CLI из собранного wheel-файла:

```bash
uv tool install dist/*.whl
database
```

## Демонстрация 

Полная демонстрация работы базы данных: создание таблицы, добавление записей, чтение, обновление, удаление записей и таблицы.

[![asciicast](https://asciinema.org/a/2JhOW0gOcDf972El.png)](https://asciinema.org/a/2JhOW0gOcDf972El)
