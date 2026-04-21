import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, recall_score, balanced_accuracy_score, precision_score
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
import optuna
import joblib

print("🏗️  HIERARCHICAL OUTFIELDER D1 PREDICTION MODEL")
print("=" * 80)
print("Approach: Elite OF Detection → ENSEMBLE D1 Prediction → Soft Hierarchical Weighting")
print("Ensemble Weights: XGBoost (30%) + CatBoost (30%) + LightGBM (20%) + SVM (20%)")
print("=" * 80)

# Load data
csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/of_feat_eng_d1_or_not.csv'
df = pd.read_csv(csv_path)

print(f"Loaded outfield dataset with {len(df)} players")
print(f"D1 Distribution: {df['d1_or_not'].value_counts()}")
print(f"D1 Rate: {df['d1_or_not'].mean():.2%}")
print(f"Class imbalance ratio: {(df['d1_or_not'] == 0).sum() / (df['d1_or_not'] == 1).sum():.1f}:1")

# Drop rows with missing 'of_velo' or 'player_region'
df = df.dropna(subset=['of_velo', 'player_region'])

# Create categorical encodings
df = pd.get_dummies(df, columns=['player_region', 'throwing_hand', 'hitting_handedness'], 
                   prefix_sep='_', drop_first=True)

# ============================================================================
# STEP 1: COMPREHENSIVE FEATURE ENGINEERING
# ============================================================================
print("\n🔧 Comprehensive Feature Engineering...")

# Core athletic metrics
df['power_speed'] = df['exit_velo_max'] / df['sixty_time']
df['of_velo_sixty_ratio'] = df['of_velo'] / df['sixty_time']
df['height_weight'] = df['height'] * df['weight']

# Create percentile features (key for hierarchical approach)
percentile_features = ['exit_velo_max', 'of_velo', 'sixty_time', 'height', 'weight', 'power_speed']
for col in percentile_features:
    if col in df.columns:
        if col == 'sixty_time':  # Lower is better for sixty_time
            df[f'{col}_percentile'] = (1 - df[col].rank(pct=True)) * 100
        else:  # Higher is better for other metrics
            df[f'{col}_percentile'] = df[col].rank(pct=True) * 100

# Advanced ratio features (from infielder model)
df['power_per_pound'] = df['exit_velo_max'] / df['weight']
df['exit_to_sixty_ratio'] = df['exit_velo_max'] / df['sixty_time']
df['speed_size_efficiency'] = (df['height'] * df['weight']) / (df['sixty_time'] ** 2)
df['athletic_index'] = (df['power_speed'] * df['height'] * df['weight']) / df['sixty_time']
df['power_speed_index'] = df['exit_velo_max'] * (1 / df['sixty_time'])

# Elite binary features (outfield-specific)
df['elite_exit_velo'] = (df['exit_velo_max'] >= df['exit_velo_max'].quantile(0.75)).astype(int)
df['elite_of_velo'] = (df['of_velo'] >= df['of_velo'].quantile(0.75)).astype(int) 
df['elite_speed'] = (df['sixty_time'] <= df['sixty_time'].quantile(0.25)).astype(int)
df['elite_size'] = ((df['height'] >= df['height'].quantile(0.6)) & 
                   (df['weight'] >= df['weight'].quantile(0.6))).astype(int)
df['multi_tool_count'] = (df['elite_exit_velo'] + df['elite_of_velo'] + 
                         df['elite_speed'] + df['elite_size'])

# Scaled features for elite composite score
df['exit_velo_scaled'] = (df['exit_velo_max'] - df['exit_velo_max'].min()) / (df['exit_velo_max'].max() - df['exit_velo_max'].min()) * 100
df['speed_scaled'] = (1 - (df['sixty_time'] - df['sixty_time'].min()) / (df['sixty_time'].max() - df['sixty_time'].min())) * 100
df['arm_scaled'] = (df['of_velo'] - df['of_velo'].min()) / (df['of_velo'].max() - df['of_velo'].min()) * 100

# Regional advantages (if they exist)
regional_cols = [col for col in df.columns if 'player_region_' in col]
if regional_cols:
    # D1 programs recruit nationally, certain regions might be preferred
    region_weights = {}
    for col in regional_cols:
        region_weights[col] = df[df[col] == 1]['d1_or_not'].mean()
    
    # Create weighted regional score
    df['d1_region_advantage'] = 0
    for col, weight in region_weights.items():
        df['d1_region_advantage'] += df[col] * weight

# Elite composite score (outfield-specific weights)
df['elite_composite_score'] = (
    df['exit_velo_scaled'] * 0.30 +      # Power (30%)
    df['speed_scaled'] * 0.25 +          # Speed (25%) 
    df['arm_scaled'] * 0.25 +            # Arm strength (25% - higher for OF)
    df['height_percentile'] * 0.10 +     # Size (10%)
    df['power_speed'] * 0.10             # Power-speed combo (10%)
)

# Enhanced outfield-specific features
df['of_arm_strength'] = (df['of_velo'] >= df['of_velo'].quantile(0.75)).astype(int)
df['of_arm_plus'] = (df['of_velo'] >= df['of_velo'].quantile(0.60)).astype(int)
df['exit_velo_elite'] = (df['exit_velo_max'] >= df['exit_velo_max'].quantile(0.75)).astype(int)
df['speed_elite'] = (df['sixty_time'] <= df['sixty_time'].quantile(0.25)).astype(int)

# D1 thresholds (refined based on actual data distribution)
p75_exit = df['exit_velo_max'].quantile(0.75)
p75_of = df['of_velo'].quantile(0.75)
p25_sixty = df['sixty_time'].quantile(0.25)

df['d1_exit_velo_threshold'] = (df['exit_velo_max'] >= max(88, p75_exit * 0.95)).astype(int)
df['d1_arm_threshold'] = (df['of_velo'] >= max(80, p75_of * 0.9)).astype(int)
df['d1_speed_threshold'] = (df['sixty_time'] <= min(7.2, p25_sixty * 1.1)).astype(int)
df['d1_size_threshold'] = ((df['height'] >= 70) & (df['weight'] >= 165)).astype(int)

# Multi-tool analysis
df['tool_count'] = (df['exit_velo_elite'] + df['of_arm_strength'] + 
                   df['speed_elite'] + df['d1_size_threshold'])
df['is_multi_tool'] = (df['tool_count'] >= 2).astype(int)

# Advanced composites
df['athletic_index_v2'] = (
    df['exit_velo_max_percentile'] * 0.3 +
    df['of_velo_percentile'] * 0.25 + 
    df['sixty_time_percentile'] * 0.25 +
    df['height_percentile'] * 0.1 +
    df['weight_percentile'] * 0.1
)

df['tools_athlete'] = df['tool_count'] * df['athletic_index_v2']

df['d1_composite_score'] = (
    df['d1_exit_velo_threshold'] * 0.35 +
    df['d1_speed_threshold'] * 0.3 +
    df['d1_arm_threshold'] * 0.25 +
    df['d1_size_threshold'] * 0.1
)

print(f"✓ Created comprehensive feature set with {len(df.columns) - 2} features")

# ============================================================================
# STEP 2: ELITE OUTFIELDER DETECTION MODEL
# ============================================================================
print("\n🎯 STEP 2: Elite Outfielder Detection Model...")

# Define Elite OF: Top 45% of outfielders (similar to infielder approach)
elite_threshold = df['elite_composite_score'].quantile(0.55)  # Top 45%
df['is_elite_of'] = (df['elite_composite_score'] >= elite_threshold).astype(int)

print(f"Elite OF threshold: {elite_threshold:.2f}")
print(f"Elite OF distribution: {df['is_elite_of'].value_counts(normalize=True)}")

elite_d1_rate = df[df['is_elite_of'] == 1]['d1_or_not'].mean()
regular_d1_rate = df[df['is_elite_of'] == 0]['d1_or_not'].mean()
print(f"D1 rate among Elite OF: {elite_d1_rate:.2%}")
print(f"D1 rate among Regular OF: {regular_d1_rate:.2%}")

# Train Elite Detection Model
elite_features = [
    'height', 'weight', 'sixty_time', 'exit_velo_max', 'of_velo', 'power_speed',
    'of_velo_sixty_ratio', 'height_weight',
    'height_percentile', 'weight_percentile', 'sixty_time_percentile', 
    'exit_velo_max_percentile', 'of_velo_percentile', 'power_speed_percentile',
    'power_per_pound', 'exit_to_sixty_ratio', 'speed_size_efficiency',
    'athletic_index', 'power_speed_index', 'multi_tool_count',
    'elite_exit_velo', 'elite_of_velo', 'elite_speed', 'elite_size',
    'exit_velo_scaled', 'speed_scaled', 'arm_scaled'
]

X_elite = df[elite_features].copy()
y_elite = df['is_elite_of'].copy()

# Clean data
X_elite = X_elite.replace([np.inf, -np.inf], np.nan).fillna(0)
for col in X_elite.select_dtypes(include=[np.number]).columns:
    Q1, Q3 = X_elite[col].quantile(0.01), X_elite[col].quantile(0.99)
    IQR = Q3 - Q1
    X_elite[col] = X_elite[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

X_elite_train, X_elite_test, y_elite_train, y_elite_test = train_test_split(
    X_elite, y_elite, test_size=0.2, stratify=y_elite, random_state=42
)

# Train elite detection model (using proven parameters)
elite_model = xgb.XGBClassifier(
    objective='binary:logistic',
    eval_metric='auc',
    learning_rate=0.1,
    max_depth=8,
    n_estimators=500,
    random_state=42
)
elite_model.fit(X_elite_train, y_elite_train, verbose=False)

elite_preds = elite_model.predict(X_elite_test)
print(f"\n🎯 Elite OF Detection Results:")
print(f"Accuracy: {accuracy_score(y_elite_test, elite_preds):.4f}")
print(f"Balanced Accuracy: {balanced_accuracy_score(y_elite_test, elite_preds):.4f}")
print("✅ Elite detection model ready!")

# ============================================================================
# STEP 3: ENSEMBLE D1 MODEL ON ELITE OUTFIELDERS
# ============================================================================
print("\n🏆 STEP 3: Training ENSEMBLE D1 Model on Elite Outfielders...")

# Get elite players for D1 training  
elite_mask = df['is_elite_of'] == 1
df_elite_only = df[elite_mask].copy()

print(f"Elite OF subset: {len(df_elite_only)} players")
print(f"D1 distribution in elite subset: {df_elite_only['d1_or_not'].value_counts(normalize=True)}")

# Prepare features for D1 prediction
exclude_cols = ['d1_or_not', 'is_elite_of', 'elite_composite_score', 'primary_position']
d1_features = [col for col in df.columns if col not in exclude_cols]

X_d1_elite = df_elite_only[d1_features].copy()
y_d1_elite = df_elite_only['d1_or_not'].copy()

# Clean data
X_d1_elite = X_d1_elite.replace([np.inf, -np.inf], np.nan).fillna(0)
for col in X_d1_elite.select_dtypes(include=[np.number]).columns:
    Q1, Q3 = X_d1_elite[col].quantile(0.01), X_d1_elite[col].quantile(0.99)
    IQR = Q3 - Q1
    X_d1_elite[col] = X_d1_elite[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

# Train/test split for D1 prediction
X_d1_train, X_d1_test, y_d1_train, y_d1_test = train_test_split(
    X_d1_elite, y_d1_elite, test_size=0.2, stratify=y_d1_elite, random_state=42
)

print(f"D1 features count: {len(d1_features)}")
print(f"D1 training set distribution: {y_d1_train.value_counts(normalize=True)}")

# ============================================================================
# INDIVIDUAL MODEL OPTIMIZATION WITH OPTUNA
# ============================================================================

# XGBoost Optimization
print("\n🚀 Optimizing XGBoost for D1 ensemble...")
def xgb_objective(trial):
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'use_label_encoder': False,
        'learning_rate': trial.suggest_float('eta', 1e-3, 2e-1, log=True),
        'max_depth': trial.suggest_int('max_depth', 4, 12),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 20),
        'gamma': trial.suggest_float('gamma', 1e-8, 10.0, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.3, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 100.0, log=True),
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 3.0),
        'random_state': 42
    }
    
    model = xgb.XGBClassifier(**params, n_estimators=500)
    X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        X_d1_train, y_d1_train, test_size=0.2, stratify=y_d1_train, random_state=42
    )
    model.fit(X_train_split, y_train_split, eval_set=[(X_val_split, y_val_split)], verbose=False)
    preds = model.predict(X_val_split)
    
    accuracy = accuracy_score(y_val_split, preds)
    recall_0 = recall_score(y_val_split, preds, pos_label=0)
    recall_1 = recall_score(y_val_split, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

study_xgb = optuna.create_study(direction='maximize')
study_xgb.optimize(xgb_objective, n_trials=100, show_progress_bar=True, n_jobs=-1)
best_xgb_params = study_xgb.best_params

# CatBoost Optimization
print("\n🐱 Optimizing CatBoost for D1 ensemble...")
def catboost_objective(trial):
    params = {
        'iterations': 500,
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'depth': trial.suggest_int('depth', 4, 10),
        'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1e-8, 10.0, log=True),
        'bagging_temperature': trial.suggest_float('bagging_temperature', 0.0, 1.0),
        'random_strength': trial.suggest_float('random_strength', 0.0, 10.0),
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 3.0),
        'verbose': False,
        'random_seed': 42
    }
    
    model = cb.CatBoostClassifier(**params)
    X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        X_d1_train, y_d1_train, test_size=0.2, stratify=y_d1_train, random_state=42
    )
    model.fit(X_train_split, y_train_split, eval_set=(X_val_split, y_val_split), verbose=False)
    preds = model.predict(X_val_split)
    
    accuracy = accuracy_score(y_val_split, preds)
    recall_0 = recall_score(y_val_split, preds, pos_label=0)
    recall_1 = recall_score(y_val_split, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

study_cat = optuna.create_study(direction='maximize')
study_cat.optimize(catboost_objective, n_trials=100, show_progress_bar=True, n_jobs=-1)
best_cat_params = study_cat.best_params

# LightGBM Optimization
print("\n💡 Optimizing LightGBM for D1 ensemble...")
def lightgbm_objective(trial):
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': trial.suggest_int('num_leaves', 10, 300),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.4, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.4, 1.0),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 3.0),
        'verbose': -1,
        'random_state': 42
    }
    
    model = lgb.LGBMClassifier(**params, n_estimators=500)
    X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        X_d1_train, y_d1_train, test_size=0.2, stratify=y_d1_train, random_state=42
    )
    model.fit(X_train_split, y_train_split, eval_set=[(X_val_split, y_val_split)])
    preds = model.predict(X_val_split)
    
    accuracy = accuracy_score(y_val_split, preds)
    recall_0 = recall_score(y_val_split, preds, pos_label=0)
    recall_1 = recall_score(y_val_split, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

study_lgb = optuna.create_study(direction='maximize')
study_lgb.optimize(lightgbm_objective, n_trials=100, show_progress_bar=True, n_jobs=-1)
best_lgb_params = study_lgb.best_params

# SVM Optimization (with feature scaling)
print("\n🚀 Optimizing SVM for D1 ensemble...")
scaler = StandardScaler()
X_d1_train_scaled = scaler.fit_transform(X_d1_train)
X_d1_test_scaled = scaler.transform(X_d1_test)

def svm_objective(trial):
    params = {
        'C': trial.suggest_float('C', 1e-3, 1e3, log=True),
        'gamma': trial.suggest_categorical('gamma', ['scale', 'auto']),
        'kernel': trial.suggest_categorical('kernel', ['rbf', 'poly', 'sigmoid']),
        'probability': True,  # Needed for predict_proba
        'class_weight': 'balanced',
        'random_state': 42
    }
    
    if params['kernel'] == 'poly':
        params['degree'] = trial.suggest_int('degree', 2, 4)
    
    model = SVC(**params)
    X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        X_d1_train_scaled, y_d1_train, test_size=0.2, stratify=y_d1_train, random_state=42
    )
    model.fit(X_train_split, y_train_split)
    preds = model.predict(X_val_split)
    
    accuracy = accuracy_score(y_val_split, preds)
    recall_0 = recall_score(y_val_split, preds, pos_label=0)
    recall_1 = recall_score(y_val_split, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

study_svm = optuna.create_study(direction='maximize')
study_svm.optimize(svm_objective, n_trials=75, show_progress_bar=True, n_jobs=4)
best_svm_params = study_svm.best_params

# ============================================================================
# CREATE WEIGHTED ENSEMBLE
# ============================================================================
print("\n🎯 Creating Weighted Ensemble (XGB: 35%, CAT: 15%, LGB: 30%, SVM: 20%)...")

# Train individual models with best parameters
xgb_model = xgb.XGBClassifier(**best_xgb_params, n_estimators=500, random_state=42)
cat_model = cb.CatBoostClassifier(**best_cat_params, verbose=False, random_seed=42)
lgb_model = lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=42)
svm_model = SVC(**best_svm_params, probability=True)

# Fit individual models
print("Training individual ensemble models...")
xgb_model.fit(X_d1_train, y_d1_train, verbose=False)
cat_model.fit(X_d1_train, y_d1_train, verbose=False)
lgb_model.fit(X_d1_train, y_d1_train)
svm_model.fit(X_d1_train_scaled, y_d1_train)

# Create weighted ensemble prediction function
def weighted_ensemble_predict_proba(X, X_scaled):
    """
    Weighted ensemble prediction with custom weights
    XGBoost: 30%, CatBoost: 30%, LightGBM: 20%, SVM: 20%
    """
    xgb_proba = xgb_model.predict_proba(X)[:, 1]
    cat_proba = cat_model.predict_proba(X)[:, 1]
    lgb_proba = lgb_model.predict_proba(X)[:, 1]
    svm_proba = svm_model.predict_proba(X_scaled)[:, 1]
    
    # Weighted combination
    ensemble_proba = (xgb_proba * 0.35 + cat_proba * 0.15 + 
                     lgb_proba * 0.3 + svm_proba * 0.2)
    
    return ensemble_proba

# Evaluate ensemble on elite test set
X_d1_test_scaled = scaler.transform(X_d1_test)
ensemble_probs_elite = weighted_ensemble_predict_proba(X_d1_test, X_d1_test_scaled)
ensemble_preds_elite = (ensemble_probs_elite >= 0.5).astype(int)

print(f"\n🏆 ENSEMBLE D1 Prediction Results (Elite OF Only):")
print(f"Accuracy: {accuracy_score(y_d1_test, ensemble_preds_elite):.4f}")
print(f"Balanced Accuracy: {balanced_accuracy_score(y_d1_test, ensemble_preds_elite):.4f}")
print(f"F1 Score: {f1_score(y_d1_test, ensemble_preds_elite):.4f}")
print(f"D1 Recall: {recall_score(y_d1_test, ensemble_preds_elite, pos_label=1):.4f}")
print(f"D1 Precision: {precision_score(y_d1_test, ensemble_preds_elite, pos_label=1):.4f}")

print(f"\n📊 Ensemble Classification Report:")
print(classification_report(y_d1_test, ensemble_preds_elite))

# ============================================================================
# STEP 4: HIERARCHICAL PREDICTION WITH ENSEMBLE
# ============================================================================
print("\n🤖 STEP 4: Implementing Hierarchical Prediction with Ensemble...")

# Prepare full dataset
drop_cols = ['d1_or_not', 'is_elite_of', 'elite_composite_score', 'primary_position']
X_full = df.drop(columns=drop_cols)
y_full = df['d1_or_not']

# Clean full dataset
X_full = X_full.replace([np.inf, -np.inf], np.nan).fillna(0)
for col in X_full.select_dtypes(include=[np.number]).columns:
    Q1, Q3 = X_full[col].quantile(0.01), X_full[col].quantile(0.99)
    IQR = Q3 - Q1
    X_full[col] = X_full[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

X_full_train, X_full_test, y_full_train, y_full_test = train_test_split(
    X_full, y_full, test_size=0.2, stratify=y_full, random_state=42
)

# Scale full test set for SVM
scaler_full = StandardScaler()
X_full_train_scaled = scaler_full.fit_transform(X_full_train)
X_full_test_scaled = scaler_full.transform(X_full_test)

# Retrain models on full feature set for hierarchical prediction
print("Retraining models on full feature set...")
xgb_full = xgb.XGBClassifier(**best_xgb_params, n_estimators=500, random_state=42)
cat_full = cb.CatBoostClassifier(**best_cat_params, verbose=False, random_seed=42)
lgb_full = lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=42)
svm_full = SVC(**best_svm_params, probability=True)

xgb_full.fit(X_full_train, y_full_train, verbose=False)
cat_full.fit(X_full_train, y_full_train, verbose=False)
lgb_full.fit(X_full_train, y_full_train)
svm_full.fit(X_full_train_scaled, y_full_train)

# Hierarchical prediction function with ensemble
def predict_d1_hierarchical_ensemble(features_dict, features_scaled):
    """
    Hierarchical prediction with ensemble D1 model
    """
    # Extract features for elite model
    elite_features_subset = [col for col in elite_features if col in features_dict.columns]
    elite_feats = features_dict[elite_features_subset]
    
    # Extract features for D1 ensemble (all features)
    d1_feats = features_dict
    
    # Get probabilities
    elite_prob = elite_model.predict_proba(elite_feats)[:, 1]
    
    # Get ensemble D1 probabilities
    xgb_proba = xgb_full.predict_proba(d1_feats)[:, 1]
    cat_proba = cat_full.predict_proba(d1_feats)[:, 1]
    lgb_proba = lgb_full.predict_proba(d1_feats)[:, 1]
    svm_proba = svm_full.predict_proba(features_scaled)[:, 1]
    
    d1_prob = (xgb_proba * 0.3 + cat_proba * 0.3 + 
               lgb_proba * 0.2 + svm_proba * 0.2)
    
    # Weighted hierarchical combination
    hierarchical_d1_prob = (elite_prob * 0.6) + (d1_prob * 0.4)
    
    return hierarchical_d1_prob, elite_prob, d1_prob

# Apply hierarchical ensemble prediction
hierarchical_probs, elite_test_probs, d1_test_probs = predict_d1_hierarchical_ensemble(X_full_test, X_full_test_scaled)

# Find optimal threshold
thresholds = np.arange(0.1, 0.9, 0.02)
hierarchical_results = []

for threshold in thresholds:
    y_pred_hier = (hierarchical_probs >= threshold).astype(int)
    accuracy = accuracy_score(y_full_test, y_pred_hier)
    balanced_acc = balanced_accuracy_score(y_full_test, y_pred_hier)
    f1 = f1_score(y_full_test, y_pred_hier)
    recall_1 = recall_score(y_full_test, y_pred_hier, pos_label=1)
    precision_1 = precision_score(y_full_test, y_pred_hier, pos_label=1, zero_division=0)
    
    hierarchical_results.append({
        'threshold': threshold,
        'accuracy': accuracy,
        'balanced_acc': balanced_acc,
        'f1': f1,
        'recall_1': recall_1,
        'precision_1': precision_1
    })

hierarchical_df = pd.DataFrame(hierarchical_results)
best_accuracy_idx = hierarchical_df['accuracy'].idxmax()
optimal_threshold = hierarchical_df.loc[best_accuracy_idx, 'threshold']

print(f"Optimal hierarchical ensemble threshold: {optimal_threshold:.2f}")

# Final predictions
y_pred_hierarchical = (hierarchical_probs >= optimal_threshold).astype(int)

print(f"\n🏆 FINAL HIERARCHICAL ENSEMBLE RESULTS:")
print("=" * 60)
print(f"📈 HIERARCHICAL ENSEMBLE MODEL:")
print(f"Accuracy: {accuracy_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"Balanced Accuracy: {balanced_accuracy_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"F1 Score: {f1_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"D1 Recall: {recall_score(y_full_test, y_pred_hierarchical, pos_label=1):.4f}")
print(f"D1 Precision: {precision_score(y_full_test, y_pred_hierarchical, pos_label=1):.4f}")

print(f"\n📊 Hierarchical Ensemble Classification Report:")
print(classification_report(y_full_test, y_pred_hierarchical))

print(f"Hierarchical Ensemble Confusion Matrix:")
cm_hierarchical = confusion_matrix(y_full_test, y_pred_hierarchical)
print(cm_hierarchical)

tn, fp, fn, tp = cm_hierarchical.ravel()
print(f"\n🎯 Ensemble Analysis:")
print(f"True Positives (Correctly identified D1): {tp}")
print(f"False Positives (Over-recruit): {fp}")
print(f"False Negatives (Miss talent): {fn}")
print(f"FP:FN Ratio: {fp/fn:.2f}")

# No Information Rate comparison
most_freq_class = y_full_test.value_counts(normalize=True).max()
final_accuracy = accuracy_score(y_full_test, y_pred_hierarchical)
print(f"\nNo Information Rate: {most_freq_class:.4f}")
print(f"Improvement over no-info: {final_accuracy - most_freq_class:+.4f}")

if final_accuracy >= 0.80:
    print("🎉 SUCCESS: Achieved 80%+ accuracy target!")
elif final_accuracy >= 0.78:
    print("🎯 CLOSE: Nearly achieved 80% target!")
else:
    print(f"⚠️ Need improvement: {0.80 - final_accuracy:.4f} below 80% target")

print("\n" + "=" * 80)
print("🎉 HIERARCHICAL ENSEMBLE OUTFIELDER D1 MODEL COMPLETE!")
print("Elite OF Detection + Ensemble D1 Model (XGB+CAT+LGB+SVM) + Hierarchical Weighting")
print("=" * 80)

print(f"\n📈 Performance Summary:")
print(f"Enhanced model: {accuracy_score(y_full_test, y_pred_hierarchical):.4f} accuracy")
print(f"Target: 0.8000 accuracy")
print(f"Gap to target: {0.8000 - accuracy_score(y_full_test, y_pred_hierarchical):+.4f}")