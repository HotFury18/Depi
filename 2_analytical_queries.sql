-- Query 1: Impact of Test Preparation
SELECT 
    TestPreparationCourse,
    COUNT(StudentID) AS TotalStudents,
    ROUND(AVG(CAST(MathScore AS FLOAT)), 2) AS AvgMath,
    ROUND(AVG(CAST(ReadingScore AS FLOAT)), 2) AS AvgReading,
    ROUND(AVG(CAST(WritingScore AS FLOAT)), 2) AS AvgWriting
FROM 
    StudentPerformance
GROUP BY 
    TestPreparationCourse;

-- Query 2: Impact of Parental Education
SELECT 
    ParentalEducation,
    COUNT(StudentID) AS TotalStudents,
    ROUND(AVG(CAST(MathScore + ReadingScore + WritingScore AS FLOAT) / 3.0), 2) AS AverageOverallScore
FROM 
    StudentPerformance
GROUP BY 
    ParentalEducation
ORDER BY 
    AverageOverallScore DESC;

-- View Generation for Power BI Dashboard
CREATE VIEW vw_PerformanceByParentEducation AS
SELECT 
    ParentalEducation,
    COUNT(StudentID) AS TotalStudents,
    ROUND(AVG(CAST(MathScore + ReadingScore + WritingScore AS FLOAT) / 3.0), 2) AS AverageOverallScore
FROM 
    StudentPerformance
GROUP BY 
    ParentalEducation;