"""Parsers for values and SQL-like command conditions."""

import re
import shlex
from typing import Any

from primitive_db.constants import ID_COLUMN
from primitive_db.core import get_column_type, get_table_columns


def split_csv_values(text: str) -> list[str]:
    """Split comma-separated values while preserving quoted commas."""
    values: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False

    for character in text:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if character == "\\" and quote is not None:
            current.append(character)
            escaped = True
            continue
        if character in ("'", '"'):
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            current.append(character)
            continue
        if character == "," and quote is None:
            values.append("".join(current).strip())
            current = []
            continue
        current.append(character)

    if quote is not None:
        raise ValueError(
            "строковое значение содержит "
            "незакрытые кавычки"
        )
    final_value = "".join(current).strip()
    if final_value or values:
        values.append(final_value)
    return values


def split_assignment(text: str) -> tuple[str, str]:
    """Split one assignment at the first equals sign outside quotes."""
    quote: str | None = None
    escaped = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote is not None:
            escaped = True
            continue
        if character in ("'", '"'):
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if character == "=" and quote is None:
            column_name = text[:index].strip()
            raw_value = text[index + 1 :].strip()
            if not column_name or not raw_value:
                break
            return column_name, raw_value
    raise ValueError(
        f"условие {text!r} должно иметь формат "
        "столбец = значение"
    )


def parse_scalar(raw_value: str, data_type: str) -> Any:
    """Parse one literal according to a column's declared type."""
    value = raw_value.strip()
    if data_type == "str":
        if len(value) < 2 or value[0] not in ("'", '"') or value[-1] != value[0]:
            raise ValueError(
                f"строковое значение {value!r} "
                "необходимо заключить в кавычки"
            )
        parsed = shlex.split(value)
        if len(parsed) != 1:
            raise ValueError(f"некорректная строка {value!r}")
        return parsed[0]
    if data_type == "int":
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(
                f"значение {value!r} должно быть "
                "целым числом"
            ) from error
    if data_type == "bool":
        lowered = value.casefold()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        raise ValueError(
            "логическое значение должно быть "
            "true или false, "
            f"не {value!r}"
        )
    raise ValueError(
        f"неподдерживаемый тип данных {data_type!r}"
    )


def parse_values(
    raw_values: str, metadata: dict[str, Any], table_name: str
) -> list[Any]:
    """Parse and type-check the values for an insert command."""
    schema = [
        column
        for column in get_table_columns(metadata, table_name)
        if column["name"].casefold() != ID_COLUMN.casefold()
    ]
    tokens = split_csv_values(raw_values)
    if len(tokens) != len(schema):
        raise ValueError(
            f"ожидалось {len(schema)} значений, "
            f"получено {len(tokens)}"
        )
    return [
        parse_scalar(token, column["type"])
        for token, column in zip(tokens, schema, strict=True)
    ]


def parse_assignments(
    text: str, metadata: dict[str, Any], table_name: str
) -> dict[str, Any]:
    """Parse a comma-separated set of column assignments."""
    assignments: dict[str, Any] = {}
    for token in split_csv_values(text):
        column_name, raw_value = split_assignment(token)
        data_type = get_column_type(metadata, table_name, column_name)
        assignments[column_name] = parse_scalar(raw_value, data_type)
    return assignments


def parse_where_clause(
    text: str, metadata: dict[str, Any], table_name: str
) -> dict[str, Any]:
    """Parse one where condition into a typed dictionary."""
    return parse_assignments(text, metadata, table_name)


def parse_insert_command(command: str) -> tuple[str, str]:
    """Extract a table name and raw values from an INSERT command."""
    match = re.fullmatch(
        r"\s*insert\s+into\s+([A-Za-z_][A-Za-z0-9_]*)\s+"
        r"values\s*\((.*)\)\s*;?\s*",
        command,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(
            "формат команды: insert into table values "
            "(значение1, значение2, ...)"
        )
    return match.group(1), match.group(2)


def parse_select_command(command: str) -> tuple[str, str | None]:
    """Extract the table name and optional where clause from SELECT."""
    match = re.fullmatch(
        r"\s*select\s+from\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"(?:\s+where\s+(.+?))?\s*;?\s*",
        command,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(
            "формат команды: select from table "
            "[where столбец = значение]"
        )
    return match.group(1), match.group(2)


def _find_keyword_outside_quotes(text: str, keyword: str) -> int:
    """Find a standalone keyword without matching text inside quotes."""
    quote: str | None = None
    escaped = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote is not None:
            escaped = True
            continue
        if character in ("'", '"'):
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        end = index + len(keyword)
        matches = text[index:end].casefold() == keyword.casefold()
        starts_word = index == 0 or text[index - 1].isspace()
        ends_word = end == len(text) or text[end].isspace()
        if quote is None and matches and starts_word and ends_word:
            return index
    return -1


def parse_update_command(command: str) -> tuple[str, str, str]:
    """Extract table name, SET assignments, and WHERE conditions."""
    prefix = re.match(
        r"\s*update\s+([A-Za-z_][A-Za-z0-9_]*)\s+set\s+",
        command,
        flags=re.IGNORECASE,
    )
    if prefix is None:
        raise ValueError(
            "формат команды: update table set "
            "столбец = значение where условие"
        )
    remainder = command[prefix.end() :].strip()
    where_index = _find_keyword_outside_quotes(remainder, "where")
    if where_index < 0:
        raise ValueError("в команде update обязательно условие where")
    set_clause = remainder[:where_index].strip()
    where_clause = remainder[where_index + len("where") :].strip()
    where_clause = where_clause.removesuffix(";").strip()
    if not set_clause or not where_clause:
        raise ValueError("условия set и where не должны быть пустыми")
    return prefix.group(1), set_clause, where_clause


def parse_delete_command(command: str) -> tuple[str, str]:
    """Extract table name and WHERE conditions from DELETE."""
    match = re.fullmatch(
        r"\s*delete\s+from\s+([A-Za-z_][A-Za-z0-9_]*)\s+"
        r"where\s+(.+?)\s*;?\s*",
        command,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(
            "формат команды: delete from table "
            "where столбец = значение"
        )
    return match.group(1), match.group(2)
