"""
Test script for school name normalization logic
Verifies the normalization function works correctly before running full matching
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database.name_matching.school_name_matcher import SchoolNameMatcher


def test_normalization():
    """Test the normalization logic with various examples"""

    matcher = SchoolNameMatcher()

    # Test cases with expected outputs
    test_cases = [
        # (input, expected_output, description)
        ("University of California, Berkeley, CA", "California", "University of prefix removal"),
        ("Stanford University, Stanford, CA", "Stanford", "University postfix removal"),
        ("Arizona State University, Tempe, AZ", "Arizona St", "State University → St"),
        ("Boston College, Chestnut Hill, MA", "Boston", "College postfix removal"),
        ("University of Southern California, Los Angeles, CA", "Southern California", "University of prefix"),
        ("Texas A&M University, College Station, TX", "Texas A&M", "University postfix"),
        ("Florida State University, Tallahassee, FL", "Florida St", "State University"),
        ("Duke University, Durham, NC", "Duke", "Simple university removal"),
        ("Vanderbilt University, Nashville, TN", "Vanderbilt", "University postfix"),
        ("University of Miami, Coral Gables, FL", "Miami", "University of prefix"),
        ("Texas Christian University, Fort Worth, TX", "Texas Christian", "University postfix"),
        ("University of North Carolina, Chapel Hill, NC", "North Carolina", "University of prefix"),
        ("Ohio State University, Columbus, OH", "Ohio St", "State University"),
        ("Louisiana State University, Baton Rouge, LA", "Louisiana St", "State University"),
        ("Michigan State University, East Lansing, MI", "Michigan St", "State University"),
        ("Penn State University, University Park, PA", "Penn St", "State University"),
        ("Georgetown University, Washington, DC", "Georgetown", "University postfix"),
        ("Williams College, Williamstown, MA", "Williams", "College postfix"),
        ("Amherst College, Amherst, MA", "Amherst", "College postfix"),
        ("University of Pennsylvania, Philadelphia, PA", "Pennsylvania", "University of prefix"),
    ]

    print("=" * 100)
    print("TESTING SCHOOL NAME NORMALIZATION")
    print("=" * 100)
    print(f"{'Input':<60} {'Expected':<25} {'Actual':<25} {'Status'}")
    print("-" * 100)

    passed = 0
    failed = 0

    for input_name, expected, description in test_cases:
        actual = matcher.normalize_school_name(input_name)
        status = "✅ PASS" if actual == expected else "❌ FAIL"

        if actual == expected:
            passed += 1
        else:
            failed += 1

        # Truncate long inputs for display
        display_input = input_name if len(input_name) <= 57 else input_name[:54] + "..."

        print(f"{display_input:<60} {expected:<25} {actual:<25} {status}")

    print("-" * 100)
    print(f"Total: {len(test_cases)} | Passed: {passed} | Failed: {failed}")
    print("=" * 100)

    if failed > 0:
        print("\n⚠️  Some tests failed. Please review the normalization logic.")
    else:
        print("\n✅ All normalization tests passed!")

    return failed == 0


if __name__ == "__main__":
    success = test_normalization()
    sys.exit(0 if success else 1)
