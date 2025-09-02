"""Output helpers for writing data to various sinks."""

from pathlib import Path

import pandas as pd
from sqlite_utils import Database


def to_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to a CSV file."""
    df.to_csv(path, index=False)


def to_sqlite(df: pd.DataFrame, db_path: Path, table: str) -> None:
    """Write a DataFrame to a SQLite database table."""
    db = Database(str(db_path))
    db[table].insert_all(df.to_dict(orient="records"), pk="id", replace=True)
