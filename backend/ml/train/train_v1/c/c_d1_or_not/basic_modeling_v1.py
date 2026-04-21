import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, recall_score, balanced_accuracy_score, precision_score, fbeta_score
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
import xgboost as xgb
import lightgbm as lgb
import optuna
import warnings
warnings.filterwarnings('ignore')

csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/c_d1_or_not_data.csv'
df = pd.read_csv(csv_path)

print(f"D1 Distribution: {df['d1_or_not'].value_counts()}")
print(f"D1 Rate: {df['d1_or_not'].mean():.2%}")
print(f"Class imbalance ratio: {(df['d1_or_not'] == 0).sum() / (df['d1_or_not'] == 1).sum():.1f}:1") 

# no NAs, good
"""
na_counts = df.isnull().sum()
print("NA value counts per column:")
print(na_counts)
"""

# Create categorical encodings
df = pd.get_dummies(df, columns=['player_region', 'throwing_hand', 'hitting_handedness'], 
                   prefix_sep='_', drop_first=True)

# ============================================================================
# CATCHER-SPECIFIC FEATURE ENGINEERING
# ============================================================================

# Core athletic metrics
df['power_speed'] = df['exit_velo_max'] / df['sixty_time']
df['c_velo_sixty_ratio'] = df['c_velo'] / df['sixty_time']
df['height_weight'] = df['height'] * df['weight']

# Catcher-specific defensive metrics
df['pop_time_c_velo_ratio'] = df['pop_time'] / df['c_velo'] * 100
df['defensive_efficiency'] = df['c_velo'] / df['pop_time']
df['catch_throw_index'] = (df['c_velo'] * 10) / df['pop_time']

# Create percentile features
percentile_features = ['exit_velo_max', 'c_velo', 'pop_time', 'sixty_time', 'height', 'weight', 'power_speed']
for col in percentile_features:
    if col in df.columns:
        if col in ['sixty_time', 'pop_time']:  # Lower is better
            df[f'{col}_percentile'] = (1 - df[col].rank(pct=True)) * 100
        else:  # Higher is better
            df[f'{col}_percentile'] = df[col].rank(pct=True) * 100

# Advanced ratio features
df['power_per_pound'] = df['exit_velo_max'] / df['weight']
df['exit_to_sixty_ratio'] = df['exit_velo_max'] / df['sixty_time']
df['speed_size_efficiency'] = (df['height'] * df['weight']) / (df['sixty_time'] ** 2)
df['athletic_index'] = (df['power_speed'] * df['height'] * df['weight']) / df['sixty_time']
df['power_speed_index'] = df['exit_velo_max'] * (1 / df['sixty_time'])

# Catcher-specific advanced metrics
df['arm_strength_per_pound'] = df['c_velo'] / df['weight']
df['pop_time_efficiency'] = 1 / df['pop_time']
df['defensive_power_combo'] = df['c_velo'] * df['exit_velo_max']
df['total_athleticism'] = (df['c_velo'] + df['exit_velo_max']) / df['sixty_time']

# Elite binary features
df['elite_exit_velo'] = (df['exit_velo_max'] >= df['exit_velo_max'].quantile(0.75)).astype(int)
df['elite_c_velo'] = (df['c_velo'] >= df['c_velo'].quantile(0.75)).astype(int)
df['elite_pop_time'] = (df['pop_time'] <= df['pop_time'].quantile(0.25)).astype(int)
df['elite_speed'] = (df['sixty_time'] <= df['sixty_time'].quantile(0.25)).astype(int)
df['elite_size'] = ((df['height'] >= df['height'].quantile(0.6)) & 
                   (df['weight'] >= df['weight'].quantile(0.6))).astype(int)
df['multi_tool_count'] = (df['elite_exit_velo'] + df['elite_c_velo'] + 
                         df['elite_pop_time'] + df['elite_speed'] + df['elite_size'])

# Scaled features for elite composite score
df['exit_velo_scaled'] = (df['exit_velo_max'] - df['exit_velo_max'].min()) / (df['exit_velo_max'].max() - df['exit_velo_max'].min()) * 100
df['speed_scaled'] = (1 - (df['sixty_time'] - df['sixty_time'].min()) / (df['sixty_time'].max() - df['sixty_time'].min())) * 100
df['arm_scaled'] = (df['c_velo'] - df['c_velo'].min()) / (df['c_velo'].max() - df['c_velo'].min()) * 100
df['pop_time_scaled'] = (1 - (df['pop_time'] - df['pop_time'].min()) / (df['pop_time'].max() - df['pop_time'].min())) * 100

# Regional advantages
regional_cols = [col for col in df.columns if 'player_region_' in col]
if regional_cols:
    region_weights = {}
    for col in regional_cols:
        region_weights[col] = df[df[col] == 1]['d1_or_not'].mean()
    
    df['d1_region_advantage'] = 0
    for col, weight in region_weights.items():
        df['d1_region_advantage'] += df[col] * weight

# Elite composite score (catcher-specific weights)
df['elite_composite_score'] = (
    df['exit_velo_scaled'] * 0.25 +      # Power (25%)
    df['speed_scaled'] * 0.20 +          # Speed (20%)
    df['arm_scaled'] * 0.30 +            # Arm strength (30% - critical for catchers)
    df['pop_time_scaled'] * 0.15 +       # Pop time (15% - catcher-specific)
    df['height_percentile'] * 0.10       # Size (10%)
)

# Enhanced catcher-specific features
df['c_arm_strength'] = (df['c_velo'] >= df['c_velo'].quantile(0.75)).astype(int)
df['c_arm_plus'] = (df['c_velo'] >= df['c_velo'].quantile(0.60)).astype(int)
df['pop_time_elite'] = (df['pop_time'] <= df['pop_time'].quantile(0.25)).astype(int)
df['exit_velo_elite'] = (df['exit_velo_max'] >= df['exit_velo_max'].quantile(0.75)).astype(int)
df['speed_elite'] = (df['sixty_time'] <= df['sixty_time'].quantile(0.25)).astype(int)

# D1 thresholds (catcher-specific)
p75_exit = df['exit_velo_max'].quantile(0.75)
p75_c_velo = df['c_velo'].quantile(0.75)
p25_sixty = df['sixty_time'].quantile(0.25)
p25_pop = df['pop_time'].quantile(0.25)

df['d1_exit_velo_threshold'] = (df['exit_velo_max'] >= max(88, p75_exit * 0.95)).astype(int)
df['d1_arm_threshold'] = (df['c_velo'] >= max(75, p75_c_velo * 0.9)).astype(int)
df['d1_pop_time_threshold'] = (df['pop_time'] <= min(2.1, p25_pop * 1.1)).astype(int)
df['d1_speed_threshold'] = (df['sixty_time'] <= min(7.3, p25_sixty * 1.1)).astype(int)
df['d1_size_threshold'] = ((df['height'] >= 69) & (df['weight'] >= 175)).astype(int)

# Multi-tool analysis
df['tool_count'] = (df['exit_velo_elite'] + df['c_arm_strength'] + 
                   df['pop_time_elite'] + df['speed_elite'] + df['d1_size_threshold'])
df['is_multi_tool'] = (df['tool_count'] >= 2).astype(int)

# Advanced composites
df['athletic_index_v2'] = (
    df['exit_velo_max_percentile'] * 0.25 +
    df['c_velo_percentile'] * 0.30 + 
    df['pop_time_percentile'] * 0.20 +
    df['sixty_time_percentile'] * 0.15 +
    df['height_percentile'] * 0.05 +
    df['weight_percentile'] * 0.05
)

df['tools_athlete'] = df['tool_count'] * df['athletic_index_v2']

df['d1_composite_score'] = (
    df['d1_exit_velo_threshold'] * 0.30 +
    df['d1_arm_threshold'] * 0.30 +
    df['d1_pop_time_threshold'] * 0.25 +
    df['d1_speed_threshold'] * 0.10 +
    df['d1_size_threshold'] * 0.05
)

# Catcher-specific premium features
df['complete_catcher'] = (df['c_arm_strength'] & df['pop_time_elite'] & df['exit_velo_elite']).astype(int)
df['defensive_first'] = (df['c_arm_strength'] & df['pop_time_elite'] & ~df['exit_velo_elite']).astype(int)

# Interaction features
df['arm_pop_interaction'] = df['c_velo'] * (1/df['pop_time']) * 10
df['power_defense_balance'] = (df['exit_velo_max'] + df['c_velo']) / 2
df['athleticism_defense'] = df['athletic_index'] * df['defensive_efficiency']

# Position-specific percentile rankings
df['catcher_defensive_percentile'] = (
    (df['c_velo_percentile'] * 0.6) + 
    (df['pop_time_percentile'] * 0.4)
)

df['catcher_offensive_percentile'] = (
    (df['exit_velo_max_percentile'] * 0.7) + 
    (df['sixty_time_percentile'] * 0.3)
)

df['catcher_overall_percentile'] = (
    (df['catcher_defensive_percentile'] * 0.4) +
    (df['catcher_offensive_percentile'] * 0.35) +
    (df['height_percentile'] * 0.15) +
    (df['weight_percentile'] * 0.10)
)

# correlation analysis
df['arm_athleticism_correlation'] = df['c_velo'] * df['athletic_index_v2']
df['arm_athleticism_correlation_squared'] = df['arm_athleticism_correlation'] ** 2
df['arm_athleticism_correlation_cubed'] = df['arm_athleticism_correlation'] ** 3
df['arm_athleticism_fourth'] = df['arm_athleticism_correlation'] ** 4
df['arm_athleticism_correlation_log'] = np.log1p(df['arm_athleticism_correlation'])
df['arm_athleticism_exp'] = np.exp(df['arm_athleticism_correlation'] / 100)

df['defensive_consistency'] = df['pop_time_percentile'] * df['c_velo_percentile'] * df['catcher_defensive_percentile']
df['power_speed_size_ratio'] = (df['exit_velo_max'] * df['sixty_time']) / df['weight']
df['pop_efficiency'] = df['c_velo'] / (df['pop_time'] ** 2)

df['region_athletic_adjustment'] = df['athletic_index_v2'] * df['d1_region_advantage']
df['tool_synergy'] = df['tools_athlete'] * df['multi_tool_count'] * df['complete_catcher']
df['athletic_ceiling'] = df['athletic_index_v2'] ** 2 * df['height_percentile']

df['arm_athleticism_correlation_x_region_athletic_adjustment'] = df['arm_athleticism_correlation'] * df['region_athletic_adjustment']
df['tool_count_x_athletic_index'] = df['tool_count'] * df['athletic_index_v2']
df['tool_athletic_log'] = np.log1p(df['tool_count_x_athletic_index'])

# Clean data
df = df.replace([np.inf, -np.inf], np.nan)
numeric_columns = df.select_dtypes(include=[np.number]).columns
df[numeric_columns] = df[numeric_columns].fillna(0)

# Apply outlier clipping
for col in df.select_dtypes(include=[np.number]).columns:
    if col != 'd1_or_not':
        Q1, Q3 = df[col].quantile(0.01), df[col].quantile(0.99)
        IQR = Q3 - Q1
        df[col] = df[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

# ============================================================================
# FEATURE SELECTION - SINGLE SOURCE OF TRUTH
# ============================================================================
# Edit this list to include/exclude features for ALL models
EXCLUDE_FEATURES = [
    'd1_or_not', 'is_elite_c', 'elite_composite_score', 'primary_position', 
    'defensive_first', 'hitting_handedness_S', 'throwing_hand_R', 
    'arm_pop_interaction', 'power_speed_index', 'speed_elite', 'd1_speed_threshold', 
    'd1_pop_time_threshold', 'd1_exit_velo_threshold', 'd1_arm_threshold', 
    'exit_velo_elite', 'pop_time_elite', 'c_arm_strength', 'c_arm_plus', 
    'elite_speed', 'elite_pop_time', 'elite_c_velo', 'elite_exit_velo', 'pop_time_scaled',
    'elite_size', 'is_multi_tool', 'arm_scaled', 'd1_size_threshold', 'pop_time_efficiency',
    'catch_throw_index', 'multi_tool_count', 'total_athleticism', 'exit_velo_scaled', 
    'speed_size_efficiency', 'exit_to_sixty_ratio', 'power_speed_percentile',
    'height_percentile', 'pop_time_percentile', 'defensive_efficiency', 'exit_velo_max_percentile',
    'complete_catcher'
]

# ============================================================================
# SCORING CONFIGURATION - SINGLE SOURCE OF TRUTH
# ============================================================================
# Edit these weights to change optimization criteria for ALL models
SCORING_WEIGHTS = {
      'accuracy': 2.5,      # Increased from current
      'recall': 1.8,        # Keep recall strong  
      'precision': 1.4,     # Boost precision for accuracy
      'f1': 1.0             # Reduce F1 weight
}

# Minimum performance thresholds for production
MIN_THRESHOLDS = {
    'accuracy': 0.75,       # At least 70% accuracy (reasonable threshold)
    'recall': 0.55,         # At least 60% D1 recall (capture most D1s)
    'precision': 0.40       # At least 40% D1 precision (allow FP >= FN)
}

def calculate_optimization_score(accuracy, recall, precision, f1):
    """Calculate weighted optimization score favoring accuracy with FP > FN preference"""
    return (accuracy * SCORING_WEIGHTS['accuracy'] + 
            recall * SCORING_WEIGHTS['recall'] + 
            precision * SCORING_WEIGHTS['precision'] + 
            f1 * SCORING_WEIGHTS['f1'])

def recruiting_score_with_fp_bias(y_true, y_pred):
    """Custom scoring function that encourages FP >= FN with strong recall focus"""
    accuracy = accuracy_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred, pos_label=1)
    precision = precision_score(y_true, y_pred, pos_label=1, zero_division=0)
    f1 = f1_score(y_true, y_pred)
    
    # Calculate confusion matrix components
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    # Penalty if FN > FP (we want FP >= FN)
    fp_fn_penalty = 0
    if fn > fp:
        fp_fn_penalty = -0.5 * (fn - fp) / len(y_true)  # Penalty proportional to excess FN
    
    base_score = calculate_optimization_score(accuracy, recall, precision, f1)
    return base_score + fp_fn_penalty

print(f"Created {len(df.columns) - len(EXCLUDE_FEATURES) - 1} features for {len(df)} catchers")

# ============================================================================
# ELITE CATCHER DETECTION MODEL
# ============================================================================

# Find optimal elite threshold
elite_thresholds = [0.60, 0.55, 0.50, 0.45]
best_elite_threshold = 0.55
best_d1_capture_rate = 0

for threshold in elite_thresholds:
    temp_elite_cutoff = df['elite_composite_score'].quantile(threshold)
    temp_elite_mask = df['elite_composite_score'] >= temp_elite_cutoff
    
    elite_count = temp_elite_mask.sum()
    elite_d1_rate = df[temp_elite_mask]['d1_or_not'].mean()
    total_d1_captured = df[temp_elite_mask]['d1_or_not'].sum()
    d1_capture_rate = total_d1_captured / df['d1_or_not'].sum()
    
    if d1_capture_rate > best_d1_capture_rate and elite_d1_rate >= 0.35:
        best_d1_capture_rate = d1_capture_rate
        best_elite_threshold = threshold

# Apply optimal elite threshold
elite_threshold = df['elite_composite_score'].quantile(best_elite_threshold)
df['is_elite_c'] = (df['elite_composite_score'] >= elite_threshold).astype(int)

print(f"Elite threshold: {best_elite_threshold:.2f}, Elite catchers: {df['is_elite_c'].sum()} ({df['is_elite_c'].mean():.1%})")

# Train Elite Detection Model
elite_features = [col for col in df.columns if col not in EXCLUDE_FEATURES]

X_elite = df[elite_features].copy()
y_elite = df['is_elite_c'].copy()

# Create train/val/test splits (65/15/20) - NO DATA LEAKAGE
X_elite_temp, X_elite_test, y_elite_temp, y_elite_test = train_test_split(
    X_elite, y_elite, test_size=0.20, stratify=y_elite, random_state=42
)
X_elite_train, X_elite_val, y_elite_train, y_elite_val = train_test_split(
    X_elite_temp, y_elite_temp, test_size=0.1875, stratify=y_elite_temp, random_state=42  # 15/(65+15) = 0.1875
)

elite_model = xgb.XGBClassifier(
    objective='binary:logistic',
    eval_metric='auc',
    learning_rate=0.1,
    max_depth=8,
    n_estimators=500,
    random_state=42
)
elite_model.fit(X_elite_train, y_elite_train, verbose=False)

# Validate elite model on validation set (not test set!)
elite_preds_val = elite_model.predict(X_elite_val)
print(f"Elite detection validation accuracy: {accuracy_score(y_elite_val, elite_preds_val):.4f}")

# ============================================================================
# ENHANCED ENSEMBLE D1 MODEL ON ELITE CATCHERS
# ============================================================================

# Get elite players for D1 training  
elite_mask = df['is_elite_c'] == 1
df_elite_only = df[elite_mask].copy()

print(f"Elite subset: {len(df_elite_only)} players, D1 rate: {df_elite_only['d1_or_not'].mean():.1%}")

# Prepare features for D1 prediction
d1_features = [col for col in df.columns if col not in EXCLUDE_FEATURES]

X_d1_elite = df_elite_only[d1_features].copy()
y_d1_elite = df_elite_only['d1_or_not'].copy()

# Create train/val/test splits for D1 prediction (65/15/20) - NO DATA LEAKAGE
X_d1_temp, X_d1_test, y_d1_temp, y_d1_test = train_test_split(
    X_d1_elite, y_d1_elite, test_size=0.20, stratify=y_d1_elite, random_state=42
)
X_d1_train, X_d1_val, y_d1_train, y_d1_val = train_test_split(
    X_d1_temp, y_d1_temp, test_size=0.1875, stratify=y_d1_temp, random_state=42  # 15/(65+15) = 0.1875
)

# Calculate class weight for tree models
class_counts = y_d1_train.value_counts().sort_index()
n_samples = len(y_d1_train)
n_classes = len(class_counts)
class_weight_ratio = n_samples / (n_classes * class_counts[1])

print(f"D1 features: {len(d1_features)}, Class weight ratio: {class_weight_ratio:.2f}")

# ============================================================================
# INDIVIDUAL MODEL OPTIMIZATION WITH OPTUNA
# ============================================================================

# XGBoost Optimization
def xgb_objective(trial):
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'use_label_encoder': False,
        'learning_rate': trial.suggest_float('eta', 1e-3, 2e-1, log=True),
        'max_depth': trial.suggest_int('max_depth', 4, 10),
        'min_child_weight': trial.suggest_int('min_child_weight', 3, 25),
        'gamma': trial.suggest_float('gamma', 1e-8, 10.0, log=True),
        'subsample': trial.suggest_float('subsample', 0.7, 0.95),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.4, 0.9),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-6, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-6, 100.0, log=True),
        'scale_pos_weight': class_weight_ratio,
        'random_state': 42
    }
    
    model = xgb.XGBClassifier(**params, n_estimators=300)
    # Use train set for training, validation set for evaluation - NO CV to prevent data leakage
    model.fit(X_d1_train, y_d1_train, verbose=False)
    val_preds = model.predict(X_d1_val)
    return recruiting_score_with_fp_bias(y_d1_val, val_preds)

study_xgb = optuna.create_study(direction='maximize')
study_xgb.optimize(xgb_objective, n_trials=50, show_progress_bar=True)
best_xgb_params = study_xgb.best_params

# Deep Neural Network Optimization
scaler_dnn = StandardScaler()
X_d1_train_scaled = scaler_dnn.fit_transform(X_d1_train)
X_d1_val_scaled = scaler_dnn.transform(X_d1_val)
X_d1_test_scaled = scaler_dnn.transform(X_d1_test)

def dnn_objective(trial):
    params = {
        'hidden_layer_sizes': trial.suggest_categorical('hidden_layer_sizes', 
            [(32,), (64,), (32, 16), (64, 32), (128, 64)]),
        'activation': trial.suggest_categorical('activation', ['relu', 'tanh']),
        'solver': 'adam',
        'alpha': trial.suggest_float('alpha', 1e-4, 1e-1, log=True),
        'learning_rate': 'adaptive',
        'learning_rate_init': trial.suggest_float('learning_rate_init', 1e-4, 1e-2, log=True),
        'max_iter': 500,
        'random_state': 42,
        'early_stopping': True,
        'validation_fraction': 0.3
    }
    
    model = MLPClassifier(**params)
    # Use train set for training, validation set for evaluation - NO CV to prevent data leakage
    model.fit(X_d1_train_scaled, y_d1_train)
    val_preds = model.predict(X_d1_val_scaled)
    return recruiting_score_with_fp_bias(y_d1_val, val_preds)

study_dnn = optuna.create_study(direction='maximize')
study_dnn.optimize(dnn_objective, n_trials=30, show_progress_bar=True)
best_dnn_params = study_dnn.best_params

# LightGBM Optimization
def lightgbm_objective(trial):
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': trial.suggest_int('num_leaves', 15, 150),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 0.9),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.6, 0.95),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 5),
        'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-6, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-6, 10.0, log=True),
        'scale_pos_weight': class_weight_ratio,
        'verbose': -1,
        'random_state': 42
    }
    
    model = lgb.LGBMClassifier(**params, n_estimators=250)
    # Use train set for training, validation set for evaluation - NO CV to prevent data leakage
    model.fit(X_d1_train, y_d1_train)
    val_preds = model.predict(X_d1_val)
    return recruiting_score_with_fp_bias(y_d1_val, val_preds)

study_lgb = optuna.create_study(direction='maximize')
study_lgb.optimize(lightgbm_objective, n_trials=50, show_progress_bar=True)
best_lgb_params = study_lgb.best_params

# SVM Optimization
scaler = StandardScaler()
X_d1_train_scaled_svm = scaler.fit_transform(X_d1_train)
X_d1_val_scaled_svm = scaler.transform(X_d1_val)
X_d1_test_scaled_svm = scaler.transform(X_d1_test)

def svm_objective(trial):
    params = {
        'C': trial.suggest_float('C', 1e-3, 1e3, log=True),
        'gamma': trial.suggest_categorical('gamma', ['scale', 'auto']),
        'kernel': trial.suggest_categorical('kernel', ['rbf', 'poly', 'sigmoid']),
        'probability': True,
        'class_weight': 'balanced',
        'random_state': 42
    }
    
    if params['kernel'] == 'poly':
        params['degree'] = trial.suggest_int('degree', 2, 4)
    
    model = SVC(**params)
    # Use train set for training, validation set for evaluation - NO CV to prevent data leakage
    model.fit(X_d1_train_scaled_svm, y_d1_train)
    val_preds = model.predict(X_d1_val_scaled_svm)
    
    return recruiting_score_with_fp_bias(y_d1_val, val_preds)

study_svm = optuna.create_study(direction='maximize')
study_svm.optimize(svm_objective, n_trials=30, show_progress_bar=True, n_jobs=-1)
best_svm_params = study_svm.best_params

# ============================================================================
# OPTIMIZE ENSEMBLE WEIGHTS BASED ON VALIDATION PERFORMANCE
# ============================================================================

individual_scores = {}
models_for_eval = {
    'XGB': xgb.XGBClassifier(**best_xgb_params, n_estimators=300, random_state=42),
    'LGB': lgb.LGBMClassifier(**best_lgb_params, n_estimators=250, verbose=-1, random_state=42),
    'DNN': MLPClassifier(**best_dnn_params),
    'SVM': SVC(**best_svm_params, probability=True)
}

# Evaluate each model on validation set (NO cross-validation to prevent data leakage)
for name, model in models_for_eval.items():
    if name in ['DNN', 'SVM']:
        model.fit(X_d1_train_scaled, y_d1_train)
        val_preds = model.predict(X_d1_val_scaled)
    else:
        model.fit(X_d1_train, y_d1_train)
        val_preds = model.predict(X_d1_val)
    
    individual_scores[name] = recruiting_score_with_fp_bias(y_d1_val, val_preds)
    print(f"{name} Val Score: {individual_scores[name]:.4f}")

# Calculate performance-based weights
total_score = sum(individual_scores.values())
optimized_weights = {name: score/total_score for name, score in individual_scores.items()}

print(f"Ensemble weights: {optimized_weights}")

# ============================================================================
# CREATE WEIGHTED ENSEMBLE
# ============================================================================

# Train individual models with best parameters
xgb_model = xgb.XGBClassifier(**best_xgb_params, n_estimators=500, random_state=42)
dnn_model = MLPClassifier(**best_dnn_params)
lgb_model = lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=42)
svm_model = SVC(**best_svm_params, probability=True)

xgb_model.fit(X_d1_train, y_d1_train, verbose=False)
dnn_model.fit(X_d1_train_scaled, y_d1_train)
lgb_model.fit(X_d1_train, y_d1_train)
svm_model.fit(X_d1_train_scaled_svm, y_d1_train)

# Create weighted ensemble prediction function
def weighted_ensemble_predict_proba(X, X_scaled_dnn, X_scaled_svm):
    xgb_proba = xgb_model.predict_proba(X)[:, 1]
    dnn_proba = dnn_model.predict_proba(X_scaled_dnn)[:, 1]
    lgb_proba = lgb_model.predict_proba(X)[:, 1]
    svm_proba = svm_model.predict_proba(X_scaled_svm)[:, 1]
    
    ensemble_proba = (xgb_proba * optimized_weights['XGB'] + 
                     dnn_proba * optimized_weights['DNN'] + 
                     lgb_proba * optimized_weights['LGB'] + 
                     svm_proba * optimized_weights['SVM'])
    
    return ensemble_proba

# Evaluate ensemble on elite test set
X_d1_test_scaled_dnn = scaler_dnn.transform(X_d1_test)
X_d1_test_scaled_svm = scaler.transform(X_d1_test)
ensemble_probs_elite = weighted_ensemble_predict_proba(X_d1_test, X_d1_test_scaled_dnn, X_d1_test_scaled_svm)
ensemble_preds_elite = (ensemble_probs_elite >= 0.5).astype(int)

print(f"\nEnsemble D1 Results (Elite Catchers):")
print(f"Accuracy: {accuracy_score(y_d1_test, ensemble_preds_elite):.4f}")
print(f"F1 Score: {f1_score(y_d1_test, ensemble_preds_elite):.4f}")
print(f"D1 Recall: {recall_score(y_d1_test, ensemble_preds_elite, pos_label=1):.4f}")
print(f"D1 Precision: {precision_score(y_d1_test, ensemble_preds_elite, pos_label=1):.4f}")

# ============================================================================
# HIERARCHICAL PREDICTION WITH ENSEMBLE
# ============================================================================

# Prepare full dataset
X_full = df.drop(columns=EXCLUDE_FEATURES)
y_full = df['d1_or_not']

# Create train/val/test splits for hierarchical prediction (65/15/20) - NO DATA LEAKAGE
X_full_temp, X_full_test, y_full_temp, y_full_test = train_test_split(
    X_full, y_full, test_size=0.20, stratify=y_full, random_state=42
)
X_full_train, X_full_val, y_full_train, y_full_val = train_test_split(
    X_full_temp, y_full_temp, test_size=0.1875, stratify=y_full_temp, random_state=42  # 15/(65+15) = 0.1875
)

# Scale full dataset (train/val/test)
scaler_full_dnn = StandardScaler()
scaler_full_svm = StandardScaler()
X_full_train_scaled_dnn = scaler_full_dnn.fit_transform(X_full_train)
X_full_val_scaled_dnn = scaler_full_dnn.transform(X_full_val)
X_full_test_scaled_dnn = scaler_full_dnn.transform(X_full_test)
X_full_train_scaled_svm = scaler_full_svm.fit_transform(X_full_train)
X_full_val_scaled_svm = scaler_full_svm.transform(X_full_val)
X_full_test_scaled_svm = scaler_full_svm.transform(X_full_test)

# Retrain models on full feature set
xgb_full = xgb.XGBClassifier(**best_xgb_params, n_estimators=500, random_state=42)
dnn_full = MLPClassifier(**best_dnn_params)
lgb_full = lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=42)
svm_full = SVC(**best_svm_params, probability=True)

xgb_full.fit(X_full_train, y_full_train, verbose=False)
dnn_full.fit(X_full_train_scaled_dnn, y_full_train)
lgb_full.fit(X_full_train, y_full_train)
svm_full.fit(X_full_train_scaled_svm, y_full_train)

# Hierarchical prediction function
def predict_d1_hierarchical_ensemble(features_dict, features_scaled_dnn, features_scaled_svm):
    # Elite model features - should match the training features exactly
    elite_feats = features_dict[elite_features]
    
    elite_prob = elite_model.predict_proba(elite_feats)[:, 1]
    
    # Ensemble D1 probabilities
    xgb_proba = xgb_full.predict_proba(features_dict)[:, 1]
    dnn_proba = dnn_full.predict_proba(features_scaled_dnn)[:, 1]
    lgb_proba = lgb_full.predict_proba(features_dict)[:, 1]
    svm_proba = svm_full.predict_proba(features_scaled_svm)[:, 1]
    
    d1_prob = (xgb_proba * optimized_weights['XGB'] + 
               dnn_proba * optimized_weights['DNN'] + 
               lgb_proba * optimized_weights['LGB'] + 
               svm_proba * optimized_weights['SVM'])
    
    # Hierarchical combination
    hierarchical_d1_prob = (elite_prob * 0.4) + (d1_prob * 0.6)
    
    return hierarchical_d1_prob, elite_prob, d1_prob

# Apply hierarchical ensemble prediction on VALIDATION set for threshold optimization
hierarchical_probs_val, elite_val_probs, d1_val_probs = predict_d1_hierarchical_ensemble(
    X_full_val, X_full_val_scaled_dnn, X_full_val_scaled_svm)

# Find optimal threshold
thresholds = np.arange(0.1, 0.9, 0.02)
hierarchical_results = []

for threshold in thresholds:
    y_pred_hier = (hierarchical_probs_val >= threshold).astype(int)
    accuracy = accuracy_score(y_full_val, y_pred_hier)
    balanced_acc = balanced_accuracy_score(y_full_val, y_pred_hier)
    f1 = f1_score(y_full_val, y_pred_hier)
    recall_1 = recall_score(y_full_val, y_pred_hier, pos_label=1)
    precision_1 = precision_score(y_full_val, y_pred_hier, pos_label=1, zero_division=0)
    
    # Calculate confusion matrix for FP/FN analysis
    cm = confusion_matrix(y_full_val, y_pred_hier)
    tn, fp, fn, tp = cm.ravel()
    
    # Calculate custom optimization score with FP/FN penalty
    fp_fn_penalty = 0
    if fn > fp:
        fp_fn_penalty = -0.5 * (fn - fp) / len(y_full_val)
    
    opt_score = calculate_optimization_score(accuracy, recall_1, precision_1, f1) + fp_fn_penalty
    
    hierarchical_results.append({
        'threshold': threshold,
        'accuracy': accuracy,
        'balanced_acc': balanced_acc,
        'f1': f1,
        'recall_1': recall_1,
        'precision_1': precision_1,
        'tp': tp,
        'fp': fp, 
        'fn': fn,
        'fp_fn_ratio': fp/fn if fn > 0 else float('inf'),
        'optimization_score': opt_score
    })

hierarchical_df = pd.DataFrame(hierarchical_results)

# Find optimal threshold using configurable scoring
production_performance = hierarchical_df[
    (hierarchical_df['accuracy'] >= MIN_THRESHOLDS['accuracy']) &
    (hierarchical_df['recall_1'] >= MIN_THRESHOLDS['recall']) &
    (hierarchical_df['precision_1'] >= MIN_THRESHOLDS['precision'])
]

if len(production_performance) > 0:
    best_production_idx = production_performance['optimization_score'].idxmax()
    optimal_threshold = production_performance.loc[best_production_idx, 'threshold']
    selected_row = production_performance.loc[best_production_idx]
    print(f"Optimal threshold: {optimal_threshold:.2f}")
    print(f"  Acc: {selected_row['accuracy']:.3f}, Rec: {selected_row['recall_1']:.3f}, Prec: {selected_row['precision_1']:.3f}")
    print(f"  TP: {selected_row['tp']}, FP: {selected_row['fp']}, FN: {selected_row['fn']}, FP/FN: {selected_row['fp_fn_ratio']:.2f}")
else:
    # Fallback: best optimization score overall
    best_score_idx = hierarchical_df['optimization_score'].idxmax()
    optimal_threshold = hierarchical_df.loc[best_score_idx, 'threshold']
    selected_row = hierarchical_df.loc[best_score_idx]
    print(f"Fallback threshold: {optimal_threshold:.2f}")
    print(f"  Acc: {selected_row['accuracy']:.3f}, Rec: {selected_row['recall_1']:.3f}, Prec: {selected_row['precision_1']:.3f}")
    print(f"  TP: {selected_row['tp']}, FP: {selected_row['fp']}, FN: {selected_row['fn']}, FP/FN: {selected_row['fp_fn_ratio']:.2f}")

# Apply optimal threshold to TEST SET for final evaluation
hierarchical_probs_test, elite_test_probs, d1_test_probs = predict_d1_hierarchical_ensemble(
    X_full_test, X_full_test_scaled_dnn, X_full_test_scaled_svm)

# Final predictions on TEST SET
y_pred_hierarchical = (hierarchical_probs_test >= optimal_threshold).astype(int)

print(f"\nFINAL HIERARCHICAL ENSEMBLE RESULTS:")
print(f"Accuracy: {accuracy_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"F1 Score: {f1_score(y_full_test, y_pred_hierarchical):.4f}")
print(f"D1 Recall: {recall_score(y_full_test, y_pred_hierarchical, pos_label=1):.4f}")
print(f"D1 Precision: {precision_score(y_full_test, y_pred_hierarchical, pos_label=1):.4f}")

print(f"\nClassification Report:")
print(classification_report(y_full_test, y_pred_hierarchical))

cm = confusion_matrix(y_full_test, y_pred_hierarchical)
tn, fp, fn, tp = cm.ravel()
print(f"\nConfusion Matrix Analysis:")
print(cm)

most_freq_class = y_full_test.value_counts(normalize=True).max()
final_accuracy = accuracy_score(y_full_test, y_pred_hierarchical)
print(f"\nNo Information Rate: {most_freq_class:.4f}")
print(f"Improvement: {final_accuracy - most_freq_class:+.4f}")

print(f"\nCATCHER D1 HIERARCHICAL ENSEMBLE MODEL COMPLETE!")

# ============================================================================
# XGB FEATURE IMPORTANCE ANALYSIS
# ============================================================================
print(f"\n📊 XGBoost Feature Importance Analysis:")

# Get feature importance from the final XGB model
feature_importance = xgb_full.feature_importances_
feature_names = X_full.columns

# Create feature importance dataframe
importance_df = pd.DataFrame({
    'feature': feature_names,
    'importance': feature_importance
}).sort_values('importance', ascending=False)

print(f"\nAll {len(importance_df)} Features (sorted by importance):")
print("=" * 60)
for i, row in importance_df.iterrows():
    print(f"{i+1:2d}. {row['feature']:<35} {row['importance']:.4f}")