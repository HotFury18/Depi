-- ====================================================================
-- Script: 01_create_database_and_schema.sql
-- Description: Creates the StudentPerformanceDB and the Star Schema tables.
-- ====================================================================

CREATE DATABASE StudentPerformanceDB;
GO

USE StudentPerformanceDB;
GO

-- 1. Create Demographic Dimension
CREATE TABLE Dim_Demographics (
    DemographicID INT IDENTITY(1,1) PRIMARY KEY,
    Gender VARCHAR(50),
    RaceEthnicity VARCHAR(50),
    ParentalEducation VARCHAR(100)
);

-- 2. Create Intervention Dimension
CREATE TABLE Dim_Interventions (
    InterventionID INT IDENTITY(1,1) PRIMARY KEY,
    LunchType VARCHAR(50),
    TestPreparationCourse VARCHAR(50)
);

-- 3. Create Fact Table (Includes ML PredictedRisk column)
CREATE TABLE Fact_StudentScores (
    StudentID INT IDENTITY(1,1) PRIMARY KEY,
    DemographicID INT FOREIGN KEY REFERENCES Dim_Demographics(DemographicID),
    InterventionID INT FOREIGN KEY REFERENCES Dim_Interventions(InterventionID),
    MathScore INT,
    ReadingScore INT,
    WritingScore INT,
    PredictedRisk INT 
);

-- 4. Create Automated Batch Reporting Table
CREATE TABLE AtRiskStudentsReport (
    LogID INT IDENTITY(1,1) PRIMARY KEY,
    LogDate DATETIME,
    StudentID INT,
    MathScore INT,
    ReadingScore INT,
    InterventionNeeded VARCHAR(50)
);
GO