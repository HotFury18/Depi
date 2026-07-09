-- Destination table for batch job
CREATE TABLE AtRiskStudentsReport (
    LogID INT IDENTITY(1,1) PRIMARY KEY,
    LogDate DATETIME,
    StudentID INT,
    MathScore INT,
    ReadingScore INT,
    InterventionNeeded VARCHAR(50)
);
GO

-- Stored Procedure for automation
CREATE PROCEDURE sp_IdentifyAtRiskStudents
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO AtRiskStudentsReport (LogDate, StudentID, MathScore, ReadingScore, InterventionNeeded)
    SELECT 
        GETDATE(),
        StudentID,
        MathScore,
        ReadingScore,
        'Math/Reading Support Required'
    FROM 
        StudentPerformance
    WHERE 
        MathScore < 50 OR ReadingScore < 50;
END;