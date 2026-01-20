"""
Script to update all spells with "Player's Handbook" source to "Player's Handbook (2024)".
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import SpellDatabase


def update_phb_sources():
    """Update all spells with source 'Player's Handbook' to 'Player's Handbook (2024)'."""
    db = SpellDatabase()
    
    # Get all spells
    all_spells = db.get_all_spells()
    
    updated_count = 0
    for spell in all_spells:
        if spell.get('source') == "Player's Handbook":
            # Update the source
            spell['source'] = "Player's Handbook (2024)"
            if db.update_spell(spell['id'], spell):
                updated_count += 1
                print(f"Updated source for: {spell['name']}")
    
    print(f"\n=== Summary ===")
    print(f"Updated source for {updated_count} spells")


if __name__ == "__main__":
    update_phb_sources()
