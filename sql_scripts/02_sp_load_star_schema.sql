-- ====================================================================
-- Script: 02_sp_load_star_schema.sql
-- Description: ELT Procedure that distributes staging data into the Star Schema.
-- ====================================================================

USE StudentPerformanceDB;
GO

CREATE PROCEDURE sp_LoadStarSchema
AS
BEGIN
    SET NOCOUNT ON;

    -- 1. Insert NEW Demographics (Ignore existing)
    INSERT INTO Dim_Demographics (Gender, RaceEthnicity, ParentalEducation)
    SELECT DISTINCT s.Gender, s.RaceEthnicity, s.ParentalEducation
    FROM stg_StudentPerformance s
    WHERE NOT EXISTS (
        SELECT 1 FROM Dim_Demographics d
        WHERE d.Gender = s.Gender 
          AND d.RaceEthnicity = s.RaceEthnicity 
          AND d.ParentalEducation = s.ParentalEducation
    );

    -- 2. Insert NEW Interventions (Ignore existing)
    INSERT INTO Dim_Interventions (LunchType, TestPreparationCourse)
    SELECT DISTINCT s.LunchType, s.TestPreparationCourse
    FROM stg_StudentPerformance s
    WHERE NOT EXISTS (
        SELECT 1 FROM Dim_Interventions i
        WHERE i.LunchType = s.LunchType 
          AND i.TestPreparationCourse = s.TestPreparationCourse
    );

    -- 3. Wipe and reload Fact table with fresh batch (including ML predictions)
    TRUNCATE TABLE Fact_StudentScores;

    INSERT INTO Fact_StudentScores (DemographicID, InterventionID, MathScore, ReadingScore, WritingScore, PredictedRisk)
    SELECT 
        d.DemographicID,
        i.InterventionID,
        s.MathScore,
        s.ReadingScore,
        s.WritingScore,
        s.PredictedRisk 
    FROM stg_StudentPerformance s
    JOIN Dim_Demographics d 
        ON s.Gender = d.Gender 
        AND s.RaceEthnicity = d.RaceEthnicity 
        AND s.ParentalEducation = d.ParentalEducation
    JOIN Dim_Interventions i 
        ON s.LunchType = i.LunchType 
        AND s.TestPreparationCourse = i.TestPreparationCourse;
END;
GO