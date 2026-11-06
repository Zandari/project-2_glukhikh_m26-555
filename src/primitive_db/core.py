"""Business logic for table management and CRUD operations."""

import json
from typing import Any

from primitive_db.constants import ID_COLUMN, ID_TYPE, VALID_TYPES
from primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)
from primitive_db.utils import load_table_data

_CACHE_RESULT = create_cacher()


def _get_columns(table_info: dict[str, Any]) -> list[dict[str, str]]:
    """Return a table schema as a normalized list of name/type dictionaries."""
    columns = table_info.get("columns", table_info)
    if isinstance(columns, dict):
        return [
            {"name": str(name), "type": str(data_type)}
            for name, data_type in columns.items()
        ]
    normalized: list[dict[str, str]] = []
    for column in columns:
        if isinstance(column, dict):
            normalized.append(
                {
                    "name": str(column["name"]),
                    "type": str(column["type"]),
                }
            )
        elif isinstance(column, (tuple, list)) and len(column) == 2:
            normalized.append({"name": str(column[0]), "type": str(column[1])})
        else:
            raise ValueError(
                f"Некорректное описание столбца: {column!r}"
            )
    return normalized


def get_table_columns(
    metadata: dict[str, Any], table_name: str
) -> list[dict[str, str]]:
    """Return the schema for a table or raise a helpful error."""
    if table_name not in metadata:
        raise KeyError(f'Таблица "{table_name}" не существует.')
    return _get_columns(metadata[table_name])


def get_column_type(
    metadata: dict[str, Any], table_name: str, column_name: str
) -> str:
    """Find a column type using a case-insensitive column name."""
    for column in get_table_columns(metadata, table_name):
        if column["name"].casefold() == column_name.casefold():
            return column["type"]
    raise KeyError(
        f'Столбец "{column_name}" не существует '
        f'в таблице "{table_name}".'
    )


def validate_value(value: Any, data_type: str) -> None:
    """Check that a Python value has exactly the declared database type."""
    if data_type not in VALID_TYPES:
        raise ValueError(
            f"Тип данных {data_type!r} не поддерживается."
        )
    is_valid = (
        (
            data_type == "int"
            and isinstance(value, int)
            and not isinstance(value, bool)
        )
        or (data_type == "str" and isinstance(value, str))
        or (data_type == "bool" and isinstance(value, bool))
    )
    if not is_valid:
        raise ValueError(
            f"ожидался тип {data_type}, получено значение "
            f"{value!r} типа {type(value).__name__}"
        )


def _normalise_column_definitions(
    columns: list[Any],
) -> list[dict[str, str]]:
    """Validate user column definitions and prepend the automatic ID column."""
    normalized: list[dict[str, str]] = [
        {"name": ID_COLUMN, "type": ID_TYPE}
    ]
    used_names = {ID_COLUMN.casefold()}

    for column in columns:
        if isinstance(column, str):
            if ":" not in column:
                raise ValueError(
                    f"столбец {column!r} должен иметь "
                    "формат имя:тип"
                )
            name, data_type = column.split(":", maxsplit=1)
        elif isinstance(column, (tuple, list)) and len(column) == 2:
            name, data_type = column
        elif isinstance(column, dict) and "name" in column and "type" in column:
            name, data_type = column["name"], column["type"]
        else:
            raise ValueError(
                f"Некорректное описание столбца: {column!r}"
            )

        name = str(name).strip()
        data_type = str(data_type).strip().lower()
        if not name or not name.isidentifier() or not name.isascii():
            raise ValueError(f"некорректное имя столбца {name!r}")
        if name.casefold() in used_names:
            raise ValueError(
                f"столбец {name!r} указан более одного раза"
            )
        if data_type not in VALID_TYPES:
            raise ValueError(
                f"тип {data_type!r} не поддерживается; "
                f"допустимые типы: {', '.join(VALID_TYPES)}"
            )
        normalized.append({"name": name, "type": data_type})
        used_names.add(name.casefold())

    if len(normalized) == 1:
        raise ValueError(
            "нужно указать хотя бы один "
            "пользовательский столбец"
        )
    return normalized


@handle_db_errors
def create_table(
    metadata: dict[str, Any], table_name: str, columns: list[Any]
) -> dict[str, Any] | None:
    """Create a table schema and return updated metadata."""
    if (
        not table_name
        or not table_name.isidentifier()
        or not table_name.isascii()
    ):
        raise ValueError(
            f"некорректное имя таблицы {table_name!r}"
        )
    if table_name in metadata:
        raise KeyError(f'Таблица "{table_name}" уже существует.')

    new_metadata = metadata.copy()
    new_metadata[table_name] = {"columns": _normalise_column_definitions(columns)}
    return new_metadata


@handle_db_errors
@confirm_action("удаление таблицы")
def drop_table(
    metadata: dict[str, Any], table_name: str
) -> dict[str, Any] | None:
    """Drop a table definition after the user confirms the operation."""
    if table_name not in metadata:
        raise KeyError(f'Таблица "{table_name}" не существует.')
    new_metadata = metadata.copy()
    del new_metadata[table_name]
    return new_metadata


def list_tables(metadata: dict[str, Any]) -> list[str]:
    """Return table names in alphabetical order."""
    return sorted(metadata)


def _matches(record: dict[str, Any], where_clause: dict[str, Any] | None) -> bool:
    """Check whether one record satisfies all conditions in a where clause."""
    if not where_clause:
        return True
    record_values = {key.casefold(): value for key, value in record.items()}
    return all(
        record_values.get(column.casefold(), object()) == expected
        for column, expected in where_clause.items()
    )


@handle_db_errors
@log_time
def insert(
    metadata: dict[str, Any],
    table_name: str,
    values: list[Any],
    table_data: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    """Validate and append a new record, generating its ID automatically."""
    columns = get_table_columns(metadata, table_name)
    user_columns = [
        column
        for column in columns
        if column["name"].casefold() != ID_COLUMN.casefold()
    ]
    if len(values) != len(user_columns):
        raise ValueError(
            f"ожидалось {len(user_columns)} значений, "
            f"получено {len(values)}"
        )

    record: dict[str, Any] = {}
    for column, value in zip(user_columns, values, strict=True):
        validate_value(value, column["type"])
        record[column["name"]] = value

    current_data = table_data if table_data is not None else load_table_data(table_name)
    record[ID_COLUMN] = max(
        (row.get(ID_COLUMN, 0) for row in current_data), default=0
    ) + 1
    ordered_record = {ID_COLUMN: record[ID_COLUMN]}
    ordered_record.update(
        {column["name"]: record[column["name"]] for column in user_columns}
    )
    current_data.append(ordered_record)
    return current_data


@handle_db_errors
@log_time
def select(
    table_data: list[dict[str, Any]],
    where_clause: dict[str, Any] | None = None,
) -> list[dict[str, Any]] | None:
    """Return all records or only records matching the supplied conditions."""
    cache_key = json.dumps(
        [table_data, where_clause], ensure_ascii=False, sort_keys=True
    )
    cached_records = _CACHE_RESULT(
        cache_key,
        lambda: [
            record.copy()
            for record in table_data
            if _matches(record, where_clause)
        ],
    )
    return [record.copy() for record in cached_records]


@handle_db_errors
def update(
    table_data: list[dict[str, Any]],
    set_clause: dict[str, Any],
    where_clause: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    table_name: str | None = None,
) -> list[dict[str, Any]] | None:
    """Update matching records and return the modified record list."""
    if not set_clause:
        raise ValueError(
            "не указаны значения для обновления"
        )
    if metadata is not None and table_name is not None:
        for column_name, value in set_clause.items():
            if column_name.casefold() == ID_COLUMN.casefold():
                raise ValueError(
                    "столбец ID нельзя изменять вручную"
                )
            validate_value(value, get_column_type(metadata, table_name, column_name))
    normalized_set = {key.casefold(): (key, value) for key, value in set_clause.items()}
    for record in table_data:
        if _matches(record, where_clause):
            for normalized_name, (original_name, value) in normalized_set.items():
                actual_name = next(
                    (
                        name
                        for name in record
                        if name.casefold() == normalized_name
                    ),
                    original_name,
                )
                if actual_name not in record:
                    raise KeyError(
                        f'Столбец "{original_name}" не найден.'
                    )
                record[actual_name] = value
    return table_data


@handle_db_errors
@confirm_action("удаление записей")
def delete(
    table_data: list[dict[str, Any]], where_clause: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """Delete records matching the supplied conditions after confirmation."""
    if not where_clause:
        raise ValueError(
            "для удаления обязательно укажите "
            "условие where"
        )
    return [record for record in table_data if not _matches(record, where_clause)]
