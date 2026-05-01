import pandas as pd
import numpy as np

# Load data
csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/vae_outfielders.csv'
og_df = pd.read_csv(csv_path)

# keep only d1 talent
og_df = og_df[og_df['three_section_commit_group'].str.lower() != 'non d1']
og_df['p4_or_not'] = (og_df['three_section_commit_group'].str.lower() != 'non p4 d1').astype(int)

keep_columns = ['p4_or_not', 'primary_position', 'height', 'weight', 'sixty_time',
                'of_velo', 'player_region', 'exit_velo_max', 'throwing_hand', 'hitting_handedness'] 

og_df = pd.DataFrame(og_df[keep_columns])

# The scraper flipped the order of 'throwing_hand' and 'hitting_handedness', so swap their values
og_df['throwing_hand'], og_df['hitting_handedness'] = og_df['hitting_handedness'], og_df['throwing_hand']

og_df['throwing_hand'] = og_df['throwing_hand'].str.strip()
og_df['hitting_handedness'] = og_df['hitting_handedness'].str.strip()

valid_throwing_hands = ['L', 'R']
valid_hitting_hands = ['R', 'L', 'S']

mask_hitting = og_df['hitting_handedness'].isin(valid_hitting_hands)
mask_throwing = og_df['throwing_hand'].isin(valid_throwing_hands)
og_df = og_df[mask_hitting & mask_throwing]

# impute of velo data
print(f"Missing of_velo values: {og_df['of_velo'].isnull().sum()} out of {len(og_df)}")

# Add imputation indicator (before imputation)
og_df['of_velo_imputed'] = og_df['of_velo'].isna().astype(int)

# Intelligent imputation based on player characteristics
from sklearn.ensemble import RandomForestRegressor
import warnings
warnings.filterwarnings('ignore')

# Create features for imputation prediction
imputation_features = ['height', 'weight', 'sixty_time', 'exit_velo_max']
categorical_features = ['player_region', 'throwing_hand', 'hitting_handedness']

# Create imputation dataset
impute_df = og_df.copy()

# Encode categorical variables for imputation
for cat_col in categorical_features:
    impute_df = pd.get_dummies(impute_df, columns=[cat_col], prefix=cat_col, drop_first=True)

# Get feature columns for imputation model
feature_cols = [col for col in impute_df.columns if col.startswith(tuple(imputation_features + ['player_region_', 'throwing_hand_', 'hitting_handedness_']))]

# Separate complete and missing of_velo cases
complete_cases = impute_df[impute_df['of_velo'].notna()]
missing_cases = impute_df[impute_df['of_velo'].isna()]

if len(missing_cases) > 0 and len(complete_cases) > 0:
    print(f"Training imputation model on {len(complete_cases)} complete cases...")
    
    # Train imputation model
    X_complete = complete_cases[feature_cols]
    y_complete = complete_cases['of_velo']
    
    # Use RandomForest for robust imputation
    impute_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=8,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42
    )
    
    impute_model.fit(X_complete, y_complete)
    
    # Predict missing values
    X_missing = missing_cases[feature_cols]
    predicted_of_velo = impute_model.predict(X_missing)
    
    # Add realistic noise based on model residuals
    residuals = y_complete - impute_model.predict(X_complete)
    noise_std = residuals.std() * 0.5  # Reduce noise by half for conservative estimates
    noise = np.random.normal(0, noise_std, len(predicted_of_velo))
    predicted_of_velo_with_noise = predicted_of_velo + noise
    
    # Ensure predictions are within reasonable bounds
    min_of_velo = complete_cases['of_velo'].quantile(0.05)
    max_of_velo = complete_cases['of_velo'].quantile(0.95)
    predicted_of_velo_with_noise = np.clip(predicted_of_velo_with_noise, min_of_velo, max_of_velo)
    
    # Fill missing values
    og_df.loc[og_df['of_velo'].isna(), 'of_velo'] = predicted_of_velo_with_noise
    
    print(f"Imputed {len(missing_cases)} missing of_velo values")
    print(f"Imputation range: {predicted_of_velo_with_noise.min():.1f} - {predicted_of_velo_with_noise.max():.1f} mph")
    print(f"Original of_velo range: {complete_cases['of_velo'].min():.1f} - {complete_cases['of_velo'].max():.1f} mph")
    
    # Feature importance for transparency
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': impute_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\nTop imputation features:")
    for i, row in feature_importance.head(5).iterrows():
        print(f"  {row['feature']}: {row['importance']:.3f}")

# Add imputation indicator (before imputation)
og_df['of_velo_imputed'] = og_df['of_velo'].isna().astype(int)

print(f"\nFinal dataset shape: {og_df.shape}")
print(f"Remaining missing of_velo: {og_df['of_velo'].isnull().sum()}")

na_counts = og_df.isnull().sum()
print("NA value counts per column:")
print(na_counts)

og_df.dropna(inplace=True)

print(f"Total number of rows after removing NAs post imputation: {len(og_df)}")

# already downloaded / saved
og_df.to_csv('/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/of_p4_or_not_data.csv', index=False)