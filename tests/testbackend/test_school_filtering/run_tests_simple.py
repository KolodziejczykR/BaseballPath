#!/usr/bin/env python3
"""
Simple test runner for school filtering system
"""

import sys
import os
import subprocess
from pathlib import Path


def main():
    # Change to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    os.chdir(project_root)

    print("🚀 Running School Filtering Tests")
    print(f"📂 Project root: {project_root}")

    # Test commands to run (only working tests)
    test_commands = [
        ("Basic Functionality", "python3 -m pytest tests/test_school_filtering/test_basic_functionality.py -v"),
        ("Existing Functionality", "python3 -m pytest tests/test_school_filtering/test_existing_functionality.py -v"),
        ("API Endpoints", "python3 -m pytest tests/test_school_filtering/test_existing_api.py -v"),
        ("All Working Tests", "python3 -m pytest tests/test_school_filtering/ -v")
    ]

    results = []

    for name, cmd in test_commands:
        print(f"\n{'='*60}")
        print(f"🧪 {name}")
        print(f"{'='*60}")

        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ {name} - PASSED")
                results.append((name, True))
            else:
                print(f"❌ {name} - FAILED")
                print("STDOUT:", result.stdout[-500:])  # Last 500 chars
                print("STDERR:", result.stderr[-500:])  # Last 500 chars
                results.append((name, False))
        except subprocess.TimeoutExpired:
            print(f"⏱️ {name} - TIMEOUT")
            results.append((name, False))
        except Exception as e:
            print(f"💥 {name} - ERROR: {e}")
            results.append((name, False))

    # Summary
    print(f"\n{'='*60}")
    print("📋 TEST SUMMARY")
    print(f"{'='*60}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{name}: {status}")

    print(f"\n🎯 Overall: {passed}/{total} passed")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())