-- ====================================================================
-- Script: 04_vw_performance_by_education.sql
-- Description: Analytical view joining the Star Schema for quick reporting.
-- ====================================================================

USE StudentPerformanceDB;
GO

CREATE OR ALTER VIEW vw_PerformanceByParentEducation AS
SELECT 
    d.ParentalEducation,
    COUNT(f.StudentID) AS TotalStudents,
    ROUND(AVG(CAST(f.MathScore + f.ReadingScore + f.WritingScore AS FLOAT) / 3.0), 2) AS AverageOverallScore
FROM 
    Fact_StudentScores f
JOIN 
    Dim_Demographics d ON f.DemographicID = d.DemographicID
GROUP BY 
    d.ParentalEducation;
GO