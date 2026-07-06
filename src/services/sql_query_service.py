"""
SQL Query Service for CAATmaster
Allows executing SQL queries on Polars DataFrames
"""
import polars as pl
import re
from typing import Optional, Dict, List, Any
import json


# Statements an AI-generated query must never contain. This is deliberately
# a denylist over the *generated* query only, not a restriction on what an
# auditor can type themselves in the same editor (they already have full,
# trusted access to their own in-memory session) - it exists because an LLM
# asked to "write SQL for this" has no reason to ever need DDL/DML, and
# DuckDB can both mutate state and touch the real filesystem (read_csv,
# COPY TO, glob, ATTACH) from inside an otherwise-ordinary-looking SELECT.
_UNSAFE_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|export|import|"
    r"install|load|pragma|call|set|vacuum|checkpoint|read_csv|read_parquet|read_json|"
    r"glob|sniff_csv|COPY_FROM|COPY_TO)\b",
    re.IGNORECASE,
)


def is_safe_readonly_select(query: str) -> tuple[bool, str]:
    """Check that an AI-generated query is a single, plain read-only SELECT
    (or WITH ... SELECT) against the already-registered tables - never
    trusting the model's own cooperation with the instructions it was given.
    Returns (is_safe, reason). reason is empty when is_safe is True."""
    stripped = re.sub(r"--[^\n]*", "", query)  # strip line comments before checking
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)  # strip block comments
    stripped = stripped.strip().rstrip(";").strip()

    if not stripped:
        return False, "Generated query is empty."
    if ";" in stripped:
        return False, "Generated query contains multiple statements; only one SELECT is allowed."
    if not re.match(r"^(select|with)\b", stripped, re.IGNORECASE):
        return False, "Generated query must start with SELECT (or WITH ... SELECT)."

    match = _UNSAFE_SQL_PATTERN.search(stripped)
    if match:
        return False, f"Generated query contains disallowed keyword '{match.group(0)}' for an AI-generated query."

    return True, ""


def trim_column_names(df: pl.DataFrame) -> pl.DataFrame:
    """Strip leading/trailing whitespace from column names before a
    dataframe is registered as a SQL table - a column header typed with a
    trailing space (invisible to the eye) otherwise doesn't match the
    identifier a generated or hand-typed query references, producing a
    confusing Binder Error instead of a real result. read_file() already
    does this at import time; this is a defensive second layer at the SQL
    boundary itself, for data that reaches here by some other path."""
    existing = set(df.columns)
    seen = set()
    rename_map = {}
    for c in df.columns:
        if not isinstance(c, str) or c == c.strip():
            seen.add(c)
            continue
        trimmed = c.strip()
        if trimmed in existing or trimmed in seen:
            seen.add(c)
            continue
        rename_map[c] = trimmed
        seen.add(trimmed)
    return df.rename(rename_map) if rename_map else df


def sanitize_table_name(name: str) -> str:
    """Sanitize a dataset name for use as a SQL table name - preserves case
    and most characters. Shared so every caller that registers a dataset as
    a queryable table (the SQL editor, the agent chat's read-only lookups)
    produces the same table name for the same dataset name."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = '_' + sanitized
    return sanitized


def format_result_for_ai(df: pl.DataFrame, max_rows: int = 20) -> str:
    """Compact, plain-text rendering of a query result to hand back to the
    model as ground truth - bounded so a large result doesn't blow up the
    follow-up prompt. The model is told the true row count even when the
    displayed rows are truncated, so it doesn't imply completeness that
    isn't there."""
    lines = [f"{df.height:,} row(s), {len(df.columns)} column(s)"]
    if df.height == 0:
        lines.append("(no rows returned)")
        return "\n".join(lines)

    display_df = df.head(max_rows)
    lines.append(" | ".join(display_df.columns))
    for row in display_df.iter_rows():
        lines.append(" | ".join("" if v is None else str(v) for v in row))
    if df.height > max_rows:
        lines.append(f"... ({df.height - max_rows:,} more row(s) not shown)")
    return "\n".join(lines)


class SQLQueryService:
    """Service for executing SQL queries on Polars DataFrames"""

    def __init__(self):
        """Initialize the SQL query service"""
        self.registered_tables: Dict[str, pl.DataFrame] = {}

    def register_dataframe(self, name: str, df: pl.DataFrame) -> None:
        """
        Register a DataFrame as a SQL table

        Args:
            name: Table name
            df: Polars DataFrame to register
        """
        self.registered_tables[name] = trim_column_names(df)

    def unregister_table(self, name: str) -> None:
        """
        Unregister a table

        Args:
            name: Table name to unregister
        """
        if name in self.registered_tables:
            del self.registered_tables[name]

    def execute_query(
        self,
        query: str,
        params: Dict[str, Any] = None
    ) -> pl.DataFrame:
        """
        Execute a SQL query on registered DataFrames

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            Polars DataFrame with results

        Raises:
            ValueError: If query is invalid or tables not found
        """
        if not self.registered_tables:
            raise ValueError("No data registered. Please load data first.")

        try:
            import duckdb

            # Create duckdb connection
            conn = duckdb.connect(':memory:')

            # Register all tables
            for table_name, df in self.registered_tables.items():
                conn.register(table_name, df)

            # Execute query
            result_df = conn.execute(query).pl()

            conn.close()

            return result_df

        except ImportError:
            raise ImportError(
                "duckdb is required for SQL queries. "
                "Install it with: pip install duckdb"
            )
        except Exception as e:
            raise ValueError(f"Query execution failed: {str(e)}")

    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """
        Get schema information for a table

        Args:
            table_name: Name of the table

        Returns:
            List of column information dictionaries
        """
        if table_name not in self.registered_tables:
            raise ValueError(f"Table '{table_name}' not found")

        df = self.registered_tables[table_name]

        schema = []
        for col_name in df.columns:
            col_type = df[col_name].dtype
            null_count = df[col_name].null_count()
            unique_count = df[col_name].n_unique()

            schema.append({
                'name': col_name,
                'type': str(col_type),
                'null_count': null_count,
                'unique_count': unique_count
            })

        return schema

    def get_registered_tables(self) -> List[str]:
        """
        Get list of registered table names

        Returns:
            List of table names
        """
        return list(self.registered_tables.keys())

    def validate_query(self, query: str) -> tuple[bool, str]:
        """
        Validate SQL query syntax without executing

        Args:
            query: SQL query string

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            import duckdb
            conn = duckdb.connect(':memory:')

            # Register tables
            for table_name, df in self.registered_tables.items():
                conn.register(table_name, df)

            # Use EXPLAIN to validate without executing
            conn.execute(f"EXPLAIN {query}")
            conn.close()

            return True, ""

        except Exception as e:
            return False, str(e)

    def get_sample_query(self, query_type: str = "select") -> str:
        """
        Get sample SQL queries

        Args:
            query_type: Type of sample query

        Returns:
            Sample SQL query string
        """
        tables = self.get_registered_tables()
        if not tables:
            return "-- Load data first to use SQL queries"

        table_name = tables[0]

        samples = {
            "select": f"-- Select all data\nSELECT * FROM {table_name}\nLIMIT 1000;",
            "filter": f"-- Filter data\nSELECT *\nFROM {table_name}\nWHERE <column_name> = '<value>'\nLIMIT 1000;",
            "aggregate": f"-- Aggregate data\nSELECT \n  <column_name>,\n  COUNT(*) as count,\n  AVG(<numeric_column>) as average\nFROM {table_name}\nGROUP BY <column_name>\nORDER BY count DESC\nLIMIT 100;",
            "join": f"-- Join tables (if multiple loaded)\nSELECT a.*, b.<column_name>\nFROM {table_name} a\nLEFT JOIN <other_table> b\nON a.<id_column> = b.<id_column>\nLIMIT 1000;",
            "order": f"-- Sort data\nSELECT *\nFROM {table_name}\nORDER BY <column_name> <ASC|DESC>\nLIMIT 1000;",
            "calculate": f"-- Calculate new columns\nSELECT \n  *,\n  <column1> + <column2> as calculated_column\nFROM {table_name}\nLIMIT 1000;"
        }

        return samples.get(query_type, samples["select"])

    def export_query_result(
        self,
        query: str,
        file_path: str,
        format: str = "csv"
    ) -> str:
        """
        Execute query and export results

        Args:
            query: SQL query
            file_path: Output file path
            format: Export format (csv, excel, parquet, json)

        Returns:
            Path to exported file
        """
        # Execute query
        result_df = self.execute_query(query)

        # Export
        if format == 'csv':
            result_df.write_csv(file_path)
        elif format in ['xlsx', 'excel']:
            import pandas as pd
            result_df.to_pandas().to_excel(file_path, index=False)
        elif format == 'parquet':
            result_df.write_parquet(file_path)
        elif format == 'json':
            result_df.write_json(file_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

        return file_path
