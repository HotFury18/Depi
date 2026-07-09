CREATE TABLE StudentPerformance (
    StudentID INT IDENTITY(1,1) PRIMARY KEY,
    Gender VARCHAR(50),
    RaceEthnicity VARCHAR(50),
    ParentalEducation VARCHAR(100),
    LunchType VARCHAR(50),
    TestPreparationCourse VARCHAR(50),
    MathScore INT,
    ReadingScore INT,
    WritingScore INT
);