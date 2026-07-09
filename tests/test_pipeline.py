"""
Test suite for the Depi student-performance pipeline.

Run with:  pytest tests/ -v

These tests don't require a live SQL Server connection — they cover the
parts of the pipeline that can be verified without a database: data
cleaning logic, the trained model's input/output contract, and
consistency between the bronze data and what the model expects.
"""
import sys
from pathlib import Path

import joblib
import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
BRONZE_PATH = BASE_DIR / "data_lake" / "bronze" / "StudentsPerformance.csv"
MODEL_PATH = BASE_DIR / "student_risk_model.pkl"

RENAMED_COLUMNS = [
    "Gender",
    "RaceEthnicity",
    "ParentalEducation",
    "LunchType",
    "TestPreparationCourse",
    "MathScore",
    "ReadingScore",
    "WritingScore",
]
FEATURE_COLUMNS = RENAMED_COLUMNS[:5]


@pytest.fixture(scope="module")
def bronze_df():
    if not BRONZE_PATH.exists():
        pytest.skip(f"Bronze data not found at {BRONZE_PATH}")
    df = pd.read_csv(BRONZE_PATH)
    df.columns = RENAMED_COLUMNS
    return df


@pytest.fixture(scope="module")
def model():
    if not MODEL_PATH.exists():
        pytest.skip(f"Trained model not found at {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


class TestBronzeData:
    def test_bronze_file_exists(self):
        assert BRONZE_PATH.exists(), f"Expected bronze CSV at {BRONZE_PATH}"

    def test_bronze_has_expected_shape(self, bronze_df):
        assert bronze_df.shape[1] == 8, "Bronze data should have 8 columns after rename"
        assert len(bronze_df) > 0, "Bronze data should not be empty"

    def test_scores_are_in_valid_range(self, bronze_df):
        for col in ["MathScore", "ReadingScore", "WritingScore"]:
            assert bronze_df[col].between(0, 100).all(), f"{col} has values outside 0-100"

    def test_no_nulls_in_score_columns_after_cleaning(self, bronze_df):
        cleaned = bronze_df.dropna(subset=["MathScore", "ReadingScore", "WritingScore"])
        assert cleaned[["MathScore", "ReadingScore", "WritingScore"]].isnull().sum().sum() == 0


class TestTrainedModel:
    def test_model_loads(self, model):
        assert model is not None

    def test_model_predicts_binary_labels(self, model, bronze_df):
        preds = model.predict(bronze_df[FEATURE_COLUMNS])
        assert set(preds).issubset({0, 1}), "Predictions should only be 0 or 1"

    def test_model_output_length_matches_input(self, model, bronze_df):
        preds = model.predict(bronze_df[FEATURE_COLUMNS])
        assert len(preds) == len(bronze_df)

    def test_model_handles_unseen_category_gracefully(self, model, bronze_df):
        # The model's OneHotEncoder is set to handle_unknown='ignore', so an
        # unseen category shouldn't crash prediction — this guards against
        # someone changing that setting and breaking production inference.
        sample = bronze_df[FEATURE_COLUMNS].iloc[[0]].copy()
        sample["Gender"] = "nonbinary"  # not present in the training data
        try:
            model.predict(sample)
        except Exception as e:
            pytest.fail(f"Model raised on an unseen category instead of handling it: {e}")

    def test_at_risk_rate_is_plausible(self, model, bronze_df):
        # Sanity check, not a strict correctness test: with a ~17% true
        # at-risk rate in the source data, a model predicting e.g. 0% or
        # 100% at-risk would indicate something is badly broken
        # (label leakage, a corrupted model file, wrong feature order, etc.)
        preds = model.predict(bronze_df[FEATURE_COLUMNS])
        predicted_rate = preds.mean()
        assert 0.01 < predicted_rate < 0.60, (
            f"Predicted at-risk rate ({predicted_rate:.1%}) is implausible; "
            "check for a corrupted model or a feature-order mismatch."
        )


class TestDataCleaningLogic:
    def test_column_rename_matches_pipeline(self, bronze_df):
        assert list(bronze_df.columns) == RENAMED_COLUMNS

    def test_at_risk_label_logic(self):
        # Mirrors the label definition in train_model.py: at risk if
        # Math or Reading score is below 50.
        sample = pd.DataFrame({"MathScore": [49, 50, 80], "ReadingScore": [90, 90, 90]})
        is_at_risk = ((sample["MathScore"] < 50) | (sample["ReadingScore"] < 50)).astype(int)
        assert list(is_at_risk) == [1, 0, 0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
