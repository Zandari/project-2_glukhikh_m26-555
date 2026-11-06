"""JSON persistence helpers for metadata and table records."""

import json
import os
from pathlib import Path
from typing import Any

from primitive_db.constants import DATA_DIR, META_FILE, TABLE_FILE_SUFFIX


def load_metadata(filepath: str | Path = META_FILE) -> dict[str, Any]:
    """Load database metadata or return an empty dictionary if absent."""
    try:
        with Path(filepath).open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError(
            "Файл метаданных должен содержать "
            "JSON-объект."
        )
    return data


def save_metadata(filepath: str | Path, data: dict[str, Any]) -> None:
    """Save database metadata as readable UTF-8 JSON."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def table_data_path(table_name: str) -> Path:
    """Build the path for one table's JSON file."""
    return DATA_DIR / f"{table_name}{TABLE_FILE_SUFFIX}"


def load_table_data(table_name: str) -> list[dict[str, Any]]:
    """Load table records or return an empty list for a new table."""
    path = table_data_path(table_name)
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    if not isinstance(data, list):
        raise ValueError(
            f"Файл таблицы {table_name} должен "
            "содержать JSON-массив."
        )
    return data


def save_table_data(table_name: str, data: list[dict[str, Any]]) -> None:
    """Save records for a table in the data directory."""
    path = table_data_path(table_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def remove_table_data(table_name: str) -> None:
    """Remove a table's JSON file when its table is dropped."""
    try:
        os.remove(table_data_path(table_name))
    except FileNotFoundError:
        pass
