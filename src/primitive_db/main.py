#!/usr/bin/env python3
"""Executable entry point for the primitive database application."""

from primitive_db.engine import run


def main() -> None:
    """Start the database command-line interface."""
    run()


if __name__ == "__main__":
    main()
