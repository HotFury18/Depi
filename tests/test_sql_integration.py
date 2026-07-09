"""
Integration tests for the SQL layer (schema, sp_LoadStarSchema, lineage
columns, and dimension uniqueness constraints).

Unlike test_pipeline.py, these tests need a real, empty SQL Server
instance with the schema already applied (i.e. sql_scripts/01, 02, 03, 04
already run). They are designed to:
  - SKIP automatically if no DB is reachable (so `pytest tests/` still
    works on a laptop with no SQL Server installed)
  - RUN for real in CI, where the workflow spins up a SQL Server
    container and applies the schema before tests run (see
    .github/workflows/ci.yml)

Configure the connection the same way medallion_pipeline.py does:
  STUDENT_DB_SERVER, STUDENT_DB_NAME, STUDENT_DB_DRIVER
"""
import os
import urllib.parse
import uuid

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DB_SERVER = os.environ.get("STUDENT_DB_SERVER", r"(localdb)\MSSQLLocalDB")
DB_NAME = os.environ.get("STUDENT_DB_NAME", "StudentPerformanceDB")
DB_DRIVER = os.environ.get("STUDENT_DB_DRIVER", "ODBC Driver 17 for SQL Server")


def _build_engine():
    connection_string = (
        f"Driver={{{DB_DRIVER}}};"
        f"Server={DB_SERVER};"
        f"Database={DB_NAME};"
        f"Trusted_Connection=yes;"
    )
    # In CI, SQL auth is used instead of Trusted_Connection — allow
    # overriding via a full connection string if provided.
    if os.environ.get("STUDENT_DB_CONNECTION_STRING"):
        connection_string = os.environ["STUDENT_DB_CONNECTION_STRING"]
    params = urllib.parse.quote_plus(connection_string)
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


@pytest.fixture(scope="module")
def engine():
    try:
        eng = _build_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except (SQLAlchemyError, ModuleNotFoundError, Exception) as e:
        pytest.skip(f"No reachable SQL Server instance for integration tests: {e}")


def _stage_sample_rows(engine, n=5):
    """Push a small synthetic staging batch so sp_LoadStarSchema has
    something to load, without depending on the real bronze CSV."""
    df = pd.DataFrame({
        "Gender": ["female"] * n,
        "RaceEthnicity": ["group B"] * n,
        "ParentalEducation": ["bachelor's degree"] * n,
        "LunchType": ["standard"] * n,
        "TestPreparationCourse": ["none"] * n,
        "MathScore": [80] * n,
        "ReadingScore": [80] * n,
        "WritingScore": [80] * n,
        "PredictedRisk": [0] * n,
    })
    df.to_sql("stg_StudentPerformance", con=engine, if_exists="replace", index=False)


class TestSchema:
    def test_expected_tables_exist(self, engine):
        with engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(text(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
                ))
            }
        expected = {"Dim_Demographics", "Dim_Interventions", "Fact_StudentScores", "AtRiskStudentsReport"}
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_fact_table_has_lineage_columns(self, engine):
        with engine.connect() as conn:
            cols = {
                row[0]
                for row in conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Fact_StudentScores'"
                ))
            }
        for expected_col in ("BatchID", "LoadDate", "SourceFile", "ModelVersion"):
            assert expected_col in cols, f"Fact_StudentScores is missing lineage column {expected_col}"

    def test_dimension_unique_constraints_exist(self, engine):
        with engine.connect() as conn:
            constraint_names = {
                row[0] for row in conn.execute(text("SELECT name FROM sys.key_constraints"))
            }
        assert "UQ_Dim_Demographics" in constraint_names
        assert "UQ_Dim_Interventions" in constraint_names


class TestLoadStarSchemaProcedure:
    def test_load_populates_fact_table_with_lineage(self, engine):
        batch_id = str(uuid.uuid4())
        _stage_sample_rows(engine, n=5)

        with engine.begin() as conn:
            conn.execute(
                text(
                    "EXEC sp_LoadStarSchema @BatchID = :batch_id, "
                    "@ModelVersion = :model_version, @SourceFile = :source_file"
                ),
                {"batch_id": batch_id, "model_version": "test-version", "source_file": "test.csv"},
            )

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM Fact_StudentScores WHERE BatchID = :batch_id"),
                {"batch_id": batch_id},
            ).scalar()
        assert row == 5, "Expected exactly 5 rows loaded and tagged with this run's BatchID"

    def test_dimension_dedup_ignores_whitespace(self, engine):
        # Insert the same demographic combo but with extra whitespace, in
        # two separate staged batches, and confirm it doesn't create two
        # dimension rows (this is the TRIM() normalization fix).
        df1 = pd.DataFrame({
            "Gender": ["male"], "RaceEthnicity": ["group A"], "ParentalEducation": ["high school"],
            "LunchType": ["standard"], "TestPreparationCourse": ["none"],
            "MathScore": [70], "ReadingScore": [70], "WritingScore": [70], "PredictedRisk": [0],
        })
        df2 = pd.DataFrame({
            "Gender": ["male  "], "RaceEthnicity": [" group A"], "ParentalEducation": ["high school "],
            "LunchType": ["standard"], "TestPreparationCourse": ["none"],
            "MathScore": [75], "ReadingScore": [75], "WritingScore": [75], "PredictedRisk": [0],
        })

        df1.to_sql("stg_StudentPerformance", con=engine, if_exists="replace", index=False)
        with engine.begin() as conn:
            conn.execute(text("EXEC sp_LoadStarSchema @BatchID = :b"), {"b": str(uuid.uuid4())})

        df2.to_sql("stg_StudentPerformance", con=engine, if_exists="replace", index=False)
        with engine.begin() as conn:
            conn.execute(text("EXEC sp_LoadStarSchema @BatchID = :b"), {"b": str(uuid.uuid4())})

        with engine.connect() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM Dim_Demographics "
                    "WHERE Gender = 'male' AND RaceEthnicity = 'group A' AND ParentalEducation = 'high school'"
                )
            ).scalar()
        assert count == 1, "Whitespace variants of the same demographic combo should not create duplicate rows"
