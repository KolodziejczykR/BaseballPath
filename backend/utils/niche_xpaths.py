"""
XPath constants for Niche.com scraping
Update these XPaths when Niche changes their site structure
"""

# Base XPath for category grades - append /li[X] for specific categories
# Example: CATEGORY_GRADES_BASE_XPATH + "/li[1]" for academics
CATEGORY_GRADES_BASE_XPATH = "/html/body/div[1]/div[1]/div[1]/div[1]/main[1]/div[1]/div[3]/div[1]/div[1]/section[2]/div[1]/div[1]/div[1]/div[2]/ol[1]"

CATEGORY_GRADE_MAPPING = {
    1: 'academics_grade',  
    2: 'value_grade',      
    3: 'diversity_grade',  
    4: 'campus_life_grade', 
    5: 'athletics_grade',   
    6: 'party_scene_grade', 
    7: 'professors_grade',  
    8: 'location_grade',    
    9: 'dorms_grade',      
    10: 'campus_food_grade', 
    11: 'student_life_grade', 
    12: 'safety_grade'      
}

# XPath for individual category grade (relative to li element)
CATEGORY_GRADE_ENDING_XPATH = "/div/div[2]"

# School statistics XPaths (update these as needed)
ENROLLMENT_XPATH = "/html/body/div[1]/div[1]/div[1]/div[1]/main[1]/div[1]/div[3]/div[1]/div[1]/section[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div[2]/div[1]/span[1]"

# Using class-based XPath for overall grade (more reliable than absolute path)
OVERALL_GRADE_XPATH = "//div[contains(@class, 'overall-grade')]//div[contains(@class, 'niche__grade')]"

# Helper function to build full category grade XPath
def get_category_grade_xpath(li_index: int) -> str:
    """Build complete XPath for a specific category grade"""
    return f"{CATEGORY_GRADES_BASE_XPATH}/li[{li_index}]{CATEGORY_GRADE_ENDING_XPATH}"