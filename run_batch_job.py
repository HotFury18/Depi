import pyodbc

# Define the connection string (matching your exact setup)
server_name = r'(localdb)\MSSQLLocalDB' 
database_name = 'StudentPerformanceDB'

conn_str = (
    r'DRIVER={ODBC Driver 17 for SQL Server};'
    f'SERVER={server_name};'
    f'DATABASE={database_name};'
    r'Trusted_Connection=yes;'
)

print("Connecting to database...")
try:
    # Connect and configure it to auto-commit so the execution saves immediately
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()
    
    print("Executing Stored Procedure sp_IdentifyAtRiskStudents...")
    cursor.execute("EXEC sp_IdentifyAtRiskStudents;")
    
    print("Batch job completed successfully!")
    
except Exception as e:
    print("An error occurred during execution:")
    print(e)
finally:
    if 'conn' in locals():
        conn.close()