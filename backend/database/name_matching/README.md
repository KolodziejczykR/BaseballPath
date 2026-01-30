# School Name to Baseball Rankings Matching System

## Overview

This system matches school names from `school_data_general` (formatted as "University Name, City, ST") to team names in `baseball_rankings_data` (formatted as "Team Name") using a combination of exact and fuzzy string matching.

## Matching Algorithm

The algorithm follows these steps:

1. **Normalize school name** by removing common prefixes and postfixes:
   - Remove prefix "University of"
   - Remove postfix "University" or "College"
   - Convert "State University" → "St"
   - Remove city and state portion (after comma)

2. **Try exact match** against team names (case-insensitive)

3. **Try fuzzy match** if no exact match found:
   - Use fuzzy string matching with 90% confidence threshold
   - Only accept matches above 90% confidence

4. **Mark for manual review** if no qualifying match found

## Files

- **`create_name_mapping_table.sql`** - SQL script to create the mapping table in Supabase
- **`school_name_matcher.py`** - Main matching script
- **`test_name_normalization.py`** - Test script to verify normalization logic
- **`requirements_matching.txt`** - Python dependencies for matching

## Database Schema

```sql
Table: school_baseball_ranking_name_mapping
├── id (SERIAL PRIMARY KEY)
├── school_name (TEXT) - Original from school_data_general
├── team_name (TEXT) - Matched from baseball_rankings_data (null if no match)
├── verified (BOOLEAN) - Manual verification status
│   ├── null = needs review
│   ├── true = verified correct
│   └── false = verified incorrect
├── match_type (TEXT) - 'exact', 'fuzzy', or 'no_match'
├── confidence_score (DECIMAL) - Fuzzy match confidence (0.0-1.0)
├── normalized_school_name (TEXT) - The normalized version used for matching
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

## Setup Instructions

### Step 1: Install Dependencies

```bash
cd backend/database
pip install -r requirements_matching.txt
```

### Step 2: Create Database Table

Run the SQL script in Supabase SQL Editor:

```sql
-- Copy contents of create_name_mapping_table.sql and run in Supabase
```

Or use the Supabase CLI:

```bash
supabase db push
```

### Step 3: Test Normalization Logic

Before running the full matching, test the normalization logic:

```bash
cd backend/database
python test_name_normalization.py
```

This will test the normalization function with 20+ example cases and show you the results.

### Step 4: Run Matching Algorithm

```bash
cd backend/database
python school_name_matcher.py
```

The script will:
1. Fetch all school names from `school_data_general`
2. Fetch all team names from `baseball_rankings_data`
3. Run the matching algorithm
4. Display summary statistics and sample matches
5. Ask for confirmation before uploading to database

**Example Output:**
```
================================================================================
MATCHING SUMMARY
================================================================================
Total schools processed: 500
Exact matches: 350 (70.0%)
Fuzzy matches (>90%): 75 (15.0%)
No matches found: 75 (15.0%)

Total matched: 425 (85.0%)
Needs manual review: 150 (30.0%)
================================================================================
```

### Step 5: Manual Verification

After uploading, manually verify the matches in Supabase:

1. **Review Fuzzy Matches** (confidence 90-99%):
   ```sql
   SELECT school_name, team_name, confidence_score
   FROM school_baseball_ranking_name_mapping
   WHERE match_type = 'fuzzy'
   ORDER BY confidence_score DESC;
   ```

2. **Review No Matches**:
   ```sql
   SELECT school_name, normalized_school_name, team_name
   FROM school_baseball_ranking_name_mapping
   WHERE match_type = 'no_match';
   ```

3. **Update Verification Status**:
   ```sql
   -- For correct matches
   UPDATE school_baseball_ranking_name_mapping
   SET verified = true
   WHERE school_name = 'University of California, Berkeley, CA';

   -- For incorrect matches (then manually fix team_name)
   UPDATE school_baseball_ranking_name_mapping
   SET verified = false
   WHERE school_name = 'Some School Name, City, ST';

   -- Fix the team name after marking as false
   UPDATE school_baseball_ranking_name_mapping
   SET team_name = 'Correct Team Name', verified = true
   WHERE school_name = 'Some School Name, City, ST';
   ```

## Example Matches

### Exact Matches (Automatic)
- `Stanford University, Stanford, CA` → `Stanford`
- `University of California, Berkeley, CA` → `California`
- `Arizona State University, Tempe, AZ` → `Arizona St`

### Fuzzy Matches (Needs Review)
- `University of North Carolina, Chapel Hill, NC` → `North Carolina` (95%)
- `Texas Christian University, Fort Worth, TX` → `TCU` (92%)

### No Matches (Needs Manual Lookup)
- `Commonwealth University-Bloomsburg, Bloomsburg, PA` → (no match)
- `Pennsylvania Western University, California, PA` → (no match)

## Using the Mapping in Code

Once verified, use the mapping in your code:

```python
from backend.database.name_matching import get_resolver

resolver = get_resolver()

# Get team name from school name
team_name = resolver.get_team_name("Stanford University, Stanford, CA")
# Returns: "Stanford"

# Get school name from team name (reverse lookup)
school_name = resolver.get_school_name("Stanford")
# Returns: "Stanford University, Stanford, CA"
```

## Integration with School Filtering Pipeline

The name mapping is **critical** for the school filtering pipeline because:

### Division Group Lookup

The `division_group` field (Power 4 D1, Non-P4 D1, Non-D1) is stored in `baseball_rankings_data`, NOT in `school_data_general`. The filtering pipeline uses this mapping to enrich schools with their division group:

```
school_data_general.school_name
    ↓ (lookup via this mapping)
school_baseball_ranking_name_mapping.team_name
    ↓ (fetch division_group)
baseball_rankings_data.division_group
```

### How It Works in the Pipeline

1. **Cache Loading**: On first query, the pipeline loads all verified mappings into memory
2. **Enrichment**: Each school from `school_data_general` is enriched with `division_group`
3. **Fallback**: Schools without a verified mapping default to "Non-D1"

### Code Example (Pipeline Usage)

```python
# In backend/school_filtering/database.py and database/async_queries.py

async def _load_division_group_cache(self):
    """Load division_group mappings from baseball_rankings_data via name mapping"""
    # Get verified mappings: school_name → team_name
    mapping_result = self.client.table('school_baseball_ranking_name_mapping')\
        .select('school_name, team_name')\
        .eq('verified', True)\
        .execute()

    # Get division_group from baseball_rankings_data using team_name
    rankings_result = self.client.table('baseball_rankings_data')\
        .select('team_name, division_group')\
        .in_('team_name', team_names)\
        .execute()

    # Cache: school_name → division_group
```

### Why This Matters

- **ML Division Prediction**: The ML model predicts which division a player belongs to (Power 4 D1, Non-P4 D1, Non-D1)
- **School Filtering**: The pipeline filters schools by their `division_group` to match the ML prediction
- **Without Mapping**: Schools couldn't be properly categorized by baseball division

## Troubleshooting

### Issue: Import error for rapidfuzz

**Solution:** Install rapidfuzz:
```bash
pip install rapidfuzz
```

Or use fuzzywuzzy as fallback:
```bash
pip install fuzzywuzzy python-Levenshtein
```

### Issue: No matches found

**Check:**
1. Verify both tables have data
2. Check database connection (SUPABASE_URL and SUPABASE_SERVICE_KEY in .env)
3. Review normalization logic - may need adjustments for your data

### Issue: Too many fuzzy matches

**Solution:** Increase threshold in `school_name_matcher.py`:
```python
# Change from 90.0 to 95.0 for stricter matching
fuzzy_match = self.find_fuzzy_match(normalized, team_names, threshold=95.0)
```

## Next Steps

After completing the matching:

1. ✅ Create `SchoolNameResolver` class for easy lookups
2. ✅ Integrate with `BaseballRankingsIntegration` class
3. ✅ Add baseball strength metrics to `SchoolMatch` objects
4. ✅ Update filtering pipeline to include rankings data
5. ✅ Add playing time filter logic using rankings

See the main README for the full integration roadmap.
