#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic tool to check swetest installation."""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from w8s_astro_mcp.utils.install_helper import InstallationHelper


def main():
    """Run diagnostic and show recommendations."""
    print("Checking swetest installation...\n")
    
    helper = InstallationHelper()
    diagnosis = helper.diagnose()
    
    print(f"Status: {diagnosis['status']}")
    print(f"Found in PATH: {'YES' if diagnosis['swetest_in_path'] else 'NO'}")
    print(f"Found elsewhere: {'YES' if diagnosis['swetest_found'] else 'NO'}")
    if diagnosis['found_at']:
        print(f"Location: {diagnosis['found_at']}")
    print()
    
    print("Recommendations:")
    for rec in diagnosis['recommendations']:
        print(f"  {rec}")
    print()
    
    if diagnosis['status'] == 'needs_path':
        print(helper.get_quick_fix_guide(diagnosis['found_at']))
    elif diagnosis['status'] == 'not_installed':
        print(helper.get_installation_guide())
    else:
        print("All set! swetest is ready.")


if __name__ == "__main__":
    main()
