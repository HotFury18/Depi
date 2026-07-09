import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
import joblib

print("1. Loading historical data for training...")
# Read the raw data to train the model
df = pd.read_csv(r'data_lake\bronze\StudentsPerformance.csv')
df.columns = ['Gender', 'RaceEthnicity', 'ParentalEducation', 'LunchType', 'TestPreparationCourse', 'MathScore', 'ReadingScore', 'WritingScore']

print("2. Defining the 'At-Risk' logic...")
# 1 means At-Risk (scored below 50), 0 means Safe
df['Is_At_Risk'] = ((df['MathScore'] < 50) | (df['ReadingScore'] < 50)).astype(int)

# The features the model will use to predict
X = df[['Gender', 'RaceEthnicity', 'ParentalEducation', 'LunchType', 'TestPreparationCourse']]
y = df['Is_At_Risk']

print("3. Building and training the Random Forest Model...")
# This pipeline handles the text-based columns automatically
categorical_features = ['Gender', 'RaceEthnicity', 'ParentalEducation', 'LunchType', 'TestPreparationCourse']
preprocessor = ColumnTransformer(transformers=[('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)])

clf = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
])

# Train the algorithm
clf.fit(X, y)

print("4. Saving the trained model...")
# Save the trained model to your project folder
joblib.dump(clf, 'student_risk_model.pkl')
print("--- Success! student_risk_model.pkl has been generated. ---")