-- ====================================================================
-- Script: 05_migrate_existing_database.sql
-- Description: Migration for databases created BEFORE the lineage
-- columns and unique constraints were added to 01_create_database_and_schema.sql.
-- Safe to re-run (checks for existing objects before altering).
--
-- Run this once against an existing StudentPerformanceDB that predates
-- these changes. Brand new installs don't need this — 01_... already
-- includes everything below.
-- ====================================================================

USE StudentPerformanceDB;
GO

-- Add lineage columns to Fact_StudentScores if they don't already exist
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('Fact_StudentScores') AND name = 'BatchID')
BEGIN
    ALTER TABLE Fact_StudentScores ADD BatchID UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID();
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('Fact_StudentScores') AND name = 'LoadDate')
BEGIN
    ALTER TABLE Fact_StudentScores ADD LoadDate DATETIME2 NOT NULL DEFAULT SYSDATETIME();
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('Fact_StudentScores') AND name = 'SourceFile')
BEGIN
    ALTER TABLE Fact_StudentScores ADD SourceFile VARCHAR(255) NULL;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('Fact_StudentScores') AND name = 'ModelVersion')
BEGIN
    ALTER TABLE Fact_StudentScores ADD ModelVersion VARCHAR(64) NULL;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('Fact_StudentScores') AND name = 'IX_Fact_StudentScores_BatchID')
BEGIN
    CREATE INDEX IX_Fact_StudentScores_BatchID ON Fact_StudentScores(BatchID);
END
GO

-- Add unique constraints to dimension tables if they don't already exist.
-- NOTE: this will FAIL if you already have duplicate/near-duplicate rows
-- (e.g. "Male" and "male ") sitting in these tables from before
-- normalization was added to sp_LoadStarSchema. If it fails, first run:
--   SELECT Gender, RaceEthnicity, ParentalEducation, COUNT(*)
--   FROM Dim_Demographics GROUP BY Gender, RaceEthnicity, ParentalEducation
--   HAVING COUNT(*) > 1;
-- and manually merge/clean duplicates (repoint any Fact_StudentScores rows
-- referencing the duplicate DemographicID before deleting it) before
-- retrying this constraint.
IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_Dim_Demographics')
BEGIN
    ALTER TABLE Dim_Demographics
        ADD CONSTRAINT UQ_Dim_Demographics UNIQUE (Gender, RaceEthnicity, ParentalEducation);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_Dim_Interventions')
BEGIN
    ALTER TABLE Dim_Interventions
        ADD CONSTRAINT UQ_Dim_Interventions UNIQUE (LunchType, TestPreparationCourse);
END
GO
