import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, fbeta_score, f1_score
from sklearn.ensemble import VotingClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.base import BaseEstimator, ClassifierMixin
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

print(f'\nTotal NA values: {X.isna().sum().sum()}')

# Split into train+val and test
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)
# Split train_val into train and val
X_train, X_val, y_train, y_val = train_test_split(
    X_train_val, y_train_val, test_size=0.2, stratify=y_train_val, random_state=42
)

# Scale data for SVM and DNN
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_val_scaled = scaler.transform(X_val)
X_train_val_scaled = scaler.fit_transform(X_train_val)
X_test_scaled = scaler.transform(X_test)

beta = 0.7

# Model saving/loading setup
models_dir = 'saved_models'
os.makedirs(models_dir, exist_ok=True)

def save_model_and_params(model, params, name):
    """Save model and parameters"""
    joblib.dump(model, f'{models_dir}/{name}_model.pkl')
    joblib.dump(params, f'{models_dir}/{name}_params.pkl')

def load_model_and_params(name):
    """Load model and parameters if they exist"""
    model_path = f'{models_dir}/{name}_model.pkl'
    params_path = f'{models_dir}/{name}_params.pkl'
    if os.path.exists(model_path) and os.path.exists(params_path):
        return joblib.load(model_path), joblib.load(params_path)
    return None, None

print("Starting hyperparameter optimization for ensemble models...")
print("Note: Models will be saved to avoid re-optimization")
print("=" * 60)

# ============================================================================
# XGBoost Optimization
# ============================================================================
print("\n" + "=" * 60)
print("Optimizing XGBoost...")

# Try to load existing XGBoost model
xgb_model_loaded, best_xgb_params = load_model_and_params('xgboost')
if xgb_model_loaded is not None:
    print("Loading existing XGBoost model...")
    xgb_model = xgb_model_loaded
else:
    print("Training new XGBoost model...")
    
    def xgb_objective(trial):
        params = {
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'use_label_encoder': False,
            'learning_rate': trial.suggest_loguniform('eta', 1e-3, 1e-1),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'gamma': trial.suggest_loguniform('gamma', 1e-8, 5.0),
            'subsample': trial.suggest_uniform('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_uniform('colsample_bytree', 0.5, 1.0),
            'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-8, 1.0),
            'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-8, 10.0),
            'scale_pos_weight': trial.suggest_loguniform('scale_pos_weight', 1.0, 5.0),
        }
        model = xgb.XGBClassifier(**params, n_estimators=1000, random_state=42, missing=np.nan)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        preds = model.predict(X_val)
        return float(fbeta_score(y_val, preds, beta=beta))

    xgb_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    xgb_study.optimize(xgb_objective, n_trials=50, show_progress_bar=True, n_jobs=-1)
    best_xgb_params = xgb_study.best_params
    print(f"Best XGBoost F{beta}-Score: {xgb_study.best_value:.4f}")
    
    # Train final XGBoost model
    xgb_model = xgb.XGBClassifier(
        **best_xgb_params, 
        n_estimators=750, 
        use_label_encoder=False, 
        eval_metric='logloss',
        random_state=42, 
        missing=np.nan
    )
    xgb_model.fit(X_train_val, y_train_val, verbose=False)
    
    # Save the model
    save_model_and_params(xgb_model, best_xgb_params, 'xgboost')

# ============================================================================
# LightGBM Optimization
# ============================================================================
print("\n" + "=" * 60)
print("\nOptimizing LightGBM...")

def lgb_objective(trial):
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'learning_rate': trial.suggest_loguniform('learning_rate', 1e-3, 1e-1),
        'num_leaves': trial.suggest_int('num_leaves', 10, 300),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
        'min_child_weight': trial.suggest_loguniform('min_child_weight', 1e-8, 10.0),
        'subsample': trial.suggest_uniform('subsample', 0.5, 1.0),
        'subsample_freq': trial.suggest_int('subsample_freq', 1, 7),
        'colsample_bytree': trial.suggest_uniform('colsample_bytree', 0.5, 1.0),
        'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-8, 10.0),
        'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-8, 10.0),
        'scale_pos_weight': trial.suggest_loguniform('scale_pos_weight', 1.0, 5.0),
        'verbose': -1,
        'random_state': 42
    }
    model = lgb.LGBMClassifier(**params, n_estimators=1000)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(0)]
    )
    preds = model.predict(X_val)
    return float(fbeta_score(y_val, preds, beta=beta))

lgb_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
lgb_study.optimize(lgb_objective, n_trials=50, show_progress_bar=True, n_jobs=-1)
best_lgb_params = lgb_study.best_params
print(f"Best LightGBM F{beta}-Score: {lgb_study.best_value:.4f}")

# ============================================================================
# CatBoost Optimization
# ============================================================================
print("\n" + "=" * 60)
print("\nOptimizing CatBoost...")

def cat_objective(trial):
    params = {
        'objective': 'Logloss',
        'eval_metric': 'AUC',
        'learning_rate': trial.suggest_loguniform('learning_rate', 1e-3, 1e-1),
        'depth': trial.suggest_int('depth', 3, 10),
        'l2_leaf_reg': trial.suggest_loguniform('l2_leaf_reg', 1e-8, 10.0),
        'bagging_temperature': trial.suggest_uniform('bagging_temperature', 0, 1),
        'random_strength': trial.suggest_uniform('random_strength', 0, 1),
        'border_count': trial.suggest_int('border_count', 32, 255),
        'scale_pos_weight': trial.suggest_loguniform('scale_pos_weight', 1.0, 5.0),
        'verbose': False,
        'random_state': 42
    }
    model = cb.CatBoostClassifier(**params, iterations=1000)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=50,
        verbose=False
    )
    preds = model.predict(X_val)
    return float(fbeta_score(y_val, preds, beta=beta))

cat_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
cat_study.optimize(cat_objective, n_trials=50, show_progress_bar=True, n_jobs=-1)
best_cat_params = cat_study.best_params
print(f"Best CatBoost F{beta}-Score: {cat_study.best_value:.4f}")

# ============================================================================
# SVM Optimization
# ============================================================================
print("\n" + "=" * 60)
print("\nOptimizing SVM...")

def svm_objective(trial):
    kernel = trial.suggest_categorical('kernel', ['rbf', 'poly', 'sigmoid', 'linear'])
    
    params = {
        'C': trial.suggest_loguniform('C', 1e-3, 1e3),
        'kernel': kernel,
        'class_weight': trial.suggest_categorical('class_weight', ['balanced', None]),
        'probability': True,  # Required for soft voting
        'random_state': 42
    }
    
    # Add gamma parameter for non-linear kernels
    if kernel != 'linear':
        params['gamma'] = trial.suggest_loguniform('gamma', 1e-5, 1e1)
        
    model = SVC(**params)
    model.fit(X_train_scaled, y_train)
    preds = model.predict(X_val_scaled)
    return float(fbeta_score(y_val, preds, beta=beta))

svm_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
svm_study.optimize(svm_objective, n_trials=15, show_progress_bar=True, n_jobs=4)
best_svm_params = svm_study.best_params
print(f"Best SVM F{beta}-Score: {svm_study.best_value:.4f}")

# ============================================================================
# DNN (MLPClassifier) Optimization
# ============================================================================
print("\n" + "=" * 60)
print("\nOptimizing DNN (MLPClassifier)...")

def dnn_objective(trial):
    # Preset layer configurations to choose from
    layer_configs = [
        (100,),           # Single layer
        (150,),
        (200,),
        (100, 50),        # Two layers  
        (150, 75),
        (200, 100),
        (100, 50, 25),    # Three layers
        (150, 100, 50)
    ]
    
    params = {
        'hidden_layer_sizes': trial.suggest_categorical('hidden_layer_sizes', layer_configs),
        'learning_rate_init': trial.suggest_float('learning_rate_init', 1e-4, 1e-2, log=True),
        'alpha': trial.suggest_float('alpha', 1e-5, 1e-2, log=True),
        'activation': trial.suggest_categorical('activation', ['relu', 'tanh']),
        'solver': 'adam',  # Stick with adam for consistency
        'max_iter': 500,   # Reduce iterations for faster training
        'random_state': 42,
        'early_stopping': True,
        'validation_fraction': 0.1,
        'n_iter_no_change': 10  # Reduce patience for faster training
    }
        
    model = MLPClassifier(**params)
    model.fit(X_train_scaled, y_train)
    preds = model.predict(X_val_scaled)
    return float(fbeta_score(y_val, preds, beta=beta))

dnn_study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
dnn_study.optimize(dnn_objective, n_trials=10, show_progress_bar=True, n_jobs=4)
best_dnn_params = dnn_study.best_params
print(f"Best DNN F{beta}-Score: {dnn_study.best_value:.4f}")

print("\n" + "=" * 60)
print("Training optimized models...")

# ============================================================================
# Train optimized models on train+val data
# ============================================================================

# XGBoost final model
xgb_model = xgb.XGBClassifier(
    **best_xgb_params, 
    n_estimators=750, 
    use_label_encoder=False, 
    eval_metric='logloss',
    random_state=42, 
    missing=np.nan
)
xgb_model.fit(X_train_val, y_train_val, verbose=False)

# LightGBM final model
lgb_model = lgb.LGBMClassifier(
    **best_lgb_params,
    n_estimators=750,
    verbose=-1
)
lgb_model.fit(X_train_val, y_train_val)

# CatBoost final model
cat_model = cb.CatBoostClassifier(
    **best_cat_params,
    iterations=750,
    verbose=False
)
cat_model.fit(X_train_val, y_train_val)

# SVM final model
svm_model = SVC(**best_svm_params, probability=True)
svm_model.fit(X_train_val_scaled, y_train_val)

# DNN final model - filter out n_layers and layer_X_size parameters
dnn_params_filtered = {k: v for k, v in best_dnn_params.items() 
                      if k != 'n_layers' and not k.startswith('layer_')}
dnn_model = MLPClassifier(**dnn_params_filtered)
dnn_model.fit(X_train_val_scaled, y_train_val)

# ============================================================================
# Individual Model Performance
# ============================================================================
print("\nIndividual Model Performance on Test Set:")
print("-" * 50)

models = {
    'XGBoost': (xgb_model, X_test),
    'LightGBM': (lgb_model, X_test), 
    'CatBoost': (cat_model, X_test),
    'SVM': (svm_model, X_test_scaled),
    'DNN': (dnn_model, X_test_scaled)
}

individual_predictions = {}
for name, (model, X_test_data) in models.items():
    y_pred = model.predict(X_test_data)
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
# Ensemble Model
# ============================================================================
print("Creating Ensemble Model...")

# Create wrapper classes for models that need scaling
class ScaledModelWrapper(BaseEstimator, ClassifierMixin):
    def __init__(self, model, scaler):
        self.model = model
        self.scaler = scaler
        self.classes_ = None
    
    def fit(self, X, y):
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.classes_ = self.model.classes_
        return self
    
    def predict(self, X):
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X):
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def _more_tags(self):
        return {'requires_positive_X': False}

# Create wrapped models for ensemble
svm_wrapper = ScaledModelWrapper(SVC(**best_svm_params, probability=True), StandardScaler())
dnn_wrapper = ScaledModelWrapper(MLPClassifier(**dnn_params_filtered), StandardScaler())

# Create ensemble with soft voting (all 5 models)
ensemble = VotingClassifier(
    estimators=[
        ('xgb', xgb_model), 
        ('lgb', lgb_model), 
        ('cat', cat_model),
        ('svm', svm_wrapper),
        ('dnn', dnn_wrapper)
    ],
    voting='soft'
)

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
# Final Ensemble Evaluation
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
    'importance': xgb_model.feature_importances_
}).sort_values('importance', ascending=False)
print(imp_df.head(27))

print(f"\nColumns used in the ensemble models:")
print(list(X.columns))

print(f"\nOptimization completed successfully!")