-- ====================================================================
-- Script: 06_enable_read_committed_snapshot.sql
-- Description: Reduces blocking between pipeline loads and Power BI
-- DirectQuery readers.
--
-- WHY THIS MATTERS: Power BI in DirectQuery mode queries
-- Fact_StudentScores live. sp_LoadStarSchema truncates and reloads that
-- table inside a single transaction (by design, for atomicity — see
-- script 02). Under SQL Server's default READ COMMITTED isolation,
-- readers can block waiting for that transaction to finish, so anyone
-- with the dashboard open during a pipeline run may see the dashboard
-- hang or time out.
--
-- READ_COMMITTED_SNAPSHOT makes readers see the last-committed version
-- of the data instead of blocking on the writer's lock — DirectQuery
-- users keep seeing the pre-load snapshot until the load commits, then
-- instantly see the new data, with no blocking either way.
--
-- REQUIREMENT: ALTER DATABASE ... SET READ_COMMITTED_SNAPSHOT requires
-- no other active connections to the database at the moment it runs.
-- Run this during a maintenance window, or expect it to hang waiting for
-- other sessions to disconnect (SQL Server will wait, not error, but it
-- can appear to hang if the dashboard or another session is connected).
-- ====================================================================

ALTER DATABASE StudentPerformanceDB
SET READ_COMMITTED_SNAPSHOT ON;
GO
