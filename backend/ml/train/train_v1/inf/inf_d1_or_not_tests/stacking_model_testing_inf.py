import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, fbeta_score, f1_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
import joblib
import os

# Load data
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

print(f'Total NA values: {X.isna().sum().sum()}')

# CRITICAL: Same data splits as ensemble for fair comparison
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# For stacking, we need to split train_val into train and holdout
# train: for base model predictions, holdout: for meta-model training
X_train, X_holdout, y_train, y_holdout = train_test_split(
    X_train_val, y_train_val, test_size=0.25, stratify=y_train_val, random_state=42  # 25% of 80% = 20% holdout
)

# Scale data for SVM
scaler_train = StandardScaler()
X_train_scaled = scaler_train.fit_transform(X_train)
X_holdout_scaled = scaler_train.transform(X_holdout)

scaler_final = StandardScaler()
X_train_val_scaled = scaler_final.fit_transform(X_train_val)
X_test_scaled = scaler_final.transform(X_test)

beta = 0.7

print("Data Splits for Stacking:")
print(f"Train (base models): {X_train.shape[0]} samples")
print(f"Holdout (meta-model): {X_holdout.shape[0]} samples") 
print(f"Test (final eval): {X_test.shape[0]} samples")
print(f"Total: {X.shape[0]} samples")
print("=" * 60)

# ============================================================================
# Load Pre-trained Base Models
# ============================================================================

def load_model_and_params(name):
    """Load model and parameters if they exist"""
    models_dir = 'saved_models'
    model_path = f'{models_dir}/{name}_model.pkl'
    params_path = f'{models_dir}/{name}_params.pkl'
    if os.path.exists(model_path) and os.path.exists(params_path):
        return joblib.load(model_path), joblib.load(params_path)
    return None, None

print("Loading pre-trained base models...")

# Load base models
base_models = {}
base_model_names = ['xgboost', 'lightgbm', 'catboost', 'svm']

for name in base_model_names:
    model, params = load_model_and_params(name)
    if model is not None:
        base_models[name] = model
        print(f"✓ Loaded {name} model")
    else:
        print(f"✗ Could not load {name} model - run ensemble script first!")

if len(base_models) != 4:
    print("ERROR: Not all base models found. Please run ensemble_model_testing_inf_clean.py first!")
    exit()

print("=" * 60)

# ============================================================================
# Generate Base Model Predictions for Meta-Training
# ============================================================================

print("Generating base model predictions...")

def get_base_predictions(models, X_data, X_data_scaled=None, return_proba=True):
    """Get predictions from all base models"""
    predictions = {}
    
    for name, model in models.items():
        if name == 'svm':
            if return_proba:
                pred = model.predict_proba(X_data_scaled)[:, 1]  # Get probability of class 1
            else:
                pred = model.predict(X_data_scaled)
        else:
            if return_proba:
                pred = model.predict_proba(X_data)[:, 1]  # Get probability of class 1
            else:
                pred = model.predict(X_data)
        
        predictions[name] = pred
    
    return np.column_stack([predictions[name] for name in base_model_names])

# Generate predictions on holdout set (for training meta-model)
print("Generating holdout predictions for meta-model training...")
X_holdout_meta = get_base_predictions(base_models, X_holdout, X_holdout_scaled, return_proba=True)

# Generate predictions on train set (for meta-model validation)
print("Generating train predictions for meta-model validation...")
X_train_meta = get_base_predictions(base_models, X_train, X_train_scaled, return_proba=True)

# Generate predictions on test set (for final evaluation)
print("Generating test predictions for final evaluation...")
X_test_meta = get_base_predictions(base_models, X_test, X_test_scaled, return_proba=True)

print(f"Meta-features shape: {X_holdout_meta.shape}")
print(f"Meta-features: {base_model_names}")
print("=" * 60)

# ============================================================================
# Train Meta-Models
# ============================================================================

print("Training meta-models...")

# Meta-model 1: Logistic Regression (simple and interpretable)
meta_lr = LogisticRegression(random_state=42, max_iter=1000)
meta_lr.fit(X_holdout_meta, y_holdout)

# Meta-model 2: Random Forest (can learn non-linear patterns)
meta_rf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=3)
meta_rf.fit(X_holdout_meta, y_holdout)

# Meta-model 3: Simple weighted average (optimized weights)
from scipy.optimize import minimize

def weighted_ensemble_objective(weights):
    weights = weights / weights.sum()  # Normalize
    ensemble_pred = np.average(X_holdout_meta, axis=1, weights=weights)
    pred_binary = (ensemble_pred > 0.5).astype(int)
    return -fbeta_score(y_holdout, pred_binary, beta=beta)

# Optimize weights
result = minimize(weighted_ensemble_objective, x0=np.ones(4)/4, 
                 bounds=[(0.01, 0.99) for _ in range(4)],
                 method='L-BFGS-B')
optimal_weights = result.x / result.x.sum()

print(f"Optimal weights: {dict(zip(base_model_names, optimal_weights))}")

meta_models = {
    'Logistic Regression': meta_lr,
    'Random Forest': meta_rf,
    'Optimized Weights': optimal_weights
}

print("=" * 60)

# ============================================================================
# Evaluate Meta-Models on Train Set (validation)
# ============================================================================

print("Meta-model validation performance:")
print("-" * 40)

best_meta_model = None
best_meta_score = 0
best_meta_name = ""

for name, model in meta_models.items():
    if name == 'Optimized Weights':
        pred_proba = np.average(X_train_meta, axis=1, weights=model)
        pred_binary = (pred_proba > 0.5).astype(int)
    else:
        pred_binary = model.predict(X_train_meta)
        pred_proba = model.predict_proba(X_train_meta)[:, 1]
    
    accuracy = accuracy_score(y_train, pred_binary)
    f1 = f1_score(y_train, pred_binary)
    fbeta = fbeta_score(y_train, pred_binary, beta=beta)
    
    print(f"{name}:")
    print(f"  Accuracy: {accuracy:.4f}")
    print(f"  F1-Score: {f1:.4f}")
    print(f"  F{beta}-Score: {fbeta:.4f}")
    print()
    
    if fbeta > best_meta_score:
        best_meta_score = fbeta
        best_meta_model = model
        best_meta_name = name

print(f"Best meta-model: {best_meta_name}")
print("=" * 60)

# ============================================================================
# Final Stacked Model Evaluation on Test Set
# ============================================================================

print("FINAL STACKED MODEL RESULTS")
print("=" * 60)

# Get final predictions using best meta-model
if best_meta_name == 'Optimized Weights':
    y_pred_stacked_proba = np.average(X_test_meta, axis=1, weights=best_meta_model)
    y_pred_stacked = (y_pred_stacked_proba > 0.5).astype(int)
else:
    y_pred_stacked = best_meta_model.predict(X_test_meta)
    y_pred_stacked_proba = best_meta_model.predict_proba(X_test_meta)[:, 1]

# Calculate metrics
test_accuracy = accuracy_score(y_test, y_pred_stacked)
test_f1 = f1_score(y_test, y_pred_stacked)
test_fbeta = fbeta_score(y_test, y_pred_stacked, beta=beta)

# Print No Information Rate
most_freq_class = y_test.value_counts(normalize=True).max()
print(f"No Information Rate: {most_freq_class:.4f}")

print(f"\nStacked Model ({best_meta_name}) Test Performance:")
print(f"Test Accuracy: {test_accuracy:.4f}")
print(f"Test F1-Score: {test_f1:.4f}")
print(f"Test F{beta}-Score: {test_fbeta:.4f}")

# Classification report
print(f"\nClassification Report:")
print(classification_report(y_test, y_pred_stacked))

# Confusion matrix
print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred_stacked))

# ============================================================================
# Individual Base Model Performance for Comparison
# ============================================================================
print("\n" + "=" * 60)
print("BASE MODEL COMPARISON ON TEST SET")
print("=" * 60)

print(f"{'Model':<20} {'Accuracy':<10} {'F1-Score':<10} {'F{beta}-Score':<12}")
print("-" * 55)

# Individual base model performance
base_results = {}
for i, name in enumerate(base_model_names):
    model = base_models[name]
    
    if name == 'svm':
        y_pred = model.predict(X_test_scaled)
    else:
        y_pred = model.predict(X_test)
    
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    fb = fbeta_score(y_test, y_pred, beta=beta)
    
    base_results[name] = {'accuracy': acc, 'f1': f1, 'fbeta': fb}
    print(f"{name.upper():<20} {acc:<10.4f} {f1:<10.4f} {fb:<12.4f}")

# Stacked model result
print(f"{'STACKED':<20} {test_accuracy:<10.4f} {test_f1:<10.4f} {test_fbeta:<12.4f}")

# ============================================================================
# Feature Importance Analysis
# ============================================================================
print("\n" + "=" * 60)
print("META-MODEL ANALYSIS")
print("=" * 60)

if best_meta_name == 'Logistic Regression':
    print("Logistic Regression Coefficients (log-odds):")
    for i, name in enumerate(base_model_names):
        coef = meta_lr.coef_[0][i]
        print(f"  {name.upper()}: {coef:.4f}")
        
elif best_meta_name == 'Random Forest':
    print("Random Forest Feature Importances:")
    for i, name in enumerate(base_model_names):
        importance = meta_rf.feature_importances_[i]
        print(f"  {name.upper()}: {importance:.4f}")
        
elif best_meta_name == 'Optimized Weights':
    print("Optimized Weights:")
    for i, name in enumerate(base_model_names):
        weight = optimal_weights[i]
        print(f"  {name.upper()}: {weight:.4f}")

# ============================================================================
# Performance Summary
# ============================================================================
print("\n" + "=" * 60)
print("PERFORMANCE SUMMARY")
print("=" * 60)

best_base_fbeta = max([result['fbeta'] for result in base_results.values()])
improvement = test_fbeta - best_base_fbeta

print(f"Best base model F{beta}-Score: {best_base_fbeta:.4f}")
print(f"Stacked model F{beta}-Score: {test_fbeta:.4f}")
print(f"Improvement: {improvement:+.4f} ({improvement/best_base_fbeta*100:+.2f}%)")

if improvement > 0:
    print("✓ Stacking improved performance!")
else:
    print("✗ Stacking did not improve performance")

print(f"\nStacking approach: {best_meta_name}")
print(f"Meta-features used: {base_model_names}")
print(f"Models saved from: ensemble_model_testing_inf_clean.py")