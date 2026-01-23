# Baseball Rankings Scraper

A comprehensive scraping system for college baseball rankings from Massey Ratings, designed to enhance school strength analysis and playing time calculations in the BaseballPATH platform.

## Overview

This scraper collects college baseball team rankings for **years 2023-2025** and **divisions D1, D2, D3** from [masseyratings.com](https://masseyratings.com), storing the data in Supabase for integration with the school filtering pipeline.

## Features

### 🎯 **Data Collection**
- **Comprehensive Coverage**: All NCAA divisions (D1, D2, D3) for 2023-2025
- **Rich Metrics**: Overall rating, power rating, offensive/defensive ratings, strength of schedule
- **Performance Data**: Win-loss records, win percentages, team rankings

### 🛡️ **Anti-Detection Measures**
- Randomized user agents and headers
- Session warmup with realistic browsing patterns
- Random delays (2-6 seconds) between requests
- Exponential backoff for rate limiting
- Respectful scraping practices

### 🗄️ **Database Integration**
- Direct Supabase upload with upsert functionality
- Row-level security (RLS) policies
- Computed fields and percentile rankings
- Data validation and error handling

### 📊 **Analysis Tools**
- Weighted 3-year averages (50%, 30%, 20%)
- Trend analysis (improving/declining/stable)
- Division percentile rankings
- Playing time opportunity factors

## File Structure

```
backend/baseball_rankings_scraper/
├── README.md                      # This documentation
├── __init__.py                     # Package initialization
├──
├── utils/
│   └── massey_rankings_xpaths.py   # XPath selectors for scraping
├──
├── sql/
│   └── create_baseball_rankings_table.sql  # Database schema
├──
├── massey_scraper.py               # Main scraper class
├── run_scraper.py                  # Easy-to-use runner script
└── rankings_integration.py        # Integration utilities
```

## Database Schema

The scraper creates a `baseball_rankings` table with the following structure:

```sql
CREATE TABLE baseball_rankings (
    id SERIAL PRIMARY KEY,
    team_name VARCHAR(255) NOT NULL,
    year INTEGER NOT NULL,
    division INTEGER CHECK (division IN (1, 2, 3)),
    record VARCHAR(50),                    -- e.g., "35-15"
    overall_rating DECIMAL(8,4),           -- Massey overall rating
    power_rating DECIMAL(8,4),             -- Massey power rating
    offensive_rating DECIMAL(8,4),         -- Offensive rating
    defensive_rating DECIMAL(8,4),         -- Defensive rating
    strength_of_schedule DECIMAL(8,4),     -- SOS rating
    wins INTEGER,                          -- Parsed from record
    losses INTEGER,                        -- Parsed from record
    win_percentage DECIMAL(5,3),           -- Calculated win %
    scraped_at TIMESTAMP WITH TIME ZONE,
    data_source VARCHAR(100) DEFAULT 'massey_ratings',

    UNIQUE(team_name, year, division)
);
```

## Setup & Installation

### 1. Environment Variables
Ensure your `.env` file contains:
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_service_key
```

### 2. Database Setup
Run the SQL script to create the table:
```bash
# Execute the SQL file in your Supabase SQL editor
cat backend/baseball_rankings_scraper/sql/create_baseball_rankings_table.sql
```

### 3. Python Dependencies
The scraper uses existing project dependencies:
- `requests` - HTTP requests
- `lxml` - HTML parsing
- `supabase` - Database integration
- `python-dotenv` - Environment variables

## Usage

### Quick Start

#### Option 1: Interactive Runner
```bash
cd backend/baseball_rankings_scraper
python run_scraper.py
```

#### Option 2: Command Line
```bash
# Test scrape (2024 D1 only)
python run_scraper.py --test

# Full scrape (all years and divisions)
python run_scraper.py --full
```

#### Option 3: Programmatic Usage
```python
from backend.baseball_rankings_scraper.massey_scraper import MasseyBaseballScraper

# Initialize scraper
scraper = MasseyBaseballScraper(delay=3.0)

# Scrape all data
results = scraper.scrape_all_data()

# Scrape specific year/division
teams = scraper.scrape_division_year(2024, 1)
```

### Integration with School Filtering

```python
from backend.baseball_rankings_scraper.rankings_integration import BaseballRankingsIntegration

# Initialize integration
integration = BaseballRankingsIntegration()

# Get school strength profile
profile = integration.get_school_strength_profile("Stanford")
print(f"Strength classification: {profile['strength_classification']}")
print(f"Playing time factor: {profile['playing_time_factor']}")

# Compare multiple schools
comparison = integration.compare_schools_strength(["Stanford", "UCLA", "Texas"])

# Get division rankings
top_teams = integration.get_division_rankings(2024, 1, limit=25)
```

## Data Analysis Examples

### Strength Classification
- **Elite** (90th+ percentile): Top-tier programs
- **Strong** (75th+ percentile): Highly competitive
- **Competitive** (50th+ percentile): Average programs
- **Developing** (25th+ percentile): Building programs
- **Rebuilding** (<25th percentile): Opportunity for playing time

### Playing Time Factors
- **Elite programs** (0.7x factor): Very competitive, harder to earn playing time
- **Strong programs** (0.8x factor): Competitive environment
- **Average programs** (1.0x factor): Normal opportunities
- **Developing programs** (1.2x factor): More opportunities available
- **Rebuilding programs** (1.3x factor): Best opportunities for immediate impact

### Trend Analysis
```python
# 3-year weighted average calculation
# Most recent year: 50% weight
# Previous year: 30% weight
# Oldest year: 20% weight

weighted_rating = (2024_rating * 0.5) + (2023_rating * 0.3) + (2022_rating * 0.2)
```

## Performance & Timing

### Expected Runtime
- **Test scrape** (2024 D1): ~2-3 minutes
- **Full scrape** (all years/divisions): ~15-20 minutes
- **Data volume**: ~2,000-3,000 teams total

### Rate Limiting
- **Base delay**: 3 seconds between requests
- **Random variation**: ±2 seconds
- **Rate limit handling**: 30+ second backoff
- **Batch uploads**: 50 teams per Supabase transaction

## Error Handling

### Robust Recovery
- **Request failures**: 3 retry attempts with exponential backoff
- **Parsing errors**: Skip individual rows, continue processing
- **Database errors**: Batch upload with transaction safety
- **Session issues**: Automatic session warmup and header rotation

### Logging
- **Detailed logs**: Request timing, success/failure rates
- **Log files**: Timestamped logs saved automatically
- **Progress tracking**: Real-time progress indicators

## Integration Points

### School Filtering Pipeline
1. **Strength Rankings**: Integrate with existing academic/athletic grades
2. **Playing Time Calculations**: Factor into ML prediction confidence
3. **Preference Matching**: Add competitive level preferences
4. **School Recommendations**: Weight by program strength and opportunity

### API Endpoints (Future)
```python
# Example endpoints to add to preferences_router.py
GET /schools/{school_name}/strength-profile
GET /rankings/{division}/{year}
POST /schools/compare-strength
```

### Database Views
The system includes a computed view for easy querying:
```sql
-- Query percentile rankings (Note: lower rating = better, so use ASC for best teams)
SELECT team_name, overall_percentile, power_percentile
FROM baseball_rankings_with_percentiles
WHERE year = 2024 AND division = 1
ORDER BY overall_rating ASC;  -- ASC shows best teams first (lowest ratings)
```

## Maintenance

### Regular Updates
- **Annual scraping**: Run after each season ends
- **Data validation**: Check for missing or anomalous data
- **Performance monitoring**: Track scraping success rates

### Data Quality
- **Duplicate handling**: Upsert prevents duplicates
- **Missing data**: Graceful handling of incomplete records
- **Data types**: Automatic validation and conversion

## Troubleshooting

### Common Issues

1. **Rate Limiting**: Increase delay parameter
2. **Missing Data**: Check XPath selectors for site changes
3. **Database Errors**: Verify Supabase credentials and permissions
4. **Session Failures**: Clear browser cache equivalents

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

scraper = MasseyBaseballScraper(delay=5.0)  # Slower for debugging
```

## Security Considerations

- **RLS Policies**: Database access controlled by Supabase RLS
- **Service Key**: Uses service key for write access
- **Rate Limiting**: Respectful scraping to avoid blocking
- **User Agents**: Realistic browser headers to avoid detection

## Future Enhancements

- **Historical Data**: Expand to more years (2020-2022)
- **Conference Data**: Add conference strength metrics
- **Playoff Performance**: Include tournament/playoff results
- **Coach Tracking**: Link coaching changes to performance trends
- **Real-time Updates**: Monitor for in-season ranking changes

---

**Note**: This scraper is designed for educational and research purposes as part of the BaseballPATH platform. Please respect the source website's terms of service and rate limits.