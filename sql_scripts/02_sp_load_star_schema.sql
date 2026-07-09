-- ====================================================================
-- Script: 02_sp_load_star_schema.sql
-- Description: ELT Procedure that distributes staging data into the Star Schema.
--
-- CHANGE LOG:
--   - Wrapped in an explicit transaction with TRY/CATCH. If the load
--     fails partway through, everything rolls back instead of leaving
--     the fact table truncated and empty.
--   - All text fields are now TRIM()'d before matching/inserting into
--     dimension tables, so "Male" and "Male " (trailing space) are
--     treated as the same value instead of silently becoming two
--     different dimension rows.
--   - Accepts @BatchID, @ModelVersion, @SourceFile parameters so every
--     loaded row can be traced back to the pipeline run and model
--     version that produced it (see Fact_StudentScores lineage columns
--     added in script 01 / migrated in script 05).
-- ====================================================================

USE StudentPerformanceDB;
GO

CREATE OR ALTER PROCEDURE sp_LoadStarSchema
    @BatchID NVARCHAR(64) = NULL,
    @ModelVersion VARCHAR(64) = NULL,
    @SourceFile VARCHAR(255) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- ensures any error automatically rolls back the transaction

    IF @BatchID IS NULL
        SET @BatchID = CONVERT(NVARCHAR(64), NEWID());

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 1. Insert NEW Demographics (Ignore existing), trimmed to avoid
        --    whitespace-only duplicates.
        INSERT INTO Dim_Demographics (Gender, RaceEthnicity, ParentalEducation)
        SELECT DISTINCT
            TRIM(s.Gender), TRIM(s.RaceEthnicity), TRIM(s.ParentalEducation)
        FROM stg_StudentPerformance s
        WHERE NOT EXISTS (
            SELECT 1 FROM Dim_Demographics d
            WHERE d.Gender = TRIM(s.Gender)
              AND d.RaceEthnicity = TRIM(s.RaceEthnicity)
              AND d.ParentalEducation = TRIM(s.ParentalEducation)
        );

        -- 2. Insert NEW Interventions (Ignore existing), trimmed as above.
        INSERT INTO Dim_Interventions (LunchType, TestPreparationCourse)
        SELECT DISTINCT
            TRIM(s.LunchType), TRIM(s.TestPreparationCourse)
        FROM stg_StudentPerformance s
        WHERE NOT EXISTS (
            SELECT 1 FROM Dim_Interventions i
            WHERE i.LunchType = TRIM(s.LunchType)
              AND i.TestPreparationCourse = TRIM(s.TestPreparationCourse)
        );

        -- 3. Wipe and reload Fact table with fresh batch (including ML
        --    predictions and lineage columns). TRUNCATE is transactional
        --    in SQL Server inside an explicit transaction, so if anything
        --    below fails, this rolls back too.
        TRUNCATE TABLE Fact_StudentScores;

        INSERT INTO Fact_StudentScores (
            DemographicID, InterventionID, MathScore, ReadingScore, WritingScore,
            PredictedRisk, BatchID, LoadDate, SourceFile, ModelVersion
        )
        SELECT
            d.DemographicID,
            i.InterventionID,
            s.MathScore,
            s.ReadingScore,
            s.WritingScore,
            s.PredictedRisk,
            @BatchID,
            SYSDATETIME(),
            @SourceFile,
            @ModelVersion
        FROM stg_StudentPerformance s
        JOIN Dim_Demographics d
            ON d.Gender = TRIM(s.Gender)
            AND d.RaceEthnicity = TRIM(s.RaceEthnicity)
            AND d.ParentalEducation = TRIM(s.ParentalEducation)
        JOIN Dim_Interventions i
            ON i.LunchType = TRIM(s.LunchType)
            AND i.TestPreparationCourse = TRIM(s.TestPreparationCourse);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRANSACTION;

        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
        DECLARE @ErrorState INT = ERROR_STATE();

        -- Re-throw so the calling application (e.g. medallion_pipeline.py)
        -- sees the failure instead of silently succeeding with stale data.
        RAISERROR(@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END;
GO
