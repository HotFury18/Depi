-- ====================================================================
-- Script: 01_create_database_and_schema.sql
-- Description: Creates the StudentPerformanceDB and the Star Schema tables.
--
-- CHANGE LOG:
--   - Added UNIQUE constraints on both dimension tables. Previously,
--     de-duplication was enforced only in application logic (a
--     WHERE NOT EXISTS check inside sp_LoadStarSchema). That's fine for a
--     single writer, but gives no protection against a race condition if
--     two loads ever ran concurrently, and nothing stopped "Male" and
--     "male " (trailing space) from becoming two different dimension rows.
--     The unique constraint is now the real backstop; sp_LoadStarSchema
--     also TRIMs incoming text before insert/match (see script 02).
--   - Added lineage columns to Fact_StudentScores (BatchID, LoadDate,
--     SourceFile, ModelVersion) so each row can be traced back to the
--     pipeline run and model version that produced it. Previously there
--     was no way to answer "which run loaded this row" or "which model
--     produced this PredictedRisk value" once multiple runs/model
--     versions existed.
-- ====================================================================

CREATE DATABASE StudentPerformanceDB;
GO

USE StudentPerformanceDB;
GO

-- 1. Create Demographic Dimension
CREATE TABLE Dim_Demographics (
    DemographicID INT IDENTITY(1,1) PRIMARY KEY,
    Gender VARCHAR(50) NOT NULL,
    RaceEthnicity VARCHAR(50) NOT NULL,
    ParentalEducation VARCHAR(100) NOT NULL,
    CONSTRAINT UQ_Dim_Demographics UNIQUE (Gender, RaceEthnicity, ParentalEducation)
);

-- 2. Create Intervention Dimension
CREATE TABLE Dim_Interventions (
    InterventionID INT IDENTITY(1,1) PRIMARY KEY,
    LunchType VARCHAR(50) NOT NULL,
    TestPreparationCourse VARCHAR(50) NOT NULL,
    CONSTRAINT UQ_Dim_Interventions UNIQUE (LunchType, TestPreparationCourse)
);

-- 3. Create Fact Table (Includes ML PredictedRisk column + lineage columns)
CREATE TABLE Fact_StudentScores (
    StudentID INT IDENTITY(1,1) PRIMARY KEY,
    DemographicID INT FOREIGN KEY REFERENCES Dim_Demographics(DemographicID),
    InterventionID INT FOREIGN KEY REFERENCES Dim_Interventions(InterventionID),
    MathScore INT,
    ReadingScore INT,
    WritingScore INT,
    PredictedRisk INT,
    -- Lineage / auditability columns:
    BatchID UNIQUEIDENTIFIER NOT NULL,        -- identifies which pipeline run loaded this row
    LoadDate DATETIME2 NOT NULL DEFAULT SYSDATETIME(), -- when this row was loaded
    SourceFile VARCHAR(255) NULL,             -- which bronze file produced this row
    ModelVersion VARCHAR(64) NULL             -- which model version produced PredictedRisk
);

-- Helpful for lineage lookups ("show me everything from batch X")
CREATE INDEX IX_Fact_StudentScores_BatchID ON Fact_StudentScores(BatchID);

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
