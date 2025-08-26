"""
XPath constants for Niche.com scraping
Update these XPaths when Niche changes their site structure
"""

# Base XPath for category grades - append /li[X] for specific categories
# Example: CATEGORY_GRADES_BASE_XPATH + "/li[1]" for academics
CATEGORY_GRADES_BASE_XPATH = "/html/body/div[1]/div/div[1]/div/main/div/div[3]/div/div[2]/section[2]/div/div[1]/div/div[2]/ol"

# Category grade mapping (li position -> field name) - shifted back by 1
CATEGORY_GRADE_MAPPING = {
    1: 'overall_grade',
    2: 'academics_grade',  # was 1
    3: 'value_grade',      # was 2
    4: 'diversity_grade',  # was 3
    5: 'campus_life_grade', # was 4
    6: 'athletics_grade',   # was 5
    7: 'party_scene_grade', # was 6
    8: 'professors_grade',  # was 7
    9: 'location_grade',    # was 8
    10: 'dorms_grade',      # was 9
    11: 'campus_food_grade', # was 10
    12: 'student_life_grade', # was 11
    13: 'safety_grade'      # was 12
}

# XPath for individual category grade (relative to li element)
CATEGORY_GRADE_ENDING_XPATH = "/div/div[2]"

# School statistics XPaths (update these as needed)
ENROLLMENT_XPATH = "/html/body/div[1]/div/div[1]/div/main/div/div[3]/div/div[2]/section[22]/div[2]/div[1]/div/div[1]/div[2]/span[1]/span[1]"

# Helper function to build full category grade XPath
def get_category_grade_xpath(li_index: int) -> str:
    """Build complete XPath for a specific category grade"""
    return f"{CATEGORY_GRADES_BASE_XPATH}/li[{li_index}]{CATEGORY_GRADE_ENDING_XPATH}"