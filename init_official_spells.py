"""
Initialization script to mark all existing spells as 'Official'.
Run this ONCE after setting up the database with all the official D&D spells.
This script will:
1. Add the 'Official' tag to all existing spells
2. Remove any 'Unofficial' tags from existing spells
3. Set is_modified to False for all spells

Usage:
    python init_official_spells.py

WARNING: This should only be run once on a fresh database with official spells.
Running it again will mark any user-created spells as official.
"""

import os
import sys

# Add the project root to path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from spell_manager import SpellManager


def main():
    print("=" * 60)
    print("Official Spells Initialization Script")
    print("=" * 60)
    print()
    
    # Check if database exists
    if not os.path.exists("spellbook.db"):
        print("ERROR: spellbook.db not found.")
        print("Please run the application first to create the database,")
        print("then run this script to mark spells as official.")
        return 1
    
    # Load spells
    manager = SpellManager()
    if not manager.load_spells():
        print("ERROR: Failed to load spells from database.")
        return 1
    
    spell_count = len(manager.spells)
    print(f"Found {spell_count} spells in database.")
    print()
    
    if spell_count == 0:
        print("No spells to process. Add spells first, then run this script.")
        return 1
    
    # Confirm
    print("This will mark ALL existing spells as 'Official'.")
    print("Any new spells added after this will be tagged 'Unofficial'.")
    print()
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Cancelled.")
        return 0
    
    print()
    print("Processing...")
    
    # Mark all spells as official
    modified = manager.mark_all_spells_official()
    
    print(f"Done! Modified {modified} spell(s).")
    print()
    print("All existing spells are now marked as 'Official'.")
    print("New spells created in the app will automatically be tagged 'Unofficial'.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
