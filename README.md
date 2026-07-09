# Project 6: Educational Performance Data Pipeline

## 📌 Project Overview
An automated, end-to-end data engineering pipeline built to analyze factors influencing student performance. The system extracts raw CSV data, transforms and loads it into a relational database, and automates a nightly batch job to flag at-risk students for intervention.

## 🏗️ Architecture & Tech Stack
* **Extraction & Transformation:** Python (`pandas`)
* **Database & Storage:** SQL Server (`(localdb)\MSSQLLocalDB`)
* **Analytical Engine:** SQL (CTEs, Views, Stored Procedures)
* **Orchestration / Automation:** Windows Task Scheduler executing Python (`pyodbc`)
* **Visualization:** Power BI (DirectQuery Mode)

## 🚀 Pipeline Milestones
### 1. Data Loading & Preprocessing
* Created a normalized destination table `StudentPerformance`.
* Developed a Python ETL script to map messy CSV headers to clean SQL schemas and load the data using `sqlalchemy`.

### 2. Analytical System Development
* Designed SQL queries to test hypotheses regarding Test Preparation and Parental Education.
* Abstracted complex analytical logic into a SQL `VIEW` (`vw_PerformanceByParentEducation`) for downstream reporting.

### 3. Deployment & Batch Processing
* Created a dedicated tracking table `AtRiskStudentsReport`.
* Built a Stored Procedure (`sp_IdentifyAtRiskStudents`) to identify students scoring below 50 in Math or Reading and log them with a dynamic `GETDATE()` timestamp.

### 4. Pipeline Automation
* Configured a headless Python execution script.
* Orchestrated a nightly trigger to automate the Stored Procedure execution without manual intervention.

## 📊 Key Business Insights
* **Test Preparation:** Students who completed the preparation course showed a statistically significant increase across all testing categories.
* **Parental Education:** There is a direct correlation between advanced degrees and higher average overall scores.