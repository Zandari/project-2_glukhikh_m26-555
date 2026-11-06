"""Reusable decorators and a closure-based result cache."""

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from primitive_db.constants import CONFIRM_ANSWER

F = TypeVar("F", bound=Callable[..., Any])


def handle_db_errors(func: F) -> F:
    """Print expected database errors and return None instead of a traceback."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError:
            print(
                "Ошибка: Файл данных не найден. "
                "База данных не инициализирована."
            )
        except KeyError as error:
            print(f"Ошибка: {error}")
        except ValueError as error:
            print(
                f"Некорректное значение: {error}. "
                "Попробуйте снова."
            )
        return None

    return wrapper  # type: ignore[return-value]


def confirm_action(action_name: str) -> Callable[[F], F]:
    """Create a decorator that asks the user to confirm a dangerous action."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            question = (
                f'Вы уверены, что хотите выполнить "{action_name}"?'
                " [y/n]: "
            )
            answer = input(question)
            if answer.strip().lower() != CONFIRM_ANSWER:
                print("Операция отменена.")
                return None
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def log_time(func: F) -> F:
    """Print how long a function takes, even if it raises an exception."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started_at = time.monotonic()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - started_at
            print(
                f"Функция {func.__name__} выполнилась за "
                f"{elapsed:.3f} секунд."
            )

    return wrapper  # type: ignore[return-value]


def create_cacher() -> Callable[[Any, Callable[[], Any]], Any]:
    """Return a cache function whose dictionary lives in this closure."""
    cache: dict[Any, Any] = {}

    def cache_result(key: Any, value_func: Callable[[], Any]) -> Any:
        if key not in cache:
            cache[key] = value_func()
        return cache[key]

    return cache_result
