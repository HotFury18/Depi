-- ====================================================================
-- Script: 03_sp_identify_at_risk_students.sql
-- Description: Batch job procedure to log historical hard-failures.
--
-- USAGE: This is a standalone batch job, not called automatically by
-- medallion_pipeline.py or sp_LoadStarSchema. Run it manually or schedule
-- it independently, e.g. via SQL Server Agent:
--   EXEC sp_IdentifyAtRiskStudents;
-- Typical cadence: after each warehouse refresh, or on its own daily/
-- weekly schedule if you want a running historical log in
-- AtRiskStudentsReport (note it does not dedupe re-runs against the same
-- Fact_StudentScores snapshot, so calling it twice against unchanged data
-- will insert duplicate log rows).
-- ====================================================================

USE StudentPerformanceDB;
GO

CREATE OR ALTER PROCEDURE sp_IdentifyAtRiskStudents
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