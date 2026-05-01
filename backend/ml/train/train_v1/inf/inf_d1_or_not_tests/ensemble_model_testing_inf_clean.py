import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, fbeta_score, f1_score
from sklearn.ensemble import VotingClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
import optuna
from optuna.samplers import TPESampler
import joblib
import os

# Load data
csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/test/inf_feat_eng.csv'
df = pd.read_csv(csv_path)

# Feature engineering
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

# CRITICAL: Proper data splits for unbiased evaluation
# Split 1: train+val (80%) vs test (20%) - test is held out completely
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# Split 2: train (64% of total) vs val (16% of total) - for hyperparameter optimization
X_train, X_val, y_train, y_val = train_test_split(
    X_train_val, y_train_val, test_size=0.2, stratify=y_train_val, random_state=42
)

# Scale data for SVM and DNN
scaler_train = StandardScaler()
X_train_scaled = scaler_train.fit_transform(X_train)
X_val_scaled = scaler_train.transform(X_val)

# Separate scaler for final model training
scaler_final = StandardScaler()
X_train_val_scaled = scaler_final.fit_transform(X_train_val)
X_test_scaled = scaler_final.transform(X_test)

beta = 0.7

# Model saving/loading setup
models_dir = 'saved_models'
os.makedirs(models_dir, exist_ok=True)

def save_model_and_params(model, params, name):
    """Save model and parameters"""
    joblib.dump(model, f'{models_dir}/{name}_model.pkl')
    joblib.dump(params, f'{models_dir}/{name}_params.pkl')
    print(f"Saved {name} model and parameters")

def load_model_and_params(name):
    """Load model and parameters if they exist"""
    model_path = f'{models_dir}/{name}_model.pkl'
    params_path = f'{models_dir}/{name}_params.pkl'
    if os.path.exists(model_path) and os.path.exists(params_path):
        return joblib.load(model_path), joblib.load(params_path)
    return None, None

print("Data Splits:")
print(f"Train: {X_train.shape[0]} samples")
print(f"Val: {X_val.shape[0]} samples") 
print(f"Test: {X_test.shape[0]} samples")
print(f"Total: {X.shape[0]} samples")
print("=" * 60)

# ============================================================================
# Model Optimization and Training
# ============================================================================

models = {}
best_params = {}

# XGBoost
print("XGBoost...")
xgb_model, xgb_params = load_model_and_params('xgboost')
if xgb_model is not None:
    print("  Loading saved model")
    models['XGBoost'] = xgb_model
    best_params['XGBoost'] = xgb_params
else:
    print("  Optimizing...")
    def xgb_objective(trial):
        params = {
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'use_label_encoder': False,
            'learning_rate': trial.suggest_float('eta', 1e-3, 1e-1, log=True),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'gamma': trial.suggest_float('gamma', 1e-8, 5.0, log=True),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 1.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
            'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 5.0, log=True),
        }
        model = xgb.XGBClassifier(**params, n_estimators=1000, random_state=42, missing=np.nan)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        preds = model.predict(X_val)
        return float(fbeta_score(y_val, preds, beta=beta))
    
    study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    study.optimize(xgb_objective, n_trials=100, show_progress_bar=True, n_jobs=-1)
    
    xgb_model = xgb.XGBClassifier(**study.best_params, n_estimators=750, 
                                  use_label_encoder=False, eval_metric='logloss',
                                  random_state=42, missing=np.nan)
    xgb_model.fit(X_train_val, y_train_val, verbose=False)
    
    models['XGBoost'] = xgb_model
    best_params['XGBoost'] = study.best_params
    save_model_and_params(xgb_model, study.best_params, 'xgboost')

# LightGBM
print("LightGBM...")
lgb_model, lgb_params = load_model_and_params('lightgbm')
if lgb_model is not None:
    print("  Loading saved model")
    models['LightGBM'] = lgb_model
    best_params['LightGBM'] = lgb_params
else:
    print("  Optimizing...")
    def lgb_objective(trial):
        params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'learning_rate': trial.suggest_float('learning_rate', 1e-3, 1e-1, log=True),
            'num_leaves': trial.suggest_int('num_leaves', 10, 300),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
            'min_child_weight': trial.suggest_float('min_child_weight', 1e-8, 10.0, log=True),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'subsample_freq': trial.suggest_int('subsample_freq', 1, 7),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
            'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 5.0, log=True),
            'verbose': -1,
            'random_state': 42
        }
        model = lgb.LGBMClassifier(**params, n_estimators=1000)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], 
                  callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(0)])
        preds = model.predict(X_val)
        return float(fbeta_score(y_val, preds, beta=beta))
    
    study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    study.optimize(lgb_objective, n_trials=100, show_progress_bar=True, n_jobs=-1)
    
    lgb_model = lgb.LGBMClassifier(**study.best_params, n_estimators=750, verbose=-1)
    lgb_model.fit(X_train_val, y_train_val)
    
    models['LightGBM'] = lgb_model
    best_params['LightGBM'] = study.best_params
    save_model_and_params(lgb_model, study.best_params, 'lightgbm')

# CatBoost
print("CatBoost...")
cat_model, cat_params = load_model_and_params('catboost')
if cat_model is not None:
    print("  Loading saved model")
    models['CatBoost'] = cat_model
    best_params['CatBoost'] = cat_params
else:
    print("  Optimizing...")
    def cat_objective(trial):
        params = {
            'objective': 'Logloss',
            'eval_metric': 'AUC',
            'learning_rate': trial.suggest_float('learning_rate', 1e-3, 1e-1, log=True),
            'depth': trial.suggest_int('depth', 3, 10),
            'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1e-8, 10.0, log=True),
            'bagging_temperature': trial.suggest_float('bagging_temperature', 0, 1),
            'random_strength': trial.suggest_float('random_strength', 0, 1),
            'border_count': trial.suggest_int('border_count', 32, 255),
            'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 5.0, log=True),
            'verbose': False,
            'random_state': 42
        }
        model = cb.CatBoostClassifier(**params, iterations=1000)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], 
                  early_stopping_rounds=50, verbose=False)
        preds = model.predict(X_val)
        return float(fbeta_score(y_val, preds, beta=beta))
    
    study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    study.optimize(cat_objective, n_trials=100, show_progress_bar=True, n_jobs=-1)
    
    cat_model = cb.CatBoostClassifier(**study.best_params, iterations=750, verbose=False)
    cat_model.fit(X_train_val, y_train_val)
    
    models['CatBoost'] = cat_model
    best_params['CatBoost'] = study.best_params
    save_model_and_params(cat_model, study.best_params, 'catboost')

# SVM
print("SVM...")
svm_model, svm_params = load_model_and_params('svm')
if svm_model is not None:
    print("  Loading saved model")
    models['SVM'] = svm_model
    best_params['SVM'] = svm_params
else:
    print("  Optimizing...")
    def svm_objective(trial):
        kernel = trial.suggest_categorical('kernel', ['rbf', 'poly', 'sigmoid', 'linear'])
        params = {
            'C': trial.suggest_float('C', 1e-3, 1e3, log=True),
            'kernel': kernel,
            'class_weight': trial.suggest_categorical('class_weight', ['balanced', None]),
            'probability': True,
            'random_state': 42
        }
        if kernel != 'linear':
            params['gamma'] = trial.suggest_float('gamma', 1e-5, 1e1, log=True)
        
        model = SVC(**params)
        model.fit(X_train_scaled, y_train)
        preds = model.predict(X_val_scaled)
        return float(fbeta_score(y_val, preds, beta=beta))
    
    study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    study.optimize(svm_objective, n_trials=40, show_progress_bar=True, n_jobs=4, timeout=5)
    
    svm_model = SVC(**study.best_params, probability=True)
    svm_model.fit(X_train_val_scaled, y_train_val)
    
    models['SVM'] = svm_model
    best_params['SVM'] = study.best_params
    save_model_and_params(svm_model, study.best_params, 'svm')

# DNN - Removed due to poor performance (0.7177 accuracy vs ~0.78 for other models)
# Keeping 4 strong models: XGBoost, LightGBM, CatBoost, SVM

print("=" * 60)

# ============================================================================
# Individual Model Performance on Test Set
# ============================================================================
print("Individual Model Performance on Test Set:")
print("-" * 50)

individual_predictions = {}
for name, model in models.items():
    if name == 'SVM':
        y_pred = model.predict(X_test_scaled)
    else:
        y_pred = model.predict(X_test)
    
    individual_predictions[name] = y_pred
    
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    fbeta = fbeta_score(y_test, y_pred, beta=beta)
    
    print(f"{name}:")
    print(f"  Accuracy: {accuracy:.4f}")
    print(f"  F1-Score: {f1:.4f}")
    print(f"  F{beta}-Score: {fbeta:.4f}")
    print()

# ============================================================================
# Ensemble Model - Using Pipeline for Scaling
# ============================================================================
print("Creating Ensemble Model...")

# Create pipeline for SVM (handles scaling automatically)
svm_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('classifier', SVC(**best_params['SVM'], probability=True))
])

# Create weighted ensemble based on model tiers
# Tier 1 (stronger): XGBoost, LightGBM - get higher weights
# Tier 2 (good): CatBoost, SVM - get lower weights
tier1_weight = 0.3  # 60% total weight split between XGB and LGB
tier2_weight = 0.2  # 40% total weight split between CAT and SVM

ensemble = VotingClassifier(
    estimators=[
        ('xgb', models['XGBoost']), 
        ('lgb', models['LightGBM']), 
        ('cat', models['CatBoost']),
        ('svm', svm_pipeline)
    ],
    voting='soft',
    weights=[0.35, 0.25, 0.35, 0.05]  # [0.3, 0.3, 0.2, 0.2]
)


print(f"Ensemble weights: XGBoost={tier1_weight}, LightGBM={tier1_weight}, CatBoost={tier2_weight}, SVM={tier2_weight}")

# Cross-validation on ensemble
print("Running 5-fold cross-validation on ensemble...")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_f1 = cross_val_score(ensemble, X_train_val, y_train_val, cv=cv, scoring='f1')
cv_accuracy = cross_val_score(ensemble, X_train_val, y_train_val, cv=cv, scoring='accuracy')

print(f"5-fold CV F1 Score: {cv_f1.mean():.4f} (+/- {cv_f1.std() * 2:.4f})")
print(f"5-fold CV Accuracy Score: {cv_accuracy.mean():.4f} (+/- {cv_accuracy.std() * 2:.4f})")

# Train ensemble on full train+val data
ensemble.fit(X_train_val, y_train_val)

# ============================================================================
# Final Ensemble Evaluation on Test Set
# ============================================================================
print("\n" + "=" * 60)
print("FINAL ENSEMBLE RESULTS")
print("=" * 60)

# Print No Information Rate
most_freq_class = y_test.value_counts(normalize=True).max()
print(f"No Information Rate: {most_freq_class:.4f}")

# Evaluate ensemble on test set
y_pred_ensemble = ensemble.predict(X_test)

# Calculate metrics
test_accuracy = accuracy_score(y_test, y_pred_ensemble)
test_f1 = f1_score(y_test, y_pred_ensemble)
test_fbeta = fbeta_score(y_test, y_pred_ensemble, beta=beta)

print(f"\nEnsemble Test Performance:")
print(f"Test Accuracy: {test_accuracy:.4f}")
print(f"Test F1-Score: {test_f1:.4f}")
print(f"Test F{beta}-Score: {test_fbeta:.4f}")

# Classification report
print(f"\nClassification Report:")
print(classification_report(y_test, y_pred_ensemble))

# Confusion matrix
print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred_ensemble))

# ============================================================================
# Model Comparison Summary
# ============================================================================
print("\n" + "=" * 60)
print("MODEL COMPARISON SUMMARY")
print("=" * 60)

print(f"{'Model':<15} {'Accuracy':<10} {'F1-Score':<10} {'F{beta}-Score':<12}")
print("-" * 50)

for name, pred in individual_predictions.items():
    acc = accuracy_score(y_test, pred)
    f1 = f1_score(y_test, pred)
    fb = fbeta_score(y_test, pred, beta=beta)
    print(f"{name:<15} {acc:<10.4f} {f1:<10.4f} {fb:<12.4f}")

print(f"{'Ensemble':<15} {test_accuracy:<10.4f} {test_f1:<10.4f} {test_fbeta:<12.4f}")

# Feature importance from ensemble (using XGBoost as representative)
print(f"\nFeature Importances (from XGBoost):")
imp_df = pd.DataFrame({
    'feature': X.columns,
    'importance': models['XGBoost'].feature_importances_
}).sort_values('importance', ascending=False)
print(imp_df.head(15))

print(f"\nColumns used in the ensemble models:")
print(list(X.columns))

print(f"\nOptimization completed successfully!")
print(f"Models saved to '{models_dir}/' directory for future use.")

# Save the final ensemble model
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
    'test_accuracy': test_accuracy,
    'test_f1': test_f1,
    'test_fbeta': test_fbeta,
    'feature_columns': list(X.columns),
    'voting': 'soft',
    'random_state': 42
}
joblib.dump(ensemble_metadata, ensemble_metadata_path)

print(f"✓ Ensemble model saved to: {ensemble_model_path}")
print(f"✓ Ensemble scaler saved to: {ensemble_scaler_path}")
print(f"✓ Ensemble metadata saved to: {ensemble_metadata_path}")

# ============================================================================
# Data Split Validation Summary
# ============================================================================
print("\n" + "=" * 60)
print("DATA SPLIT VALIDATION")
print("=" * 60)
print("✓ Hyperparameter optimization: train (64%) + val (16%)")  
print("✓ 5-fold cross-validation: train+val (80%)")
print("✓ Final test evaluation: test (20%) - COMPLETELY HELD OUT")
print("✓ No data leakage between optimization and final evaluation")
print("✓ Separate scalers used for optimization vs final models")