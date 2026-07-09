from pathlib import Path

import hashlib
import json
from datetime import datetime, timezone

import joblib
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# ------------------------------------------------------------------
# Cross-platform paths (works on Windows, macOS, Linux)
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
BRONZE_PATH = BASE_DIR / "data_lake" / "bronze" / "StudentsPerformance.csv"
MODEL_PATH = BASE_DIR / "student_risk_model.pkl"
MODEL_METADATA_PATH = BASE_DIR / "student_risk_model.metadata.json"

CATEGORICAL_FEATURES = [
    "Gender",
    "RaceEthnicity",
    "ParentalEducation",
    "LunchType",
    "TestPreparationCourse",
]

print("1. Loading historical data for training...")
try:
    df = pd.read_csv(BRONZE_PATH)
except FileNotFoundError as e:
    raise FileNotFoundError(
        f"Could not find bronze data at {BRONZE_PATH}. "
        "Make sure you're running this script from the project root, "
        "or that data_lake/bronze/StudentsPerformance.csv exists."
    ) from e

expected_cols = 8
if df.shape[1] != expected_cols:
    raise ValueError(
        f"Expected {expected_cols} columns in {BRONZE_PATH.name}, found {df.shape[1]}. "
        "The source CSV's schema may have changed."
    )

df.columns = [
    "Gender",
    "RaceEthnicity",
    "ParentalEducation",
    "LunchType",
    "TestPreparationCourse",
    "MathScore",
    "ReadingScore",
    "WritingScore",
]

print("2. Defining the 'At-Risk' logic...")
# ------------------------------------------------------------------
# DESIGN DECISION — flagged, not silently changed:
# "At risk" is defined using only MathScore and ReadingScore.
# WritingScore is loaded and stored throughout the pipeline (bronze,
# silver, and the Fact_StudentScores warehouse table all carry it) but
# does NOT factor into this label or into the model's features anywhere.
# This may be intentional (e.g. math/reading are treated as the
# foundational risk indicators, writing is tracked for reporting only)
# or it may be an oversight in the original design. I'm not changing this
# without a product/stakeholder decision, since redefining "at risk" would
# retroactively change what every existing PredictedRisk value means.
# If writing performance SHOULD count toward risk, update the line below
# to: (df["MathScore"] < 50) | (df["ReadingScore"] < 50) | (df["WritingScore"] < 50)
# and retrain — note this will also change the class balance and the
# evaluation numbers reported below.
# ------------------------------------------------------------------
# 1 means At-Risk (scored below 50), 0 means Safe
df["Is_At_Risk"] = ((df["MathScore"] < 50) | (df["ReadingScore"] < 50)).astype(int)

X = df[CATEGORICAL_FEATURES]
y = df["Is_At_Risk"]

print(f"   Class balance -> Not at risk: {(y == 0).sum()}, At risk: {(y == 1).sum()} "
      f"({y.mean():.1%} at-risk rate)")

# ------------------------------------------------------------------
# Train/test split — stratified so both classes are represented
# proportionally in train and test (important given ~17% positive rate)
# ------------------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print("3. Building and training the Random Forest Model...")
preprocessor = ColumnTransformer(
    transformers=[("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)]
)

# class_weight='balanced' compensates for the ~5:1 class imbalance by
# up-weighting the minority (at-risk) class during training, instead of
# letting the model default to always predicting "not at risk".
clf = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            RandomForestClassifier(
                n_estimators=300,
                max_depth=6,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=42,
            ),
        ),
    ]
)

clf.fit(X_train, y_train)

# ------------------------------------------------------------------
# Evaluation on the held-out test set
# ------------------------------------------------------------------
print("\n4. Evaluating on held-out test data...")
y_pred = clf.predict(X_test)
y_proba = clf.predict_proba(X_test)[:, 1]

print("\nConfusion matrix (rows=actual, cols=predicted) [0=Not at risk, 1=At risk]:")
print(confusion_matrix(y_test, y_pred))

print("\nClassification report:")
print(classification_report(y_test, y_pred, target_names=["Not at risk", "At risk"]))

try:
    auc = roc_auc_score(y_test, y_proba)
    print(f"ROC-AUC: {auc:.3f}")
except ValueError:
    pass

print(
    "\nNote: this model predicts risk from demographic/intervention data only "
    "(no scores), by design — it's meant to flag students *before* scores "
    "exist. Given the weak signal in categorical demographics alone, expect "
    "moderate recall; treat this as an early-warning triage tool, not a "
    "high-precision classifier."
)

print("\n5. Saving the trained model...")
joblib.dump(clf, MODEL_PATH)

# ------------------------------------------------------------------
# Model versioning: hash the saved pickle's bytes to get a stable,
# content-based version identifier. This gets written into
# Fact_StudentScores.ModelVersion by the pipeline (via sp_LoadStarSchema),
# so every prediction in the warehouse can be traced back to exactly
# which trained model produced it — retrains no longer silently mix with
# old predictions in historical data.
# ------------------------------------------------------------------
model_bytes = MODEL_PATH.read_bytes()
model_version = hashlib.sha256(model_bytes).hexdigest()[:12]

metadata = {
    "model_version": model_version,
    "trained_at_utc": datetime.now(timezone.utc).isoformat(),
    "sklearn_version": sklearn.__version__,
    "training_rows": int(len(X_train)),
    "test_rows": int(len(X_test)),
    "at_risk_label_definition": "MathScore < 50 OR ReadingScore < 50 (WritingScore not included, see comment above)",
    "features": CATEGORICAL_FEATURES,
    "metrics": {
        "roc_auc": float(auc) if "auc" in locals() else None,
        "at_risk_precision": float(
            classification_report(y_test, y_pred, target_names=["Not at risk", "At risk"], output_dict=True)
            ["At risk"]["precision"]
        ),
        "at_risk_recall": float(
            classification_report(y_test, y_pred, target_names=["Not at risk", "At risk"], output_dict=True)
            ["At risk"]["recall"]
        ),
    },
}
MODEL_METADATA_PATH.write_text(json.dumps(metadata, indent=2))

print(f"    Model version: {model_version}")
print(f"    Metadata written to {MODEL_METADATA_PATH.name}")
print(f"--- Success! {MODEL_PATH.name} has been generated at {MODEL_PATH} ---")
