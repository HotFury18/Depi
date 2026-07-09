import pandas as pd
from sqlalchemy import create_engine
import urllib

# 1. Read the CSV file
print("Loading CSV...")
df = pd.read_csv('StudentsPerformance.csv')

# --- NEW STEP: Rename DataFrame columns to match SQL table ---
df.columns = [
    'Gender', 
    'RaceEthnicity', 
    'ParentalEducation', 
    'LunchType', 
    'TestPreparationCourse', 
    'MathScore', 
    'ReadingScore', 
    'WritingScore'
]

# 2. Define your connection parameters
server_name = r'(localdb)\MSSQLLocalDB' 
database_name = 'StudentPerformanceDB'

connection_string = (
    f"Driver={{ODBC Driver 17 for SQL Server}};"
    f"Server={server_name};"
    f"Database={database_name};"
    f"Trusted_Connection=yes;"
)

# Parse the connection string for SQLAlchemy
params = urllib.parse.quote_plus(connection_string)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# 3. Push the data to SQL Server
print("Pushing data to SQL Server...")
try:
    df.to_sql('StudentPerformance', con=engine, if_exists='append', index=False)
    print("Success! Data loaded into StudentPerformanceDB.")
except Exception as e:
    print("An error occurred:")
    print(e)