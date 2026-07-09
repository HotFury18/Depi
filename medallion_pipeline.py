import pandas as pd
from sqlalchemy import create_engine
import urllib
import os
import joblib

# Define file paths
BRONZE_PATH = r'data_lake\bronze\StudentsPerformance.csv'
SILVER_PATH = r'data_lake\silver\Cleaned_StudentsPerformance.parquet'
MODEL_PATH = 'student_risk_model.pkl'

print("--- Starting AI-Enhanced Medallion Pipeline ---")

# ==========================================
# 1. BRONZE TO SILVER (Cleaning, Transformation, & ML Inference)
# ==========================================
print("1. Extracting data from Bronze zone...")
df = pd.read_csv(BRONZE_PATH)

print("2. Transforming data (Renaming columns & handling nulls)...")
df.columns = [
    'Gender', 'RaceEthnicity', 'ParentalEducation', 'LunchType', 
    'TestPreparationCourse', 'MathScore', 'ReadingScore', 'WritingScore'
]
df = df.dropna(subset=['MathScore', 'ReadingScore', 'WritingScore'])

print("3. Executing Machine Learning Predictions...")
# Load the trained model and make predictions on the new data
model = joblib.load(MODEL_PATH)
features = df[['Gender', 'RaceEthnicity', 'ParentalEducation', 'LunchType', 'TestPreparationCourse']]
df['PredictedRisk'] = model.predict(features)

print("4. Loading clean, scored data into Silver zone (as Parquet)...")
df.to_parquet(SILVER_PATH, index=False, engine='pyarrow')

# ==========================================
# 2. SILVER TO GOLD (Database Load)
# ==========================================
print("5. Extracting data from Silver zone...")
clean_df = pd.read_parquet(SILVER_PATH, engine='pyarrow')

print("6. Pushing data to Staging table (SQL Server Database)...")
server_name = r'(localdb)\MSSQLLocalDB' 
database_name = 'StudentPerformanceDB'

connection_string = (
    f"Driver={{ODBC Driver 17 for SQL Server}};"
    f"Server={server_name};"
    f"Database={database_name};"
    f"Trusted_Connection=yes;"
)

params = urllib.parse.quote_plus(connection_string)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

try:
    clean_df.to_sql('stg_StudentPerformance', con=engine, if_exists='replace', index=False)
    print("7. Executing SQL Stored Procedure to distribute data to Star Schema...")
    
    with engine.begin() as conn:
        conn.exec_driver_sql("EXEC sp_LoadStarSchema;")
        
    print("--- Pipeline Success! AI Predictions injected into Data Warehouse. ---")

except Exception as e:
    print("An error occurred during database operations:")
    print(e)