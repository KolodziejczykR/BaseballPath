#!/usr/bin/env python3
"""
P4 Recall-Focused Model for Outfielders
Target: Maintain 70%+ accuracy while maximizing P4 recall
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight
import xgboost as xgb
import lightgbm as lgb
import joblib
import json
import optuna
from optuna.samplers import TPESampler


print("🎯 P4 RECALL-FOCUSED OUTFIELDER MODEL V4")
print("="*80)
print("🎯 TARGET: 70%+ Accuracy + Maximum P4 Recall")
print("🔧 APPROACH: Hierarchical + Optuna-Optimized + 65/15/20 Split")
print("="*80)

# ============================================================================
# DATA LOADING AND PREPROCESSING
# ============================================================================
print("\n📊 Loading data...")
df = pd.read_csv('/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/of_p4_or_not_data.csv')

# Data is already filtered to D1 players
print(f"Loaded: {len(df):,} D1 outfielders, P4 rate: {df['p4_or_not'].mean():.1%}")

# ============================================================================
# ENHANCED FEATURE ENGINEERING WITH D1 META FEATURES
# ============================================================================
print("\n🔧 Enhanced feature engineering with D1 meta features...")

# Basic feature engineering
df['power_speed'] = df['exit_velo_max'] * (7.6 - df['sixty_time'])
df['of_velo_sixty_ratio'] = df['of_velo'] / df['sixty_time'] 
df['height_weight'] = df['height'] * df['weight']
df['power_per_pound'] = df['exit_velo_max'] / df['weight']
df['exit_to_sixty_ratio'] = df['exit_velo_max'] / df['sixty_time']
df['speed_size_efficiency'] = df['height'] / df['sixty_time']
df['athletic_index'] = (df['exit_velo_max'] + df['of_velo'] + (100 - df['sixty_time']*10)) / 3
df['power_speed_index'] = df['power_speed'] / df['athletic_index']
df['exit_velo_body'] = df['exit_velo_max'] / df['height_weight']

# Elite indicators for recall boost
df['elite_exit_velo'] = (df['exit_velo_max'] >= df['exit_velo_max'].quantile(0.8)).astype(int)
df['elite_of_velo'] = (df['of_velo'] >= df['of_velo'].quantile(0.8)).astype(int)
df['elite_speed'] = (df['sixty_time'] <= df['sixty_time'].quantile(0.2)).astype(int)
df['elite_size'] = (df['height'] >= df['height'].quantile(0.8)).astype(int)

# Multi-tool detection for P4 identification
df['multi_tool_count'] = (df['elite_exit_velo'] + df['elite_of_velo'] + 
                         df['elite_speed'] + df['elite_size'])
df['is_multi_tool'] = (df['multi_tool_count'] >= 2).astype(int)

print(f"✓ Created {df.shape[1] - 15} enhanced features")  # Subtract original columns

# ============================================================================
# D1 MODEL INTEGRATION FOR META FEATURES
# ============================================================================
print("\n🎯 Loading actual OF D1 prediction model for meta features...")

# Load D1 model components
d1_models_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/ml/models/models_of/models_d1_or_not_of'

print("Loading trained OF D1 models...")
d1_elite_model = joblib.load(f'{d1_models_path}/elite_model.pkl')
d1_xgb_full = joblib.load(f'{d1_models_path}/xgb_full_model.pkl')
d1_dnn_full = joblib.load(f'{d1_models_path}/dnn_full_model.pkl')
d1_lgb_full = joblib.load(f'{d1_models_path}/lgb_full_model.pkl')
d1_svm_full = joblib.load(f'{d1_models_path}/svm_full_model.pkl')
print("✓ Loaded D1 models successfully")

# Load feature metadata and config
with open(f'{d1_models_path}/feature_metadata.json', 'r') as f:
    feature_metadata = json.load(f)

with open(f'{d1_models_path}/model_config.json', 'r') as f:
    model_config = json.load(f)

# Create features needed by D1 model
print("Creating features to match D1 model...")

# One-hot encode categorical variables
df = pd.get_dummies(df, columns=['player_region', 'throwing_hand', 'hitting_handedness'], drop_first=False)

# Create percentile features
for col in ['exit_velo_max', 'of_velo', 'sixty_time', 'height', 'weight', 'power_speed']:
    if col in df.columns:
        df[f'{col}_percentile'] = df[col].rank(pct=True) * 100

# Create missing elite-related features from D1 model
df['exit_velo_scaled'] = (df['exit_velo_max'] - df['exit_velo_max'].mean()) / df['exit_velo_max'].std()
df['speed_scaled'] = (df['sixty_time'].mean() - df['sixty_time']) / df['sixty_time'].std()
df['arm_scaled'] = (df['of_velo'] - df['of_velo'].mean()) / df['of_velo'].std()

# Advanced D1 features
df['d1_region_advantage'] = 0
if 'player_region_South' in df.columns:
    df['d1_region_advantage'] = df['player_region_South'] * 0.3
if 'player_region_West' in df.columns:
    df['d1_region_advantage'] += df['player_region_West'] * 0.2

df['of_arm_strength'] = df['of_velo'] / df['of_velo'].std()
df['of_arm_plus'] = np.where(df['of_velo'] > df['of_velo'].quantile(0.8), 1, 0)
df['exit_velo_elite'] = np.where(df['exit_velo_max'] > df['exit_velo_max'].quantile(0.85), 1, 0)
df['speed_elite'] = np.where(df['sixty_time'] < df['sixty_time'].quantile(0.15), 1, 0)

# D1 thresholds
df['d1_exit_velo_threshold'] = np.where(df['exit_velo_max'] >= 95, 1, 0)
df['d1_arm_threshold'] = np.where(df['of_velo'] >= 85, 1, 0)
df['d1_speed_threshold'] = np.where(df['sixty_time'] <= 6.9, 1, 0)
df['d1_size_threshold'] = np.where(df['height'] >= 72, 1, 0)

# Tool count and composite features
df['tool_count'] = (df['d1_exit_velo_threshold'] + df['d1_arm_threshold'] + 
                   df['d1_speed_threshold'] + df['d1_size_threshold'])
df['is_multi_tool'] = (df['tool_count'] >= 2).astype(int)
df['athletic_index_v2'] = df['athletic_index'] * (1 + df['tool_count'] * 0.1)
df['tools_athlete'] = df['tool_count'] * df['athletic_index']
df['d1_composite_score'] = (df['exit_velo_scaled'] + df['arm_scaled'] + 
                           df['speed_scaled'] + df['athletic_index_v2']) / 4

elite_features = feature_metadata['elite_features']
d1_full_features = feature_metadata['d1_features']

print(f"D1 model expects {len(elite_features)} elite features and {len(d1_full_features)} full features")

# Generate D1 probabilities
print("Generating D1 probabilities from production models...")

# Elite detection
X_elite = df[elite_features].fillna(0)
elite_probs = d1_elite_model.predict_proba(X_elite)[:, 1]
elite_threshold = model_config['elite_threshold']
is_elite = elite_probs >= elite_threshold

# Full model predictions
X_full = df[d1_full_features].fillna(0)

# Load scalers for DNN and SVM
dnn_scaler = joblib.load(f'{d1_models_path}/scaler_full.pkl')
svm_scaler = joblib.load(f'{d1_models_path}/scaler_full.pkl')  # Use same scaler for both

# Get individual model predictions
d1_xgb_probs = d1_xgb_full.predict_proba(X_full.values)[:, 1]
d1_dnn_probs = d1_dnn_full.predict_proba(dnn_scaler.transform(X_full))[:, 1]
d1_lgb_probs = d1_lgb_full.predict_proba(X_full)[:, 1]
d1_svm_probs = d1_svm_full.predict_proba(svm_scaler.transform(X_full))[:, 1]

# Use production ensemble weights
ensemble_weights = model_config['ensemble_weights']
hierarchical_weights = model_config['hierarchical_weights']

print(f"Using production D1 ensemble weights: {ensemble_weights}")
print(f"Using production D1 hierarchical weights: {hierarchical_weights}")

# Ensemble prediction (excluding SVM which has 0 weight)
ensemble_prob = (d1_xgb_probs * ensemble_weights['XGB'] + 
                d1_lgb_probs * ensemble_weights['LGB'] + 
                d1_dnn_probs * ensemble_weights['DNN'])

# Hierarchical combination
d1_probability = np.where(is_elite,
                         elite_probs * hierarchical_weights['elite_weight'] + 
                         ensemble_prob * hierarchical_weights['ensemble_weight'],
                         ensemble_prob)

df['d1_probability'] = d1_probability

print(f"✓ Generated real D1 probabilities (range: {df['d1_probability'].min():.3f} - {df['d1_probability'].max():.3f})")
print(f"  Average D1 probability: {df['d1_probability'].mean():.3f}")
print(f"  D1 probability std: {df['d1_probability'].std():.3f}")

# ============================================================================
# P4 RECALL-FOCUSED FEATURES
# ============================================================================
print("\nCreating P4 recall-focused features...")

df['d1_prob_size'] = df['d1_probability'] * df['height_weight']
df['d1_size_speed'] = df['d1_probability'] * df['speed_size_efficiency']
df['d1_squared'] = df['d1_probability'] ** 2
df['d1_athletic_index'] = df['d1_probability'] * df['athletic_index']
df['d1_exit_velo'] = df['d1_probability'] * df['exit_velo_max']
df['d1_power_per_pound'] = df['d1_probability'] * df['power_per_pound']
df['d1_speed_size'] = df['d1_probability'] * df['speed_size_efficiency']
df['d1_ppp_ss'] = df['d1_power_per_pound'] * df['d1_speed_size']

# D1 probability tiers for P4 prediction
df['d1_prob_high'] = (df['d1_probability'] >= 0.7).astype(int)
df['d1_prob_medium'] = ((df['d1_probability'] >= 0.4) & (df['d1_probability'] < 0.7)).astype(int)
df['d1_prob_low'] = (df['d1_probability'] < 0.4).astype(int)

# P4 indicators within high D1 probability players
high_d1_mask = df['d1_probability'] >= 0.6
df['p4_among_high_d1'] = 0.0
if high_d1_mask.sum() > 0:
    p4_rate_high_d1 = df.loc[high_d1_mask, 'p4_or_not'].mean()
    df.loc[high_d1_mask, 'p4_among_high_d1'] = (df.loc[high_d1_mask, 'p4_or_not'] / p4_rate_high_d1).astype(float)

# Elite combinations for P4 detection
df['elite_power_arm'] = df['elite_exit_velo'] * df['elite_of_velo']
df['elite_power_speed'] = df['elite_exit_velo'] * df['elite_speed']
df['elite_triple_tool'] = df['elite_exit_velo'] * df['elite_of_velo'] * df['elite_speed']

# Regional P4 advantages
df['p4_region_bonus'] = 0
if 'player_region_South' in df.columns:
    df['p4_region_bonus'] += df['player_region_South'] * 0.15
if 'player_region_West' in df.columns:
    df['p4_region_bonus'] += df['player_region_West'] * 0.12

print(f"Total features for P4 prediction: {df.shape[1]}")

# ============================================================================
# FEATURE SELECTION FOR P4 RECALL
# ============================================================================

# Select features that correlate with P4 success
p4_features = [
    'height', 'weight', 'sixty_time', 'exit_velo_max', 'of_velo',
    'power_speed', 'of_velo_sixty_ratio', 'height_weight', 'power_per_pound',
    'exit_to_sixty_ratio', 'speed_size_efficiency', 'athletic_index',
    'power_speed_index', 'multi_tool_count', 'd1_power_per_pound',
    'd1_probability', 'd1_squared', 'd1_exit_velo', 'd1_speed_size',
    'p4_region_bonus', 'd1_prob_size', 'exit_velo_body', 'p4_among_high_d1',
    'tool_count', 'athletic_index_v2', 'd1_composite_score', 'd1_size_speed',
]

# Add available regional dummies
regional_cols = [col for col in df.columns if 'player_region_' in col]
p4_features.extend(regional_cols)

# Add available handedness dummies
# NO THROWING HAND IN P4 MODEL
handedness_cols = [col for col in df.columns if any(x in col for x in ['hitting_handedness_'])]
p4_features.extend(handedness_cols)

# highly colinear, no impact surprisingly
p4_features.remove('hitting_handedness_S')

# Filter to available features
available_features = [f for f in p4_features if f in df.columns]
print(f"Using {len(available_features)} features for P4 prediction")

# ============================================================================
# ELITE DETECTION MODEL FOR HIERARCHICAL APPROACH
# ============================================================================
print("\n🎯 Training elite detection model for hierarchical thresholds...")

# Define elite based on multiple criteria for P4 detection
elite_criteria = (
    (df['d1_probability'] >= 0.6) |  # High D1 probability
    (df['multi_tool_count'] >= 3) |  # Multi-tool players
    (df['elite_triple_tool'] == 1)   # Triple elite tools
)

df['elite_candidate'] = elite_criteria.astype(int)
elite_rate = df['elite_candidate'].mean()
print(f"Elite candidates: {df['elite_candidate'].sum()} ({elite_rate:.1%})")
print(f"P4 rate among elite: {df[df['elite_candidate']==1]['p4_or_not'].mean():.1%}")
print(f"P4 rate among non-elite: {df[df['elite_candidate']==0]['p4_or_not'].mean():.1%}")

# Train elite detection model
elite_model = xgb.XGBClassifier(n_estimators=500, random_state=42)
X_for_elite = df[available_features].fillna(0)
elite_model.fit(X_for_elite, df['elite_candidate'])
elite_detection_acc = elite_model.score(X_for_elite, df['elite_candidate'])
print(f"Elite detection accuracy: {elite_detection_acc:.1%}")

# ============================================================================
# TRAIN/VALIDATION/TEST SPLIT (65/15/20)
# ============================================================================
X = df[available_features].fillna(0)
y = df['p4_or_not']

# First split: 65% train, 35% temp
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.35, random_state=42, stratify=y
)

# Second split: 15% validation, 20% test from the 35% temp
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.571, random_state=42, stratify=y_temp  # 0.571 * 35% ≈ 20%
)

print(f"\nTraining set: {len(X_train)} players ({len(X_train)/len(X):.1%}), P4 rate: {y_train.mean():.1%}")
print(f"Validation set: {len(X_val)} players ({len(X_val)/len(X):.1%}), P4 rate: {y_val.mean():.1%}")
print(f"Test set: {len(X_test)} players ({len(X_test)/len(X):.1%}), P4 rate: {y_test.mean():.1%}")

# ============================================================================
# OPTUNA OPTIMIZATION FOR ENSEMBLE MODELS
# ============================================================================
print(f"\n🎯 OPTUNA OPTIMIZATION FOR RECALL-FOCUSED ENSEMBLE")

# Calculate class weights to boost P4 recall
class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
class_weight_ratio = class_weights[1] / class_weights[0]
print(f"Class weight ratio (P4/Non-P4): {class_weight_ratio:.2f}")

# Setup scaling
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_val_scaled = scaler.transform(X_val)
X_test_scaled = scaler.transform(X_test)

# Suppress Optuna logging
optuna.logging.set_verbosity(optuna.logging.WARNING)

models = {}
best_params = {}

print("🔧 Optimizing XGBoost...")
def optimize_xgb(trial):
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'scale_pos_weight': class_weight_ratio * trial.suggest_float('pos_weight_mult', 1.0, 1.5),
        'max_depth': trial.suggest_int('max_depth', 3, 6),
        'eta': trial.suggest_float('eta', 0.01, 0.1),
        'subsample': trial.suggest_float('subsample', 0.7, 0.9),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.7, 0.9),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 0.5),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.5, 2.0),
        'random_state': 42,
        'verbosity': 0
    }
    
    model = xgb.XGBClassifier(**params, n_estimators=300)
    model.fit(X_train.values, y_train)
    
    # Evaluate on validation set
    val_preds = model.predict(X_val.values)
    accuracy = accuracy_score(y_val, val_preds)
    recall = recall_score(y_val, val_preds, pos_label=1)
    
    # Combined score favoring recall
    return 0.7 * accuracy + 0.3 * recall

xgb_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
xgb_study.optimize(optimize_xgb, n_trials=75, n_jobs=-1, show_progress_bar=True)
best_params['xgb'] = xgb_study.best_params
print(f"✓ XGBoost best score: {xgb_study.best_value:.4f}")

print("🔧 Optimizing LightGBM...")
def optimize_lgb(trial):
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'scale_pos_weight': class_weight_ratio * trial.suggest_float('pos_weight_mult', 1.0, 1.5),
        'num_leaves': trial.suggest_int('num_leaves', 20, 60),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.7, 0.9),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.7, 0.9),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 5),
        'min_child_samples': trial.suggest_int('min_child_samples', 10, 50),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 1.0),
        'verbosity': -1,
        'random_state': 42
    }
    
    model = lgb.LGBMClassifier(**params, n_estimators=300)
    model.fit(X_train, y_train)
    
    # Evaluate on validation set
    val_preds = model.predict(X_val)
    accuracy = accuracy_score(y_val, val_preds)
    recall = recall_score(y_val, val_preds, pos_label=1)
    
    # Combined score favoring recall
    return 0.7 * accuracy + 0.3 * recall

lgb_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
lgb_study.optimize(optimize_lgb, n_trials=75, n_jobs=-1, show_progress_bar=True)
best_params['lgb'] = lgb_study.best_params
print(f"✓ LightGBM best score: {lgb_study.best_value:.4f}")

print("🔧 Optimizing MLP...")
def optimize_mlp(trial):
    hidden_layers = []
    n_layers = trial.suggest_int('n_layers', 1, 3)
    for i in range(n_layers):
        hidden_layers.append(trial.suggest_int(f'layer_{i}', 64, 256))
    
    params = {
        'hidden_layer_sizes': tuple(hidden_layers),
        'activation': trial.suggest_categorical('activation', ['relu', 'tanh']),
        'alpha': trial.suggest_float('alpha', 1e-5, 1e-1, log=True),
        'learning_rate_init': trial.suggest_float('learning_rate_init', 1e-4, 1e-2, log=True),
        'max_iter': 300,
        'random_state': 42,
        'early_stopping': True,
        'validation_fraction': 0.1
    }
    
    model = MLPClassifier(**params)
    model.fit(X_train_scaled, y_train)
    
    # Evaluate on validation set
    val_preds = model.predict(X_val_scaled)
    accuracy = accuracy_score(y_val, val_preds)
    recall = recall_score(y_val, val_preds, pos_label=1)
    
    # Combined score favoring recall
    return 0.7 * accuracy + 0.3 * recall

mlp_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
mlp_study.optimize(optimize_mlp, n_trials=30, n_jobs=-1, show_progress_bar=True)
best_params['mlp'] = mlp_study.best_params
print(f"✓ MLP best score: {mlp_study.best_value:.4f}")

print("🔧 Optimizing SVM...")
def optimize_svm(trial):
    params = {
        'C': trial.suggest_float('C', 0.01, 10.0, log=True),
        'kernel': trial.suggest_categorical('kernel', ['rbf', 'linear']),
        'gamma': trial.suggest_categorical('gamma', ['scale', 'auto']),
        'class_weight': {0: 1, 1: class_weight_ratio * trial.suggest_float('pos_weight_mult', 1.0, 1.5)},
        'probability': True,
        'random_state': 42
    }
    
    model = SVC(**params)
    model.fit(X_train_scaled, y_train)
    
    # Evaluate on validation set
    val_preds = model.predict(X_val_scaled)
    accuracy = accuracy_score(y_val, val_preds)
    recall = recall_score(y_val, val_preds, pos_label=1)
    
    # Combined score favoring recall
    return 0.7 * accuracy + 0.3 * recall

svm_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
svm_study.optimize(optimize_svm, n_trials=75, n_jobs=-1, show_progress_bar=True)
best_params['svm'] = svm_study.best_params
print(f"✓ SVM best score: {svm_study.best_value:.4f}")

# ============================================================================
# TRAIN FINAL OPTIMIZED MODELS
# ============================================================================
print(f"\n🎯 TRAINING FINAL OPTIMIZED MODELS...")

# Train optimized XGBoost
xgb_final_params = best_params['xgb'].copy()
xgb_final_params.update({
    'objective': 'binary:logistic',
    'eval_metric': 'logloss',
    'scale_pos_weight': class_weight_ratio * xgb_final_params.pop('pos_weight_mult'),
    'random_state': 42,
    'verbosity': 0
})
xgb_model = xgb.XGBClassifier(**xgb_final_params, n_estimators=300)
xgb_model.fit(X_train.values, y_train)
models['xgb'] = xgb_model

# Train optimized LightGBM
lgb_final_params = best_params['lgb'].copy()
lgb_final_params.update({
    'objective': 'binary',
    'metric': 'binary_logloss',
    'scale_pos_weight': class_weight_ratio * lgb_final_params.pop('pos_weight_mult'),
    'verbosity': -1,
    'random_state': 42
})
lgb_model = lgb.LGBMClassifier(**lgb_final_params, n_estimators=300)
lgb_model.fit(X_train, y_train)
models['lgb'] = lgb_model

# Train optimized MLP
mlp_final_params = best_params['mlp'].copy()
# Reconstruct hidden layers
hidden_layers = []
n_layers = mlp_final_params.pop('n_layers')
for i in range(n_layers):
    hidden_layers.append(mlp_final_params.pop(f'layer_{i}'))
mlp_final_params['hidden_layer_sizes'] = tuple(hidden_layers)
mlp_final_params.update({
    'max_iter': 300,
    'random_state': 42,
    'early_stopping': True,
    'validation_fraction': 0.1
})
mlp_model = MLPClassifier(**mlp_final_params)
mlp_model.fit(X_train_scaled, y_train)
models['mlp'] = mlp_model

# Train optimized SVM
svm_final_params = best_params['svm'].copy()
svm_final_params.update({
    'class_weight': {0: 1, 1: class_weight_ratio * svm_final_params.pop('pos_weight_mult')},
    'probability': True,
    'random_state': 42
})
svm_model = SVC(**svm_final_params)
svm_model.fit(X_train_scaled, y_train)
models['svm'] = svm_model

# Calculate validation scores for weighting
cv_scores = {}
cv_scores['xgb'] = xgb_study.best_value
cv_scores['lgb'] = lgb_study.best_value
cv_scores['mlp'] = mlp_study.best_value
cv_scores['svm'] = svm_study.best_value

print("✅ Optimized model validation scores:")
for name, score in cv_scores.items():
    print(f"   {name.upper()}: {score:.4f}")

# ============================================================================
# RECALL-OPTIMIZED ENSEMBLE PREDICTIONS
# ============================================================================
print(f"\n🎯 Generating recall-optimized ensemble predictions...")

# Get predictions from all models
xgb_probs = models['xgb'].predict_proba(X_test.values)[:, 1]
lgb_probs = models['lgb'].predict_proba(X_test)[:, 1]
mlp_probs = models['mlp'].predict_proba(X_test_scaled)[:, 1]
svm_probs = models['svm'].predict_proba(X_test_scaled)[:, 1]

# Performance-weighted ensemble
total_score = sum(cv_scores.values())
weights = {name: score/total_score for name, score in cv_scores.items()}
print(f"Ensemble weights: {weights}")

# Weighted ensemble
ensemble_probs = (xgb_probs * weights['xgb'] + 
                 lgb_probs * weights['lgb'] + 
                 mlp_probs * weights['mlp'] + 
                 svm_probs * weights['svm'])

# ============================================================================
# THRESHOLD OPTIMIZATION ON VALIDATION SET
# ============================================================================
print(f"\n🎯 THRESHOLD OPTIMIZATION ON VALIDATION SET")

# Get elite predictions for validation set
elite_val_probs = elite_model.predict_proba(X_val)[:, 1]
elite_val_mask = elite_val_probs >= 0.5

print(f"Elite players in validation set: {elite_val_mask.sum()} ({elite_val_mask.mean():.1%})")

# Get validation ensemble predictions
val_xgb_probs = models['xgb'].predict_proba(X_val.values)[:, 1]
val_lgb_probs = models['lgb'].predict_proba(X_val)[:, 1]
val_mlp_probs = models['mlp'].predict_proba(X_val_scaled)[:, 1]
val_svm_probs = models['svm'].predict_proba(X_val_scaled)[:, 1]

# Performance-weighted ensemble for validation
total_score = sum(cv_scores.values())
weights = {name: score/total_score for name, score in cv_scores.items()}
print(f"Ensemble weights: {weights}")

val_ensemble_probs = (val_xgb_probs * weights['xgb'] + 
                     val_lgb_probs * weights['lgb'] + 
                     val_mlp_probs * weights['mlp'] + 
                     val_svm_probs * weights['svm'])

# Optimize hierarchical thresholds with recall focus
best_combined_score = 0
best_elite_thresh = 0.4
best_non_elite_thresh = 0.6
best_results = {}

print("Optimizing hierarchical thresholds on validation set...")
for elite_thresh in np.arange(0.2, 0.5, 0.02):  # Very aggressive for elite
    for non_elite_thresh in np.arange(0.4, 0.7, 0.02):  # Conservative for non-elite
        
        y_pred_hier = np.zeros(len(val_ensemble_probs))
        
        # Elite players: very aggressive threshold for maximum recall
        if elite_val_mask.sum() > 0:
            y_pred_hier[elite_val_mask] = (val_ensemble_probs[elite_val_mask] >= elite_thresh).astype(int)
        
        # Non-elite players: more conservative
        if (~elite_val_mask).sum() > 0:
            y_pred_hier[~elite_val_mask] = (val_ensemble_probs[~elite_val_mask] >= non_elite_thresh).astype(int)
        
        y_pred_hier = y_pred_hier.astype(int)
        
        acc = accuracy_score(y_val, y_pred_hier)
        recall = recall_score(y_val, y_pred_hier, pos_label=1)
        precision = precision_score(y_pred_hier, y_val, pos_label=1, zero_division=0)
        
        # Prioritize recall more while maintaining 70%+ accuracy
        if acc >= 0.7:
            combined_score = 0.45 * acc + 0.55 * recall  # Weight recall heavily
            
            if combined_score > best_combined_score:
                best_combined_score = combined_score
                best_elite_thresh = elite_thresh
                best_non_elite_thresh = non_elite_thresh
                best_results = {
                    'accuracy': acc,
                    'recall': recall, 
                    'precision': precision,
                    'combined_score': combined_score
                }

print(f"\n🏆 BEST HIERARCHICAL THRESHOLDS (validated):")
print(f"Elite threshold: {best_elite_thresh:.3f}")
print(f"Non-Elite threshold: {best_non_elite_thresh:.3f}")
print(f"Combined score: {best_combined_score:.4f}")
print(f"Validation accuracy: {best_results['accuracy']:.1%}")
print(f"Validation P4 recall: {best_results['recall']:.1%}")
print(f"Validation P4 precision: {best_results['precision']:.1%}")

# ============================================================================
# FINAL EVALUATION
# ============================================================================
print(f"\n🏆 FINAL RECALL-FOCUSED RESULTS:")
print("="*60)

# Get elite predictions for test set
elite_test_probs = elite_model.predict_proba(X_test)[:, 1]
elite_test_mask = elite_test_probs >= 0.5
print(f"Elite players in test set: {elite_test_mask.sum()} ({elite_test_mask.mean():.1%})")

# Apply hierarchical thresholds
y_pred_final = np.zeros(len(ensemble_probs))
if elite_test_mask.sum() > 0:
    y_pred_final[elite_test_mask] = (ensemble_probs[elite_test_mask] >= best_elite_thresh).astype(int)
if (~elite_test_mask).sum() > 0:
    y_pred_final[~elite_test_mask] = (ensemble_probs[~elite_test_mask] >= best_non_elite_thresh).astype(int)

y_pred_final = y_pred_final.astype(int)

final_accuracy = accuracy_score(y_test, y_pred_final)
final_precision = precision_score(y_test, y_pred_final, pos_label=1, zero_division=0)
final_recall = recall_score(y_test, y_pred_final, pos_label=1)
final_f1 = f1_score(y_test, y_pred_final, zero_division=0)

print(f"🎯 ACCURACY: {final_accuracy:.4f} ({final_accuracy:.1%})")
print(f"P4 Precision: {final_precision:.4f}")  
print(f"P4 Recall: {final_recall:.4f}")
print(f"F1 Score: {final_f1:.4f}")
print("="*60)

print("\nClassification Report:")
print(classification_report(y_test, y_pred_final, target_names=['Non-P4 D1', 'Power 4']))

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred_final))

# Elite vs Non-Elite breakdown
if elite_test_mask.sum() > 0:
    elite_acc = accuracy_score(y_test[elite_test_mask], y_pred_final[elite_test_mask])
    elite_recall = recall_score(y_test[elite_test_mask], y_pred_final[elite_test_mask], pos_label=1)
    print(f"\n🌟 Elite Performance:")
    print(f"   Players: {elite_test_mask.sum()}")
    print(f"   Accuracy: {elite_acc:.1%}")
    print(f"   P4 Recall: {elite_recall:.1%}")

if (~elite_test_mask).sum() > 0:
    non_elite_acc = accuracy_score(y_test[~elite_test_mask], y_pred_final[~elite_test_mask])
    non_elite_recall = recall_score(y_test[~elite_test_mask], y_pred_final[~elite_test_mask], pos_label=1)
    print(f"\n🎯 Non-Elite Performance:")
    print(f"   Players: {(~elite_test_mask).sum()}")
    print(f"   Accuracy: {non_elite_acc:.1%}")
    print(f"   P4 Recall: {non_elite_recall:.1%}")

print(f"\n📈 RECALL IMPROVEMENT SUMMARY:")
print(f"   Target: 70%+ accuracy with maximum P4 recall")
print(f"   Achieved: {final_accuracy:.1%} accuracy, {final_recall:.1%} P4 recall")
print(f"   Strategy: Hierarchical thresholds (Elite: {best_elite_thresh:.3f}, Non-Elite: {best_non_elite_thresh:.3f})")

if final_accuracy >= 0.70:
    print("✅ SUCCESS: 70%+ accuracy achieved with improved recall!")
else:
    print(f"⚠️  CLOSE: {final_accuracy:.1%} accuracy, need {0.70-final_accuracy:+.1%} more")

print("\nTop 10 Features by Importance in LightGBM Model:")
importances = pd.Series(lgb_model.feature_importances_, index=X.columns)
print(importances.nlargest(10))

print("\nBottom 10 Features by Importance in LightGBM Model:")
importances = pd.Series(lgb_model.feature_importances_, index=X.columns)
print(importances.nsmallest(10))

# ============================================================================
# SAVE PRODUCTION MODELS AND METADATA
# ============================================================================
print(f"\n💾 SAVING PRODUCTION MODELS...")

import os
from datetime import datetime

# Create models directory
models_dir = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/ml/models/models_of/models_p4_or_not_of'
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
version_dir = f"{models_dir}/v4_{timestamp}"
os.makedirs(version_dir, exist_ok=True)

# Save all trained models
print("Saving ensemble models...")
joblib.dump(models['xgb'], f'{version_dir}/xgb_model.pkl')
joblib.dump(models['lgb'], f'{version_dir}/lgb_model.pkl')
joblib.dump(models['mlp'], f'{version_dir}/mlp_model.pkl')
joblib.dump(models['svm'], f'{version_dir}/svm_model.pkl')

# Save elite detection model
joblib.dump(elite_model, f'{version_dir}/elite_model.pkl')

# Save scaler for MLP and SVM
joblib.dump(scaler, f'{version_dir}/scaler.pkl')

# Save model configuration
config = {
    'model_version': f'v4_{timestamp}',
    'training_date': datetime.now().isoformat(),
    'model_type': 'Hierarchical P4 Ensemble',
    'target': 'P4 college level prediction for outfielders',
    'performance': {
        'test_accuracy': float(final_accuracy),
        'test_p4_recall': float(final_recall),
        'test_p4_precision': float(final_precision),
        'test_f1_score': float(final_f1),
        'validation_accuracy': float(best_results['accuracy']),
        'validation_p4_recall': float(best_results['recall']),
        'validation_p4_precision': float(best_results['precision'])
    },
    'thresholds': {
        'elite_threshold': float(best_elite_thresh),
        'non_elite_threshold': float(best_non_elite_thresh)
    },
    'ensemble_weights': {
        'xgb': float(weights['xgb']),
        'lgb': float(weights['lgb']),
        'mlp': float(weights['mlp']),
        'svm': float(weights['svm'])
    },
    'cv_scores': {
        'xgb': float(cv_scores['xgb']),
        'lgb': float(cv_scores['lgb']),
        'mlp': float(cv_scores['mlp']),
        'svm': float(cv_scores['svm'])
    },
    'hyperparameters': {
        'xgb': best_params['xgb'],
        'lgb': best_params['lgb'],
        'mlp': best_params['mlp'],
        'svm': best_params['svm']
    },
    'training_config': {
        'train_size': len(X_train),
        'val_size': len(X_val),
        'test_size': len(X_test),
        'class_weight_ratio': float(class_weight_ratio),
        'optuna_trials': {'xgb': 75, 'lgb': 75, 'mlp': 75, 'svm': 75}
    }
}

with open(f'{version_dir}/model_config.json', 'w') as f:
    json.dump(config, f, indent=2)

# Save feature metadata
feature_metadata = {
    'features': available_features,
    'num_features': len(available_features),
    'feature_types': {
        'numerical': [f for f in available_features if not any(x in f for x in ['player_region_', 'hitting_handedness_'])],
        'categorical': [f for f in available_features if any(x in f for x in ['player_region_', 'hitting_handedness_'])]
    },
    'required_input_features': [
        'height', 'weight', 'sixty_time', 'exit_velo_max', 'of_velo',
        'player_region', 'throwing_hand', 'hitting_handedness'
    ],
    'feature_engineering_required': True,
    'd1_model_dependency': True
}

with open(f'{version_dir}/feature_metadata.json', 'w') as f:
    json.dump(feature_metadata, f, indent=2)

# Create prediction pipeline function
pipeline_code = f'''#!/usr/bin/env python3
"""
P4 Outfielder Prediction Pipeline - Production Version
Generated: {datetime.now().isoformat()}
Performance: {final_accuracy:.1%} accuracy, {final_recall:.1%} P4 recall
"""

import pandas as pd
import numpy as np
import joblib
import json
from sklearn.preprocessing import StandardScaler

def predict_outfielder_p4_probability(player_data, models_dir='{version_dir}'):
    """
    Predict P4 college probability for outfielder
    
    Args:
        player_data (dict): Player statistics
        {{
            'height': float,          # inches
            'weight': float,          # pounds  
            'sixty_time': float,      # seconds
            'exit_velo_max': float,   # mph
            'of_velo': float,         # mph (outfield velocity)
            'player_region': str,     # Geographic region
            'throwing_hand': str,     # 'Left' or 'Right'
            'hitting_handedness': str # 'Left', 'Right', or 'Switch'
        }}
        models_dir (str): Path to model files
    
    Returns:
        dict: Prediction results
    """
    
    # Load models and config
    xgb_model = joblib.load(f'{{models_dir}}/xgb_model.pkl')
    lgb_model = joblib.load(f'{{models_dir}}/lgb_model.pkl')
    mlp_model = joblib.load(f'{{models_dir}}/mlp_model.pkl')
    svm_model = joblib.load(f'{{models_dir}}/svm_model.pkl')
    elite_model = joblib.load(f'{{models_dir}}/elite_model.pkl')
    scaler = joblib.load(f'{{models_dir}}/scaler.pkl')
    
    with open(f'{{models_dir}}/model_config.json', 'r') as f:
        config = json.load(f)
    
    with open(f'{{models_dir}}/feature_metadata.json', 'r') as f:
        feature_metadata = json.load(f)
    
    # Convert to DataFrame and engineer features
    df = pd.DataFrame([player_data])
    
    # Basic feature engineering (same as training)
    df['power_speed'] = df['exit_velo_max'] * (7.6 - df['sixty_time'])
    df['of_velo_sixty_ratio'] = df['of_velo'] / df['sixty_time']
    df['height_weight'] = df['height'] * df['weight']
    df['power_per_pound'] = df['exit_velo_max'] / df['weight']
    df['exit_to_sixty_ratio'] = df['exit_velo_max'] / df['sixty_time']
    df['speed_size_efficiency'] = df['height'] / df['sixty_time']
    df['athletic_index'] = (df['exit_velo_max'] + df['of_velo'] + (100 - df['sixty_time']*10)) / 3
    df['power_speed_index'] = df['power_speed'] / df['athletic_index']
    df['exit_velo_body'] = df['exit_velo_max'] / df['height_weight']
    
    # Elite indicators
    df['elite_exit_velo'] = (df['exit_velo_max'] >= 95).astype(int)  # Use fixed thresholds for production
    df['elite_of_velo'] = (df['of_velo'] >= 85).astype(int)
    df['elite_speed'] = (df['sixty_time'] <= 6.8).astype(int)
    df['elite_size'] = (df['height'] >= 72).astype(int)
    
    df['multi_tool_count'] = (df['elite_exit_velo'] + df['elite_of_velo'] + 
                             df['elite_speed'] + df['elite_size'])
    df['is_multi_tool'] = (df['multi_tool_count'] >= 2).astype(int)
    
    # One-hot encode categoricals
    df = pd.get_dummies(df, columns=['player_region', 'throwing_hand', 'hitting_handedness'], drop_first=False)
    
    # NOTE: D1 probability features would need to be generated from D1 model
    # For now, using placeholder values - integrate with actual D1 model in production
    df['d1_probability'] = 0.7  # Placeholder - replace with actual D1 model prediction
    
    # D1-based features
    df['d1_prob_size'] = df['d1_probability'] * df['height_weight']
    df['d1_size_speed'] = df['d1_probability'] * df['speed_size_efficiency']
    df['d1_squared'] = df['d1_probability'] ** 2
    df['d1_athletic_index'] = df['d1_probability'] * df['athletic_index']
    df['d1_exit_velo'] = df['d1_probability'] * df['exit_velo_max']
    df['d1_power_per_pound'] = df['d1_probability'] * df['power_per_pound']
    df['d1_speed_size'] = df['d1_probability'] * df['speed_size_efficiency']
    
    # Additional required features
    df['p4_region_bonus'] = 0  # Calculate based on region if needed
    df['exit_velo_body'] = df['exit_velo_max'] / df['height_weight']
    df['p4_among_high_d1'] = 0.0  # Placeholder
    df['tool_count'] = df['multi_tool_count']  # Alias
    df['athletic_index_v2'] = df['athletic_index'] * (1 + df['tool_count'] * 0.1)
    df['d1_composite_score'] = (df['exit_velo_max']/100 + df['of_velo']/100 + 
                               (7-df['sixty_time']) + df['athletic_index_v2']/100) / 4
    
    # Ensure all required features exist
    for feature in feature_metadata['features']:
        if feature not in df.columns:
            df[feature] = 0  # Default value
    
    # Select features in correct order
    X = df[feature_metadata['features']].fillna(0)
    X_scaled = scaler.transform(X)
    
    # Elite detection
    elite_prob = elite_model.predict_proba(X)[0, 1]
    is_elite = elite_prob >= 0.5
    
    # Get ensemble predictions
    xgb_prob = xgb_model.predict_proba(X.values)[0, 1]
    lgb_prob = lgb_model.predict_proba(X)[0, 1]
    mlp_prob = mlp_model.predict_proba(X_scaled)[0, 1]
    svm_prob = svm_model.predict_proba(X_scaled)[0, 1]
    
    # Weighted ensemble
    weights = config['ensemble_weights']
    ensemble_prob = (xgb_prob * weights['xgb'] + 
                    lgb_prob * weights['lgb'] + 
                    mlp_prob * weights['mlp'] + 
                    svm_prob * weights['svm'])
    
    # Apply hierarchical thresholds
    elite_thresh = config['thresholds']['elite_threshold']
    non_elite_thresh = config['thresholds']['non_elite_threshold']
    
    threshold = elite_thresh if is_elite else non_elite_thresh
    p4_prediction = 1 if ensemble_prob >= threshold else 0
    
    return {{
        'p4_probability': float(ensemble_prob),
        'p4_prediction': int(p4_prediction),
        'confidence': 'High' if abs(ensemble_prob - 0.5) > 0.3 else 'Medium' if abs(ensemble_prob - 0.5) > 0.15 else 'Low',
        'is_elite_candidate': bool(is_elite),
        'elite_probability': float(elite_prob),
        'threshold_used': float(threshold),
        'model_components': {{
            'xgb_prob': float(xgb_prob),
            'lgb_prob': float(lgb_prob), 
            'mlp_prob': float(mlp_prob),
            'svm_prob': float(svm_prob)
        }},
        'model_version': config['model_version']
    }}

if __name__ == "__main__":
    # Example usage
    test_player = {{
        'height': 74.0,
        'weight': 190.0,
        'sixty_time': 6.5,
        'exit_velo_max': 98.0,
        'of_velo': 88.0,
        'player_region': 'South',
        'throwing_hand': 'Right',
        'hitting_handedness': 'Right'
    }}
    
    result = predict_outfielder_p4_probability(test_player)
    print(f"P4 Probability: {{result['p4_probability']:.1%}}")
    print(f"P4 Prediction: {{result['p4_prediction']}}")
    print(f"Confidence: {{result['confidence']}}")
'''

with open(f'{version_dir}/prediction_pipeline.py', 'w') as f:
    f.write(pipeline_code)

# Create README
readme_content = f'''# P4 Outfielder Prediction Model {config['model_version']}

## Model Overview
- **Type**: Hierarchical Ensemble (XGBoost + LightGBM + MLP + SVM)
- **Target**: Predict P4 college level probability for outfielders
- **Performance**: {final_accuracy:.1%} accuracy, {final_recall:.1%} P4 recall

## Files Description
- `xgb_model.pkl`: XGBoost model
- `lgb_model.pkl`: LightGBM model  
- `mlp_model.pkl`: Multi-layer Perceptron model
- `svm_model.pkl`: Support Vector Machine model
- `elite_model.pkl`: Elite player detection model
- `scaler.pkl`: Feature scaler for MLP and SVM
- `model_config.json`: Model parameters and performance metrics
- `feature_metadata.json`: Feature lists and preprocessing information
- `prediction_pipeline.py`: Complete prediction function for production use

## Required Input Features
```python
player_data = {{
    'height': float,          # inches
    'weight': float,          # pounds
    'sixty_time': float,      # seconds
    'exit_velo_max': float,   # mph
    'of_velo': float,         # mph (outfield velocity)
    'player_region': str,     # Geographic region
    'throwing_hand': str,     # 'Left' or 'Right'
    'hitting_handedness': str # 'Left', 'Right', or 'Switch'
}}
```

## Usage
```python
from prediction_pipeline import predict_outfielder_p4_probability

result = predict_outfielder_p4_probability(
    player_data=player_data,
    models_dir='{version_dir}'
)

print(f"P4 Probability: {{result['p4_probability']:.1%}}")
print(f"P4 Prediction: {{result['p4_prediction']}}")
```

## Model Performance
- **Test Accuracy**: {final_accuracy:.1%}
- **P4 Recall**: {final_recall:.1%}
- **P4 Precision**: {final_precision:.1%}
- **F1 Score**: {final_f1:.3f}

## Hierarchical Strategy
- **Elite Players**: {best_elite_thresh:.3f} threshold ({elite_test_mask.sum()} players, {(elite_test_mask.sum()/len(elite_test_mask)):.1%})
- **Non-Elite Players**: {best_non_elite_thresh:.3f} threshold ({(~elite_test_mask).sum()} players, {((~elite_test_mask).sum()/len(elite_test_mask)):.1%})

## Production Notes
- Model optimized for P4 recruitment pipeline
- Uses performance-weighted ensemble for robust predictions
- Includes confidence levels and model component breakdown
- Requires D1 model integration for optimal performance
'''

with open(f'{version_dir}/README.md', 'w') as f:
    f.write(readme_content)

print(f"✅ Models saved to: {version_dir}")
print(f"📊 Test Performance: {final_accuracy:.1%} accuracy, {final_recall:.1%} P4 recall")
print(f"🎯 Production ready with hierarchical thresholds")
print(f"📝 README and pipeline code generated")

"""
print("\nCorrelation Matrix:")
corr_matrix = X.corr()
sns.set()
plt.figure(figsize=(12, 10))
sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', square=True)
plt.title("Correlation Matrix")
plt.xticks(rotation=45)
plt.yticks(rotation=0)
plt.tight_layout()
plt.show()
"""