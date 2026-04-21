"""
RECALL-FOCUSED CATCHER P4 PREDICTION MODEL V3
=============================================

Prioritizes P4 player detection (recall) over conservative predictions.
Uses 4-model ensemble: XGBoost + LightGBM + Neural Network + SVM

Key Changes:
- Recall-first optimization (catch P4 players, accept some false positives)
- Aggressive thresholds (0.15-0.60 range)
- Elite player business rules
- Class weight boosting for minority class
- Simplified ensemble without meta-learner complexity

Target: Maximize recall while maintaining F1 > 0.35 and precision > 0.25
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix, f1_score, balanced_accuracy_score, accuracy_score, recall_score, precision_score
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
import lightgbm as lgb
import xgboost as xgb
import optuna
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

# Load data
csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/c_p4_or_not_data.csv'
df = pd.read_csv(csv_path)

print(f"P4 Distribution: {df['p4_or_not'].value_counts()}")
print(f"P4 Rate: {df['p4_or_not'].mean():.2%}")
p4_ratio = (df['p4_or_not'] == 0).sum() / (df['p4_or_not'] == 1).sum()
print(f"Class imbalance ratio: {p4_ratio:.1f}:1")

# Aggressive class weighting for recall focus
class_weight_ratio = p4_ratio * 1.75  # Boost minority class significantly
print(f"Boosted class weight ratio: {class_weight_ratio:.2f}")

# Create categorical encodings
df = pd.get_dummies(df, columns=['player_region', 'throwing_hand', 'hitting_handedness'], 
                   prefix_sep='_', drop_first=True)

# ============================================================================
# RECALL-FOCUSED FEATURE ENGINEERING
# ============================================================================

print("🎯 RECALL-FOCUSED FEATURE ENGINEERING...")

# 1. CORE CATCHER METRICS
df['power_speed'] = df['exit_velo_max'] / df['sixty_time']
df['c_velo_sixty_ratio'] = df['c_velo'] / df['sixty_time']
df['height_weight'] = df['height'] * df['weight']
df['bmi'] = df['weight'] / (df['height'] / 12) ** 2

# 2. DEFENSIVE EXCELLENCE METRICS
df['pop_time_c_velo_ratio'] = df['pop_time'] / df['c_velo'] * 100
df['defensive_efficiency'] = df['c_velo'] / df['pop_time']
df['catch_throw_index'] = (df['c_velo'] * 10) / df['pop_time']
df['framing_potential'] = df['height'] * (1 / df['pop_time'])
df['blocking_profile'] = df['weight'] * (1 / df['sixty_time'])

# 3. P4 ELITE THRESHOLDS (Aggressive for recall)
df['elite_exit_velo'] = (df['exit_velo_max'] >= 96.0).astype(int)  # Lowered from 98
df['elite_c_velo'] = (df['c_velo'] >= 76.0).astype(int)          # Lowered from 78
df['elite_pop_time'] = (df['pop_time'] <= 2.0).astype(int)       # Increased from 1.95
df['elite_speed'] = (df['sixty_time'] <= 7.2).astype(int)        # Increased from 7.0
df['elite_size'] = ((df['height'] >= 71) & (df['weight'] >= 185)).astype(int)  # Lowered

# 4. P4 TOOL COMBINATIONS
df['power_arm_combo'] = df['elite_exit_velo'] * df['elite_c_velo']
df['arm_pop_combo'] = df['elite_c_velo'] * df['elite_pop_time']
df['speed_power_combo'] = df['elite_speed'] * df['elite_exit_velo']
df['total_elite_tools'] = (df['elite_exit_velo'] + df['elite_c_velo'] + 
                          df['elite_pop_time'] + df['elite_speed'] + df['elite_size'])

# 5. PERCENTILE RANKINGS
percentile_features = ['exit_velo_max', 'c_velo', 'pop_time', 'sixty_time', 'height', 'weight']
for col in percentile_features:
    if col in ['sixty_time', 'pop_time']:  # Lower is better
        df[f'{col}_percentile'] = (1 - df[col].rank(pct=True)) * 100
    else:  # Higher is better
        df[f'{col}_percentile'] = df[col].rank(pct=True) * 100

# 6. POWER & ATHLETICISM
df['power_per_pound'] = df['exit_velo_max'] / df['weight']
df['arm_per_pound'] = df['c_velo'] / df['weight']
df['speed_size_efficiency'] = (df['height'] * df['weight']) / (df['sixty_time'] ** 2)
df['athletic_index'] = (df['power_speed'] * df['height'] * df['weight']) / df['sixty_time']
df['size_adjusted_power'] = df['exit_velo_max'] / (df['height'] / 72) / (df['weight'] / 180)

# 7. COMPOSITE P4 SCORES (Recall-oriented weights)
df['p4_offensive_score'] = (
    df['exit_velo_max_percentile'] * 0.5 +    # Power emphasized for P4
    df['sixty_time_percentile'] * 0.3 +      # Speed important
    df['height_percentile'] * 0.2            # Size factor
)

df['p4_defensive_score'] = (
    df['c_velo_percentile'] * 0.6 +          # Arm strength critical  
    df['pop_time_percentile'] * 0.4          # Release time
)

df['p4_overall_score'] = (
    df['p4_offensive_score'] * 0.65 +        # Offense weighted higher
    df['p4_defensive_score'] * 0.35          # Defense still important
)

# 8. ELITE DETECTION FEATURES
df['super_elite'] = ((df['exit_velo_max'] >= 100) & (df['c_velo'] >= 80) & (df['pop_time'] <= 1.9)).astype(int)
df['power_catcher'] = ((df['exit_velo_max'] >= 98) & (df['height'] >= 72)).astype(int)
df['defensive_specialist'] = ((df['c_velo'] >= 78) & (df['pop_time'] <= 1.95)).astype(int)
df['complete_player'] = (df['total_elite_tools'] >= 4).astype(int)

# 9. ADVANCED RATIOS
df['exit_to_sixty_ratio'] = df['exit_velo_max'] / df['sixty_time']
df['defensive_power_ratio'] = df['c_velo'] / df['exit_velo_max']
df['arm_strength_index'] = df['c_velo'] * df['height'] / 100
df['pop_efficiency'] = 1 / df['pop_time']

print(f"Total engineered features: {df.shape[1]}")

# ============================================================================
# RECALL-FOCUSED FEATURE SELECTION
# ============================================================================

print("🔍 RECALL-FOCUSED FEATURE SELECTION...")

# Prepare features
y = df['p4_or_not']
X = df.drop(['p4_or_not', 'primary_position'], axis=1)

# Quick feature importance ranking
quick_lgb = lgb.LGBMClassifier(
    objective='binary',
    scale_pos_weight=class_weight_ratio,
    num_leaves=50,
    learning_rate=0.1,
    n_estimators=100,
    random_state=42,
    verbose=-1
)

quick_lgb.fit(X, y)
feature_importance_df = pd.DataFrame({
    'feature': X.columns,
    'importance': quick_lgb.feature_importances_
}).sort_values('importance', ascending=False)

# Select top features (keep more for recall)
n_features_to_keep = min(35, max(20, int(len(X.columns) * 0.7)))  # 35 features max
top_features = feature_importance_df.head(n_features_to_keep)['feature'].tolist()
X_selected = X[top_features]

print(f"Selected {len(top_features)} features from {len(X.columns)} total")
print(f"Top 10 features: {top_features[:10]}")

# ============================================================================
# DATA SPLITTING
# ============================================================================

# Split data: 65% train, 15% validation, 20% test
X_temp, X_test, y_temp, y_test = train_test_split(X_selected, y, test_size=0.20, random_state=42, stratify=y)
X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.1875, random_state=42, stratify=y_temp)

print(f"Train size: {len(X_train)} ({len(X_train)/len(X_selected):.1%})")
print(f"Validation size: {len(X_val)} ({len(X_val)/len(X_selected):.1%})")
print(f"Test size: {len(X_test)} ({len(X_test)/len(X_selected):.1%})")

# Scale features for neural network and SVM
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_val_scaled = scaler.transform(X_val)
X_test_scaled = scaler.transform(X_test)

# SMOTE for neural network training only
smote = SMOTE(random_state=42, k_neighbors=3)
X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)
X_train_scaled_smote = scaler.fit_transform(X_train_smote)

print(f"SMOTE training distribution: {pd.Series(y_train_smote).value_counts().to_dict()}")

# ============================================================================
# RECALL-FIRST OPTIMIZATION FUNCTIONS
# ============================================================================

def recall_focused_score(y_true, y_pred):
    """Prioritize recall while maintaining reasonable precision"""
    recall = recall_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    
    # Heavy recall weighting with precision floor
    if precision < 0.20:  # Penalty for extremely low precision
        precision_penalty = (0.20 - precision) * 2
    else:
        precision_penalty = 0
    
    # Score: 60% recall + 25% F1 + 15% precision - penalty
    score = 0.6 * recall + 0.25 * f1 + 0.15 * precision - precision_penalty
    return score

# 1. LightGBM with aggressive class weights
def objective_lgb(trial):
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'scale_pos_weight': class_weight_ratio * trial.suggest_float('pos_weight_mult', 1.2, 2.0),
        'num_leaves': trial.suggest_int('num_leaves', 20, 80),
        'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.15),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.7, 0.95),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.7, 0.95),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 5),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 30),
        'reg_alpha': trial.suggest_float('reg_alpha', 0, 1.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0, 1.0),
        'verbose': -1,
        'random_state': 42
    }
    
    model = lgb.LGBMClassifier(**params, n_estimators=200)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)
    return recall_focused_score(y_val, y_pred)

# 2. XGBoost with recall focus
def objective_xgb(trial):
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'scale_pos_weight': class_weight_ratio * trial.suggest_float('pos_weight_mult', 1.2, 2.0),
        'max_depth': trial.suggest_int('max_depth', 3, 7),
        'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.15),
        'subsample': trial.suggest_float('subsample', 0.7, 0.95),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.7, 0.95),
        'reg_alpha': trial.suggest_float('reg_alpha', 0, 1.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0, 1.0),
        'random_state': 42,
        'verbosity': 0
    }
    
    model = xgb.XGBClassifier(**params, n_estimators=200)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)
    return recall_focused_score(y_val, y_pred)

# 3. Neural Network with SMOTE
def objective_mlp(trial):
    hidden_layers = []
    n_layers = trial.suggest_int('n_layers', 2, 4)
    for i in range(n_layers):
        hidden_layers.append(trial.suggest_int(f'layer_{i}', 64, 400))
    
    params = {
        'hidden_layer_sizes': tuple(hidden_layers),
        'activation': trial.suggest_categorical('activation', ['relu', 'tanh']),
        'alpha': trial.suggest_float('alpha', 1e-5, 1e-2, log=True),
        'learning_rate_init': trial.suggest_float('learning_rate_init', 1e-4, 1e-2, log=True),
        'max_iter': 400,
        'random_state': 42,
        'early_stopping': True,
        'validation_fraction': 0.1
    }
    
    model = MLPClassifier(**params)
    model.fit(X_train_scaled_smote, y_train_smote)
    y_pred = model.predict(X_val_scaled)
    return recall_focused_score(y_val, y_pred)

# 4. SVM with aggressive class weights
def objective_svm(trial):
    params = {
        'C': trial.suggest_float('C', 0.1, 100, log=True),
        'gamma': trial.suggest_categorical('gamma', ['scale', 'auto']),
        'kernel': trial.suggest_categorical('kernel', ['rbf', 'poly']),
        'class_weight': {0: 1, 1: class_weight_ratio * trial.suggest_float('pos_weight_mult', 1.2, 2.0)},
        'random_state': 42,
        'probability': True
    }
    
    if params['kernel'] == 'poly':
        params['degree'] = trial.suggest_int('degree', 2, 4)
    
    model = SVC(**params)
    model.fit(X_train_scaled, y_train)
    y_pred = model.predict(X_val_scaled)
    return recall_focused_score(y_val, y_pred)

# ============================================================================
# OPTIMIZE MODELS FOR RECALL
# ============================================================================

print("\n🚀 OPTIMIZING 4-MODEL ENSEMBLE FOR RECALL...")

print("Optimizing LightGBM...")
study_lgb = optuna.create_study(direction='maximize')
study_lgb.optimize(objective_lgb, n_trials=75, show_progress_bar=True)

print("Optimizing XGBoost...")
study_xgb = optuna.create_study(direction='maximize')
study_xgb.optimize(objective_xgb, n_trials=75, show_progress_bar=True)

print("Optimizing Neural Network...")
study_mlp = optuna.create_study(direction='maximize')
study_mlp.optimize(objective_mlp, n_trials=50, show_progress_bar=True)

print("Optimizing SVM...")
study_svm = optuna.create_study(direction='maximize')
study_svm.optimize(objective_svm, n_trials=50, show_progress_bar=True)

# Store CV scores for ensemble weighting
cv_scores = {
    'lgb': study_lgb.best_value,
    'xgb': study_xgb.best_value,
    'mlp': study_mlp.best_value,
    'svm': study_svm.best_value
}

print(f"\n✅ Recall-Focused CV Scores:")
for name, score in cv_scores.items():
    print(f"   {name.upper()}: {score:.4f}")

# ============================================================================
# TRAIN FINAL MODELS
# ============================================================================

print("\n🎯 TRAINING FINAL RECALL-FOCUSED MODELS...")

# LightGBM
best_params_lgb = study_lgb.best_params.copy()
pos_weight_mult = best_params_lgb.pop('pos_weight_mult', 1.0)
best_params_lgb.update({
    'scale_pos_weight': class_weight_ratio * pos_weight_mult,
    'verbose': -1,
    'random_state': 42
})
lgb_model = lgb.LGBMClassifier(**best_params_lgb, n_estimators=200)
lgb_model.fit(X_train, y_train)

# XGBoost
best_params_xgb = study_xgb.best_params.copy()
pos_weight_mult_xgb = best_params_xgb.pop('pos_weight_mult', 1.0)
best_params_xgb.update({
    'scale_pos_weight': class_weight_ratio * pos_weight_mult_xgb,
    'random_state': 42,
    'verbosity': 0
})
xgb_model = xgb.XGBClassifier(**best_params_xgb, n_estimators=200)
xgb_model.fit(X_train, y_train)

# Neural Network
best_params_mlp = study_mlp.best_params.copy()
hidden_layers = []
n_layers = best_params_mlp.pop('n_layers')
for i in range(n_layers):
    hidden_layers.append(best_params_mlp.pop(f'layer_{i}'))
best_params_mlp['hidden_layer_sizes'] = tuple(hidden_layers)
best_params_mlp.update({'max_iter': 400, 'random_state': 42, 'early_stopping': True, 'validation_fraction': 0.1})
mlp_model = MLPClassifier(**best_params_mlp)
mlp_model.fit(X_train_scaled_smote, y_train_smote)

# SVM
best_params_svm = study_svm.best_params.copy()
pos_weight_mult_svm = best_params_svm.pop('pos_weight_mult', 1.0)
best_params_svm.update({
    'class_weight': {0: 1, 1: class_weight_ratio * pos_weight_mult_svm},
    'probability': True
})
svm_model = SVC(**best_params_svm)
svm_model.fit(X_train_scaled, y_train)

models = {
    'lgb': lgb_model,
    'xgb': xgb_model,
    'mlp': mlp_model,
    'svm': svm_model
}

# ============================================================================
# RECALL-FIRST THRESHOLD OPTIMIZATION
# ============================================================================

print("\n🎯 RECALL-FIRST THRESHOLD OPTIMIZATION...")

# Get validation probabilities
lgb_val_probs = lgb_model.predict_proba(X_val)[:, 1]
xgb_val_probs = xgb_model.predict_proba(X_val)[:, 1]
mlp_val_probs = mlp_model.predict_proba(X_val_scaled)[:, 1]
svm_val_probs = svm_model.predict_proba(X_val_scaled)[:, 1]

# Performance-weighted ensemble
total_score = sum(cv_scores.values())
weights = {name: score/total_score for name, score in cv_scores.items()}
print(f"Ensemble weights: {weights}")

# Weighted ensemble
ensemble_val_probs = (lgb_val_probs * weights['lgb'] + 
                     xgb_val_probs * weights['xgb'] + 
                     mlp_val_probs * weights['mlp'] + 
                     svm_val_probs * weights['svm'])

# Apply elite business rules
def apply_elite_boost(probs, features):
    """Boost probabilities for obviously elite players"""
    elite_mask = (
        (features['exit_velo_max'] >= 98) & (features['c_velo'] >= 78) |  # Power + Arm
        (features['super_elite'] == 1) |                                   # Super elite combo
        (features['total_elite_tools'] >= 4)                              # 4+ elite tools
    )
    
    if elite_mask.sum() > 0:
        probs[elite_mask] = np.maximum(probs[elite_mask], 0.75)
        print(f"Applied elite boost to {elite_mask.sum()} players")
    
    return probs

ensemble_val_probs = apply_elite_boost(ensemble_val_probs, X_val)

# Test balanced thresholds for optimal precision/recall trade-off
thresholds = np.arange(0.15, 0.70, 0.05)
best_threshold = 0.5
best_f1 = 0
threshold_results = []

print("Testing balanced thresholds (Recall | Precision | F1 | Balance Score):")
for threshold in thresholds:
    val_preds = (ensemble_val_probs >= threshold).astype(int)
    val_recall = recall_score(y_val, val_preds)
    val_precision = precision_score(y_val, val_preds) if val_preds.sum() > 0 else 0
    val_f1 = f1_score(y_val, val_preds)
    
    # Balance score: prioritize recall but require decent precision
    if val_precision >= 0.35:  # Minimum precision threshold
        balance_score = 0.6 * val_recall + 0.4 * val_precision  # 60% recall, 40% precision
    else:
        balance_score = 0  # Penalty for low precision
    
    threshold_results.append((threshold, val_recall, val_precision, val_f1, balance_score))
    print(f"  {threshold:.2f}: {val_recall:.3f} | {val_precision:.3f} | {val_f1:.3f} | {balance_score:.3f}")
    
    # Select threshold with best balance score (recall + precision)
    if balance_score > best_f1:
        best_f1 = balance_score
        best_threshold = threshold

print(f"\n✅ Optimal balanced threshold: {best_threshold:.3f} (Balance score: {best_f1:.3f})")

# Also test specific threshold range 0.35-0.45 for comparison
print(f"\n🎯 FOCUSED ANALYSIS: Threshold range 0.35-0.45")
focused_thresholds = [0.35, 0.40, 0.45]
for threshold in focused_thresholds:
    val_preds = (ensemble_val_probs >= threshold).astype(int)
    val_recall = recall_score(y_val, val_preds)
    val_precision = precision_score(y_val, val_preds) if val_preds.sum() > 0 else 0
    val_f1 = f1_score(y_val, val_preds)
    
    print(f"  Threshold {threshold:.2f}: Recall={val_recall:.3f}, Precision={val_precision:.3f}, F1={val_f1:.3f}")

# If no threshold meets precision requirement, use 0.40 as reasonable default
if best_f1 == 0:
    best_threshold = 0.40
    print(f"\n⚠️  No threshold met precision >= 0.35, using default 0.40")

# ============================================================================
# FINAL TEST EVALUATION
# ============================================================================

print("\n" + "="*80)
print("RECALL-FOCUSED CATCHER P4 MODEL RESULTS (V3)")
print("="*80)

# Get test probabilities
lgb_test_probs = lgb_model.predict_proba(X_test)[:, 1]
xgb_test_probs = xgb_model.predict_proba(X_test)[:, 1]
mlp_test_probs = mlp_model.predict_proba(X_test_scaled)[:, 1]
svm_test_probs = svm_model.predict_proba(X_test_scaled)[:, 1]

# Weighted ensemble
ensemble_test_probs = (lgb_test_probs * weights['lgb'] + 
                      xgb_test_probs * weights['xgb'] + 
                      mlp_test_probs * weights['mlp'] + 
                      svm_test_probs * weights['svm'])

# Apply elite boost
ensemble_test_probs = apply_elite_boost(ensemble_test_probs, X_test)

# Final predictions
final_preds = (ensemble_test_probs >= best_threshold).astype(int)

# Calculate metrics
final_f1 = f1_score(y_test, final_preds)
final_accuracy = accuracy_score(y_test, final_preds)
final_bal_acc = balanced_accuracy_score(y_test, final_preds)
final_recall = recall_score(y_test, final_preds)
final_precision = precision_score(y_test, final_preds)

# NIR calculation
p4_rate = y_test.mean()
nir = max(p4_rate, 1 - p4_rate)

# Elite players identified
elite_test_count = ((X_test['exit_velo_max'] >= 98) & (X_test['c_velo'] >= 78)).sum()

print(f"Optimized Threshold: {best_threshold:.3f}")
print(f"F1 Score: {final_f1:.4f}")
print(f"Recall (P4 Detection): {final_recall:.4f}")
print(f"Precision: {final_precision:.4f}")
print(f"Accuracy: {final_accuracy:.4f}")
print(f"Balanced Accuracy: {final_bal_acc:.4f}")
print(f"NIR (No Information Rate): {nir:.4f}")
print(f"Beat NIR: {'✅ YES' if final_accuracy > nir else '❌ NO'} ({final_accuracy - nir:+.4f})")

print(f"\nFeatures Used: {len(top_features)}")
print(f"Elite Players in Test Set: {elite_test_count}")
print(f"Ensemble Weights: {weights}")

print(f"\nIndividual Model CV Scores:")
for name, score in cv_scores.items():
    print(f"  {name.upper()}: {score:.4f}")

print("\nClassification Report:")
print(classification_report(y_test, final_preds))

print("\nConfusion Matrix:")
cm = confusion_matrix(y_test, final_preds)
print(cm)

# Confusion matrix analysis
tn, fp, fn, tp = cm.ravel()
print(f"\nConfusion Matrix Breakdown:")
print(f"True Negatives (Non-P4 correct): {tn}")
print(f"False Positives (Non-P4 as P4): {fp}")
print(f"False Negatives (P4 missed): {fn}")
print(f"True Positives (P4 caught): {tp}")
print(f"P4 Detection Rate: {tp}/{tp+fn} = {tp/(tp+fn):.1%}")

print("\nTop 15 Feature Importances (LightGBM):")
final_importance = pd.DataFrame({
    'feature': top_features,
    'importance': lgb_model.feature_importances_
}).sort_values('importance', ascending=False)

print(final_importance.head(15).to_string(index=False))

print(f"\n{'='*80}")
print("RECALL-FOCUSED IMPROVEMENTS:")
print(f"- 4-model ensemble: LightGBM + XGBoost + Neural Network + SVM")
print(f"- Aggressive class weighting (boosted {class_weight_ratio:.1f}x)")
print(f"- Recall-first optimization (60% recall + 25% F1 + 15% precision)")
print(f"- Elite player business rules and probability boosting")
print(f"- Lower P4 thresholds for broader talent identification")
print(f"- SMOTE oversampling for neural network training")
print(f"- Aggressive threshold testing (0.15-0.60 range)")
print(f"{'='*80}")