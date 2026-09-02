import sqlite3
import re
import pandas as pd
import logging
from typing import List, Dict, Any, Tuple
from app.config import DB_DIR

logger = logging.getLogger("database_service")

class DatabaseService:
    def __init__(self):
        self.db_path = DB_DIR / "platform_data.db"

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def sanitize_table_name(self, name: str) -> str:
        """Sanitizes table names for safe SQLite usage."""
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
        if not clean or clean[0].isdigit():
            clean = "tbl_" + clean
        return clean

    def load_dataframe_to_sqlite(self, df: pd.DataFrame, dataset_id: str, original_filename: str) -> str:
        """
        Loads cleaned DataFrame into SQLite table.
        Returns the created table_name.
        """
        base_name = original_filename.rsplit(".", 1)[0]
        table_name = self.sanitize_table_name(f"{base_name}_{dataset_id[:8]}")

        conn = self._get_connection()
        try:
            # Write dataframe to SQLite table
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            logger.info(f"Loaded {len(df)} rows into SQLite table '{table_name}'")
            return table_name
        finally:
            conn.close()

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Returns list of column names and SQLite data types.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info('{table_name}');")
            columns_info = cursor.fetchall()
            schema = []
            for col in columns_info:
                schema.append({
                    "name": col["name"],
                    "type": col["type"],
                    "notnull": bool(col["notnull"]),
                    "pk": bool(col["pk"])
                })
            return schema
        finally:
            conn.close()

    def get_sample_rows(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves sample rows from SQLite table.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM "{table_name}" LIMIT ?;', (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def execute_query(self, sql: str) -> Tuple[List[str], List[Dict[str, Any]], int]:
        """
        Executes read-only SQL query on SQLite database.
        Returns (columns, rows_list_of_dicts, row_count).
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            dict_rows = [dict(row) for row in rows]
            return columns, dict_rows, len(dict_rows)
        finally:
            conn.close()

database_service = DatabaseService()
