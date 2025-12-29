"""
Export Service for CAATmaster
Handles data export in various formats
"""
import polars as pl
from pathlib import Path
from typing import Optional
import datetime


class ExportService:
    """Service for exporting data in various formats"""

    def export_dataframe(
        self,
        df: pl.DataFrame,
        file_path: str,
        format: str = None,
        include_index: bool = False
    ) -> str:
        """
        Export a dataframe to a file

        Args:
            df: Polars DataFrame to export
            file_path: Output file path
            format: Export format (csv, excel, parquet, json)
            include_index: Whether to include row index

        Returns:
            Path to exported file
        """
        file_path = Path(file_path)

        # Auto-detect format from extension if not specified
        if format is None:
            format = file_path.suffix.lstrip('.').lower()

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Export based on format
        if format == 'csv':
            df.write_csv(str(file_path), include_header=True)
        elif format in ['xlsx', 'excel', 'xls']:
            # Use pandas for Excel export
            import pandas as pd
            df_pandas = df.to_pandas()
            df_pandas.to_excel(str(file_path), index=include_index)
        elif format == 'parquet':
            df.write_parquet(str(file_path))
        elif format == 'json':
            df.write_json(str(file_path))
        else:
            raise ValueError(f"Unsupported export format: {format}")

        return str(file_path)

    def export_summary(
        self,
        df: pl.DataFrame,
        file_path: str,
        title: str = "Data Summary"
    ):
        """
        Export a summary report with statistics and visualizations

        Args:
            df: Polars DataFrame
            file_path: Output file path
            title: Report title
        """
        # Create HTML report
        html = self._create_html_summary(df, title)

        # Save as HTML
        if not file_path.endswith('.html'):
            file_path += '.html'

        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return file_path

    def _create_html_summary(self, df: pl.DataFrame, title: str) -> str:
        """Create an HTML summary report"""
        rows = len(df)
        cols = len(df.columns)
        memory_mb = df.estimated_size('mb')

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: #f8f8f8; padding: 15px; border-radius: 6px; border-left: 4px solid #0078d4; }}
        .stat-card h3 {{ margin: 0 0 10px 0; font-size: 14px; color: #666; }}
        .stat-card .value {{ font-size: 24px; font-weight: bold; color: #0078d4; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }}
        th {{ background: #f8f8f8; font-weight: 600; }}
        tr:hover {{ background: #f9f9f9; }}
        .timestamp {{ color: #999; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>

        <div class="stats">
            <div class="stat-card">
                <h3>Total Rows</h3>
                <div class="value">{rows:,}</div>
            </div>
            <div class="stat-card">
                <h3>Total Columns</h3>
                <div class="value">{cols}</div>
            </div>
            <div class="stat-card">
                <h3>Memory Size</h3>
                <div class="value">{memory_mb:.2f} MB</div>
            </div>
            <div class="stat-card">
                <h3>Export Date</h3>
                <div class="value" style="font-size: 16px;">{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
            </div>
        </div>

        <h2>Column Information</h2>
        <table>
            <thead>
                <tr>
                    <th>Column Name</th>
                    <th>Data Type</th>
                    <th>Null Count</th>
                    <th>Unique Values</th>
                </tr>
            </thead>
            <tbody>
"""

        # Add column information
        for col in df.columns:
            col_type = df[col].dtype
            null_count = df[col].null_count()
            unique_count = df[col].n_unique()

            html += f"""
                <tr>
                    <td>{col}</td>
                    <td>{col_type}</td>
                    <td>{null_count:,}</td>
                    <td>{unique_count:,}</td>
                </tr>
"""

        html += f"""
            </tbody>
        </table>

        <div class="timestamp">
            Generated by CAATmaster - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""

        return html

    def export_filtered_data(
        self,
        df: pl.DataFrame,
        file_path: str,
        filters: dict = None
    ):
        """
        Export filtered data

        Args:
            df: Source DataFrame
            file_path: Output file path
            filters: Dictionary of filters to apply before export
        """
        if filters:
            from core.data_processor import LegacyDataProcessor
            processor = LegacyDataProcessor()
            df = processor.filter_data(df, filters)

        return self.export_dataframe(df, file_path)

    def create_export_package(
        self,
        df: pl.DataFrame,
        base_path: str,
        package_name: str,
        include_summary: bool = True,
        formats: list = None
    ):
        """
        Create a complete export package with data and summary

        Args:
            df: DataFrame to export
            base_path: Base directory for exports
            package_name: Name of the export package
            include_summary: Whether to include HTML summary
            formats: List of formats to export (csv, parquet, excel)
        """
        if formats is None:
            formats = ['csv', 'parquet']

        # Create package directory
        package_dir = Path(base_path) / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        exported_files = []

        # Export data in each format
        for fmt in formats:
            file_path = package_dir / f"data.{fmt}"
            try:
                result_path = self.export_dataframe(df, str(file_path), fmt)
                exported_files.append(result_path)
            except Exception as e:
                print(f"Warning: Failed to export {fmt}: {e}")

        # Export summary
        if include_summary:
            summary_path = package_dir / "summary.html"
            self.export_summary(df, str(summary_path), f"{package_name} Summary")
            exported_files.append(str(summary_path))

        return str(package_dir), exported_files
