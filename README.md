# Student Performance Predictive Analytics & Data Pipeline

**Author:** Hossam Eldin Mahmoud Ali  
**Program:** Digital Egypt Pioneers Initiative (DEPI) | AI & Data Science - Microsoft Data Engineer Track

## 📌 Project Overview
This project is an end-to-end, enterprise-grade data engineering pipeline that extracts raw student performance data, predicts at-risk students using Machine Learning, and loads the transformed data into a highly optimized Star Schema Data Warehouse. The pipeline is visualized in real-time using a Power BI DirectQuery dashboard.

## 🏗️ Architecture & Workflow
The pipeline implements a **Medallion Architecture (Data Lake)** and an automated **ELT workflow**:

1. **Bronze Layer (Raw Data):** Ingests raw CSV data containing student demographics, intervention metrics, and test scores. Each pipeline run also archives an immutable, dated snapshot of the source file (`data_lake/bronze/archive/`) so historical raw data isn't overwritten.
2. **Silver Layer (Cleaned & Scored):** Uses `pandas` to clean data and handle nulls. A trained `scikit-learn` Random Forest Classifier evaluates the data to predict which students are at risk of failing (scoring below 50, see the model performance note below). The cleaned, scored data is written to Parquet, partitioned by load date (`data_lake/silver/dt=YYYY-MM-DD/`), so prior runs' output isn't lost.
3. **Gold Layer (Data Warehouse):** Data is uploaded to a SQL Server staging table. An automated, transactional Stored Procedure distributes the data into a **Star Schema** consisting of:
   - `Dim_Demographics`, `Dim_Interventions` — deduplicated via a unique constraint, with incoming text trimmed of whitespace before matching
   - `Fact_StudentScores` — includes lineage columns (`BatchID`, `LoadDate`, `SourceFile`, `ModelVersion`) so every row can be traced back to the exact pipeline run and model version that produced it
4. **Analytics & BI:** A Power BI dashboard connected via DirectQuery provides live, real-time insights into student performance and ML-driven risk predictions. `READ_COMMITTED_SNAPSHOT` isolation (script 06) prevents the load transaction from blocking DirectQuery readers.

## 🛠️ Tech Stack
* **Languages:** Python, SQL, DAX
* **Data Engineering:** pandas, pyarrow, SQLAlchemy, pyodbc
* **Machine Learning:** scikit-learn, joblib (Random Forest Classifier)
* **Database Management:** SQL Server (localdb, or any SQL Server instance via env vars)
* **Business Intelligence:** Power BI (DirectQuery Mode)
* **Testing/CI:** pytest, GitHub Actions (unit tests on every push; SQL integration tests against a containerized SQL Server)

## 📁 Repository Structure
* `/data_lake/bronze/` - Raw CSV input, plus an `archive/` subfolder of immutable dated snapshots created by each pipeline run.
* `/data_lake/silver/` - Cleaned, ML-scored Parquet output, partitioned by load date (`dt=YYYY-MM-DD/`).
* `/sql_scripts/` - DDL/DML scripts for the Star Schema, stored procedures, the view, a migration script for pre-existing databases, and the read-committed-snapshot isolation fix. Run in numerical order.
* `/tests/` - `test_pipeline.py` (no DB required) and `test_sql_integration.py` (requires a live SQL Server; auto-skips otherwise).
* `/.github/workflows/ci.yml` - CI: unit tests on every push, plus a full integration run against a containerized SQL Server.
* `medallion_pipeline.py` - The master Python ELT script; structured logging to console + `logs/`, generates a `BatchID` per run, and passes lineage info into the warehouse.
* `train_model.py` - Trains the Random Forest classifier with a held-out evaluation, and writes `student_risk_model.metadata.json` (model version hash, metrics, training timestamp).
* `student_risk_model.pkl` / `student_risk_model.metadata.json` - The serialized model and its version metadata.
* `StudentPerformance_Dashboard.pbix` - The Power BI dashboard.

## 🚀 How to Run the Project from Scratch

**1. Setup Environment**
* Clone the repository.
* Run `pip install -r requirements.txt` to install all dependencies (or `pip install -r requirements-dev.txt` if you also want to run the test suite).

**2. Setup the Data Warehouse**
* Ensure you have a local SQL Server instance running (default script uses `(localdb)\MSSQLLocalDB`).
* Execute `sql_scripts/01` through `04` in numerical order to create the database, Star Schema, and stored procedures.
* If you're migrating a database created *before* these changes (no lineage columns/unique constraints), run `sql_scripts/05_migrate_existing_database.sql` instead of re-running `01`.
* Optionally run `sql_scripts/06_enable_read_committed_snapshot.sql` to prevent the pipeline's load transaction from blocking a live Power BI DirectQuery session.
* Connection settings are configurable via environment variables (`STUDENT_DB_SERVER`, `STUDENT_DB_NAME`, `STUDENT_DB_DRIVER`, or a full `STUDENT_DB_CONNECTION_STRING` for non-Windows-auth setups) — see `.env.example`. If unset, defaults match the localdb setup above.

**3. Train the Model (optional — a trained model is already committed)**
* Run `train_model.py` to retrain `student_risk_model.pkl` from the bronze data. This prints a held-out evaluation (confusion matrix, precision/recall/F1, ROC-AUC) and writes `student_risk_model.metadata.json` with a content-hash version ID, so every future prediction can be traced back to exactly this model.
* Model performance note: the model predicts risk from demographic/intervention fields only (no scores), by design, so it can flag students before scores exist. On held-out data this currently achieves ROC-AUC ≈ 0.72, ~61% recall and ~27% precision on the at-risk class — tuned to favor catching more at-risk students at the cost of more false positives. Treat it as an early-warning triage signal, not a high-precision classifier.
* **Note on WritingScore:** the "at risk" label is currently defined from `MathScore` and `ReadingScore` only — `WritingScore` is tracked throughout the pipeline but doesn't factor into risk. This is flagged with a comment in `train_model.py` as a decision that may need stakeholder input, not silently changed.

**4. Execute the Pipeline**
* Run `medallion_pipeline.py`. This will clean the raw CSV, generate ML predictions, upload to the staging table, and trigger the SQL Stored Procedure to populate the Data Warehouse.
* `sp_LoadStarSchema` runs inside an explicit transaction — if anything fails mid-load, the warehouse rolls back to its previous state instead of being left half-loaded.
* Each run logs to both the console and a timestamped file under `logs/` — row counts ingested, dropped, and predicted-at-risk, plus total elapsed time. A failed run exits with a non-zero status code (previously it could print an error but still exit successfully, which would let an automated scheduler think the run succeeded).

**5. (Optional) Run the historical at-risk batch job**
* `sp_IdentifyAtRiskStudents` is a separate, standalone batch job — it is *not* called automatically by the pipeline. Run it manually or on its own schedule (e.g. SQL Server Agent) after a warehouse refresh: `EXEC sp_IdentifyAtRiskStudents;`. It logs students whose actual scores (not the ML prediction) fell below 50 into `AtRiskStudentsReport`. Note it doesn't dedupe re-runs against an unchanged snapshot.

**6. View the Analytics**
* Open `StudentPerformance_Dashboard.pbix` in Power BI.
* If prompted, update the Data Source settings to point to your local SQL Server instance.

## ✅ Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

`test_pipeline.py` covers data cleaning logic and the trained model's input/output contract — no database required. `test_sql_integration.py` exercises the actual schema and `sp_LoadStarSchema` (lineage columns, unique-constraint dedup) against a live SQL Server, and auto-skips if none is reachable. CI (`.github/workflows/ci.yml`) runs both: the fast suite on every push, and the full integration suite against a containerized SQL Server.

## 📝 Known Limitations

* The ML model's ceiling is capped by its inputs — it only uses 5 categorical demographic/intervention fields, so precision on the at-risk class is inherently limited (see performance note above).
* `Fact_StudentScores` is fully truncated and reloaded on every pipeline run rather than loaded incrementally; the new `BatchID`/`LoadDate` lineage columns make each load traceable, but the table itself still only reflects the most recent batch, not full history.
* There's no natural student identifier in the source data — `StudentID` is a surrogate key regenerated each run, so this is a snapshot-reporting tool rather than a true longitudinal per-student tracking system.
* The pipeline assumes a single-batch CSV load; it doesn't yet support incremental/streaming ingestion.