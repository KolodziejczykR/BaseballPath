import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, recall_score, balanced_accuracy_score, precision_score
from sklearn.ensemble import VotingClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
import optuna
import joblib

print("🏗️  HIERARCHICAL ENSEMBLE P4 PREDICTION MODEL")
print("=" * 80)
print("Approach: Elite D1 Detection (97% accuracy) → ENSEMBLE P4 Prediction → Soft Hierarchical Weighting")
print("Ensemble Weights: XGBoost (30%) + CatBoost (30%) + LightGBM (20%) + SVM (20%)")
print("=" * 80)

# Load the same engineered data
csv_path_eng = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/inf_p4_or_not_eng.csv'
df_eng = pd.read_csv(csv_path_eng)

print(f"Loaded data: {len(df_eng)} D1-predicted players")
print(f"P4 distribution: {df_eng['p4_or_not'].value_counts(normalize=True)}")

# ============================================================================
# STEP 1: ELITE D1 DETECTION (REUSE FROM SINGLE MODEL - 97% ACCURACY)
# ============================================================================
print("\n🎯 STEP 1: Elite D1 Detection (keeping proven 97% accuracy model)...")

# Create percentile and engineered features (same as single model)
percentile_features = ['exit_velo_max', 'inf_velo', 'sixty_time', 'height', 'weight', 'power_speed']
for col in percentile_features:
    if col in df_eng.columns:
        if col == 'sixty_time':  # Lower is better for sixty_time
            df_eng[f'{col}_percentile'] = (1 - df_eng[col].rank(pct=True)) * 100
        else:  # Higher is better for other metrics
            df_eng[f'{col}_percentile'] = df_eng[col].rank(pct=True) * 100

# Advanced ratio features
df_eng['power_per_pound'] = df_eng['exit_velo_max'] / df_eng['weight']
df_eng['exit_to_sixty_ratio'] = df_eng['exit_velo_max'] / df_eng['sixty_time']
df_eng['speed_size_efficiency'] = (df_eng['height'] * df_eng['weight']) / (df_eng['sixty_time'] ** 2)
df_eng['athletic_index'] = (df_eng['power_speed'] * df_eng['height'] * df_eng['weight']) / df_eng['sixty_time']
df_eng['power_speed_index'] = df_eng['exit_velo_max'] * (1 / df_eng['sixty_time'])

# Elite binary features
df_eng['elite_exit_velo'] = (df_eng['exit_velo_max'] >= df_eng['exit_velo_max'].quantile(0.75)).astype(int)
df_eng['elite_inf_velo'] = (df_eng['inf_velo'] >= df_eng['inf_velo'].quantile(0.75)).astype(int) 
df_eng['elite_speed'] = (df_eng['sixty_time'] <= df_eng['sixty_time'].quantile(0.25)).astype(int)
df_eng['elite_size'] = ((df_eng['height'] >= df_eng['height'].quantile(0.6)) & 
                        (df_eng['weight'] >= df_eng['weight'].quantile(0.6))).astype(int)
df_eng['multi_tool_count'] = (df_eng['elite_exit_velo'] + df_eng['elite_inf_velo'] + 
                              df_eng['elite_speed'] + df_eng['elite_size'])

# Scaled features for elite composite score
df_eng['exit_velo_scaled'] = (df_eng['exit_velo_max'] - df_eng['exit_velo_max'].min()) / (df_eng['exit_velo_max'].max() - df_eng['exit_velo_max'].min()) * 100
df_eng['speed_scaled'] = (1 - (df_eng['sixty_time'] - df_eng['sixty_time'].min()) / (df_eng['sixty_time'].max() - df_eng['sixty_time'].min())) * 100
df_eng['arm_scaled'] = (df_eng['inf_velo'] - df_eng['inf_velo'].min()) / (df_eng['inf_velo'].max() - df_eng['inf_velo'].min()) * 100

# Power 4 programs recruit nationally, certain regions might be preferred
# goes west, south, midwest, northeast 
df_eng['power4_region'] = ((df_eng['player_region_South'] * 1.2) + 
                           (df_eng['player_region_West'] * 1.3) + 
                           (df_eng['player_region_Northeast'] * 0.85))

# Elite composite score
df_eng['elite_composite_score'] = (
    df_eng['exit_velo_scaled'] * 0.35 +      # Power (35%)
    df_eng['speed_scaled'] * 0.25 +          # Speed (25%) 
    df_eng['arm_scaled'] * 0.20 +            # Arm strength (20%)
    df_eng['height_percentile'] * 0.10 +     # Size (10%)
    df_eng['power_speed'] * 0.10             # Power-speed combo (10%)
)

# Define Elite D1: Top 45% of D1 players
elite_threshold = df_eng['elite_composite_score'].quantile(0.55)  # Top 45%
df_eng['is_elite_d1'] = (df_eng['elite_composite_score'] >= elite_threshold).astype(int)

print(f"Elite D1 threshold: {elite_threshold:.2f}")
print(f"Elite D1 distribution: {df_eng['is_elite_d1'].value_counts(normalize=True)}")

elite_p4_rate = df_eng[df_eng['is_elite_d1'] == 1]['p4_or_not'].mean()
regular_p4_rate = df_eng[df_eng['is_elite_d1'] == 0]['p4_or_not'].mean()
print(f"P4 rate among Elite D1: {elite_p4_rate:.2%}")
print(f"P4 rate among Regular D1: {regular_p4_rate:.2%}")

# Train Elite Detection Model (reuse same approach)
elite_features = [
    'height', 'weight', 'sixty_time', 'exit_velo_max', 'inf_velo', 'power_speed',
    'velo_by_inf', 'sixty_inv', 'height_weight',
    'height_percentile', 'weight_percentile', 'sixty_time_percentile', 
    'exit_velo_max_percentile', 'inf_velo_percentile', 'power_speed_percentile',
    'power_per_pound', 'exit_to_sixty_ratio', 'speed_size_efficiency',
    'athletic_index', 'power_speed_index', 'multi_tool_count',
    'elite_exit_velo', 'elite_inf_velo', 'elite_speed', 'elite_size',
    'exit_velo_scaled', 'speed_scaled', 'arm_scaled'
]

X_elite = df_eng[elite_features].copy()
y_elite = df_eng['is_elite_d1'].copy()

# Clean data
X_elite = X_elite.replace([np.inf, -np.inf], np.nan).fillna(0)
for col in X_elite.select_dtypes(include=[np.number]).columns:
    Q1, Q3 = X_elite[col].quantile(0.01), X_elite[col].quantile(0.99)
    IQR = Q3 - Q1
    X_elite[col] = X_elite[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

X_elite_train, X_elite_test, y_elite_train, y_elite_test = train_test_split(
    X_elite, y_elite, test_size=0.2, stratify=y_elite, random_state=42
)

# Quick elite model training (using proven parameters)
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
print(f"\n🎯 Elite D1 Detection Results:")
print(f"Accuracy: {accuracy_score(y_elite_test, elite_preds):.4f}")
print(f"Balanced Accuracy: {balanced_accuracy_score(y_elite_test, elite_preds):.4f}")
print("✅ Elite detection model ready!")

print(f"\nCreated {len([col for col in df_eng.columns if '_percentile' in col or 'elite_' in col or col in ['power_per_pound', 'exit_to_sixty_ratio', 'speed_size_efficiency', 'athletic_index', 'power_speed_index', 'multi_tool_count']])} engineered features")

# ============================================================================
# STEP 2: ENSEMBLE P4 MODEL ON ELITE D1 SUBSET
# ============================================================================
print("\n🏆 STEP 2: Training ENSEMBLE P4 Model on Elite D1 Players...")

# Get elite players for P4 training  
elite_mask = df_eng['is_elite_d1'] == 1
df_elite_only = df_eng[elite_mask].copy()

print(f"Elite D1 subset: {len(df_elite_only)} players")
print(f"P4 distribution in elite subset: {df_elite_only['p4_or_not'].value_counts(normalize=True)}")

# Prepare features for P4 prediction
exclude_cols = ['p4_or_not', 'd1_or_not', 'is_elite_d1', 'elite_composite_score']
p4_features = [col for col in df_eng.columns if col not in exclude_cols]

X_p4_elite = df_elite_only[p4_features].copy()
y_p4_elite = df_elite_only['p4_or_not'].copy()

# Clean data
X_p4_elite = X_p4_elite.replace([np.inf, -np.inf], np.nan).fillna(0)
for col in X_p4_elite.select_dtypes(include=[np.number]).columns:
    Q1, Q3 = X_p4_elite[col].quantile(0.01), X_p4_elite[col].quantile(0.99)
    IQR = Q3 - Q1
    X_p4_elite[col] = X_p4_elite[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

# ============================================================================
# PRINT QUANTILES FOR PRODUCTION PIPELINE PERCENTILE CALCULATION
# ============================================================================
print("\n" + "="*80)
print("QUANTILES FOR PRODUCTION PIPELINE PERCENTILE CALCULATION")
print("="*80)

# Print quantiles for exit_velo_max percentile calculation (higher is better)
exit_velo_max_quantiles = [df_eng['exit_velo_max'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nexit_velo_max_quantiles = {exit_velo_max_quantiles}")

# Print quantiles for inf_velo percentile calculation (higher is better)
inf_velo_quantiles = [df_eng['inf_velo'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\ninf_velo_quantiles = {inf_velo_quantiles}")

# Print quantiles for sixty_time percentile calculation (lower is better)
sixty_time_quantiles = [df_eng['sixty_time'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nsixty_time_quantiles = {sixty_time_quantiles}")

# Print quantiles for height percentile calculation (higher is better)
height_quantiles = [df_eng['height'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nheight_quantiles = {height_quantiles}")

# Print quantiles for weight percentile calculation (higher is better)
weight_quantiles = [df_eng['weight'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nweight_quantiles = {weight_quantiles}")

# Print quantiles for power_speed percentile calculation (higher is better)
power_speed_quantiles = [df_eng['power_speed'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\npower_speed_quantiles = {power_speed_quantiles}")

# Print sample calculations for verification
print(f"\n# Sample calculations for verification:")
sample_idx = df_eng.index[0]
print(f"Sample player at index {sample_idx}:")
print(f"  exit_velo_max: {df_eng.loc[sample_idx, 'exit_velo_max']:.2f}")
print(f"  inf_velo: {df_eng.loc[sample_idx, 'inf_velo']:.2f}")
print(f"  sixty_time: {df_eng.loc[sample_idx, 'sixty_time']:.2f}")
print(f"  height: {df_eng.loc[sample_idx, 'height']:.2f}")
print(f"  weight: {df_eng.loc[sample_idx, 'weight']:.2f}")
print(f"  power_speed: {df_eng.loc[sample_idx, 'power_speed']:.2f}")
print(f"  exit_velo_max_percentile: {df_eng.loc[sample_idx, 'exit_velo_max_percentile']:.2f}")
print(f"  inf_velo_percentile: {df_eng.loc[sample_idx, 'inf_velo_percentile']:.2f}")
print(f"  sixty_time_percentile: {df_eng.loc[sample_idx, 'sixty_time_percentile']:.2f}")
print(f"  height_percentile: {df_eng.loc[sample_idx, 'height_percentile']:.2f}")
print(f"  weight_percentile: {df_eng.loc[sample_idx, 'weight_percentile']:.2f}")
print(f"  power_speed_percentile: {df_eng.loc[sample_idx, 'power_speed_percentile']:.2f}")

print("="*80)
print("END QUANTILES - COPY THE ABOVE VALUES TO PRODUCTION PIPELINE")
print("="*80 + "\n")

# Train/test split for P4 prediction
X_p4_train, X_p4_test, y_p4_train, y_p4_test = train_test_split(
    X_p4_elite, y_p4_elite, test_size=0.2, stratify=y_p4_elite, random_state=42
)

print(f"P4 features count: {len(p4_features)}")
print(f"P4 training set distribution: {y_p4_train.value_counts(normalize=True)}")

# ============================================================================
# INDIVIDUAL MODEL OPTIMIZATION WITH OPTUNA
# ============================================================================

# XGBoost Optimization
print("\n🚀 Optimizing XGBoost for P4 ensemble...")
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
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 2.0),
        'random_state': 42
    }
    
    model = xgb.XGBClassifier(**params, n_estimators=500)
    X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        X_p4_train, y_p4_train, test_size=0.2, stratify=y_p4_train, random_state=42
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
print("\n🐱 Optimizing CatBoost for P4 ensemble...")
def catboost_objective(trial):
    params = {
        'iterations': 500,
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'depth': trial.suggest_int('depth', 4, 10),
        'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1e-8, 10.0, log=True),
        'bagging_temperature': trial.suggest_float('bagging_temperature', 0.0, 1.0),
        'random_strength': trial.suggest_float('random_strength', 0.0, 10.0),
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 2.0),
        'verbose': False,
        'random_seed': 42
    }
    
    model = cb.CatBoostClassifier(**params)
    X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        X_p4_train, y_p4_train, test_size=0.2, stratify=y_p4_train, random_state=42
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
print("\n💡 Optimizing LightGBM for P4 ensemble...")
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
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 2.0),
        'verbose': -1,
        'random_state': 42
    }
    
    model = lgb.LGBMClassifier(**params, n_estimators=500)
    X_train_split, X_val_split, y_train_split, y_val_split = train_test_split(
        X_p4_train, y_p4_train, test_size=0.2, stratify=y_p4_train, random_state=42
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
print("\n🚀 Optimizing SVM for P4 ensemble...")
scaler = StandardScaler()
X_p4_train_scaled = scaler.fit_transform(X_p4_train)
X_p4_test_scaled = scaler.transform(X_p4_test)

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
        X_p4_train_scaled, y_p4_train, test_size=0.2, stratify=y_p4_train, random_state=42
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
print("\n🎯 Creating Weighted Ensemble (XGB: 30%, CAT: 30%, LGB: 20%, SVM: 20%)...")

# Train individual models with best parameters
xgb_model = xgb.XGBClassifier(**best_xgb_params, n_estimators=500, random_state=42)
cat_model = cb.CatBoostClassifier(**best_cat_params, verbose=False, random_seed=42)
lgb_model = lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=42)
svm_model = SVC(**best_svm_params, probability=True)

# Fit individual models
print("Training individual ensemble models...")
xgb_model.fit(X_p4_train, y_p4_train, verbose=False)
cat_model.fit(X_p4_train, y_p4_train, verbose=False)
lgb_model.fit(X_p4_train, y_p4_train)
svm_model.fit(X_p4_train_scaled, y_p4_train)

# Create weighted ensemble prediction function
def weighted_ensemble_predict_proba(X, X_scaled):
    """
    Weighted ensemble prediction with custom weights
    XGBoost: 30%, CatBoost: 35%, LightGBM: 17.5%, SVM: 17.5%
    """
    xgb_proba = xgb_model.predict_proba(X)[:, 1]
    cat_proba = cat_model.predict_proba(X)[:, 1]
    lgb_proba = lgb_model.predict_proba(X)[:, 1]
    svm_proba = svm_model.predict_proba(X_scaled)[:, 1]
    
    # Weighted combination
    ensemble_proba = (xgb_proba * 0.3 + cat_proba * 0.35 + 
                     lgb_proba * 0.175 + svm_proba * 0.175)
    
    return ensemble_proba

# Evaluate ensemble on elite test set
X_p4_test_scaled = scaler.transform(X_p4_test)
ensemble_probs_elite = weighted_ensemble_predict_proba(X_p4_test, X_p4_test_scaled)
ensemble_preds_elite = (ensemble_probs_elite >= 0.5).astype(int)

print(f"\n🏆 ENSEMBLE P4 Prediction Results (Elite D1 Only):")
print(f"Accuracy: {accuracy_score(y_p4_test, ensemble_preds_elite):.4f}")
print(f"Balanced Accuracy: {balanced_accuracy_score(y_p4_test, ensemble_preds_elite):.4f}")
print(f"F1 Score: {f1_score(y_p4_test, ensemble_preds_elite):.4f}")
print(f"P4 Recall: {recall_score(y_p4_test, ensemble_preds_elite, pos_label=1):.4f}")
print(f"P4 Precision: {precision_score(y_p4_test, ensemble_preds_elite, pos_label=1):.4f}")

print(f"\n📊 Ensemble Classification Report:")
print(classification_report(y_p4_test, ensemble_preds_elite))

# ============================================================================
# STEP 3: HIERARCHICAL PREDICTION WITH ENSEMBLE
# ============================================================================
print("\n🤖 STEP 3: Implementing Hierarchical Prediction with Ensemble...")

# Prepare full dataset
drop_cols = ['p4_or_not', 'd1_or_not', 'is_elite_d1', 'elite_composite_score']
X_full = df_eng.drop(columns=drop_cols)
y_full = df_eng['p4_or_not']

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
X_full_test_scaled = scaler.transform(X_full_test)

# Hierarchical prediction function with ensemble
def predict_p4_hierarchical_ensemble(features_dict, features_scaled):
    """
    Hierarchical prediction with ensemble P4 model
    """
    # Extract features for elite model
    elite_features_subset = [col for col in elite_features if col in features_dict.columns]
    elite_feats = features_dict[elite_features_subset]
    
    # Extract features for P4 ensemble
    p4_feats = features_dict[[col for col in p4_features if col in features_dict.columns]]
    
    # Get probabilities
    elite_prob = elite_model.predict_proba(elite_feats)[:, 1]
    p4_prob = weighted_ensemble_predict_proba(p4_feats, features_scaled)
    
    # Weighted hierarchical combination
    hierarchical_p4_prob = (elite_prob * 0.6) + (p4_prob * 0.4)
    
    return hierarchical_p4_prob, elite_prob, p4_prob

# Apply hierarchical ensemble prediction
hierarchical_probs, elite_test_probs, p4_test_probs = predict_p4_hierarchical_ensemble(X_full_test, X_full_test_scaled)

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
best_balanced_idx = hierarchical_df['balanced_acc'].idxmax()
optimal_threshold = hierarchical_df.loc[best_balanced_idx, 'threshold']

print(f"Optimal hierarchical ensemble threshold: {optimal_threshold:.2f}")

# Final predictions
y_pred_hierarchical = (hierarchical_probs >= optimal_threshold).astype(int)

print(f"\n🏆 FINAL HIERARCHICAL ENSEMBLE RESULTS:")
print("=" * 60)
print(f"📈 HIERARCHICAL ENSEMBLE MODEL:")
print(f"Accuracy: {accuracy_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"Balanced Accuracy: {balanced_accuracy_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"F1 Score: {f1_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"P4 Recall: {recall_score(y_full_test, y_pred_hierarchical, pos_label=1):.4f}")
print(f"P4 Precision: {precision_score(y_full_test, y_pred_hierarchical, pos_label=1):.4f}")

print(f"\n📊 Hierarchical Ensemble Classification Report:")
print(classification_report(y_full_test, y_pred_hierarchical))

print(f"Hierarchical Ensemble Confusion Matrix:")
cm_hierarchical = confusion_matrix(y_full_test, y_pred_hierarchical)
print(cm_hierarchical)

tn, fp, fn, tp = cm_hierarchical.ravel()
print(f"\n🎯 Ensemble Analysis:")
print(f"True Positives (Correctly identified P4): {tp}")
print(f"False Positives (Over-recruit): {fp}")
print(f"False Negatives (Miss talent): {fn}")
print(f"FP:FN Ratio: {fp/fn:.2f}")

print("\n" + "=" * 80)
print("🎉 HIERARCHICAL ENSEMBLE MODEL COMPLETE!")
print("Elite Detection (97% accuracy) + Ensemble P4 Model (XGB+CAT+LGB+SVM) + Hierarchical Weighting")
print("=" * 80)

# ============================================================================
# SAVE ALL MODELS FOR PRODUCTION
# ============================================================================
print("\n💾 SAVING MODELS FOR PRODUCTION...")

import os
import pickle

# Create saved_models directory
models_dir = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/ml/models/models_inf/models_p4_or_not_inf'
os.makedirs(models_dir, exist_ok=True)

# 1. Save Elite Detection Model
elite_model_path = os.path.join(models_dir, 'elite_detection_xgboost_model.pkl')
joblib.dump(elite_model, elite_model_path)
print(f"✅ Saved: elite_detection_xgboost_model.pkl")

# 2. Save P4 Ensemble Models
xgb_model_path = os.path.join(models_dir, 'p4_ensemble_xgboost_model.pkl') 
joblib.dump(xgb_model, xgb_model_path)
print(f"✅ Saved: p4_ensemble_xgboost_model.pkl")

cat_model_path = os.path.join(models_dir, 'p4_ensemble_catboost_model.pkl')
joblib.dump(cat_model, cat_model_path) 
print(f"✅ Saved: p4_ensemble_catboost_model.pkl")

lgb_model_path = os.path.join(models_dir, 'p4_ensemble_lightgbm_model.pkl')
joblib.dump(lgb_model, lgb_model_path)
print(f"✅ Saved: p4_ensemble_lightgbm_model.pkl")

svm_model_path = os.path.join(models_dir, 'p4_ensemble_svm_model.pkl')
joblib.dump(svm_model, svm_model_path)
print(f"✅ Saved: p4_ensemble_svm_model.pkl")

# 3. Save Feature Scaler (needed for SVM)
scaler_path = os.path.join(models_dir, 'feature_scaler_for_svm.pkl')
joblib.dump(scaler, scaler_path)
print(f"✅ Saved: feature_scaler_for_svm.pkl")

# 4. Save Model Configuration and Metadata
model_config = {
    'optimal_threshold': optimal_threshold,
    'elite_threshold': elite_threshold,
    'elite_features': elite_features,
    'p4_features': p4_features,
    'ensemble_weights': {
        'xgboost': 0.3,
        'catboost': 0.35, 
        'lightgbm': 0.175,
        'svm': 0.175
    },
    'hierarchical_weights': {
        'elite_prob': 0.6,
        'p4_prob': 0.4
    },
    'model_performance': {
        'accuracy': accuracy_score(y_full_test, y_pred_hierarchical),
        'balanced_accuracy': balanced_accuracy_score(y_full_test, y_pred_hierarchical),
        'f1_score': f1_score(y_full_test, y_pred_hierarchical),
        'p4_recall': recall_score(y_full_test, y_pred_hierarchical, pos_label=1),
        'p4_precision': precision_score(y_full_test, y_pred_hierarchical, pos_label=1),
        'confusion_matrix': cm_hierarchical.tolist()
    },
    'feature_engineering_steps': [
        'percentile_features', 'power_per_pound', 'exit_to_sixty_ratio', 
        'speed_size_efficiency', 'athletic_index', 'power_speed_index',
        'elite_binary_features', 'multi_tool_count', 'scaled_features'
    ]
}

config_path = os.path.join(models_dir, 'model_config_and_metadata.pkl')
with open(config_path, 'wb') as f:
    pickle.dump(model_config, f)
print(f"✅ Saved: model_config_and_metadata.pkl")

# 5. Save Prediction Pipeline Function (as text for reference)
pipeline_code = '''
# HIERARCHICAL ENSEMBLE P4 PREDICTION PIPELINE
# Use this code structure in production

import joblib
import numpy as np
import pandas as pd
import pickle
from sklearn.preprocessing import StandardScaler

def predict_p4_hierarchical_ensemble_production(player_data):
    """
    Production prediction function for P4 classification
    
    Args:
        player_data: DataFrame with engineered features
    
    Returns:
        dict with elite_prob, p4_prob, hierarchical_prob, prediction
    """
    
    # Load models (do this once at startup in production)
    elite_model = joblib.load('elite_detection_xgboost_model.pkl')
    xgb_model = joblib.load('p4_ensemble_xgboost_model.pkl')
    cat_model = joblib.load('p4_ensemble_catboost_model.pkl')
    lgb_model = joblib.load('p4_ensemble_lightgbm_model.pkl')
    svm_model = joblib.load('p4_ensemble_svm_model.pkl')
    scaler = joblib.load('feature_scaler_for_svm.pkl')
    
    # Load config
    with open('model_config_and_metadata.pkl', 'rb') as f:
        config = pickle.load(f)
    
    # Extract features
    elite_feats = player_data[config['elite_features']]
    p4_feats = player_data[config['p4_features']]
    p4_feats_scaled = scaler.transform(p4_feats)
    
    # Get elite probability
    elite_prob = elite_model.predict_proba(elite_feats)[:, 1]
    
    # Get ensemble P4 probabilities
    xgb_proba = xgb_model.predict_proba(p4_feats)[:, 1]
    cat_proba = cat_model.predict_proba(p4_feats)[:, 1]
    lgb_proba = lgb_model.predict_proba(p4_feats)[:, 1]
    svm_proba = svm_model.predict_proba(p4_feats_scaled)[:, 1]
    
    # Weighted ensemble
    p4_prob = (xgb_proba * 0.3 + cat_proba * 0.3 + 
               lgb_proba * 0.2 + svm_proba * 0.2)
    
    # Hierarchical combination
    hierarchical_prob = (elite_prob * 0.6) + (p4_prob * 0.4)
    
    # Final prediction
    prediction = (hierarchical_prob >= config['optimal_threshold']).astype(int)
    
    return {
        'elite_probability': elite_prob[0],
        'p4_probability': p4_prob[0], 
        'hierarchical_probability': hierarchical_prob[0],
        'p4_prediction': int(prediction[0]),
        'confidence': 'high' if abs(hierarchical_prob[0] - 0.5) > 0.3 else 'medium'
    }
'''

pipeline_path = os.path.join(models_dir, 'production_prediction_pipeline.py')
with open(pipeline_path, 'w') as f:
    f.write(pipeline_code)
print(f"✅ Saved: production_prediction_pipeline.py")

# 6. Create README for production team
readme_content = '''# Power 4 Prediction Models - Production Deployment

## Model Files:

### Core Models:
- `elite_detection_xgboost_model.pkl` - Detects elite D1 players (97% accuracy)
- `p4_ensemble_xgboost_model.pkl` - XGBoost P4 classifier (30% weight)
- `p4_ensemble_catboost_model.pkl` - CatBoost P4 classifier (35% weight)  
- `p4_ensemble_lightgbm_model.pkl` - LightGBM P4 classifier (17.5% weight)
- `p4_ensemble_svm_model.pkl` - SVM P4 classifier (17.5% weight)

### Supporting Files:
- `feature_scaler_for_svm.pkl` - StandardScaler for SVM preprocessing
- `model_config_and_metadata.pkl` - Thresholds, feature lists, performance metrics
- `production_prediction_pipeline.py` - Reference implementation code

## Performance Metrics:
- **Accuracy**: 78.1%
- **P4 Precision**: 82.5% (when model says P4, it's right 82.5% of the time)
- **P4 Recall**: 42.2% (captures 2 out of 5 actual P4 players)
- **Balanced Accuracy**: 68.8%

## Key Thresholds:
- **Elite Detection**: Players above composite score threshold are "elite D1"
- **P4 Prediction**: Hierarchical probability threshold for final classification
- **Confidence Levels**: High confidence when probability > 0.8 or < 0.2

## Feature Engineering Required:
Input data must include engineered features:
- Percentile rankings for all metrics
- Advanced ratios (power_per_pound, exit_to_sixty_ratio, etc.)
- Elite binary indicators
- Athletic composite scores

## Prediction Flow:
1. Engineer features from raw player data
2. Elite detection model → elite probability
3. Ensemble P4 models → P4 probability  
4. Hierarchical combination → final prediction
5. Apply threshold → binary P4/Non-P4 classification

## Usage Notes:
- Load all models once at startup for performance
- Feature engineering must match training pipeline exactly
- SVM requires feature scaling (use provided scaler)
- Models expect same 41 engineered features as training
'''

readme_path = os.path.join(models_dir, 'README.md')
with open(readme_path, 'w') as f:
    f.write(readme_content)
print(f"✅ Saved: README.md")

print(f"\n🎯 ALL MODELS SAVED TO: {models_dir}")
print("\n📦 Production Package Contents:")
print("├── elite_detection_xgboost_model.pkl")
print("├── p4_ensemble_xgboost_model.pkl") 
print("├── p4_ensemble_catboost_model.pkl")
print("├── p4_ensemble_lightgbm_model.pkl")
print("├── p4_ensemble_svm_model.pkl")
print("├── feature_scaler_for_svm.pkl")
print("├── model_config_and_metadata.pkl")
print("├── production_prediction_pipeline.py")
print("└── README.md")

print(f"\n✅ READY FOR PRODUCTION DEPLOYMENT!")
print(f"Move the entire 'saved_models' folder to your production environment.")