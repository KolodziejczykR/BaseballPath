import pandas as pd
import numpy as np

# Load data
csv_path = '/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/vae_outfielders.csv'
og_df = pd.read_csv(csv_path)

og_df['d1_or_not'] = (og_df['three_section_commit_group'].str.lower() != 'non d1').astype(int)

keep_columns = ['d1_or_not', 'primary_position', 'height', 'weight', 'sixty_time',
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

# og_df.to_csv('/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/hitters/of_feat_eng_d1_or_not.csv', index=False)

na_counts = og_df.isnull().sum()
print("NA value counts per column:")
print(na_counts)

print(f"Total number of rows: {len(og_df)}")


