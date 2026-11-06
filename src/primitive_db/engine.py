"""Interactive command loop and command dispatch for the database."""

import shlex
from typing import Any

import prompt
from prettytable import PrettyTable

from primitive_db import core
from primitive_db.constants import ID_COLUMN, META_FILE, PROMPT_TEXT
from primitive_db.parser import (
    parse_assignments,
    parse_delete_command,
    parse_insert_command,
    parse_select_command,
    parse_update_command,
    parse_values,
    parse_where_clause,
)
from primitive_db.utils import (
    load_metadata,
    load_table_data,
    remove_table_data,
    save_metadata,
    save_table_data,
)


def print_help() -> None:
    """Print the available database commands."""
    print("\n***Процесс работы с таблицей***")
    print("Функции:")
    print(
        "<command> create_table <имя_таблицы> <столбец1:тип> .. "
        "- создать таблицу"
    )
    print("<command> list_tables - показать список всех таблиц")
    print(
        "<command> drop_table <имя_таблицы> - удалить таблицу"
    )
    print(
        "<command> insert into <таблица> values (<значения>) "
        "- добавить запись"
    )
    print(
        "<command> select from <таблица> "
        "[where столбец = значение] - чтение"
    )
    print(
        "<command> update <таблица> set столбец = значение where "
        "условие - обновить запись"
    )
    print(
        "<command> delete from <таблица> where условие "
        "- удалить запись"
    )
    print(
        "<command> info <имя_таблицы> - "
        "информация о таблице"
    )
    print("\nОбщие команды:")
    print("<command> exit - выход из программы")
    print("<command> help - справочная информация\n")


def _read_command() -> str:
    """Read a non-empty command using prompt when available."""
    return prompt.string(prompt=PROMPT_TEXT)


def _get_table_metadata(
    metadata: dict[str, Any], table_name: str
) -> dict[str, Any]:
    """Return table metadata or raise a descriptive KeyError."""
    if table_name not in metadata:
        raise KeyError(f'Таблица "{table_name}" не существует.')
    return metadata[table_name]


def _print_records(
    metadata: dict[str, Any], table_name: str, records: list[dict[str, Any]]
) -> None:
    """Render records with PrettyTable using the declared column order."""
    columns = core.get_table_columns(metadata, table_name)
    table = PrettyTable()
    table.field_names = [column["name"] for column in columns]
    for record in records:
        table.add_row([record.get(column) for column in table.field_names])
    if records:
        print(table)
    else:
        print("Записи не найдены.")


def _handle_create_table(tokens: list[str], metadata: dict[str, Any]) -> None:
    """Handle create_table and persist the updated schema."""
    if len(tokens) < 3:
        raise ValueError(
            "формат команды: create_table имя_таблицы "
            "столбец:тип [столбец:тип ...]"
        )
    table_name = tokens[1]
    updated_metadata = core.create_table(metadata, table_name, tokens[2:])
    if updated_metadata is None:
        return
    save_metadata(META_FILE, updated_metadata)
    columns = core.get_table_columns(updated_metadata, table_name)
    description = ", ".join(
        f"{column['name']}:{column['type']}" for column in columns
    )
    print(
        f'Таблица "{table_name}" успешно создана '
        f'со столбцами: {description}'
    )


def _handle_drop_table(tokens: list[str], metadata: dict[str, Any]) -> None:
    """Handle drop_table and remove both schema and table data."""
    if len(tokens) != 2:
        raise ValueError(
            "формат команды: drop_table имя_таблицы"
        )
    table_name = tokens[1]
    _get_table_metadata(metadata, table_name)
    updated_metadata = core.drop_table(metadata, table_name)
    if updated_metadata is None:
        return
    save_metadata(META_FILE, updated_metadata)
    remove_table_data(table_name)
    print(f'Таблица "{table_name}" успешно удалена.')


def _handle_insert(command: str, metadata: dict[str, Any]) -> None:
    """Parse and execute an INSERT command."""
    table_name, raw_values = parse_insert_command(command)
    _get_table_metadata(metadata, table_name)
    values = parse_values(raw_values, metadata, table_name)
    table_data = load_table_data(table_name)
    updated_data = core.insert(metadata, table_name, values, table_data)
    if updated_data is None:
        return
    save_table_data(table_name, updated_data)
    print(
        f'Запись с ID={updated_data[-1][ID_COLUMN]} '
        f'успешно добавлена в таблицу "{table_name}".'
    )


def _handle_select(command: str, metadata: dict[str, Any]) -> None:
    """Parse and execute a SELECT command."""
    table_name, raw_where = parse_select_command(command)
    _get_table_metadata(metadata, table_name)
    where_clause = (
        parse_where_clause(raw_where, metadata, table_name)
        if raw_where
        else None
    )
    records = core.select(load_table_data(table_name), where_clause)
    if records is not None:
        _print_records(metadata, table_name, records)


def _handle_update(command: str, metadata: dict[str, Any]) -> None:
    """Parse and execute an UPDATE command."""
    table_name, raw_set, raw_where = parse_update_command(command)
    _get_table_metadata(metadata, table_name)
    set_clause = parse_assignments(raw_set, metadata, table_name)
    where_clause = parse_where_clause(raw_where, metadata, table_name)
    old_data = load_table_data(table_name)
    before_update = [record.copy() for record in old_data]
    updated_data = core.update(
        old_data, set_clause, where_clause, metadata, table_name
    )
    if updated_data is None:
        return
    changed_ids = [
        old_record[ID_COLUMN]
        for old_record, new_record in zip(before_update, updated_data, strict=True)
        if old_record != new_record
    ]
    if not changed_ids:
        print("Подходящие записи не найдены.")
        return
    save_table_data(table_name, updated_data)
    for record_id in changed_ids:
        print(
            f'Запись с ID={record_id} в таблице "{table_name}" '
            "успешно обновлена."
        )


def _handle_delete(command: str, metadata: dict[str, Any]) -> None:
    """Parse and execute a DELETE command after confirmation."""
    table_name, raw_where = parse_delete_command(command)
    _get_table_metadata(metadata, table_name)
    where_clause = parse_where_clause(raw_where, metadata, table_name)
    old_data = load_table_data(table_name)
    matching_records = core.select(old_data, where_clause)
    if matching_records is None:
        return
    if not matching_records:
        print("Подходящие записи не найдены.")
        return
    updated_data = core.delete(old_data, where_clause)
    if updated_data is None:
        return
    remaining_ids = {record[ID_COLUMN] for record in updated_data}
    deleted_records = [
        record for record in old_data if record[ID_COLUMN] not in remaining_ids
    ]
    save_table_data(table_name, updated_data)
    if not deleted_records:
        print("Подходящие записи не найдены.")
        return
    for record in deleted_records:
        print(
            f'Запись с ID={record[ID_COLUMN]} '
            f'успешно удалена из таблицы "{table_name}".'
        )


def _handle_info(tokens: list[str], metadata: dict[str, Any]) -> None:
    """Print a table schema and its current record count."""
    if len(tokens) != 2:
        raise ValueError("формат команды: info имя_таблицы")
    table_name = tokens[1]
    columns = core.get_table_columns(metadata, table_name)
    description = ", ".join(
        f"{column['name']}:{column['type']}" for column in columns
    )
    print(f"Таблица: {table_name}")
    print(f"Столбцы: {description}")
    print(f"Количество записей: {len(load_table_data(table_name))}")


def _dispatch(command_text: str, metadata: dict[str, Any]) -> bool:
    """Execute one command; return False when the application should exit."""
    try:
        tokens = shlex.split(command_text)
    except ValueError as error:
        print(
            f"Некорректная команда: {error}. "
            "Попробуйте снова."
        )
        return True
    if not tokens:
        return True

    command = tokens[0].casefold()
    try:
        if command == "exit":
            print("Работа с базой данных завершена.")
            return False
        if command == "help":
            print_help()
        elif command == "create_table":
            _handle_create_table(tokens, metadata)
        elif command == "drop_table":
            _handle_drop_table(tokens, metadata)
        elif command == "list_tables":
            if len(tokens) != 1:
                raise ValueError(
                    "команда list_tables не принимает "
                    "аргументы"
                )
            table_names = core.list_tables(metadata)
            if table_names:
                for table_name in table_names:
                    print(f"- {table_name}")
            else:
                print("Таблиц пока нет.")
        elif command == "insert":
            _handle_insert(command_text, metadata)
        elif command == "select":
            _handle_select(command_text, metadata)
        elif command == "update":
            _handle_update(command_text, metadata)
        elif command == "delete":
            _handle_delete(command_text, metadata)
        elif command == "info":
            _handle_info(tokens, metadata)
        else:
            print(
                f"Функции {tokens[0]} нет. Попробуйте снова."
            )
    except KeyError as error:
        print(f"Ошибка: {error}")
    except ValueError as error:
        print(
            f"Некорректное значение: {error}. "
            "Попробуйте снова."
        )
    except FileNotFoundError:
        print("Ошибка: файл базы данных не найден.")
    return True


def welcome() -> None:
    """Show the introductory help for the database application."""
    print("\n***База данных***")
    print_help()


def run() -> None:
    """Run the interactive database command loop."""
    welcome()
    while True:
        metadata = load_metadata(META_FILE)
        try:
            command_text = _read_command()
        except (EOFError, KeyboardInterrupt):
            print("\nРабота с базой данных завершена.")
            break
        if not command_text.strip():
            continue
        if not _dispatch(command_text, metadata):
            break
