MASSEY_LINK = "https://masseyratings.com/cbase{year}/ncaa-d{division_number}/ratings"

MASSEY_TABLE_XPATH = "/html/body/div[1]/div[3]/div[1]/table/tbody/tr[{row}]"

CATEGORY_SUFFIXES = {
    "Team" : "/td[1]/a[1]",
    "Record" : "/td[2]",
    "Overall_Rating" : "/td[3]",
    "Power_Rating" : "/td[4]",
    
    "Offensive_Rating" : "/td[5]",
    "Defensive_Rating" : "/td[6]",
    "Strength_of_Schedule" : "/td[8]",
}

def get_massey_link(year: int, division_number: int):
    return MASSEY_LINK.format(year=year, division_number=division_number)