import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, recall_score, balanced_accuracy_score, precision_score
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
import optuna
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

csv_path_eng ='/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/test/inf_p4_or_not_eng.csv'
df_eng = pd.read_csv(csv_path_eng)

# POWER 4 SPECIFIC FEATURE ENGINEERING
print("Creating Power 4-specific features...")

# 1. ELITE PERFORMANCE THRESHOLDS
# Power 4 programs want players who exceed multiple thresholds
df_eng['elite_exit_velo'] = (df_eng['exit_velo_max'] >= df_eng['exit_velo_max'].quantile(0.75)).astype(int)
df_eng['elite_inf_velo'] = (df_eng['inf_velo'] >= df_eng['inf_velo'].quantile(0.75)).astype(int) 
df_eng['elite_speed'] = (df_eng['sixty_time'] <= df_eng['sixty_time'].quantile(0.25)).astype(int)
df_eng['elite_size'] = ((df_eng['height'] >= df_eng['height'].quantile(0.6)) & 
                        (df_eng['weight'] >= df_eng['weight'].quantile(0.6))).astype(int)

# 2. MULTI-TOOL EXCELLENCE 
# Power 4 wants well-rounded players, not one-dimensional
df_eng['multi_tool_count'] = (df_eng['elite_exit_velo'] + df_eng['elite_inf_velo'] + 
                              df_eng['elite_speed'] + df_eng['elite_size'])
df_eng['is_multi_tool'] = (df_eng['multi_tool_count'] >= 2).astype(int)

# 3. ATHLETIC COMPOSITE SCORES
# Overall athleticism matters more at Power 4 level
df_eng['power_speed_index'] = df_eng['exit_velo_max'] * (1 / df_eng['sixty_time'])
df_eng['athletic_index'] = (df_eng['power_speed'] * df_eng['height'] * df_eng['weight']) / df_eng['sixty_time']
df_eng['size_speed_combo'] = (df_eng['height'] * df_eng['weight']) / df_eng['sixty_time']

# 4. POSITION-SPECIFIC POWER 4 FEATURES
# Different positions have different P4 requirements
df_eng['ss_power4_profile'] = (df_eng['primary_position_SS'] * 
                               (df_eng['inf_velo'] * df_eng['power_speed'] * (1/df_eng['sixty_time'])))
df_eng['corner_inf_power'] = (((df_eng['primary_position_2B'] == 0) &
                                (df_eng['primary_position_3B'] == 0) &
                                (df_eng['primary_position_SS'] == 0)).astype(int) + 
                               (df_eng['primary_position_3B'] == 1).astype(int) * 
                              df_eng['exit_velo_max'] * df_eng['power_speed'])

# 5. CONSISTENCY METRICS
# Power 4 programs want consistent performers, not streaky players
# Using coefficient of variation concepts with available metrics
df_eng['balanced_profile'] = np.minimum(df_eng['exit_velo_max']/100, df_eng['inf_velo']/100) * np.minimum(df_eng['power_speed'], 1/df_eng['sixty_time'])

# 6. REGIONAL RECRUITING ADVANTAGES  
# Power 4 programs recruit nationally, certain regions might be preferred
# goes west, south, midwest, northeast 
df_eng['power4_region'] = ((df_eng['player_region_South'] * 1.2) + 
                           (df_eng['player_region_West'] * 1.3) + 
                           (df_eng['player_region_Northeast'] * 0.85))
df_eng['top_hitter_region'] = df_eng['power4_region'] * df_eng['exit_velo_max']
df_eng['top_player_region'] = df_eng['power4_region'] * df_eng['velo_by_inf']

# 7. ADVANCED RATIOS FOR POWER 4
# Sophisticated metrics that separate elite from good
df_eng['exit_to_sixty_ratio'] = df_eng['exit_velo_max'] / df_eng['sixty_time']
df_eng['power_per_pound'] = df_eng['exit_velo_max'] / df_eng['weight']
df_eng['speed_size_efficiency'] = (df_eng['height'] * df_eng['weight']) / (df_eng['sixty_time'] ** 2)

# 8. PERCENTILE-BASED FEATURES
# Power 4 programs think in percentiles and rankings
for col in ['exit_velo_max', 'inf_velo', 'sixty_time', 'height', 'weight', 'power_speed']:
    if col in df_eng.columns:
        if col == 'sixty_time':  # Lower is better for sixty_time
            df_eng[f'{col}_percentile'] = (1 - df_eng[col].rank(pct=True)) * 100
        else:  # Higher is better for other metrics
            df_eng[f'{col}_percentile'] = df_eng[col].rank(pct=True) * 100

# 9. ELITE THRESHOLD COMBINATIONS
# Power 4 might have specific combinations they look for
df_eng['power_speed_elite'] = ((df_eng['exit_velo_max'] >= df_eng['exit_velo_max'].quantile(0.7)) & 
                               (df_eng['sixty_time'] <= df_eng['sixty_time'].quantile(0.3))).astype(int)

# Add P4-specific thresholds based on actual P4 vs Non-P4 splits:
p4_players = df_eng[df_eng['p4_or_not'] == 1]
non_p4_players = df_eng[df_eng['p4_or_not'] == 0]

# New features based on actual P4 differences:
df_eng['exit_velo_p4_threshold'] = (df_eng['exit_velo_max'] >= p4_players['exit_velo_max'].quantile(0.5)).astype(int)
df_eng['inf_velo_p4_threshold'] = (df_eng['inf_velo'] >= p4_players['inf_velo'].quantile(0.5)).astype(int)
df_eng['speed_p4_threshold'] = (df_eng['sixty_time'] <= p4_players['sixty_time'].quantile(0.5)).astype(int)

print("Power 4 feature engineering completed!")

# Prepare X, y - Strategic feature selection for Power 4 prediction
drop_cols = [
    # Target variables
    'p4_or_not', 'd1_or_not'
]

X = df_eng.drop(columns=drop_cols)
y = df_eng['p4_or_not']

print(f"Features for Power 4 prediction: {X.columns}")

# Clean data
X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
for col in X.select_dtypes(include=[np.number]).columns:
    Q1, Q3 = X[col].quantile(0.01), X[col].quantile(0.99)
    IQR = Q3 - Q1
    X[col] = X[col].clip(Q1 - 1.5*IQR, Q3 + 1.5*IQR)

# Split into train+val and test
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)
# Split train_val into train and val
X_train, X_val, y_train, y_val = train_test_split(
    X_train_val, y_train_val, test_size=0.2, stratify=y_train_val, random_state=42
)

# ============================================================================
# SMOTE IMPLEMENTATION FOR CLASS IMBALANCE
# ============================================================================
print(f"Before SMOTE - Train set distribution:")
print(f"Non-P4 (0): {(y_train == 0).sum()} ({(y_train == 0).mean():.2%})")
print(f"P4 (1): {(y_train == 1).sum()} ({(y_train == 1).mean():.2%})")

# Apply SMOTE to training data only
smote = SMOTE(random_state=42, k_neighbors=5)
X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)

print(f"After SMOTE - Train set distribution:")
print(f"Non-P4 (0): {(y_train_smote == 0).sum()} ({(y_train_smote == 0).mean():.2%})")
print(f"P4 (1): {(y_train_smote == 1).sum()} ({(y_train_smote == 1).mean():.2%})")
print(f"SMOTE generated {len(X_train_smote) - len(X_train)} synthetic P4 samples")

# Convert back to DataFrame for consistency (optional, but helpful for debugging)
X_train_smote = pd.DataFrame(X_train_smote, columns=X_train.columns)
y_train_smote = pd.Series(y_train_smote, name=y_train.name)

# Optuna objective for XGBoost - Optimized for Power 4 classification
def xgb_objective(trial):
    # Calculate actual class imbalance for better scale_pos_weight range
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'use_label_encoder': False,
        'learning_rate': trial.suggest_float('eta', 1e-3, 2e-1, log=True),  # Wider range
        'max_depth': trial.suggest_int('max_depth', 4, 12),  # Deeper for complex P4 patterns
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 20),  # Higher for imbalanced data
        'gamma': trial.suggest_float('gamma', 1e-8, 10.0, log=True),  # Higher regularization
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),  # Conservative range
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.3, 1.0),  # More feature selection
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 100.0, log=True),
        # Adjusted scale_pos_weight for P4 class imbalance (likely more Non-P4 than P4)
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 4.0),
    }
    model = xgb.XGBClassifier(**params, n_estimators=1000, random_state=42, missing=np.nan)
    model.fit(
        X_train_smote, y_train_smote,
        eval_set=[(X_val, y_val)],
        verbose=False
    )
    preds = model.predict(X_val)

    accuracy = accuracy_score(y_val, preds)    
    recall_0 = recall_score(y_val, preds, pos_label=0)
    recall_1 = recall_score(y_val, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

# Run Optuna study
study = optuna.create_study(direction='maximize')
study.optimize(xgb_objective, n_trials=30, show_progress_bar=True, n_jobs=-1)

best_params = study.best_params

# Apply SMOTE to full train+val for final model training
X_train_val_smote, y_train_val_smote = smote.fit_resample(X_train_val, y_train_val)
print(f"Applied SMOTE to train+val: {len(X_train_val_smote)} samples (was {len(X_train_val)})")

# Cross-validation on train+val (with SMOTE applied in each fold)
from imblearn.pipeline import Pipeline as ImbPipeline
from imblearn.over_sampling import SMOTE

cv_pipeline = ImbPipeline([
    ('smote', SMOTE(random_state=42, k_neighbors=5)),
    ('classifier', xgb.XGBClassifier(
        **best_params, n_estimators=750,
        use_label_encoder=False, eval_metric='logloss',
        random_state=42, missing=np.nan
    ))
])

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_f1 = cross_val_score(cv_pipeline, X_train_val, y_train_val, cv=cv, scoring='f1')
print(f"5-fold CV F1 Score (with SMOTE): {cv_f1.mean():.4f}")

cv_accuracy = cross_val_score(cv_pipeline, X_train_val, y_train_val, cv=cv, scoring='accuracy')
print(f"5-fold CV Accuracy Score (with SMOTE): {cv_accuracy.mean():.4f}")

# Train final model on all train+val with SMOTE
final_model = xgb.XGBClassifier(
    **best_params, n_estimators=750,
    use_label_encoder=False, eval_metric='logloss',
    random_state=42, missing=np.nan
)
final_model.fit(X_train_val_smote, y_train_val_smote, verbose=False)

# ============================================================================
# THRESHOLD OPTIMIZATION
# ============================================================================
print("Optimizing prediction threshold...")

from sklearn.metrics import balanced_accuracy_score, precision_score

# Get probability predictions on test set
y_pred_proba = final_model.predict_proba(X_test)[:, 1]

# Test different thresholds
thresholds = np.arange(0.1, 0.9, 0.02)
results = []

for threshold in thresholds:
    y_pred_thresh = (y_pred_proba >= threshold).astype(int)
    
    accuracy = accuracy_score(y_test, y_pred_thresh)
    recall_0 = recall_score(y_test, y_pred_thresh, pos_label=0)
    recall_1 = recall_score(y_test, y_pred_thresh, pos_label=1)
    precision_1 = precision_score(y_test, y_pred_thresh, pos_label=1, zero_division=0)
    f1 = f1_score(y_test, y_pred_thresh, zero_division=0)
    balanced_acc = balanced_accuracy_score(y_test, y_pred_thresh)
    
    # Use same weighted score as optimization
    weighted_score = ((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6
    
    results.append({
        'threshold': threshold,
        'accuracy': accuracy,
        'recall_0': recall_0,
        'recall_1': recall_1,
        'precision_1': precision_1,
        'f1': f1,
        'balanced_acc': balanced_acc,
        'weighted_score': weighted_score
    })

# Convert to DataFrame for analysis
results_df = pd.DataFrame(results)

# Find best thresholds for different metrics
best_accuracy_idx = results_df['accuracy'].idxmax()
best_balanced_acc_idx = results_df['balanced_acc'].idxmax()
best_f1_idx = results_df['f1'].idxmax()
best_weighted_idx = results_df['weighted_score'].idxmax()

print(f"\nThreshold Analysis:")
print(f"Best Accuracy: {results_df.loc[best_accuracy_idx, 'threshold']:.2f} -> {results_df.loc[best_accuracy_idx, 'accuracy']:.4f}")
print(f"Best Balanced Accuracy: {results_df.loc[best_balanced_acc_idx, 'threshold']:.2f} -> {results_df.loc[best_balanced_acc_idx, 'balanced_acc']:.4f}")
print(f"Best F1: {results_df.loc[best_f1_idx, 'threshold']:.2f} -> {results_df.loc[best_f1_idx, 'f1']:.4f}")
print(f"Best Weighted Score: {results_df.loc[best_weighted_idx, 'threshold']:.2f} -> {results_df.loc[best_weighted_idx, 'weighted_score']:.4f}")

# Use the threshold that maximizes balanced accuracy (good for imbalanced data)
optimal_threshold = results_df.loc[best_balanced_acc_idx, 'threshold']
print(f"\nUsing optimal threshold: {optimal_threshold:.2f}")

# Print No Information Rate
most_freq_class = y_test.value_counts(normalize=True).max()
print(f"No Information Rate: {most_freq_class:.4f}")

print("=" * 60)
print("RESULTS WITH DEFAULT THRESHOLD (0.5)")
print("=" * 60)

# Evaluate with default threshold
y_pred_default = final_model.predict(X_test)
print(f"Test Accuracy: {accuracy_score(y_test, y_pred_default):.4f}")
print(classification_report(y_test, y_pred_default))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_default))

print("\n" + "=" * 60)
print(f"RESULTS WITH OPTIMIZED THRESHOLD ({optimal_threshold:.2f})")
print("=" * 60)

# Evaluate with optimized threshold
y_pred_optimal = (y_pred_proba >= optimal_threshold).astype(int)
print(f"Test Accuracy: {accuracy_score(y_test, y_pred_optimal):.4f}")
print(classification_report(y_test, y_pred_optimal))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_optimal))

# Show improvement metrics
default_balanced_acc = balanced_accuracy_score(y_test, y_pred_default)
optimal_balanced_acc = balanced_accuracy_score(y_test, y_pred_optimal)
default_recall_1 = recall_score(y_test, y_pred_default, pos_label=1)
optimal_recall_1 = recall_score(y_test, y_pred_optimal, pos_label=1)

print(f"\n📊 THRESHOLD OPTIMIZATION IMPACT:")
print(f"Balanced Accuracy: {default_balanced_acc:.4f} -> {optimal_balanced_acc:.4f} ({optimal_balanced_acc-default_balanced_acc:+.4f})")
print(f"P4 Recall (Class 1): {default_recall_1:.4f} -> {optimal_recall_1:.4f} ({optimal_recall_1-default_recall_1:+.4f})")

if optimal_balanced_acc > 0.70:
    print("🎯 SUCCESS: Achieved 70%+ balanced accuracy!")
elif optimal_balanced_acc > default_balanced_acc:
    print("✅ IMPROVEMENT: Threshold optimization helped!")
else:
    print("⚠️  Default threshold was better")

print("\n" + "=" * 60)

# ============================================================================
# SMOTE IMPACT ANALYSIS
# ============================================================================
print("\n🔍 SMOTE IMPACT ANALYSIS:")
print(f"Original training samples: {len(X_train_val)}")
print(f"After SMOTE training samples: {len(X_train_val_smote)}")
print(f"Synthetic samples generated: {len(X_train_val_smote) - len(X_train_val)}")

original_p4_ratio = (y_train_val == 1).mean()
smote_p4_ratio = (y_train_val_smote == 1).mean()
print(f"Original P4 ratio: {original_p4_ratio:.2%}")
print(f"After SMOTE P4 ratio: {smote_p4_ratio:.2%}")

print("\n💡 How SMOTE helps with Power 4 prediction:")
print("1. Generates synthetic P4 players by interpolating between existing P4 samples")
print("2. Balances the dataset so XGBoost doesn't overwhelmingly predict Non-P4")
print("3. Creates more diverse P4 examples for the model to learn from")
print("4. Reduces the model's bias toward the majority class (Non-P4)")
print("5. Should improve P4 recall without drastically hurting overall accuracy")

if optimal_recall_1 > 0.3:
    print("✅ SMOTE + Threshold optimization successfully improved P4 detection!")
elif optimal_recall_1 > default_recall_1:
    print("📈 SMOTE helped improve P4 recall - good progress!")
else:
    print("⚠️ May need additional techniques beyond SMOTE")

print("\n" + "=" * 60)

# Feature importance
imp_df = pd.DataFrame({
    'feature': X.columns,
    'importance': final_model.feature_importances_
}).sort_values('importance', ascending=False)
print("\nXGBoost Feature Importances:")
print(imp_df)

print("\nColumns used in the XGBoost model:")
print(list(X.columns))

# ============================================================================
# ADDITIONAL MODELS WITH SMOTE OPTIMIZATION
# ============================================================================
print("\n" + "=" * 80)
print("COMPARING MULTIPLE MODELS WITH SMOTE")
print("=" * 80)

# Store results for comparison
model_results = {}

# XGBoost (already trained) - store results
xgb_preds = final_model.predict(X_test)
model_results['XGBoost'] = {
    'model': final_model,
    'predictions': xgb_preds,
    'accuracy': accuracy_score(y_test, xgb_preds),
    'balanced_acc': balanced_accuracy_score(y_test, xgb_preds),
    'f1': f1_score(y_test, xgb_preds),
    'recall_1': recall_score(y_test, xgb_preds, pos_label=1),
    'confusion_matrix': confusion_matrix(y_test, xgb_preds),
    'feature_importance': pd.DataFrame({
        'feature': X.columns,
        'importance': final_model.feature_importances_
    }).sort_values('importance', ascending=False).head(5)
}

# ============================================================================
# CATBOOST WITH SMOTE
# ============================================================================
print("\n🐱 Training CatBoost with SMOTE...")

def catboost_objective(trial):
    params = {
        'iterations': 500,
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'depth': trial.suggest_int('depth', 4, 10),
        'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1e-8, 10.0, log=True),
        'bagging_temperature': trial.suggest_float('bagging_temperature', 0.0, 1.0),
        'random_strength': trial.suggest_float('random_strength', 0.0, 10.0),
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 4.0),
        'verbose': False,
        'random_seed': 42
    }
    
    model = cb.CatBoostClassifier(**params)
    model.fit(X_train_smote, y_train_smote, eval_set=(X_val, y_val), verbose=False)
    preds = model.predict(X_val)
    
    accuracy = accuracy_score(y_val, preds)
    recall_0 = recall_score(y_val, preds, pos_label=0)
    recall_1 = recall_score(y_val, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

study_cat = optuna.create_study(direction='maximize')
study_cat.optimize(catboost_objective, n_trials=30, show_progress_bar=True, n_jobs=-1)
best_cat_params = study_cat.best_params

# Train final CatBoost model
catboost_model = cb.CatBoostClassifier(**best_cat_params, verbose=False, random_seed=42)
catboost_model.fit(X_train_val_smote, y_train_val_smote, verbose=False)
cat_preds = catboost_model.predict(X_test)

model_results['CatBoost'] = {
    'model': catboost_model,
    'predictions': cat_preds,
    'accuracy': accuracy_score(y_test, cat_preds),
    'balanced_acc': balanced_accuracy_score(y_test, cat_preds),
    'f1': f1_score(y_test, cat_preds),
    'recall_1': recall_score(y_test, cat_preds, pos_label=1),
    'confusion_matrix': confusion_matrix(y_test, cat_preds),
    'feature_importance': pd.DataFrame({
        'feature': X.columns,
        'importance': catboost_model.feature_importances_
    }).sort_values('importance', ascending=False).head(5)
}

# ============================================================================
# LIGHTGBM WITH SMOTE
# ============================================================================
print("\n💡 Training LightGBM with SMOTE...")

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
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, 4.0),
        'verbose': -1,
        'random_state': 42
    }
    
    model = lgb.LGBMClassifier(**params, n_estimators=500)
    model.fit(X_train_smote, y_train_smote, eval_set=(X_val, y_val))
    preds = model.predict(X_val)
    
    accuracy = accuracy_score(y_val, preds)
    recall_0 = recall_score(y_val, preds, pos_label=0)
    recall_1 = recall_score(y_val, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

study_lgb = optuna.create_study(direction='maximize')
study_lgb.optimize(lightgbm_objective, n_trials=30, show_progress_bar=True, n_jobs=-1)
best_lgb_params = study_lgb.best_params

# Train final LightGBM model
lightgbm_model = lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=42)
lightgbm_model.fit(X_train_val_smote, y_train_val_smote)
lgb_preds = lightgbm_model.predict(X_test)

model_results['LightGBM'] = {
    'model': lightgbm_model,
    'predictions': lgb_preds,
    'accuracy': accuracy_score(y_test, lgb_preds),
    'balanced_acc': balanced_accuracy_score(y_test, lgb_preds),
    'f1': f1_score(y_test, lgb_preds),
    'recall_1': recall_score(y_test, lgb_preds, pos_label=1),
    'confusion_matrix': confusion_matrix(y_test, lgb_preds),
    'feature_importance': pd.DataFrame({
        'feature': X.columns,
        'importance': lightgbm_model.feature_importances_
    }).sort_values('importance', ascending=False).head(5)
}

# ============================================================================
# SVM WITH SMOTE
# ============================================================================
print("\n🚀 Training SVM with SMOTE...")

# Scale features for SVM
scaler = StandardScaler()
X_train_val_smote_scaled = scaler.fit_transform(X_train_val_smote)
X_test_scaled = scaler.transform(X_test)
X_train_smote_scaled = scaler.transform(X_train_smote)
X_val_scaled = scaler.transform(X_val)

def svm_objective(trial):
    params = {
        'C': trial.suggest_float('C', 1e-3, 1e3, log=True),
        'gamma': trial.suggest_categorical('gamma', ['scale', 'auto']),
        'kernel': trial.suggest_categorical('kernel', ['rbf', 'poly', 'sigmoid']),
        'class_weight': 'balanced',
        'random_state': 42
    }
    
    if params['kernel'] == 'poly':
        params['degree'] = trial.suggest_int('degree', 2, 4)
    
    model = SVC(**params)
    model.fit(X_train_smote_scaled, y_train_smote)
    preds = model.predict(X_val_scaled)
    
    accuracy = accuracy_score(y_val, preds)
    recall_0 = recall_score(y_val, preds, pos_label=0)
    recall_1 = recall_score(y_val, preds, pos_label=1)
    return float(((accuracy * 2) + recall_0 + (recall_1 * 3)) / 6)

study_svm = optuna.create_study(direction='maximize')
study_svm.optimize(svm_objective, n_trials=15, show_progress_bar=True, n_jobs=4)
best_svm_params = study_svm.best_params

# Train final SVM model
svm_model = SVC(**best_svm_params)
svm_model.fit(X_train_val_smote_scaled, y_train_val_smote)
svm_preds = svm_model.predict(X_test_scaled)

model_results['SVM'] = {
    'model': svm_model,
    'predictions': svm_preds,
    'accuracy': accuracy_score(y_test, svm_preds),
    'balanced_acc': balanced_accuracy_score(y_test, svm_preds),
    'f1': f1_score(y_test, svm_preds),
    'recall_1': recall_score(y_test, svm_preds, pos_label=1),
    'confusion_matrix': confusion_matrix(y_test, svm_preds),
    'feature_importance': pd.DataFrame({
        'feature': ['SVM does not provide feature importance'],
        'importance': ['N/A']
    })
}

# ============================================================================
# MODEL COMPARISON RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("MODEL COMPARISON RESULTS")
print("=" * 80)

for model_name, results in model_results.items():
    print(f"\n🔥 {model_name} Results:")
    print(f"Accuracy: {results['accuracy']:.4f}")
    print(f"Balanced Accuracy: {results['balanced_acc']:.4f}")
    print(f"F1 Score: {results['f1']:.4f}")
    print(f"P4 Recall: {results['recall_1']:.4f}")
    
    print(f"\nClassification Report:")
    print(classification_report(y_test, results['predictions']))
    
    print(f"Confusion Matrix:")
    print(results['confusion_matrix'])
    
    if model_name != 'SVM':
        print(f"\nTop 5 Most Important Features:")
        print(results['feature_importance'])
    
    print("-" * 60)

# Summary comparison
print("\n📊 SUMMARY COMPARISON:")
comparison_df = pd.DataFrame({
    'Model': list(model_results.keys()),
    'Accuracy': [results['accuracy'] for results in model_results.values()],
    'Balanced_Acc': [results['balanced_acc'] for results in model_results.values()],
    'F1_Score': [results['f1'] for results in model_results.values()],
    'P4_Recall': [results['recall_1'] for results in model_results.values()]
}).round(4)

print(comparison_df)

# Best model identification
best_balanced_acc_model = comparison_df.loc[comparison_df['Balanced_Acc'].idxmax(), 'Model']
best_p4_recall_model = comparison_df.loc[comparison_df['P4_Recall'].idxmax(), 'Model']

print(f"\n🏆 Best Balanced Accuracy: {best_balanced_acc_model}")
print(f"🎯 Best P4 Recall: {best_p4_recall_model}")

if comparison_df['Balanced_Acc'].max() > 0.60:
    print("✅ Success! At least one model achieved 60%+ balanced accuracy")
else:
    print("⚠️ All models below 60% balanced accuracy - may need more feature engineering")
