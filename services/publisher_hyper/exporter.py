import os
from pathlib import Path

import psycopg2


def export_tables_to_hyper(
    database_url: str,
    output_dir: str = "artifacts",
    hyper_filename: str = "jobs_ranked.hyper",
) -> str:
    """
    Export marts tables to a Tableau .hyper file.

    Notes:
    - Imports tableauhyperapi lazily at runtime to avoid CI dependency unless executed.
    - Creates output directory if it doesn't exist.

    Returns the path to the created .hyper file.
    """
    try:
        from tableauhyperapi import (
            Connection,
            CreateMode,
            HyperProcess,
            SqlType,
            TableDefinition,
            TableName,
            Telemetry,
        )
    except Exception as err:  # pragma: no cover
        raise RuntimeError(
            "tableauhyperapi is required to export .hyper files. Install with `pip install tableauhyperapi`."
        ) from err

    os.makedirs(output_dir, exist_ok=True)
    hyper_path = str(Path(output_dir) / hyper_filename)

    # Pull data
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM marts.fact_jobs ORDER BY job_id LIMIT 100000")
            fact_rows = cur.fetchall()
            fact_cols = [d.name for d in cur.description]

            cur.execute("SELECT * FROM marts.dim_companies ORDER BY company_id LIMIT 100000")
            dim_rows = cur.fetchall()
            dim_cols = [d.name for d in cur.description]

    def _infer_sqltype(value) -> "SqlType":
        if isinstance(value, (int, float)):
            return SqlType.double()
        return SqlType.text()

    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(endpoint=hyper.endpoint, database=hyper_path, create_mode=CreateMode.CREATE_AND_REPLACE) as connection:
            fact_name = TableName("Extract", "fact_jobs")
            dim_name = TableName("Extract", "dim_companies")

            # Define tables
            fact_def = TableDefinition(fact_name)
            dim_def = TableDefinition(dim_name)

            if fact_rows:
                for i, col in enumerate(fact_cols):
                    fact_def.add_column(TableDefinition.Column(col, _infer_sqltype(fact_rows[0][i] if i < len(fact_rows[0]) else None)))
            else:
                for col in fact_cols:
                    fact_def.add_column(TableDefinition.Column(col, SqlType.text()))

            if dim_rows:
                for i, col in enumerate(dim_cols):
                    dim_def.add_column(TableDefinition.Column(col, _infer_sqltype(dim_rows[0][i] if i < len(dim_rows[0]) else None)))
            else:
                for col in dim_cols:
                    dim_def.add_column(TableDefinition.Column(col, SqlType.text()))

            connection.catalog.create_table_if_not_exists(fact_def)
            connection.catalog.create_table_if_not_exists(dim_def)

            if fact_rows:
                connection.insert_into_table(fact_name, fact_rows)
            if dim_rows:
                connection.insert_into_table(dim_name, dim_rows)

    return hyper_path


def export_from_env(output_dir: str = "artifacts", hyper_filename: str = "jobs_ranked.hyper") -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set")
    return export_tables_to_hyper(database_url, output_dir, hyper_filename)


