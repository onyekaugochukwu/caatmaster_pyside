"""
SQL Query Service for CAATmaster
Allows executing SQL queries on Polars DataFrames
"""
import polars as pl
from typing import Optional, Dict, List, Any
import json


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
        self.registered_tables[name] = df

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
