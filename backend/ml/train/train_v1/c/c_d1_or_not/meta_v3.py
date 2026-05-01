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

# Set consistent random seed for reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Set additional seeds for full reproducibility
import random
import os
random.seed(RANDOM_SEED)
os.environ['PYTHONHASHSEED'] = str(RANDOM_SEED)

# Set library-specific seeds
import tensorflow as tf
tf.random.set_seed(RANDOM_SEED) if 'tensorflow' in globals() else None

# Set optuna sampler seed
optuna.logging.set_verbosity(optuna.logging.WARNING)

# Set sklearn for deterministic behavior
from sklearn import set_config
set_config(enable_metadata_routing=False)  # Ensure deterministic sklearn behavior

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

"""
df['arm_athleticism_correlation_squared'] = df['arm_athleticism_correlation'] ** 2
df['arm_athleticism_correlation_cubed'] = df['arm_athleticism_correlation'] ** 3
df['arm_athleticism_fourth'] = df['arm_athleticism_correlation'] ** 4
df['arm_athleticism_correlation_log'] = np.log1p(df['arm_athleticism_correlation'])
df['arm_athleticism_exp'] = np.exp(df['arm_athleticism_correlation'] / 100)
"""

df['defensive_consistency'] = df['pop_time_percentile'] * df['c_velo_percentile'] * df['catcher_defensive_percentile']
df['power_speed_size_ratio'] = (df['exit_velo_max'] * df['sixty_time']) / df['weight']
df['pop_efficiency'] = df['c_velo'] / (df['pop_time'] ** 2)

df['region_athletic_adjustment'] = df['athletic_index_v2'] * df['d1_region_advantage']
"""
df['region_athletic_adjustment_squared'] = df['region_athletic_adjustment'] ** 2

df['region_athletic_adjustment_cubed'] = df['region_athletic_adjustment'] ** 3
"""
df['region_athletic_adjustment_exp'] = np.exp(df['region_athletic_adjustment'] / 100)


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
# PRINT QUANTILES FOR PRODUCTION PIPELINE PERCENTILE CALCULATION
# ============================================================================
print("\n" + "="*80)
print("QUANTILES FOR PRODUCTION PIPELINE PERCENTILE CALCULATION")
print("="*80)

# Print quantiles for c_velo percentile calculation
c_velo_quantiles = [df['c_velo'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nc_velo_quantiles = {c_velo_quantiles}")

# Print quantiles for pop_time percentile calculation (lower is better)
pop_time_quantiles = [df['pop_time'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\npop_time_quantiles = {pop_time_quantiles}")

# Print quantiles for exit_velo_max percentile calculation (higher is better)
exit_velo_max_quantiles = [df['exit_velo_max'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nexit_velo_max_quantiles = {exit_velo_max_quantiles}")

# Print quantiles for sixty_time percentile calculation (lower is better)
sixty_time_quantiles = [df['sixty_time'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nsixty_time_quantiles = {sixty_time_quantiles}")

# Print quantiles for height percentile calculation (higher is better)
height_quantiles = [df['height'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nheight_quantiles = {height_quantiles}")

# Print quantiles for weight percentile calculation (higher is better)
weight_quantiles = [df['weight'].quantile(i/100) for i in range(0, 101, 5)]
print(f"\nweight_quantiles = {weight_quantiles}")

# Calculate catcher_defensive_percentile components and print quantiles
print(f"\n# Catcher defensive percentile components:")
print(f"# Formula: (c_velo_percentile * 0.6) + (pop_time_percentile * 0.4)")
catcher_defensive_values = df['catcher_defensive_percentile']
catcher_defensive_quantiles = [catcher_defensive_values.quantile(i/100) for i in range(0, 101, 5)]
print(f"catcher_defensive_quantiles = {catcher_defensive_quantiles}")

# Calculate catcher_offensive_percentile components and print quantiles  
print(f"\n# Catcher offensive percentile components:")
print(f"# Formula: (exit_velo_max_percentile * 0.7) + (sixty_time_percentile * 0.3)")
catcher_offensive_values = df['catcher_offensive_percentile']
catcher_offensive_quantiles = [catcher_offensive_values.quantile(i/100) for i in range(0, 101, 5)]
print(f"catcher_offensive_quantiles = {catcher_offensive_quantiles}")

# Calculate catcher_overall_percentile components and print quantiles
print(f"\n# Catcher overall percentile components:")
print(f"# Formula: (catcher_defensive_percentile * 0.4) + (catcher_offensive_percentile * 0.35) + (height_percentile * 0.15) + (weight_percentile * 0.10)")
catcher_overall_values = df['catcher_overall_percentile']
catcher_overall_quantiles = [catcher_overall_values.quantile(i/100) for i in range(0, 101, 5)]
print(f"catcher_overall_quantiles = {catcher_overall_quantiles}")

# Print sample calculations for verification
print(f"\n# Sample calculations for verification:")
sample_idx = df.index[0]
print(f"Sample player at index {sample_idx}:")
print(f"  c_velo: {df.loc[sample_idx, 'c_velo']:.2f}")
print(f"  pop_time: {df.loc[sample_idx, 'pop_time']:.2f}")
print(f"  c_velo_percentile: {df.loc[sample_idx, 'c_velo_percentile']:.2f}")
print(f"  pop_time_percentile: {df.loc[sample_idx, 'pop_time_percentile']:.2f}")
print(f"  catcher_defensive_percentile: {df.loc[sample_idx, 'catcher_defensive_percentile']:.2f}")
print(f"  catcher_offensive_percentile: {df.loc[sample_idx, 'catcher_offensive_percentile']:.2f}")
print(f"  catcher_overall_percentile: {df.loc[sample_idx, 'catcher_overall_percentile']:.2f}")

print("="*80)
print("END QUANTILES - COPY THE ABOVE VALUES TO PRODUCTION PIPELINE")
print("="*80 + "\n")

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
    'height_percentile', 'defensive_efficiency', 'exit_velo_max_percentile',
    'complete_catcher', 'speed_scaled', 'power_speed', 'sixty_time', 
    'sixty_time_percentile', 'weight_percentile', 'tool_athletic_log'
]

# ============================================================================
# SCORING CONFIGURATION - SINGLE SOURCE OF TRUTH
# ============================================================================
# Edit these weights to change optimization criteria for ALL models
SCORING_WEIGHTS = {
      'accuracy': 2.4,      # Slight boost for higher accuracy
      'recall': 2.5,        # Slight reduction but still prioritized
      'precision': 1.25,     # Increase to reduce some FPs
      'f1': 1.7            # Keep F1 balance
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
    """Custom scoring function that encourages FP/FN >= 0.45 with accuracy optimization"""
    accuracy = accuracy_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred, pos_label=1)
    precision = precision_score(y_true, y_pred, pos_label=1, zero_division=0)
    f1 = f1_score(y_true, y_pred)
    
    # Calculate confusion matrix components
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    # Calculate FP/FN ratio and apply penalties/bonuses
    fp_fn_ratio = fp / fn if fn > 0 else float('inf')
    
    # Target FP/FN ratio of 0.45 or higher, but cap rewards at 1.2 for accuracy optimization
    fp_fn_penalty = 0
    if fp_fn_ratio < 0.45:
        # Strong penalty for being too conservative
        fp_fn_penalty = -1.0 * (0.45 - fp_fn_ratio)
    elif fp_fn_ratio >= 0.45 and fp_fn_ratio <= 1.2:
        # Bonus for being in the sweet spot, but cap at 1.2 to prevent too many FPs
        fp_fn_penalty = 0.15 * min(fp_fn_ratio, 1.2)
    elif fp_fn_ratio > 1.2:
        # Small penalty for too many FPs (hurts accuracy)
        fp_fn_penalty = -0.1 * (fp_fn_ratio - 1.2)
    
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
    X_elite, y_elite, test_size=0.20, stratify=y_elite, random_state=RANDOM_SEED
)
X_elite_train, X_elite_val, y_elite_train, y_elite_val = train_test_split(
    X_elite_temp, y_elite_temp, test_size=0.1875, stratify=y_elite_temp, random_state=RANDOM_SEED  # 15/(65+15) = 0.1875
)

elite_model = xgb.XGBClassifier(
    objective='binary:logistic',
    eval_metric='auc',
    learning_rate=0.1,
    max_depth=8,
    n_estimators=500,
    random_state=RANDOM_SEED
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
    X_d1_elite, y_d1_elite, test_size=0.20, stratify=y_d1_elite, random_state=RANDOM_SEED
)
X_d1_train, X_d1_val, y_d1_train, y_d1_val = train_test_split(
    X_d1_temp, y_d1_temp, test_size=0.1875, stratify=y_d1_temp, random_state=RANDOM_SEED  # 15/(65+15) = 0.1875
)

# Calculate class weight for tree models - boost minority class more for better FP/FN ratio
class_counts = y_d1_train.value_counts().sort_index()
n_samples = len(y_d1_train)
n_classes = len(class_counts)
base_class_weight_ratio = n_samples / (n_classes * class_counts[1])
class_weight_ratio = base_class_weight_ratio * 1.3  # Boost D1 class weight by 30% to capture more

print(f"D1 features: {len(d1_features)}, Class weight ratio: {class_weight_ratio:.2f}")

# ============================================================================
# INDIVIDUAL MODEL OPTIMIZATION WITH OPTUNA
# ============================================================================

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
        'random_state': RANDOM_SEED,
        'early_stopping': True,
        'validation_fraction': 0.3
    }
    
    model = MLPClassifier(**params)
    # Use train set for training, validation set for evaluation - NO CV to prevent data leakage
    model.fit(X_d1_train_scaled, y_d1_train)
    val_preds = model.predict(X_d1_val_scaled)
    return recruiting_score_with_fp_bias(y_d1_val, val_preds)

study_dnn = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
study_dnn.optimize(dnn_objective, n_trials=150, show_progress_bar=True)
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
        'random_state': RANDOM_SEED
    }
    
    model = lgb.LGBMClassifier(**params, n_estimators=250)
    # Use train set for training, validation set for evaluation - NO CV to prevent data leakage
    model.fit(X_d1_train, y_d1_train)
    val_preds = model.predict(X_d1_val)
    return recruiting_score_with_fp_bias(y_d1_val, val_preds)

study_lgb = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
study_lgb.optimize(lightgbm_objective, n_trials=150, show_progress_bar=True)
best_lgb_params = study_lgb.best_params

# ============================================================================
# META-LEARNER STACKING APPROACH
# ============================================================================

# Train base models and collect validation predictions for meta-learner
# Focus on LGB and DNN since meta-learner gives XGB/SVM ~0.5% weight each
base_models = {
    'LGB': lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=RANDOM_SEED),  # Boost estimators
    'DNN': MLPClassifier(**best_dnn_params)
}

# Create meta-features from validation predictions
val_meta_features = []
test_meta_features = []
model_predictions = {}

print("Training base models and generating meta-features...")

for name, model in base_models.items():
    print(f"Training {name}...")
    
    if name == 'DNN':
        # Use scaled features for neural network
        model.fit(X_d1_train_scaled, y_d1_train)
        val_pred_proba = model.predict_proba(X_d1_val_scaled)[:, 1]
        test_pred_proba = model.predict_proba(X_d1_test_scaled)[:, 1]
    else:
        # Use original features for tree models (LGB)
        model.fit(X_d1_train, y_d1_train)
        val_pred_proba = model.predict_proba(X_d1_val)[:, 1]
        test_pred_proba = model.predict_proba(X_d1_test)[:, 1]
    
    val_meta_features.append(val_pred_proba)
    test_meta_features.append(test_pred_proba)
    model_predictions[name] = {
        'val_proba': val_pred_proba,
        'test_proba': test_pred_proba
    }
    
    # Evaluate individual model performance
    val_preds = (val_pred_proba >= 0.5).astype(int)
    score = recruiting_score_with_fp_bias(y_d1_val, val_preds)
    print(f"{name} Val Score: {score:.4f}")

# Stack meta-features into arrays
X_meta_val = np.column_stack(val_meta_features)
X_meta_test = np.column_stack(test_meta_features)

print(f"Meta-features shape: {X_meta_val.shape}")

# Train meta-learner on validation predictions
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.ensemble import RandomForestClassifier

# Create enhanced meta-features with interactions
print("Creating enhanced meta-features with interactions...")
X_meta_val_enhanced = np.column_stack([
    X_meta_val[:, 0],  # LGB pred
    X_meta_val[:, 1],  # DNN pred
    X_meta_val[:, 0] * X_meta_val[:, 1],  # LGB * DNN interaction
    np.mean(X_meta_val, axis=1),          # Average prediction
    np.mean(X_meta_val, axis=1) ** 2,     # Average prediction squared
    np.std(X_meta_val, axis=1),           # Prediction uncertainty
    np.max(X_meta_val, axis=1),           # Max confidence
    np.min(X_meta_val, axis=1),           # Min confidence
    np.abs(X_meta_val[:, 0] - X_meta_val[:, 1]),  # Disagreement between models
    X_meta_val[:, 0] ** 2,  # LGB^2
    X_meta_val[:, 0] ** 3,  # LGB^3
    X_meta_val[:, 0] ** 4,  # LGB^4
    np.exp(X_meta_val[:, 0])  # e^LGB
])

X_meta_test_enhanced = np.column_stack([
    X_meta_test[:, 0],  # LGB pred
    X_meta_test[:, 1],  # DNN pred
    X_meta_test[:, 0] * X_meta_test[:, 1],  # LGB * DNN interaction
    np.mean(X_meta_test, axis=1),          # Average prediction
    np.mean(X_meta_test, axis=1) ** 2,     # Average prediction squared
    np.std(X_meta_test, axis=1),           # Prediction uncertainty
    np.max(X_meta_test, axis=1),           # Max confidence
    np.min(X_meta_test, axis=1),           # Min confidence
    np.abs(X_meta_test[:, 0] - X_meta_test[:, 1]),  # Disagreement between models
    X_meta_test[:, 0] ** 2,  # LGB^2
    X_meta_test[:, 0] ** 3,  # LGB^3
    X_meta_test[:, 0] ** 4,  # LGB^4
    np.exp(X_meta_test[:, 0])  # e^LGB
])

print(f"Enhanced meta-features shape: {X_meta_val_enhanced.shape}")

# Try multiple meta-learners with more regularization
meta_learners = {
    'LogisticRegression': LogisticRegression(random_state=RANDOM_SEED, class_weight='balanced'),
    'LogisticRegression_Constrained': LogisticRegression(
        random_state=RANDOM_SEED, 
        class_weight='balanced',
        C=0.1  # Higher regularization to prevent extreme weights
    ),
    'Ridge': RidgeClassifier(alpha=10.0, random_state=RANDOM_SEED),
    'RandomForest': RandomForestClassifier(n_estimators=100, max_depth=3, random_state=RANDOM_SEED, class_weight='balanced')
}

best_meta_learner = None
best_meta_score = -np.inf
best_meta_name = ""

print("\nTraining meta-learners...")
for name, meta_model in meta_learners.items():
    # Train meta-learner on enhanced features
    meta_model.fit(X_meta_val_enhanced, y_d1_val)
    
    # Evaluate on validation set
    meta_preds = meta_model.predict(X_meta_val_enhanced)
    meta_score = recruiting_score_with_fp_bias(y_d1_val, meta_preds)
    
    print(f"{name} Meta Score: {meta_score:.4f}")
    
    if meta_score > best_meta_score:
        best_meta_score = meta_score
        best_meta_learner = meta_model
        best_meta_name = name

print(f"\nBest meta-learner: {best_meta_name} (Score: {best_meta_score:.4f})")

# For comparison, also calculate simple weighted average
individual_scores = {}
for name in base_models.keys():
    val_preds = (model_predictions[name]['val_proba'] >= 0.5).astype(int)
    individual_scores[name] = recruiting_score_with_fp_bias(y_d1_val, val_preds)

total_score = sum(individual_scores.values())
optimized_weights = {name: score/total_score for name, score in individual_scores.items()}

print(f"Traditional ensemble weights: {optimized_weights}")

# ============================================================================
# COMPARE META-LEARNER VS WEIGHTED ENSEMBLE
# ============================================================================

# Meta-learner predictions on test set using enhanced features
meta_test_preds = best_meta_learner.predict(X_meta_test_enhanced)
meta_test_probs = best_meta_learner.predict_proba(X_meta_test_enhanced)[:, 1]

# Traditional weighted ensemble predictions (LGB + DNN only)
weighted_test_probs = (
    model_predictions['LGB']['test_proba'] * optimized_weights['LGB'] +
    model_predictions['DNN']['test_proba'] * optimized_weights['DNN']
)
weighted_test_preds = (weighted_test_probs >= 0.5).astype(int)

# Compare both approaches
print(f"\n=== META-LEARNER RESULTS (Elite Catchers) ===")
print(f"Accuracy: {accuracy_score(y_d1_test, meta_test_preds):.4f}")
print(f"F1 Score: {f1_score(y_d1_test, meta_test_preds):.4f}")
print(f"D1 Recall: {recall_score(y_d1_test, meta_test_preds, pos_label=1):.4f}")
print(f"D1 Precision: {precision_score(y_d1_test, meta_test_preds, pos_label=1):.4f}")

print(f"\n=== WEIGHTED ENSEMBLE RESULTS (Elite Catchers) ===")
print(f"Accuracy: {accuracy_score(y_d1_test, weighted_test_preds):.4f}")
print(f"F1 Score: {f1_score(y_d1_test, weighted_test_preds):.4f}")
print(f"D1 Recall: {recall_score(y_d1_test, weighted_test_preds, pos_label=1):.4f}")
print(f"D1 Precision: {precision_score(y_d1_test, weighted_test_preds, pos_label=1):.4f}")

# Choose the better approach
meta_score = recruiting_score_with_fp_bias(y_d1_test, meta_test_preds)
weighted_score = recruiting_score_with_fp_bias(y_d1_test, weighted_test_preds)

if meta_score > weighted_score:
    print(f"\n🏆 META-LEARNER WINS! (Score: {meta_score:.4f} vs {weighted_score:.4f})")
    ensemble_probs_elite = meta_test_probs
    ensemble_preds_elite = meta_test_preds
    ensemble_type = "meta_learner"
else:
    print(f"\n🏆 WEIGHTED ENSEMBLE WINS! (Score: {weighted_score:.4f} vs {meta_score:.4f})")
    ensemble_probs_elite = weighted_test_probs
    ensemble_preds_elite = weighted_test_preds
    ensemble_type = "weighted"

# ============================================================================
# HIERARCHICAL PREDICTION WITH ENSEMBLE
# ============================================================================

# Prepare full dataset
X_full = df.drop(columns=EXCLUDE_FEATURES)
y_full = df['d1_or_not']

# Create train/val/test splits for hierarchical prediction (65/15/20) - NO DATA LEAKAGE
X_full_temp, X_full_test, y_full_temp, y_full_test = train_test_split(
    X_full, y_full, test_size=0.20, stratify=y_full, random_state=RANDOM_SEED
)
X_full_train, X_full_val, y_full_train, y_full_val = train_test_split(
    X_full_temp, y_full_temp, test_size=0.1875, stratify=y_full_temp, random_state=RANDOM_SEED  # 15/(65+15) = 0.1875
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

# Retrain models on full feature set for hierarchical prediction
X_full_combined = pd.concat([X_full_train, X_full_val])
y_full_combined = pd.concat([y_full_train, y_full_val])
X_full_combined_scaled_dnn = np.vstack([X_full_train_scaled_dnn, X_full_val_scaled_dnn])
X_full_combined_scaled_svm = np.vstack([X_full_train_scaled_svm, X_full_val_scaled_svm])

full_base_models = {
    'LGB': lgb.LGBMClassifier(**best_lgb_params, n_estimators=500, verbose=-1, random_state=RANDOM_SEED),
    'DNN': MLPClassifier(**best_dnn_params)
}

full_base_models['LGB'].fit(X_full_combined, y_full_combined)
full_base_models['DNN'].fit(X_full_combined_scaled_dnn, y_full_combined)

# Train meta-learner on full dataset if using meta-learner approach
if ensemble_type == "meta_learner":
    full_meta_features = []
    for name, model in full_base_models.items():
        if name == 'DNN':
            proba = model.predict_proba(X_full_combined_scaled_dnn)[:, 1]
        else:  # LGB
            proba = model.predict_proba(X_full_combined)[:, 1]
        full_meta_features.append(proba)
    
    # Create enhanced meta-features for full dataset
    X_full_meta_combined = np.column_stack(full_meta_features)
    X_full_meta_combined_enhanced = np.column_stack([
        X_full_meta_combined[:, 0],  # LGB pred
        X_full_meta_combined[:, 1],  # DNN pred
        X_full_meta_combined[:, 0] * X_full_meta_combined[:, 1],  # LGB * DNN
        np.mean(X_full_meta_combined, axis=1),          # Average prediction
        np.mean(X_full_meta_combined, axis=1) ** 2,          # Average prediction squared
        np.std(X_full_meta_combined, axis=1),           # Prediction uncertainty
        np.max(X_full_meta_combined, axis=1),           # Max confidence
        np.min(X_full_meta_combined, axis=1),           # Min confidence
        np.abs(X_full_meta_combined[:, 0] - X_full_meta_combined[:, 1]),  # Disagreement between models
        X_full_meta_combined[:, 0] ** 2,  # LGB^2
        X_full_meta_combined[:, 0] ** 3,  # LGB^3
        X_full_meta_combined[:, 0] ** 4,  # LGB^4
        np.exp(X_full_meta_combined[:, 0])  # e^LGB
    ])
    
    full_meta_learner = type(best_meta_learner)(**best_meta_learner.get_params())
    full_meta_learner.fit(X_full_meta_combined_enhanced, y_full_combined)

# Updated hierarchical prediction function for full dataset
def predict_d1_hierarchical_ensemble(features_dict, features_scaled_dnn):
    # Elite model features - should match the training features exactly
    elite_feats = features_dict[elite_features]
    
    elite_prob = elite_model.predict_proba(elite_feats)[:, 1]
    
    if ensemble_type == "meta_learner":
        # Generate meta-features for prediction
        meta_features = []
        for name, model in full_base_models.items():
            if name == 'DNN':
                proba = model.predict_proba(features_scaled_dnn)[:, 1]
            else:  # LGB
                proba = model.predict_proba(features_dict)[:, 1]
            meta_features.append(proba)
        
        # Create enhanced meta-features for prediction
        X_meta_pred = np.column_stack(meta_features)
        X_meta_pred_enhanced = np.column_stack([
            X_meta_pred[:, 0],  # Original predictions (LGB)
            X_meta_pred[:, 1],  # Original predictions (LGB, DNN)
            X_meta_pred[:, 0] * X_meta_pred[:, 1],  # LGB * DNN
            np.mean(X_meta_pred, axis=1),          # Average prediction
            np.mean(X_meta_pred, axis=1) ** 2,          # Average prediction squared
            np.std(X_meta_pred, axis=1),           # Prediction uncertainty
            np.max(X_meta_pred, axis=1),           # Max confidence
            np.min(X_meta_pred, axis=1),           # Min confidence
            np.abs(X_meta_pred[:, 0] - X_meta_pred[:, 1]),  # Disagreement between models
            X_meta_pred[:, 0] ** 2,  # LGB^2
            X_meta_pred[:, 0] ** 3,  # LGB^3
            X_meta_pred[:, 0] ** 4,  # LGB^4
            np.exp(X_meta_pred[:, 0])  # e^LGB
        ])
        
        d1_prob = full_meta_learner.predict_proba(X_meta_pred_enhanced)[:, 1]
    else:
        # Traditional weighted ensemble (LGB + DNN only)
        lgb_proba = full_base_models['LGB'].predict_proba(features_dict)[:, 1]
        dnn_proba = full_base_models['DNN'].predict_proba(features_scaled_dnn)[:, 1]
        
        d1_prob = (lgb_proba * optimized_weights['LGB'] + 
                   dnn_proba * optimized_weights['DNN'])
    
    # Hierarchical combination
    hierarchical_d1_prob = (elite_prob * 0.4) + (d1_prob * 0.6)
    
    return hierarchical_d1_prob, elite_prob, d1_prob

# Apply hierarchical ensemble prediction on VALIDATION set for threshold optimization
hierarchical_probs_val, elite_val_probs, d1_val_probs = predict_d1_hierarchical_ensemble(
    X_full_val, X_full_val_scaled_dnn)

# Find optimal threshold with expanded range for better FP/FN ratio
thresholds = np.arange(0.25, 0.85, 0.01)  # More granular search, start higher to capture more D1s
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
    
    # Calculate custom optimization score with FP/FN ratio targeting
    fp_fn_ratio = fp/fn if fn > 0 else float('inf')
    
    # Target FP/FN ratio of 0.45 or higher, but cap rewards at 1.2 for accuracy optimization
    fp_fn_penalty = 0
    if fp_fn_ratio < 0.45:
        # Strong penalty for being too conservative
        fp_fn_penalty = -1.0 * (0.45 - fp_fn_ratio)
    elif fp_fn_ratio >= 0.45 and fp_fn_ratio <= 1.2:
        # Bonus for being in the sweet spot, but cap at 1.2 to prevent too many FPs
        fp_fn_penalty = 0.15 * min(fp_fn_ratio, 1.2)
    elif fp_fn_ratio > 1.2:
        # Small penalty for too many FPs (hurts accuracy)
        fp_fn_penalty = -0.1 * (fp_fn_ratio - 1.2)
    
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
    X_full_test, X_full_test_scaled_dnn)

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

print(f"\nCATCHER D1 HIERARCHICAL {ensemble_type.upper().replace('_', '-')} MODEL COMPLETE!")

# ============================================================================
# FEATURE IMPORTANCE ANALYSIS
# ============================================================================
print(f"\n📊 Feature Importance Analysis ({ensemble_type.upper().replace('_', '-')}):")

if ensemble_type == "meta_learner":
    # For meta-learner, show both base model importance and meta-learner weights
    print(f"\n🔍 Meta-Learner Feature Weights:")
    if hasattr(full_meta_learner, 'coef_'):
        meta_weights = full_meta_learner.coef_[0]
        meta_feature_names = [
            'LGB_prediction', 'DNN_prediction', 'LGB×DNN_interaction', 
            'Average_prediction', 'Average_prediction_squared', 'Prediction_uncertainty', 'Max_confidence', 
            'Min_confidence', 'Model_disagreement', 'LGB_squared', 'LGB_cubed', 'LGB_exponential', 
            'LGB_fourth'
        ]
        for i, (name, weight) in enumerate(zip(meta_feature_names, meta_weights)):
            print(f"{i+1:2d}. {name:<35} {weight:.4f}")
      
    elif hasattr(full_meta_learner, 'feature_importances_'):
        meta_importances = full_meta_learner.feature_importances_
        meta_feature_names = [
            'LGB_prediction', 'DNN_prediction', 'LGB×DNN_interaction', 
            'Average_prediction', 'Average_prediction_squared', 'Prediction_uncertainty', 'Max_confidence', 
            'Min_confidence', 'Model_disagreement', 'LGB_squared', 'LGB_cubed', 'LGB_exponential',
            'LGB_fourth'
        ]
        for i, (name, weight) in enumerate(zip(meta_feature_names, meta_importances)):
            print(f"{i+1:2d}. {name:<35} {weight:.4f}")

# Show LGB feature importance as the base reference
feature_importance = full_base_models['LGB'].feature_importances_
feature_names = X_full.columns

# Create feature importance dataframe
importance_df = pd.DataFrame({
    'feature': feature_names,
    'importance': feature_importance
}).sort_values('importance', ascending=False)

print(f"\n📊 LightGBM Base Model Feature Importance:")
print(f"\nAll {len(importance_df)} Features (sorted by importance):")
print("=" * 60)
for i, row in importance_df.iterrows():
    print(f"{i+1:2d}. {row['feature']:<35} {row['importance']:.4f}")

# ============================================================================
# MODEL SAVING AND DEPLOYMENT PIPELINE
# ============================================================================

import joblib
import os
from datetime import datetime

# Create model directory
model_dir = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/ml/models/models_c/models_d1_or_not_c/version_08182025'
os.makedirs(model_dir, exist_ok=True)

print(f"\n💾 Saving models to: {model_dir}")

# Save individual base models and their parameters
print("Saving base models...")
joblib.dump(full_base_models['LGB'], f"{model_dir}/lightgbm_model.pkl")
joblib.dump(best_lgb_params, f"{model_dir}/lightgbm_params.pkl")

joblib.dump(full_base_models['DNN'], f"{model_dir}/dnn_model.pkl") 
joblib.dump(best_dnn_params, f"{model_dir}/dnn_params.pkl")

# Save scalers if they exist
scalers_saved = []
if 'scaler_dnn' in locals():
    joblib.dump(scaler_dnn, f"{model_dir}/dnn_scaler.pkl")
    scalers_saved.append('dnn_scaler.pkl')
print(f"Scalers saved: {scalers_saved}")

# Save meta-learner if using meta-learner approach
if ensemble_type == "meta_learner":
    joblib.dump(full_meta_learner, f"{model_dir}/meta_learner.pkl")
    joblib.dump(best_meta_learner.get_params(), f"{model_dir}/meta_learner_params.pkl")

# Save model metadata
metadata = {
    'model_type': f'catcher_d1_{ensemble_type}',
    'ensemble_type': ensemble_type,
    'training_date': datetime.now().isoformat(),
    'random_seed': RANDOM_SEED,
    'test_accuracy': final_accuracy,
    'test_f1': f1_score(y_full_test, y_pred_hierarchical),
    'test_precision': precision_score(y_full_test, y_pred_hierarchical),
    'test_recall': recall_score(y_full_test, y_pred_hierarchical),
    'test_balanced_accuracy': balanced_accuracy_score(y_full_test, y_pred_hierarchical),
    'optimal_threshold': optimal_threshold,
    'feature_columns': list(X_full.columns),
    'elite_features': [],  # No elite features in this version
    'base_models': list(full_base_models.keys()),
    'data_shape': df.shape,
    'd1_rate': df['d1_or_not'].mean(),
    'class_distribution': df['d1_or_not'].value_counts().to_dict(),
    'feature_importance': importance_df.to_dict('records')[:20]  # Top 20 features
}

# Add meta-learner specific metadata
if ensemble_type == "meta_learner":
    if hasattr(full_meta_learner, 'coef_'):
        meta_feature_names = [
            'LGB_prediction', 'DNN_prediction', 'LGB×DNN_interaction', 
            'Average_prediction', 'Average_prediction_squared', 'Prediction_uncertainty', 'Max_confidence', 
            'Min_confidence', 'Model_disagreement', 'LGB_squared', 'LGB_cubed', 'LGB_exponential', 
            'LGB_fourth'
        ]
        metadata['meta_feature_weights'] = dict(zip(meta_feature_names, full_meta_learner.coef_[0]))
    elif hasattr(full_meta_learner, 'feature_importances_'):
        meta_feature_names = [
            'LGB_prediction', 'DNN_prediction', 'LGB×DNN_interaction', 
            'Average_prediction', 'Average_prediction_squared', 'Prediction_uncertainty', 'Max_confidence', 
            'Min_confidence', 'Model_disagreement', 'LGB_squared', 'LGB_cubed', 'LGB_exponential',
            'LGB_fourth'
        ]
        metadata['meta_feature_importances'] = dict(zip(meta_feature_names, full_meta_learner.feature_importances_))
else:
    metadata['ensemble_weights'] = optimized_weights

joblib.dump(metadata, f"{model_dir}/model_metadata.pkl")

print("✅ Models saved successfully!")
print(f"📁 Model directory: {model_dir}")
print(f"📊 Test accuracy: {final_accuracy:.4f}")
print(f"🎯 Model type: {ensemble_type}")
print(f"🔧 Base models: {list(full_base_models.keys())}")