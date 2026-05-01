import pandas as pd
import numpy as np
from sklearn.ensemble import VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
from sklearn.svm import SVC
import joblib
import os
import shutil

# Load the data and prepare it (same as ensemble script)
csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/test/inf_feat_eng.csv'
df = pd.read_csv(csv_path)

# Feature engineering (same as ensemble file)
df['exit_and_inf_velo_ss'] = df.velo_by_inf * df.primary_position_SS
df['west_coast_ss'] = df.player_region_West * df.primary_position_SS
df['all_around_ss'] = df.power_speed * df.primary_position_SS
df['inf_velo_x_velo_by_inf'] = df.inf_velo * df.velo_by_inf
df['inf_velo_sq'] = df.inf_velo**2
df['velo_by_inf_sq'] = df.velo_by_inf**2
df['inf_velo_x_velo_by_inf_sq'] = df.velo_by_inf**2 * df.inf_velo**2
df['inf_velo_x_velo_by_inf_cubed'] = df.velo_by_inf**3 * df.inf_velo**3

df['exit_inf_velo_inv'] = 1 / df.velo_by_inf
df['inf_velo_sixty_ratio'] = df.inf_velo / df.sixty_time
df['inf_velo_sixty_ratio_sq'] = df.inf_velo_sixty_ratio**2

# Prepare X, y
drop_cols = [
    'd1_or_not', 'ten_yard_time', 'thirty_time', 'hand_speed_max',
    'exit_velo_avg', 'sweet_spot_p', 'accel_power', 'arm_swing',
    'sweet_mid', 'rot_acc_max', 'bat_speed_max', 'primary_position_3B',
    'rot_efficiency', 'accel_per_10', 'accel_per_10_sq', 'sweet_power',
    'distance_max', 'velo_dist', 'run_speed_max', 'number_of_missing',
    'speed_ratio'
]
X = df.drop(columns=drop_cols)
y = df['d1_or_not']

# Clean data
X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
for col in X.select_dtypes(include=[np.number]).columns:
    Q1, Q3 = X[col].quantile(0.01), X[col].quantile(0.99)
    IQR = Q3 - Q1
    X[col] = X[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

print("Loading existing models and creating ensemble...")
models_dir = 'saved_models'

# Load existing models
def load_model_and_params(name):
    model_path = f'{models_dir}/{name}_model.pkl'
    params_path = f'{models_dir}/{name}_params.pkl'
    if os.path.exists(model_path) and os.path.exists(params_path):
        return joblib.load(model_path), joblib.load(params_path)
    return None, None

models = {}
base_model_names = ['xgboost', 'lightgbm', 'catboost', 'svm']

for name in base_model_names:
    model, params = load_model_and_params(name)
    if model is not None:
        models[name.title()] = model
        print(f"✓ Loaded {name} model")
    else:
        print(f"✗ Could not load {name} model")

# Load SVM parameters for pipeline
svm_model, svm_params = load_model_and_params('svm')

# Create pipeline for SVM (handles scaling automatically)
svm_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('classifier', SVC(**svm_params, probability=True))
])

# Create weighted ensemble
ensemble = VotingClassifier(
    estimators=[
        ('xgb', models['Xgboost']), 
        ('lgb', models['Lightgbm']), 
        ('cat', models['Catboost']),
        ('svm', svm_pipeline)
    ],
    voting='soft',
    weights=[0.35, 0.25, 0.35, 0.05]  # Updated weights
)

print("Training ensemble on full data...")
from sklearn.model_selection import train_test_split

# Same split as original
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# Fit ensemble
ensemble.fit(X_train_val, y_train_val)

# Create final scaler
scaler_final = StandardScaler()
X_train_val_scaled = scaler_final.fit_transform(X_train_val)

print("Saving final ensemble model...")
ensemble_model_path = f'{models_dir}/ensemble_model.pkl'
ensemble_scaler_path = f'{models_dir}/ensemble_scaler.pkl'
ensemble_metadata_path = f'{models_dir}/ensemble_metadata.pkl'

joblib.dump(ensemble, ensemble_model_path)
joblib.dump(scaler_final, ensemble_scaler_path)

# Save ensemble metadata
ensemble_metadata = {
    'model_type': 'VotingClassifier_WeightedSoft',
    'weights': [0.35, 0.25, 0.35, 0.05],  # XGB, LGB, CAT, SVM
    'base_models': ['XGBoost', 'LightGBM', 'CatBoost', 'SVM'],
    'feature_columns': list(X.columns),
    'voting': 'soft',
    'random_state': 42,
    'note': 'Ensemble of optimized base models with weighted soft voting'
}
joblib.dump(ensemble_metadata, ensemble_metadata_path)

print(f"✓ Ensemble model saved to: {ensemble_model_path}")
print(f"✓ Ensemble scaler saved to: {ensemble_scaler_path}")
print(f"✓ Ensemble metadata saved to: {ensemble_metadata_path}")

# Now move all models to the new directory
target_dir = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/ml/models/models_d1_or_not_inf'
print(f"\nMoving all models to: {target_dir}")

# Create target directory if it doesn't exist
os.makedirs(target_dir, exist_ok=True)

# Copy all files from saved_models to target directory
for filename in os.listdir(models_dir):
    source = os.path.join(models_dir, filename)
    target = os.path.join(target_dir, filename)
    
    if os.path.isfile(source):
        shutil.copy2(source, target)
        print(f"✓ Moved {filename}")

print(f"\n✅ All models successfully moved to: {target_dir}")
print(f"Models include:")
print("- Individual base models: XGBoost, LightGBM, CatBoost, SVM")
print("- Parameters for each model")
print("- Final ensemble model with weighted soft voting")
print("- Ensemble scaler and metadata")