import json
import logging
import os
import sys
import time
import urllib.parse
import uuid
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import create_engine, text

# ------------------------------------------------------------------
# Cross-platform paths (works on Windows, macOS, Linux)
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
BRONZE_PATH = BASE_DIR / "data_lake" / "bronze" / "StudentsPerformance.csv"
BRONZE_ARCHIVE_DIR = BASE_DIR / "data_lake" / "bronze" / "archive"
SILVER_DIR = BASE_DIR / "data_lake" / "silver"
MODEL_PATH = BASE_DIR / "student_risk_model.pkl"
MODEL_METADATA_PATH = BASE_DIR / "student_risk_model.metadata.json"
LOG_DIR = BASE_DIR / "logs"

# ------------------------------------------------------------------
# DB connection is configurable via environment variables instead of
# being hardcoded, so the same script works against any SQL Server
# instance (local dev box, CI runner, cloud VM) without editing code.
# Defaults preserve the original localdb behavior.
# ------------------------------------------------------------------
DB_SERVER = os.environ.get("STUDENT_DB_SERVER", r"(localdb)\MSSQLLocalDB")
DB_NAME = os.environ.get("STUDENT_DB_NAME", "StudentPerformanceDB")
DB_DRIVER = os.environ.get("STUDENT_DB_DRIVER", "ODBC Driver 17 for SQL Server")

# ------------------------------------------------------------------
# Structured logging: replaces bare print() statements with real log
# levels and both console + file output, so a scheduled run (cron, SQL
# Agent, Airflow, etc.) has a persistent record of row counts, timing,
# and failures instead of relying on someone watching stdout live.
# ------------------------------------------------------------------
LOG_DIR.mkdir(parents=True, exist_ok=True)
BATCH_ID = str(uuid.uuid4())
log_file = LOG_DIR / f"pipeline_{date.today().isoformat()}_{BATCH_ID[:8]}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file)],
)
log = logging.getLogger("medallion_pipeline")


def get_model_version() -> str:
    """Read the model version from metadata written by train_model.py, or
    fall back to hashing the pickle directly if metadata is missing (e.g.
    an older model trained before metadata tracking was added)."""
    if MODEL_METADATA_PATH.exists():
        try:
            meta = json.loads(MODEL_METADATA_PATH.read_text())
            return meta.get("model_version", "unknown")
        except (json.JSONDecodeError, OSError):
            log.warning("Could not parse %s; falling back to hashing the model file.", MODEL_METADATA_PATH.name)
    import hashlib
    return hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:12] if MODEL_PATH.exists() else "unknown"


def main() -> int:
    start_time = time.monotonic()
    log.info("--- Starting AI-Enhanced Medallion Pipeline (BatchID=%s) ---", BATCH_ID)

    # ==========================================
    # 1. BRONZE TO SILVER (Cleaning, Transformation, & ML Inference)
    # ==========================================
    log.info("Step 1: Extracting data from Bronze zone...")
    try:
        df = pd.read_csv(BRONZE_PATH)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Could not find bronze data at {BRONZE_PATH}. "
            "Make sure you're running this script from the project root."
        ) from e
    rows_ingested = len(df)
    log.info("  Ingested %d rows from %s", rows_ingested, BRONZE_PATH.name)

    # Archive an immutable, dated snapshot of the raw bronze file. The
    # original design overwrote the same bronze CSV on every run with no
    # history — this preserves what Bronze actually looked like for each
    # batch, so a bad or corrected source file doesn't erase the record of
    # what was originally ingested.
    BRONZE_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = BRONZE_ARCHIVE_DIR / f"{date.today().isoformat()}_{BATCH_ID[:8]}_{BRONZE_PATH.name}"
    archive_path.write_bytes(BRONZE_PATH.read_bytes())
    log.info("  Archived immutable bronze snapshot to %s", archive_path.relative_to(BASE_DIR))

    log.info("Step 2: Transforming data (Renaming columns & handling nulls)...")
    df.columns = [
        "Gender",
        "RaceEthnicity",
        "ParentalEducation",
        "LunchType",
        "TestPreparationCourse",
        "MathScore",
        "ReadingScore",
        "WritingScore",
    ]
    rows_before_dropna = len(df)
    df = df.dropna(subset=["MathScore", "ReadingScore", "WritingScore"])
    rows_dropped = rows_before_dropna - len(df)
    if rows_dropped:
        log.warning("  Dropped %d rows with null scores", rows_dropped)
    else:
        log.info("  No null scores found; 0 rows dropped")

    log.info("Step 3: Executing Machine Learning Predictions...")
    try:
        model = joblib.load(MODEL_PATH)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Could not find trained model at {MODEL_PATH}. "
            "Run train_model.py first to generate student_risk_model.pkl."
        ) from e
    model_version = get_model_version()
    features = df[["Gender", "RaceEthnicity", "ParentalEducation", "LunchType", "TestPreparationCourse"]]
    df["PredictedRisk"] = model.predict(features)
    predicted_at_risk = int(df["PredictedRisk"].sum())
    log.info(
        "  Model version %s predicted %d/%d rows as at-risk (%.1f%%)",
        model_version, predicted_at_risk, len(df), 100 * predicted_at_risk / len(df) if len(df) else 0,
    )

    log.info("Step 4: Loading clean, scored data into Silver zone (as Parquet)...")
    # Partition silver output by load date instead of overwriting a single
    # file every run, so prior runs' cleaned/scored data isn't lost and
    # can be compared or replayed later.
    silver_partition_dir = SILVER_DIR / f"dt={date.today().isoformat()}"
    silver_partition_dir.mkdir(parents=True, exist_ok=True)
    silver_path = silver_partition_dir / f"Cleaned_StudentsPerformance_{BATCH_ID[:8]}.parquet"
    df.to_parquet(silver_path, index=False, engine="pyarrow")
    log.info("  Wrote silver output to %s", silver_path.relative_to(BASE_DIR))

    # ==========================================
    # 2. SILVER TO GOLD (Database Load)
    # ==========================================
    log.info("Step 5: Extracting data from Silver zone...")
    clean_df = pd.read_parquet(silver_path, engine="pyarrow")

    log.info("Step 6: Pushing data to Staging table (SQL Server Database)...")
    connection_string = (
        f"Driver={{{DB_DRIVER}}};"
        f"Server={DB_SERVER};"
        f"Database={DB_NAME};"
        f"Trusted_Connection=yes;"
    )
    # Trusted_Connection (Windows auth) doesn't work in environments like
    # Linux CI containers. STUDENT_DB_CONNECTION_STRING lets those
    # environments supply a full SQL-auth connection string instead,
    # without changing the default (Windows/localdb) behavior for anyone
    # who doesn't set it.
    if os.environ.get("STUDENT_DB_CONNECTION_STRING"):
        connection_string = os.environ["STUDENT_DB_CONNECTION_STRING"]
    params = urllib.parse.quote_plus(connection_string)
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

    clean_df.to_sql("stg_StudentPerformance", con=engine, if_exists="replace", index=False)
    log.info("  Staged %d rows", len(clean_df))

    log.info("Step 7: Executing SQL Stored Procedure to distribute data to Star Schema...")
    with engine.begin() as conn:
        conn.execute(
            text("EXEC sp_LoadStarSchema @BatchID = :batch_id, @ModelVersion = :model_version, @SourceFile = :source_file"),
            {
                "batch_id": BATCH_ID,
                "model_version": model_version,
                "source_file": BRONZE_PATH.name,
            },
        )

    elapsed = time.monotonic() - start_time
    log.info(
        "--- Pipeline Success! BatchID=%s, ModelVersion=%s, %d rows loaded, %.1fs elapsed ---",
        BATCH_ID, model_version, len(clean_df), elapsed,
    )
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception:
        log.exception("Pipeline failed")
        exit_code = 1
    sys.exit(exit_code)
