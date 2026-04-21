import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, fbeta_score, f1_score
import xgboost as xgb
from statsmodels.stats.outliers_influence import variance_inflation_factor
import optuna

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

# Split into train+val and test
X_train_val, X_test, y_train_val, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)
# Split train_val into train and val
X_train, X_val, y_train, y_val = train_test_split(
    X_train_val, y_train_val, test_size=0.2, stratify=y_train_val, random_state=42
)

#0.7 gives 0.7996 test acc
beta = 0.75

# Optuna objective for XGBoost
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

    # Metrics
    f1 = f1_score(y_val, preds)
    accuracy = accuracy_score(y_val, preds)
    precision = classification_report(y_val, preds, output_dict=True)['1']['precision']
    recall = classification_report(y_val, preds, output_dict=True)['1']['recall']
    logloss = model.evals_result()['validation_0']['logloss'][-1] if 'logloss' in model.evals_result()['validation_0'] else None
    fbeta = fbeta_score(y_val, preds, beta=beta)

    return float(fbeta_score(y_val, preds, beta=beta))

# Run Optuna study
study = optuna.create_study(direction='maximize')
study.optimize(xgb_objective, n_trials=75, show_progress_bar=True)

best_params = study.best_params

# Cross-validation on train+val
cv_model = xgb.XGBClassifier(
    **best_params, n_estimators=750,
    use_label_encoder=False, eval_metric='logloss',
    random_state=42, missing=np.nan
)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_f1 = cross_val_score(cv_model, X_train_val, y_train_val, cv=cv, scoring='f1')
print(f"5-fold CV F1 Score: {cv_f1.mean():.4f}")

cv_accuracy = cross_val_score(cv_model, X_train_val, y_train_val, cv=cv, scoring='accuracy')
print(f"5-fold CV Accuracy Score: {cv_f1.mean():.4f}")

# Train final model on all train+val
cv_model.fit(X_train_val, y_train_val, verbose=False)
final_model = cv_model

# Print No Information Rate
most_freq_class = y_test.value_counts(normalize=True).max()
print(f"No Information Rate: {most_freq_class:.4f}")

# Evaluate on test
y_pred = final_model.predict(X_test)
print(f"Test F{beta}-Score: {fbeta_score(y_test, y_pred, beta=beta):.4f}")
print(f"Test Accuracy: {accuracy_score(y_test, y_pred):.4f}")
print(classification_report(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))

"""
# VIF calculation
X_train_vif = pd.DataFrame(X_train_val) if isinstance(X_train_val, list) else X_train_val.copy()
cat_cols = X_train_vif.select_dtypes(include=['object', 'category']).columns

if len(cat_cols) > 0:
    X_train_vif = pd.get_dummies(X_train_vif, columns=cat_cols, drop_first=True)

X_num = X_train_vif.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan).dropna()
vif_data = [(col, variance_inflation_factor(X_num.values, i)) for i, col in enumerate(X_num.columns)]
vif_df = pd.DataFrame(vif_data, columns=['feature','VIF']).sort_values('VIF', ascending=False)  # type: ignore
print("\nVIF Scores:")
print(vif_df.round(2))
"""

# Feature importance
imp_df = pd.DataFrame({
    'feature': X.columns,
    'importance': final_model.feature_importances_
}).sort_values('importance', ascending=False)
print("\nFeature Importances:")
print(imp_df)

print("\nColumns used in the XGBoost model:")
print(list(X.columns))