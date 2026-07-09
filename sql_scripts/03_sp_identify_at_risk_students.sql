-- ====================================================================
-- Script: 03_sp_identify_at_risk_students.sql
-- Description: Batch job procedure to log historical hard-failures.
-- ====================================================================

USE StudentPerformanceDB;
GO

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
        Fact_StudentScores
    WHERE 
        MathScore < 50 OR ReadingScore < 50;
END;
GO