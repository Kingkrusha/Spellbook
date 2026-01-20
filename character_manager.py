"""
Character Spell List Manager for D&D Spellbook Application.
Handles persistence of character spell lists to JSON file.
"""

import os
import json
from typing import List, Optional, Callable
from character import CharacterSpellList


class CharacterManager:
    """Manages character spell lists with file persistence."""
    
    DEFAULT_FILE = "characters.json"
    
    def __init__(self, file_path: str = None):
        """Initialize the character manager with an optional file path."""
        self.file_path = file_path or self.DEFAULT_FILE
        self._characters: List[CharacterSpellList] = []
        self._listeners: List[Callable[[], None]] = []
    
    @property
    def characters(self) -> List[CharacterSpellList]:
        """Return a copy of the character list."""
        return self._characters.copy()
    
    def add_listener(self, callback: Callable[[], None]):
        """Add a listener to be notified when characters change."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[], None]):
        """Remove a listener to prevent memory leaks when views are destroyed."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of a change."""
        for listener in self._listeners:
            listener()
    
    def load_characters(self) -> bool:
        """Load characters from the JSON file. Returns True if successful."""
        if not os.path.exists(self.file_path):
            # No file exists yet, start with empty list
            self._characters = []
            return True
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._characters = [
                    CharacterSpellList.from_dict(char_data)
                    for char_data in data.get("characters", [])
                ]
            self._notify_listeners()
            return True
        except Exception as e:
            print(f"Error loading characters: {e}")
            self._characters = []
            return False
    
    def save_characters(self) -> bool:
        """Save all characters to the JSON file. Returns True if successful."""
        try:
            data = {
                "characters": [char.to_dict() for char in self._characters]
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving characters: {e}")
            return False
    
    def add_character(self, character: CharacterSpellList) -> bool:
        """Add a new character. Returns False if name already exists."""
        if any(c.name.lower() == character.name.lower() for c in self._characters):
            return False
        
        self._characters.append(character)
        self._characters.sort(key=lambda c: c.name.lower())
        self.save_characters()
        self._notify_listeners()
        return True
    
    def update_character(self, old_name: str, updated_character: CharacterSpellList) -> bool:
        """Update an existing character. Returns True if successful."""
        for i, char in enumerate(self._characters):
            if char.name.lower() == old_name.lower():
                # Check for name conflict if name changed
                if old_name.lower() != updated_character.name.lower():
                    if any(c.name.lower() == updated_character.name.lower() for c in self._characters):
                        return False
                
                self._characters[i] = updated_character
                self._characters.sort(key=lambda c: c.name.lower())
                self.save_characters()
                self._notify_listeners()
                return True
        return False
    
    def delete_character(self, name: str) -> bool:
        """Delete a character by name. Returns True if successful."""
        for i, char in enumerate(self._characters):
            if char.name.lower() == name.lower():
                del self._characters[i]
                self.save_characters()
                self._notify_listeners()
                return True
        return False
    
    def get_character(self, name: str) -> Optional[CharacterSpellList]:
        """Get a character by name."""
        for char in self._characters:
            if char.name.lower() == name.lower():
                return char
        return None
    
    def add_spell_to_character(self, character_name: str, spell_name: str) -> bool:
        """Add a spell to a character's known spells."""
        char = self.get_character(character_name)
        if char and char.add_spell(spell_name):
            self.save_characters()
            self._notify_listeners()
            return True
        return False
    
    def remove_spell_from_character(self, character_name: str, spell_name: str) -> bool:
        """Remove a spell from a character's known spells."""
        char = self.get_character(character_name)
        if char and char.remove_spell(spell_name):
            self.save_characters()
            self._notify_listeners()
            return True
        return False

