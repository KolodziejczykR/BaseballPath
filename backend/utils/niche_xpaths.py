"""
XPath constants for Niche.com scraping
Update these XPaths when Niche changes their site structure
"""

# Base XPath for category grades - append /li[X] for specific categories
# Example: CATEGORY_GRADES_BASE_XPATH + "/li[1]" for academics
CATEGORY_GRADES_BASE_XPATH = "/html/body/div[1]/div[1]/div[1]/div[1]/main[1]/div[1]/div[3]/div[1]/div[1]/section[2]/div[1]/div[1]/div[1]/div[2]/ol[1]"

# Alternative base XPath for category grades (some Niche pages load with different structure)
CATEGORY_GRADES_BASE_XPATH_2 = "/html/body/div[1]/div/div[1]/div/main/div/div[3]/div/div[2]/section[3]/div/div[1]/div/div[2]/ol"

# Class-based XPath for raw HTML (what lxml sees)
CATEGORY_GRADES_BASE_XPATH_RAW = '//ol[@class="ordered__list__bucket"]'

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
ENROLLMENT_XPATH_2 = "/html/body/div[1]/div/div[1]/div/main/div/div[3]/div/div[2]/section[2]/div/div[2]/div[1]/div/div/div[2]/div/span"

# Using class-based XPath for overall grade (more reliable than absolute path)
OVERALL_GRADE_XPATH = "//div[contains(@class, 'overall-grade')]//div[contains(@class, 'niche__grade')]"

# Helper function to build full category grade XPath
def get_category_grade_xpath(li_index: int, use_alternative: bool = False) -> str:
    """
    Build complete XPath for a specific category grade

    Args:
        li_index: The list item index (1-12)
        use_alternative: If True, use CATEGORY_GRADES_BASE_XPATH_2 instead of default
    """
    base_path = CATEGORY_GRADES_BASE_XPATH_2 if use_alternative else CATEGORY_GRADES_BASE_XPATH
    return f"{base_path}/li[{li_index}]{CATEGORY_GRADE_ENDING_XPATH}"

def get_category_grade_xpath_lasting(li_index: int, use_alternative: bool = False) -> str:
    """
    Build complete XPath for a specific category grade using class-based approach for raw HTML

    Args:
        li_index: The list item index (1-12)
        use_alternative: Not used, kept for compatibility
    """
    # Use class-based XPath that works with raw HTML structure
    # Note: Use contains() because the div has multiple classes like "niche__grade niche__grade--section--c-plus"
    return f'{CATEGORY_GRADES_BASE_XPATH_RAW}/li[@class="ordered__list__bucket__item"][{li_index}]//div[contains(@class, "niche__grade")]'