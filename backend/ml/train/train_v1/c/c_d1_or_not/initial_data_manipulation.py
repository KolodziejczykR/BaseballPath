import pandas as pd
import numpy as np

# Load data
csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/vae_catchers.csv'
og_df = pd.read_csv(csv_path)

og_df['d1_or_not'] = (og_df['three_section_commit_group'].str.lower() != 'non d1').astype(int)

keep_columns = ['d1_or_not', 'primary_position', 'height', 'weight', 'sixty_time',
                'c_velo', 'pop_time','player_region', 'exit_velo_max', 'throwing_hand', 'hitting_handedness'] 

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

# dropping misinputed/bad data columns
og_df = og_df[og_df['c_velo'] <= 95]
og_df = og_df[og_df['c_velo'] >= 40]

og_df = og_df[og_df['pop_time'] <= 4]
og_df = og_df[og_df['pop_time'] >= 1]

print(f"\nAverage c_velo: {og_df['c_velo'].mean():.2f} mph")
print(f"Average pop_time: {og_df['pop_time'].mean():.2f} sec")

print(f"pop_time range: {og_df['pop_time'].min():.2f} - {og_df['pop_time'].max():.2f} sec")
print(f"c_velo range: {og_df['c_velo'].min():.2f} - {og_df['c_velo'].max():.2f} mph")

na_counts = og_df.isnull().sum()
print("NA value counts per column:")
print(na_counts)

og_df.dropna(inplace=True)

print(f"Total number of rows after removing NAs post imputation: {len(og_df)}")

og_df.to_csv('/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/c_d1_or_not_data.csv', index=False)