# Student Performance Predictive Analytics & Data Pipeline

**Author:** Hossam Eldin Mahmoud Ali  
**Program:** Digital Egypt Pioneers Initiative (DEPI) | AI & Data Science - Microsoft Data Engineer Track

## 📌 Project Overview
This project is an end-to-end, enterprise-grade data engineering pipeline that extracts raw student performance data, predicts at-risk students using Machine Learning, and loads the transformed data into a highly optimized Star Schema Data Warehouse. The pipeline is visualized in real-time using a Power BI DirectQuery dashboard.

## 🏗️ Architecture & Workflow
The pipeline implements a **Medallion Architecture (Data Lake)** and an automated **ELT workflow**:

1. **Bronze Layer (Raw Data):** Ingests raw CSV data containing student demographics, intervention metrics, and test scores.
2. **Silver Layer (Cleaned & Scored):** Uses `pandas` to clean data and handle nulls. A trained `scikit-learn` Random Forest Classifier evaluates the data to predict which students are at risk of failing (scoring below 50). The cleaned, scored data is converted to Parquet format for optimized storage.
3. **Gold Layer (Data Warehouse):** Data is uploaded to a SQL Server staging table. An automated Stored Procedure distributes the data into a **Star Schema** consisting of:
   - `Dim_Demographics`
   - `Dim_Interventions`
   - `Fact_StudentScores`
4. **Analytics & BI:** A Power BI dashboard connected via DirectQuery provides live, real-time insights into student performance and ML-driven risk predictions.

## 🛠️ Tech Stack
* **Languages:** Python, SQL, DAX
* **Data Engineering:** pandas, pyarrow, SQLAlchemy, pyodbc
* **Machine Learning:** scikit-learn, joblib (Random Forest Classifier)
* **Database Management:** SQL Server (localdb)
* **Business Intelligence:** Power BI (DirectQuery Mode)

## 📁 Repository Structure
* `/data_lake/` - Contains the `bronze` (CSV) and `silver` (Parquet) storage zones.
* `/sql_scripts/` - Contains the DDL and DML scripts for the Star Schema and Stored Procedures.
* `medallion_pipeline.py` - The master Python ELT script that orchestrates the pipeline.
* `train_model.py` - The script used to train the Random Forest classification model.
* `student_risk_model.pkl` - The serialized Machine Learning model.
* `StudentPerformance_Dashboard.pbix` - The Power BI dashboard.