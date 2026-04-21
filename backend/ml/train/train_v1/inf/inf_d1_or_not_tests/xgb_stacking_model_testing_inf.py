import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, fbeta_score, f1_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
from sklearn.svm import SVC
import optuna
from optuna.samplers import TPESampler
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

# CRITICAL: Same test split as ensemble for fair comparison
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# Scale data for SVM
scaler_final = StandardScaler()
X_train_val_scaled = scaler_final.fit_transform(X_train_val)
X_test_scaled = scaler_final.transform(X_test)

beta = 0.7

print("Data Splits for CV-Stacking:")
print(f"Train+Val (CV meta-features): {X_train_val.shape[0]} samples")
print(f"Test (final eval): {X_test.shape[0]} samples")
print(f"Total: {X.shape[0]} samples")
print("Using 5-fold CV to generate out-of-fold predictions")
print("=" * 60)

# ============================================================================
# Load Pre-trained Model Parameters (for CV-Stacking)
# ============================================================================

def load_model_params(name):
    """Load model parameters"""
    models_dir = 'saved_models'
    params_path = f'{models_dir}/{name}_params.pkl'
    if os.path.exists(params_path):
        return joblib.load(params_path)
    return None

print("Loading pre-trained model parameters for CV-stacking...")

base_model_params = {}
base_model_names = ['xgboost', 'lightgbm', 'catboost', 'svm']

for name in base_model_names:
    params = load_model_params(name)
    if params is not None:
        base_model_params[name] = params
        print(f"✓ Loaded {name} parameters")
    else:
        print(f"✗ Could not load {name} parameters - run ensemble script first!")

if len(base_model_params) != 4:
    print("ERROR: Not all model parameters found. Please run ensemble_model_testing_inf_clean.py first!")
    exit()

print("=" * 60)

# ============================================================================
# Generate CV Out-of-Fold Predictions
# ============================================================================

print("Generating 5-fold CV out-of-fold predictions...")

def create_model_from_params(name, params):
    """Create model instance from saved parameters"""
    if name == 'xgboost':
        return xgb.XGBClassifier(**params, n_estimators=750, use_label_encoder=False, 
                                 eval_metric='logloss', random_state=42, missing=np.nan)
    elif name == 'lightgbm':
        return lgb.LGBMClassifier(**params, n_estimators=750, verbose=-1)
    elif name == 'catboost':
        return cb.CatBoostClassifier(**params, iterations=750, verbose=False)
    elif name == 'svm':
        return SVC(**params, probability=True)

# Initialize arrays for out-of-fold predictions
n_samples = len(X_train_val)
oof_predictions = np.zeros((n_samples, len(base_model_names)))
test_predictions = np.zeros((len(X_test), len(base_model_names)))

# 5-fold cross-validation
kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

for fold, (train_idx, val_idx) in enumerate(kf.split(X_train_val, y_train_val)):
    print(f"Processing fold {fold + 1}/5...")
    
    # Split data for this fold
    X_fold_train, X_fold_val = X_train_val.iloc[train_idx], X_train_val.iloc[val_idx]
    y_fold_train, y_fold_val = y_train_val.iloc[train_idx], y_train_val.iloc[val_idx]
    
    # Scale data for SVM
    scaler_fold = StandardScaler()
    X_fold_train_scaled = scaler_fold.fit_transform(X_fold_train)
    X_fold_val_scaled = scaler_fold.transform(X_fold_val)
    X_test_scaled_fold = scaler_fold.transform(X_test)
    
    # Train each model on this fold
    for i, name in enumerate(base_model_names):
        model = create_model_from_params(name, base_model_params[name])
        
        if name == 'svm':
            model.fit(X_fold_train_scaled, y_fold_train)
            # Out-of-fold predictions
            oof_predictions[val_idx, i] = model.predict_proba(X_fold_val_scaled)[:, 1]
            # Test predictions (will be averaged across folds)
            test_predictions[:, i] += model.predict_proba(X_test_scaled_fold)[:, 1] / 5
        else:
            if name == 'xgboost':
                model.fit(X_fold_train, y_fold_train, verbose=False)
            elif name == 'lightgbm':
                model.fit(X_fold_train, y_fold_train)
            elif name == 'catboost':
                model.fit(X_fold_train, y_fold_train)
            
            # Out-of-fold predictions
            oof_predictions[val_idx, i] = model.predict_proba(X_fold_val)[:, 1]
            # Test predictions (will be averaged across folds)
            test_predictions[:, i] += model.predict_proba(X_test)[:, 1] / 5

print("CV out-of-fold prediction generation completed!")
print(f"OOF predictions shape: {oof_predictions.shape}")
print(f"Test predictions shape: {test_predictions.shape}")

print("=" * 60)

# ============================================================================
# Feature Augmentation - Add Intelligent Meta-Features
# ============================================================================

print("Creating augmented meta-features...")

def create_augmented_features(base_probs, original_features):
    """Create intelligent meta-features from base model predictions and original features"""
    n_samples = base_probs.shape[0]
    
    # 1. Confidence Features
    prediction_entropy = -np.sum(base_probs * np.log(base_probs + 1e-15), axis=1)
    max_prob = np.max(base_probs, axis=1)
    min_prob = np.min(base_probs, axis=1)
    confidence_spread = max_prob - min_prob
    prob_std = np.std(base_probs, axis=1)
    
    # 2. Agreement Features  
    binary_preds = (base_probs > 0.5).astype(int)
    model_consensus = np.sum(binary_preds, axis=1)  # 0-4 models predicting positive
    unanimous_positive = (model_consensus == 4).astype(int)
    unanimous_negative = (model_consensus == 0).astype(int)
    majority_vote = (model_consensus > 2).astype(int)
    
    # High confidence agreement (models agree AND confident)
    high_conf_agreement = ((max_prob > 0.7) & (confidence_spread < 0.3)).astype(int)
    
    # 3. Model-Specific Confidence
    xgb_confident = (base_probs[:, 0] > 0.7).astype(int)
    lgb_confident = (base_probs[:, 1] > 0.7).astype(int) 
    cat_confident = (base_probs[:, 2] > 0.7).astype(int)
    svm_confident = (base_probs[:, 3] > 0.7).astype(int)
    
    # 4. Tree Model vs SVM Agreement
    tree_avg = np.mean(base_probs[:, :3], axis=1)  # XGB, LGB, CAT average
    tree_svm_diff = np.abs(tree_avg - base_probs[:, 3])  # Difference with SVM
    tree_svm_agreement = (tree_svm_diff < 0.2).astype(int)
    
    # 5. Model Pairs Agreement
    xgb_cat_agreement = (np.abs(base_probs[:, 0] - base_probs[:, 2]) < 0.2).astype(int)
    lgb_svm_agreement = (np.abs(base_probs[:, 1] - base_probs[:, 3]) < 0.2).astype(int)
    
    # 6. Get top original features (most important from base models)
    # Select top features that are most predictive
    top_feature_names = [
        'inf_velo', 'exit_velo_max', 'velo_by_inf', 'sixty_time', 'height', 
        'weight', 'inf_velo_x_velo_by_inf', 'power_speed', 'inf_velo_sq',
        'player_region_West', 'primary_position_SS', 'hitting_handedness_R',
        'inf_velo_x_velo_by_inf_sq', 'inf_velo_x_velo_by_inf_cubed', 
        'inf_velo_sixty_ratio', 'inf_velo_sixty_ratio_sq', 'exit_inf_velo_inv',
        'exit_and_inf_velo_ss', 'player_region_West', 'player_region_South'
    ]
    
    # Get these features from original data
    top_original_features = original_features[top_feature_names].values
    
    # Combine all meta-features
    confidence_features = np.column_stack([
        prediction_entropy, max_prob, min_prob, confidence_spread, prob_std
    ])
    
    agreement_features = np.column_stack([
        model_consensus, unanimous_positive, unanimous_negative, majority_vote,
        high_conf_agreement, tree_svm_agreement, xgb_cat_agreement, lgb_svm_agreement
    ])
    
    model_confidence_features = np.column_stack([
        xgb_confident, lgb_confident, cat_confident, svm_confident
    ])
    
    interaction_features = np.column_stack([
        tree_avg, tree_svm_diff
    ])
    
    # Combine everything
    augmented_features = np.column_stack([
        base_probs,                    # Original 4 base model probabilities
        confidence_features,           # 5 confidence features  
        agreement_features,            # 8 agreement features
        model_confidence_features,     # 4 model confidence features
        interaction_features,          # 2 interaction features
        top_original_features          # 12 top original features
    ])
    
    return augmented_features

# Create feature names for all augmented features
base_prob_names = [f'{name}_prob' for name in base_model_names]
confidence_names = ['pred_entropy', 'max_prob', 'min_prob', 'conf_spread', 'prob_std']
agreement_names = ['consensus', 'unanimous_pos', 'unanimous_neg', 'majority_vote', 
                  'high_conf_agree', 'tree_svm_agree', 'xgb_cat_agree', 'lgb_svm_agree']
model_conf_names = ['xgb_confident', 'lgb_confident', 'cat_confident', 'svm_confident']
interaction_names = ['tree_avg', 'tree_svm_diff']
top_original_names = [
    'inf_velo', 'exit_velo_max', 'velo_by_inf', 'sixty_time', 'height', 
    'weight', 'inf_velo_x_velo_by_inf', 'power_speed', 'inf_velo_sq',
    'player_region_West', 'primary_position_SS', 'hitting_handedness_R',
    'inf_velo_x_velo_by_inf_sq', 'inf_velo_x_velo_by_inf_cubed', 
    'inf_velo_sixty_ratio', 'inf_velo_sixty_ratio_sq', 'exit_inf_velo_inv',
    'exit_and_inf_velo_ss', 'player_region_West', 'player_region_South'
]

meta_feature_names = (base_prob_names + confidence_names + agreement_names + 
                     model_conf_names + interaction_names + top_original_names)

# Create augmented features
oof_augmented = create_augmented_features(oof_predictions, X_train_val)
test_augmented = create_augmented_features(test_predictions, X_test)

print(f"Augmented OOF features shape: {oof_augmented.shape}")
print(f"Augmented test features shape: {test_augmented.shape}")
print(f"Total meta-features: {len(meta_feature_names)}")
print(f"Feature breakdown:")
print(f"  Base probabilities: 4")
print(f"  Confidence features: 5") 
print(f"  Agreement features: 8")
print(f"  Model confidence: 4")
print(f"  Interactions: 2")
print(f"  Top original features: 12")
print(f"  Total: {oof_augmented.shape[1]} features")

print("=" * 60)

# ============================================================================
# Train Logistic Regression Meta-Learner
# ============================================================================

print("Training Logistic Regression meta-learner on CV out-of-fold predictions...")

from sklearn.linear_model import LogisticRegression
import xgboost as xgb

# Try both simple base probabilities and augmented features
print("Comparing simple vs augmented meta-features...")

# Simple meta-learner with just base model probabilities
simple_meta_model = xgb.XGBClassifier(
    n_estimators=750, 
    use_label_encoder=False, 
    eval_metric='logloss',
    random_state=42
)
simple_meta_model.fit(oof_predictions, y_train_val, verbose=False)

# Augmented meta-learner with all features
augmented_meta_model = xgb.XGBClassifier(
    n_estimators=750, 
    use_label_encoder=False, 
    eval_metric='logloss',
    random_state=42
)
augmented_meta_model.fit(oof_augmented, y_train_val, verbose=False)

# Evaluate both on CV data
from sklearn.model_selection import cross_val_score
cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

simple_cv_scores = cross_val_score(simple_meta_model, oof_predictions, y_train_val, 
                                  cv=cv, scoring='accuracy')
augmented_cv_scores = cross_val_score(augmented_meta_model, oof_augmented, y_train_val, 
                                     cv=cv, scoring='accuracy')

print(f"Simple meta-learner CV accuracy: {simple_cv_scores.mean():.4f} (+/- {simple_cv_scores.std() * 2:.4f})")
print(f"Augmented meta-learner CV accuracy: {augmented_cv_scores.mean():.4f} (+/- {augmented_cv_scores.std() * 2:.4f})")

# Choose the better performing model
if augmented_cv_scores.mean() > simple_cv_scores.mean():
    final_meta_model = augmented_meta_model
    final_test_features = test_augmented
    meta_type = "Augmented Logistic Regression"
    print("Using augmented features for final model")
else:
    final_meta_model = simple_meta_model  
    final_test_features = test_predictions
    meta_type = "Simple Logistic Regression"
    print("Using simple base probabilities for final model")

print("=" * 60)

# ============================================================================
# Final Evaluation on Test Set
# ============================================================================

print(f"FINAL CV-STACKED {meta_type.upper()} MODEL RESULTS")
print("=" * 60)

# Get final predictions using selected test features
y_pred_proba = final_meta_model.predict_proba(final_test_features)[:, 1]
y_pred = final_meta_model.predict(final_test_features)

# Calculate metrics
test_accuracy = accuracy_score(y_test, y_pred)
test_f1 = f1_score(y_test, y_pred)
test_fbeta = fbeta_score(y_test, y_pred, beta=beta)

# Print No Information Rate
most_freq_class = y_test.value_counts(normalize=True).max()
print(f"No Information Rate: {most_freq_class:.4f}")

print(f"\nXGBoost Stacked Model Test Performance:")
print(f"Test Accuracy: {test_accuracy:.4f}")
print(f"Test F1-Score: {test_f1:.4f}")
print(f"Test F{beta}-Score: {test_fbeta:.4f}")

# Check if we hit the 80% accuracy target
if test_accuracy >= 0.80:
    print("🎯 SUCCESS: Achieved 80%+ accuracy target!")
else:
    print(f"📈 Progress: {test_accuracy:.1%} accuracy ({(0.8-test_accuracy)*100:.1f}% away from 80% target)")

# Classification report
print(f"\nClassification Report:")
print(classification_report(y_test, y_pred))

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
print("Confusion Matrix:")
print(cm)

# Calculate true positive rate and other key metrics for class 1
tn, fp, fn, tp = cm.ravel()
true_positive_rate = tp / (tp + fn)  # Recall for class 1
precision = tp / (tp + fp)
print(f"\nKey Metrics for Class 1 (D1 players):")
print(f"True Positive Rate (Recall): {true_positive_rate:.4f}")
print(f"Precision: {precision:.4f}")
print(f"True Positives Captured: {tp}/{tp+fn} ({tp/(tp+fn)*100:.1f}%)")

print("=" * 60)

# ============================================================================
# Compare with Base Models and Previous Ensemble
# ============================================================================

print("PERFORMANCE COMPARISON")
print("=" * 60)

print(f"{'Model':<25} {'Accuracy':<10} {'F1-Score':<10} {'F{beta}-Score':<12} {'TP Rate':<8}")
print("-" * 70)

# Individual base model performance
base_results = {}
base_models = {}

# Fit base models on the full training data
for i, name in enumerate(base_model_names):
    model = create_model_from_params(name, base_model_params[name])
    if name == 'svm':
        model.fit(X_train_val_scaled, y_train_val)
        y_pred_base = model.predict(X_test_scaled)
    else:
        model.fit(X_train_val, y_train_val)
        y_pred_base = model.predict(X_test)
    base_models[name] = model

    acc = accuracy_score(y_test, y_pred_base)
    f1 = f1_score(y_test, y_pred_base)
    fb = fbeta_score(y_test, y_pred_base, beta=beta)
    
    # Calculate TP rate for this model
    cm_base = confusion_matrix(y_test, y_pred_base)
    tn_b, fp_b, fn_b, tp_b = cm_base.ravel()
    tp_rate_base = tp_b / (tp_b + fn_b)
    
    base_results[name] = {'accuracy': acc, 'f1': f1, 'fbeta': fb, 'tp_rate': tp_rate_base}
    print(f"{name.upper():<25} {acc:<10.4f} {f1:<10.4f} {fb:<12.4f} {tp_rate_base:<8.4f}")

# Stacked result
print(f"{meta_type.upper():<25} {test_accuracy:<10.4f} {test_f1:<10.4f} {test_fbeta:<12.4f} {true_positive_rate:<8.4f}")

# Previous ensemble result (from your earlier run)
print(f"{'PREVIOUS ENSEMBLE':<25} {'0.7916':<10} {'0.5865':<10} {'0.5902':<12} {'0.5758':<8}")

print("=" * 60)

# ============================================================================
# Meta-Learner Analysis
# ============================================================================

print(f"{meta_type.upper()} META-LEARNER ANALYSIS")
print("=" * 60)

if meta_type == "Simple Logistic Regression":
    # Logistic regression coefficients for base model probabilities
    print("Logistic Regression Coefficients (log-odds):")
    for i, name in enumerate(base_model_names):
        coef = final_meta_model.coef_[0][i]
        print(f"  {name.upper()}: {coef:.4f}")
    
    # Most important base model (highest absolute coefficient)
    most_important_idx = np.argmax(np.abs(final_meta_model.coef_[0][:4]))
    print(f"\nMost important base model: {base_model_names[most_important_idx].upper()}")
    
elif meta_type == "Augmented Logistic Regression":
    # Show coefficients for base models and top augmented features
    print("Base Model Coefficients (log-odds):")
    for i, name in enumerate(base_model_names):
        coef = final_meta_model.coef_[0][i]
        print(f"  {name.upper()}: {coef:.4f}")
    
    print(f"\nTop 5 Augmented Feature Coefficients:")
    feature_coefs = [(meta_feature_names[i], final_meta_model.coef_[0][i]) 
                     for i in range(len(meta_feature_names))]
    sorted_coefs = sorted(feature_coefs, key=lambda x: abs(x[1]), reverse=True)[:5]
    for feat_name, coef in sorted_coefs:
        print(f"  {feat_name}: {coef:.4f}")

print("=" * 60)

# ============================================================================
# Performance Summary
# ============================================================================

print("FINAL SUMMARY")
print("=" * 60)

best_base_fbeta = max([result['fbeta'] for result in base_results.values()])
best_base_acc = max([result['accuracy'] for result in base_results.values()])
ensemble_fbeta = 0.5902  # From your previous ensemble run
ensemble_acc = 0.7916

improvement_vs_base = test_fbeta - best_base_fbeta
improvement_vs_ensemble = test_fbeta - ensemble_fbeta
acc_improvement_vs_ensemble = test_accuracy - ensemble_acc

print(f"Best base model F{beta}-Score: {best_base_fbeta:.4f}")
print(f"Previous ensemble F{beta}-Score: {ensemble_fbeta:.4f}")
print(f"Stacked model F{beta}-Score: {test_fbeta:.4f}")
print(f"")
print(f"Improvement vs best base: {improvement_vs_base:+.4f} ({improvement_vs_base/best_base_fbeta*100:+.2f}%)")
print(f"Improvement vs ensemble: {improvement_vs_ensemble:+.4f} ({improvement_vs_ensemble/ensemble_fbeta*100:+.2f}%)")
print(f"")
print(f"Previous ensemble accuracy: {ensemble_acc:.4f}")
print(f"Stacked model accuracy: {test_accuracy:.4f}")
print(f"Accuracy improvement: {acc_improvement_vs_ensemble:+.4f} ({acc_improvement_vs_ensemble/ensemble_acc*100:+.2f}%)")

print(f"\n🎯 Target: 80% accuracy with high F{beta}-score")
if test_accuracy >= 0.80 and test_fbeta > ensemble_fbeta:
    print("✅ SUCCESS: Both targets achieved!")
elif test_accuracy >= 0.80:
    print("✅ Accuracy target achieved! F-score could be higher.")
elif test_fbeta > ensemble_fbeta:
    print("✅ F-score improved! Getting closer to accuracy target.")
else:
    print("📈 Progress made, consider trying CV-stacking or feature augmentation next.")

print(f"\nXGBoost meta-learner approach: {'SUCCESS' if improvement_vs_ensemble > 0 else 'NEEDS REFINEMENT'}")
print(f"Meta-features: Base model probabilities")
print(f"Optimization trials: 75")
