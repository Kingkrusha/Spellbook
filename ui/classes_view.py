"""
Classes Collection View for D&D Spellbook Application.
Displays class information with feature tables like the PHB 2024.
"""

import customtkinter as ctk
from typing import Optional, Callable, List
from theme import get_theme_manager
from character_class import (
    get_class_manager, CharacterClassDefinition, ClassLevel, ClassAbility,
    SubclassDefinition
)
from .class_editor import ClassEditorDialog, SubclassEditorDialog


def get_spell_manager():
    """Get the global spell manager lazily."""
    global _spell_manager
    if _spell_manager is None:
        from spell_manager import SpellManager
        _spell_manager = SpellManager()
        _spell_manager.load_spells()
    return _spell_manager

_spell_manager = None


class ClassesCollectionView(ctk.CTkFrame):
    """View for browsing character classes with detailed feature tables."""
    
    def __init__(self, parent, on_back: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        
        self.on_back = on_back
        self.theme = get_theme_manager()
        self.class_manager = get_class_manager()
        self.current_class: Optional[CharacterClassDefinition] = None
        # Track subclass cards for navigation: {subclass_name: (card_widget, toggle_func, expanded_state)}
        self._subclass_cards: dict = {}
        # Pending subclass to select after class page loads
        self._pending_subclass: Optional[str] = None
        self._class_loaded: bool = False
        
        self._create_widgets()
        
        # Load first class by default
        classes = self.class_manager.classes
        if classes:
            self._select_class(classes[0].name)
    
    def _create_widgets(self):
        """Create the classes view UI."""
        # Left sidebar for class list
        sidebar = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_secondary'), width=220)
        sidebar.pack(side="left", fill="y", padx=(0, 2))
        sidebar.pack_propagate(False)
        
        # Back button
        if self.on_back:
            back_btn = ctk.CTkButton(
                sidebar, text="← Back to Collections",
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                anchor="w",
                command=self.on_back
            )
            back_btn.pack(fill="x", padx=10, pady=(10, 5))
        
        # Header
        ctk.CTkLabel(
            sidebar, text="Classes",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(padx=15, pady=10, anchor="w")
        
        # Add Class button
        self.add_class_btn = ctk.CTkButton(
            sidebar, text="+ Add Class",
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            height=30,
            command=self._open_class_editor
        )
        self.add_class_btn.pack(fill="x", padx=10, pady=(0, 10))
        
        # Class list
        self.class_list_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.class_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self._populate_class_list()
        
        # Main content area (scrollable)
        self.content_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content_scroll.pack(side="left", fill="both", expand=True)
        
        # Content container
        self.content = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=20)
    
    def _populate_class_list(self):
        """Populate the class list sidebar."""
        for widget in self.class_list_frame.winfo_children():
            widget.destroy()
        
        classes = self.class_manager.classes
        
        for class_def in classes:
            # Create a row frame for each class
            row = ctk.CTkFrame(self.class_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            
            # Class name button
            btn = ctk.CTkButton(
                row,
                text=class_def.name,
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                anchor="w",
                command=lambda c=class_def.name: self._select_class(c)
            )
            btn.pack(side="left", fill="x", expand=True)
            
            # Edit/Delete buttons for custom classes only
            if class_def.is_custom:
                ctk.CTkButton(
                    row, text="✎", width=24, height=24,
                    fg_color=self.theme.get_current_color('button_normal'),
                    hover_color=self.theme.get_current_color('button_hover'),
                    text_color=self.theme.get_current_color('text_primary'),
                    command=lambda c=class_def: self._open_class_editor(c)
                ).pack(side="right", padx=2)
                
                ctk.CTkButton(
                    row, text="✕", width=24, height=24,
                    fg_color=self.theme.get_current_color('button_danger'),
                    hover_color=self.theme.get_current_color('button_danger_hover'),
                    text_color=self.theme.get_current_color('text_primary'),
                    command=lambda c=class_def.name: self._delete_class(c)
                ).pack(side="right")
    
    def _delete_class(self, class_name: str):
        """Delete a custom class."""
        from tkinter import messagebox
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the class '{class_name}'?\n\nThis cannot be undone."):
            self.class_manager.delete_class(class_name)
            self._populate_class_list()
            # Select first class if available
            if self.class_manager.classes:
                self._select_class(self.class_manager.classes[0].name)
    
    def _select_class(self, class_name: str):
        """Select and display a class."""
        class_def = self.class_manager.get_class(class_name)
        if not class_def:
            return
        
        self.current_class = class_def
        self._display_class(class_def)
        
        # Reset scroll position to top
        self.content_scroll._parent_canvas.yview_moveto(0)
    
    def select_class(self, name: str) -> bool:
        """Public method to select a class or subclass by name. Returns True if found.
        
        For subclasses, format can be:
        - "Subclass Name (Parent Class)" - from global search
        - Just "Subclass Name" - will search all classes
        """
        # First check if it's a regular class
        class_def = self.class_manager.get_class(name)
        if class_def:
            self._select_class(name)
            return True
        
        # Check if this is a subclass - format: "Subclass Name (Parent Class)"
        subclass_name = name
        parent_class_name = None
        
        if "(" in name and name.endswith(")"):
            # Extract subclass name and parent class from format "Subclass (Class)"
            parts = name.rsplit(" (", 1)
            if len(parts) == 2:
                subclass_name = parts[0]
                parent_class_name = parts[1].rstrip(")")
        
        # Find the subclass
        for class_def in self.class_manager.classes:
            # If we know the parent class, only search that class
            if parent_class_name and class_def.name != parent_class_name:
                continue
            
            for subclass in class_def.subclasses:
                if subclass.name.lower() == subclass_name.lower():
                    # Found it! Set pending subclass and select the parent class
                    self._pending_subclass = subclass.name
                    self._class_loaded = False
                    self._select_class(class_def.name)
                    # Start polling for the subclass card to be ready
                    self._wait_for_subclass_card()
                    return True
        
        return False
    
    def _wait_for_subclass_card(self, attempts: int = 0):
        """Poll for the subclass card to be registered, then expand and scroll to it."""
        if not self._pending_subclass:
            return
        
        # Always wait at least 2 iterations to let Tkinter render the view
        # This ensures the UI is actually visible before we try to scroll
        min_attempts = 2
        
        # Check if the card is registered AND we've waited minimum time
        if self._pending_subclass in self._subclass_cards and self._class_loaded and attempts >= min_attempts:
            # Force a full update to ensure everything is rendered
            self.update_idletasks()
            self.update()
            
            subclass_name = self._pending_subclass
            self._pending_subclass = None
            self._expand_and_scroll_to_subclass(subclass_name)
        elif attempts < 30:  # Max ~3 seconds of polling (30 * 100ms)
            # Keep polling
            self.after(100, lambda: self._wait_for_subclass_card(attempts + 1))
        else:
            # Give up after max attempts
            self._pending_subclass = None
    
    def _expand_and_scroll_to_subclass(self, subclass_name: str):
        """Expand a subclass card and scroll to it."""
        # Ensure widgets are ready
        self.update_idletasks()
        
        if subclass_name in self._subclass_cards:
            card, toggle_func, expanded_state = self._subclass_cards[subclass_name]
            
            # Expand if collapsed
            if not expanded_state.get("is_expanded", False):
                toggle_func()
            
            # Scroll to the card
            self.update_idletasks()
            try:
                # Get card position relative to the scrollable frame
                card_y = card.winfo_y()
                canvas = self.content_scroll._parent_canvas
                canvas_height = canvas.winfo_height()
                scroll_region = canvas.cget('scrollregion')
                
                if scroll_region:
                    region_parts = scroll_region.split()
                    total_height = float(region_parts[3]) if len(region_parts) > 3 else 1
                    # Calculate scroll position to put subclass at top of view
                    scroll_pos = max(0, min(1, card_y / total_height))
                    canvas.yview_moveto(scroll_pos)
            except Exception:
                pass
    
    def _open_class_editor(self, class_def: Optional[CharacterClassDefinition] = None):
        """Open the class editor dialog."""
        dialog = ClassEditorDialog(self, class_def, on_save=self._on_class_saved)
        self.wait_window(dialog)
    
    def _on_class_saved(self, class_def: CharacterClassDefinition):
        """Called when a class is saved."""
        self._populate_class_list()
        self._select_class(class_def.name)
    
    def _open_subclass_editor(self, parent_class: CharacterClassDefinition, subclass: Optional[SubclassDefinition] = None):
        """Open the subclass editor dialog."""
        dialog = SubclassEditorDialog(self, parent_class, subclass, on_save=self._on_subclass_saved)
        self.wait_window(dialog)
    
    def _on_subclass_saved(self, subclass: SubclassDefinition):
        """Called when a subclass is saved."""
        # Refresh the current class display
        if self.current_class:
            # Reload class data
            self.current_class = self.class_manager.get_class(self.current_class.name)
            if self.current_class:
                self._display_class(self.current_class)
    
    def _delete_subclass(self, parent_class: CharacterClassDefinition, subclass: SubclassDefinition):
        """Delete a custom subclass."""
        from tkinter import messagebox
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the subclass '{subclass.name}'?\n\nThis cannot be undone."):
            # Remove subclass from parent class
            parent_class.subclasses = [s for s in parent_class.subclasses if s.name != subclass.name]
            self.class_manager.add_class(parent_class)  # Save the updated class
            
            # Reload and refresh display
            self.current_class = self.class_manager.get_class(parent_class.name)
            if self.current_class:
                self._display_class(self.current_class)
    
    def _display_class(self, class_def: CharacterClassDefinition):
        """Display the class information with feature table."""
        # Mark as loading
        self._class_loaded = False
        
        # Clear content and subclass tracking
        for widget in self.content.winfo_children():
            widget.destroy()
        self._subclass_cards.clear()
        
        # Header with class name and "Class Details"
        header_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            header_frame, text=class_def.name,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        ).pack(side="left")
        
        ctk.CTkLabel(
            header_frame, text="Class Details",
            font=ctk.CTkFont(size=16),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(side="left", padx=15)
        
        if class_def.source:
            ctk.CTkLabel(
                header_frame, text=f"Source: {class_def.source}",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(side="right")
        
        # Core Class Traits section
        self._create_core_traits_section(class_def)
        
        # Description paragraphs with dynamic resizing
        if class_def.description:
            from ui.rich_text_utils import DynamicText
            desc_frame = ctk.CTkFrame(self.content, fg_color="transparent")
            desc_frame.pack(fill="x", expand=True, pady=(0, 20))
            
            dt = DynamicText(
                desc_frame, self.theme,
                bg_color='bg_primary'  # Use theme color key
            )
            dt.set_text(class_def.description)
            dt.pack(fill="x", expand=True)
        
        # Feature table header
        table_header = ctk.CTkFrame(self.content, fg_color="transparent")
        table_header.pack(fill="x", pady=(10, 10))
        
        ctk.CTkLabel(
            table_header, text=f"{class_def.name} Features",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")
        
        # Create the feature table
        self._create_feature_table(class_def)
        
        # Detailed Class Features section (written out)
        self._create_detailed_features_section(class_def)
        
        # Subclasses section (always show so user can add subclasses)
        self._create_subclasses_section(class_def)
        
        # Mark as fully loaded (for pending subclass selection)
        self._class_loaded = True
    
    def _create_core_traits_section(self, class_def: CharacterClassDefinition):
        """Create the Core Class Traits table like in the PHB."""
        traits_frame = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        traits_frame.pack(fill="x", pady=(0, 15))
        
        # Header
        header = ctk.CTkFrame(traits_frame, fg_color=self.theme.get_current_color('accent_primary'), corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(
            header, text=f"Core {class_def.name} Traits",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white"
        ).pack(anchor="w", padx=10, pady=6)
        
        # Traits table
        traits_content = ctk.CTkFrame(traits_frame, fg_color="transparent")
        traits_content.pack(fill="x", padx=10, pady=10)
        
        # Define traits to show
        traits = [
            ("Primary Ability", self._get_primary_ability(class_def)),
            ("Hit Point Die", f"{class_def.hit_die} per {class_def.name} level"),
            ("Saving Throw Proficiencies", " and ".join(self._expand_ability_names(class_def.saving_throw_proficiencies))),
            ("Skill Proficiencies", self._format_skill_proficiencies(class_def)),
            ("Weapon Proficiencies", ", ".join(class_def.weapon_proficiencies) if class_def.weapon_proficiencies else "None"),
            ("Armor Training", ", ".join(class_def.armor_proficiencies) if class_def.armor_proficiencies else "None"),
            ("Starting Equipment", self._format_starting_equipment(class_def)),
        ]
        
        for i, (label, value) in enumerate(traits):
            row_color = self.theme.get_current_color('bg_tertiary') if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(traits_content, fg_color=row_color)
            row.pack(fill="x")
            
            # Label column
            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=150,
                anchor="w"
            ).pack(side="left", padx=5, pady=4)
            
            # Value column
            ctk.CTkLabel(
                row, text=value,
                font=ctk.CTkFont(size=11),
                anchor="w",
                wraplength=550,
                justify="left"
            ).pack(side="left", padx=5, pady=4, fill="x", expand=True)
    
    def _get_primary_ability(self, class_def: CharacterClassDefinition) -> str:
        """Get the primary ability for a class."""
        # Use stored primary_ability if available
        if class_def.primary_ability:
            return class_def.primary_ability
        
        # Fallback mapping for classes that don't have it set
        primary_abilities = {
            "Barbarian": "Strength",
            "Bard": "Charisma",
            "Cleric": "Wisdom",
            "Druid": "Wisdom",
            "Fighter": "Strength or Dexterity",
            "Monk": "Dexterity and Wisdom",
            "Paladin": "Strength and Charisma",
            "Ranger": "Dexterity and Wisdom",
            "Rogue": "Dexterity",
            "Sorcerer": "Charisma",
            "Warlock": "Charisma",
            "Wizard": "Intelligence",
            "Artificer": "Intelligence",
        }
        return primary_abilities.get(class_def.name, "Varies")
    
    def _expand_ability_names(self, abbreviations: List[str]) -> List[str]:
        """Expand ability abbreviations to full names."""
        mapping = {
            "STR": "Strength",
            "DEX": "Dexterity", 
            "CON": "Constitution",
            "INT": "Intelligence",
            "WIS": "Wisdom",
            "CHA": "Charisma"
        }
        return [mapping.get(abbr, abbr) for abbr in abbreviations]
    
    def _format_skill_proficiencies(self, class_def: CharacterClassDefinition) -> str:
        """Format skill proficiency choices."""
        if not class_def.skill_proficiency_options:
            return "None"
        
        count = class_def.skill_proficiency_choices or 2
        skills = ", ".join(class_def.skill_proficiency_options)
        return f"Choose {count}: {skills}"
    
    def _format_starting_equipment(self, class_def: CharacterClassDefinition) -> str:
        """Format starting equipment options."""
        # First check if there's a simple starting_equipment string (new format with full description)
        if class_def.starting_equipment:
            # Join multiple lines if present
            return "\n".join(class_def.starting_equipment)
        
        # Fall back to structured starting_equipment_options
        if not class_def.starting_equipment_options:
            if class_def.starting_gold_alternative:
                return f"Or {class_def.starting_gold_alternative}"
            return "See class description"
        
        options = []
        for opt in class_def.starting_equipment_options:
            items = ", ".join(opt.items)
            options.append(f"({opt.option_letter}) {items}")
        
        result = "Choose A or B: " + "; or ".join(options)
        return result
    
    def _create_feature_table(self, class_def: CharacterClassDefinition):
        """Create the class feature table like the PHB."""
        # Determine columns
        # Base columns: Level, Proficiency Bonus, Class Features
        # Plus class-specific columns from class_table_columns
        base_columns = ["Level", "Proficiency Bonus", "Class Features"]
        extra_columns = class_def.class_table_columns if class_def.class_table_columns else []
        all_columns = base_columns + extra_columns
        
        # Calculate column widths
        col_widths = {
            "Level": 50,
            "Proficiency Bonus": 90,
            "Class Features": 280,
        }
        for col in extra_columns:
            col_widths[col] = 90  # Standard width for extra columns
        
        # Standard table (no horizontal scrolling)
        table_frame = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        table_frame.pack(fill="x", pady=(0, 20))
        
        # Header row
        header_row = ctk.CTkFrame(table_frame, fg_color=self.theme.get_current_color('accent_primary'))
        header_row.pack(fill="x")
        
        for col in all_columns:
            width = col_widths.get(col, 90)
            label = ctk.CTkLabel(
                header_row, text=col,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="white",
                width=width
            )
            label.pack(side="left", padx=5, pady=8)
        
        # Data rows
        for level in range(1, 21):
            level_data = class_def.levels.get(level)
            
            # Alternate row colors
            row_color = self.theme.get_current_color('bg_tertiary') if level % 2 == 0 else self.theme.get_current_color('bg_secondary')
            
            row = ctk.CTkFrame(table_frame, fg_color=row_color)
            row.pack(fill="x")
            
            # Level
            ctk.CTkLabel(
                row, text=str(level),
                font=ctk.CTkFont(size=11),
                width=col_widths["Level"]
            ).pack(side="left", padx=5, pady=5)
            
            # Proficiency Bonus
            prof_bonus = level_data.proficiency_bonus if level_data else self._get_proficiency_bonus(level)
            ctk.CTkLabel(
                row, text=f"+{prof_bonus}",
                font=ctk.CTkFont(size=11),
                width=col_widths["Proficiency Bonus"]
            ).pack(side="left", padx=5, pady=5)
            
            # Class Features - show ALL features including ASI and Epic Boon
            features_text = ""
            if level_data and level_data.abilities:
                visible_abilities = []
                for ability in level_data.abilities:
                    if ability.is_subclass_feature:
                        # Show actual title at subclass selection level, "Subclass feature" for later
                        if level == class_def.subclass_level:
                            visible_abilities.append(ability.title)
                        else:
                            visible_abilities.append("Subclass feature")
                    else:
                        visible_abilities.append(ability.title)
                features_text = ", ".join(visible_abilities)
            
            features_label = ctk.CTkLabel(
                row, text=features_text if features_text else "—",
                font=ctk.CTkFont(size=11),
                width=col_widths["Class Features"],
                anchor="w",
                wraplength=270
            )
            features_label.pack(side="left", padx=5, pady=5)
            
            # Extra columns (class-specific and spell slots)
            # Map spell slot column names to slot levels
            spell_slot_map = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8, "9th": 9}
            
            for col in extra_columns:
                value = "—"
                if level_data:
                    # Check if this is a spell slot column
                    if col in spell_slot_map and level_data.spell_slots:
                        slot_level = spell_slot_map[col]
                        slot_count = level_data.spell_slots.get(slot_level, 0)
                        value = str(slot_count) if slot_count > 0 else "—"
                    elif level_data.class_specific:
                        value = level_data.class_specific.get(col, "—")
                
                ctk.CTkLabel(
                    row, text=value,
                    font=ctk.CTkFont(size=11),
                    width=col_widths.get(col, 90)
                ).pack(side="left", padx=5, pady=5)
    
    def _get_proficiency_bonus(self, level: int) -> int:
        """Get proficiency bonus for a given level."""
        if level >= 17:
            return 6
        elif level >= 13:
            return 5
        elif level >= 9:
            return 4
        elif level >= 5:
            return 3
        else:
            return 2
    
    def _create_detailed_features_section(self, class_def: CharacterClassDefinition):
        """Create the detailed class features section with full descriptions."""
        # Section header
        features_header = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5
        )
        features_header.pack(fill="x", pady=(20, 15))
        
        ctk.CTkLabel(
            features_header, text=f"{class_def.name} Class Features",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white"
        ).pack(anchor="w", padx=10, pady=8)
        
        # Intro text
        ctk.CTkLabel(
            self.content,
            text=f"As a {class_def.name}, you gain the following class features when you reach the specified {class_def.name} levels. These features are listed in the {class_def.name} Features table.",
            font=ctk.CTkFont(size=12),
            wraplength=750,
            justify="left"
        ).pack(anchor="w", pady=(0, 15))
        
        # Track which features we've already shown (by title + description hash)
        # Features like ASI with identical description should only appear once
        # Features like Improved Brutal Strike with different descriptions should appear each time
        features_shown = {}  # title -> (first_level, description_hash, additional_levels)
        
        # First pass: collect all features and find repeating ones
        for level in range(1, 21):
            level_data = class_def.levels.get(level)
            if not level_data or not level_data.abilities:
                continue
            
            for ability in level_data.abilities:
                if ability.is_subclass_feature:
                    continue
                
                desc_hash = hash(ability.description.strip())
                feature_key = (ability.title, desc_hash)
                
                if feature_key not in features_shown:
                    features_shown[feature_key] = (level, desc_hash, [])
                else:
                    # Same feature appears again - track additional level
                    features_shown[feature_key][2].append(level)
        
        # Second pass: render features
        rendered_features = set()
        for level in range(1, 21):
            level_data = class_def.levels.get(level)
            if not level_data or not level_data.abilities:
                continue
            
            for ability in level_data.abilities:
                # Show subclass selection feature at subclass_level (e.g., "Barbarian Subclass")
                # but skip "Subclass feature" placeholders at later levels
                if ability.is_subclass_feature:
                    if level == class_def.subclass_level:
                        # Show the subclass selection feature
                        self._create_feature_detail(level, ability)
                    # Skip subclass feature placeholders at other levels
                    continue
                
                # Create a key based on title and description content
                desc_hash = hash(ability.description.strip())
                feature_key = (ability.title, desc_hash)
                
                if feature_key in rendered_features:
                    # Skip - we already rendered this feature
                    continue
                
                rendered_features.add(feature_key)
                
                # Get additional levels for this feature
                additional_levels = features_shown.get(feature_key, (level, desc_hash, []))[2]
                self._create_feature_detail(level, ability, additional_levels)
    
    def _create_feature_detail(self, level: int, ability: ClassAbility, additional_levels: Optional[List] = None):
        """Create a detailed feature entry."""
        feature_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        feature_frame.pack(fill="x", pady=(0, 15))
        
        # Feature title with level - styled heading with background (fits text only)
        title_frame = ctk.CTkFrame(
            feature_frame,
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5
        )
        title_frame.pack(anchor="w")  # anchor="w" makes it only as wide as needed
        
        # Build title text - include additional levels if this feature repeats
        title_text = f"Level {level}: {ability.title}"
        if additional_levels:
            all_levels = [level] + additional_levels
            level_str = ", ".join(str(l) for l in all_levels)
            title_text = f"Levels {level_str}: {ability.title}"
        
        ctk.CTkLabel(
            title_frame,
            text=title_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white"
        ).pack(anchor="w", padx=10, pady=6)
        
        # Show description if present
        if ability.description.strip():
            # Feature description - parse markdown-style formatting
            desc_text = ability.description.strip()
            
            # Create a text display for the description
            desc_frame = ctk.CTkFrame(feature_frame, fg_color="transparent")
            desc_frame.pack(fill="x", pady=(8, 0), padx=5)
            
            # Parse and display description with basic formatting
            self._render_formatted_description(desc_frame, desc_text)
        
        # Render any tables associated with this ability
        if hasattr(ability, 'tables') and ability.tables:
            for table_data in ability.tables:
                self._render_feature_table(feature_frame, table_data)
    
    def _render_feature_table(self, parent, table_data: dict):
        """Render a table within a feature description."""
        title = table_data.get("title", "")
        columns = table_data.get("columns", [])
        rows = table_data.get("rows", [])
        
        if not columns or not rows:
            return
        
        # Check if this is a spell list table (has "Spells" column)
        is_spell_table = any("Spells" in col or "Spell" in col for col in columns)
        spell_col_index = next((i for i, col in enumerate(columns) if "Spells" in col or "Spell" in col), -1)
        
        self._render_compact_table(parent, columns, rows, title, is_spell_table, spell_col_index)
    
    def _render_formatted_description(self, parent, text: str):
        """Render description text with basic markdown formatting.
        
        Bold headers like *Text.* are rendered inline with following text.
        """
        import re
        
        # Split by double newlines to get paragraphs
        paragraphs = text.split('\n\n')
        
        for para_idx, paragraph in enumerate(paragraphs):
            lines = paragraph.strip().split('\n')
            
            # Combine lines that should flow together
            combined_text = ' '.join(line.strip() for line in lines if line.strip())
            
            if not combined_text:
                continue
            
            # Check for bullet points
            if combined_text.startswith('•') or combined_text.startswith('-'):
                bullet_text = combined_text.lstrip('•- ')
                self._render_line_with_formatting(parent, f"  • {bullet_text}")
                continue
            
            # Add small spacing between paragraphs (but not before first)
            pady = (6, 2) if para_idx > 0 else (2, 2)
            
            # Render the paragraph with inline formatting
            self._render_line_with_formatting(parent, combined_text, pady=pady)
    
    def _render_line_with_formatting(self, parent, line: str, pady=(2, 0)):
        """Render a single line/paragraph that may contain *bold* formatting.
        
        Handles inline bold text like *Header.* followed by regular text,
        all rendered in a single flowing paragraph with dynamic resizing.
        """
        from ui.rich_text_utils import DynamicText
        
        # Create DynamicText for flowing, resizable text with bold support
        dt = DynamicText(
            parent, self.theme,
            bg_color='bg_primary'  # Use theme color key
        )
        # Use single asterisk pattern for bold (class features use *text* format)
        dt.set_text(line, bold_pattern=r'\*([^*]+)\*')
        dt.pack(fill="x", expand=True, pady=pady)
    
    def _create_subclasses_section(self, class_def: CharacterClassDefinition):
        """Create the subclasses section."""
        # Section header with Add Subclass button
        header_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        header_frame.pack(fill="x", pady=(20, 10))
        
        ctk.CTkLabel(
            header_frame, text=f"{class_def.subclass_name or 'Subclasses'}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")
        
        # Add Subclass button
        ctk.CTkButton(
            header_frame, text="+ Add Subclass",
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            height=28, width=120,
            command=lambda: self._open_subclass_editor(class_def)
        ).pack(side="right")
        
        desc_text = f"At level {class_def.subclass_level}, you choose a subclass that grants you features at specific levels."
        ctk.CTkLabel(
            self.content, text=desc_text,
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(anchor="w", pady=(0, 15))
        
        # Group Circle of the Land variants together
        land_variants = []
        other_subclasses = []
        for subclass in class_def.subclasses:
            if subclass.name.startswith("Circle of the Land"):
                land_variants.append(subclass)
            else:
                other_subclasses.append(subclass)
        
        # Create Circle of the Land as a single collapsible with variants
        if land_variants:
            self._create_land_circle_subclass(land_variants)
        
        # Create a collapsible section for each other subclass
        for subclass in other_subclasses:
            self._create_collapsible_subclass(subclass)
    
    def _create_land_circle_subclass(self, variants):
        """Create a collapsible Circle of the Land card showing variants."""
        # Use first variant as template for common info
        template = variants[0]
        
        # Main container
        card = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        card.pack(fill="x", pady=5)
        
        # Header (clickable to expand/collapse)
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=10)
        
        # Expand/collapse indicator and name
        expand_indicator = ctk.CTkLabel(
            header_frame, text="▶",
            font=ctk.CTkFont(size=12),
            width=20
        )
        expand_indicator.pack(side="left")
        
        # Extract land types from variant names
        land_types = [v.name.replace("Circle of the Land (", "").replace(")", "") for v in variants]
        variant_text = f"Circle of the Land ({', '.join(land_types)})"
        
        name_label = ctk.CTkLabel(
            header_frame, text=variant_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        )
        name_label.pack(side="left", padx=5)
        
        if template.source:
            ctk.CTkLabel(
                header_frame, text=f"Source: {template.source}",
                font=ctk.CTkFont(size=10),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(side="right")
        
        # Lazy loading: content_frame and content created on first expand
        expanded_state = {"is_expanded": False, "content_created": False, "content_frame": None}
        
        def toggle_expand():
            if expanded_state["is_expanded"]:
                # Collapse
                if expanded_state["content_frame"]:
                    expanded_state["content_frame"].pack_forget()
                expand_indicator.configure(text="▶")
                expanded_state["is_expanded"] = False
            else:
                # Expand - create content on first expand
                if not expanded_state["content_created"]:
                    content_frame = ctk.CTkFrame(card, fg_color="transparent")
                    expanded_state["content_frame"] = content_frame
                    self._populate_land_circle_content(content_frame, variants, template)
                    expanded_state["content_created"] = True
                expanded_state["content_frame"].pack(fill="x", padx=15, pady=(0, 15))
                expand_indicator.configure(text="▼")
                expanded_state["is_expanded"] = True
        
        # Make header clickable
        header_frame.bind("<Button-1>", lambda e: toggle_expand())
        expand_indicator.bind("<Button-1>", lambda e: toggle_expand())
        name_label.bind("<Button-1>", lambda e: toggle_expand())
        
        # Register all Circle of the Land variants for navigation
        for variant in variants:
            self._subclass_cards[variant.name] = (card, toggle_expand, expanded_state)
    
    def _populate_land_circle_content(self, content_frame, variants, template):
        """Populate Circle of the Land content frame."""
        # Shared description for Circle of the Land
        shared_description = "Druids of the Circle of the Land are mystics and sages who safeguard ancient knowledge and rites through a vast oral tradition. These Druids meet within sacred circles of trees or standing stones to whisper primal secrets in Druidic. The circle's wisest members preside as the chief priests of communities that hold to the Old Faith and serve as advisors to the rulers of those folk.\n\nAs a member of this circle, your magic is influenced by the land where you were initiated into the circle's mysterious rites. Choose your land type from the options below."
        ctk.CTkLabel(
            content_frame, text=shared_description,
            font=ctk.CTkFont(size=11),
            wraplength=700,
            justify="left",
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(anchor="w", pady=(0, 15))
        
        # Show spell lists for each land type FIRST
        spell_section = ctk.CTkFrame(content_frame, fg_color="transparent")
        spell_section.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            spell_section, text="Circle Spells by Land Type",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        ).pack(anchor="w", pady=(0, 10))
        
        # Create table showing spells for each land type
        for variant in variants:
            land_type = variant.name.replace("Circle of the Land (", "").replace(")", "")
            if variant.subclass_spells:
                land_frame = ctk.CTkFrame(spell_section, fg_color="transparent")
                land_frame.pack(fill="x", pady=3)
                
                ctk.CTkLabel(
                    land_frame, text=f"{land_type}:",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    width=90,
                    anchor="w"
                ).pack(side="left")
                
                spell_names = [s.spell_name for s in variant.subclass_spells]
                ctk.CTkLabel(
                    land_frame, text=", ".join(spell_names),
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.get_current_color('text_secondary'),
                    wraplength=580,
                    justify="left"
                ).pack(side="left", padx=5)
        
        # Show features - but handle Nature's Ward specially to show all resistances
        for feature in template.features:
            if feature.title == "Nature's Ward":
                # Create custom Nature's Ward showing all variant resistances
                self._create_land_natures_ward_feature(content_frame, variants)
            else:
                self._create_subclass_feature_detail(content_frame, feature)
    
    def _create_land_natures_ward_feature(self, parent, variants):
        """Create Nature's Ward feature showing all land type resistances."""
        feature_frame = ctk.CTkFrame(parent, fg_color="transparent")
        feature_frame.pack(fill="x", pady=(0, 12))
        
        # Feature title with level
        title_frame = ctk.CTkFrame(
            feature_frame,
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5
        )
        title_frame.pack(anchor="w")
        
        ctk.CTkLabel(
            title_frame,
            text="Level 10: Nature's Ward",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white"
        ).pack(anchor="w", padx=8, pady=4)
        
        # Common description
        desc_frame = ctk.CTkFrame(feature_frame, fg_color="transparent")
        desc_frame.pack(fill="x", pady=(6, 0), padx=5)
        
        common_desc = "You are immune to the Poisoned condition, and you have Resistance to a damage type based on your land choice:"
        ctk.CTkLabel(
            desc_frame, text=common_desc,
            font=ctk.CTkFont(size=11),
            wraplength=680,
            justify="left",
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(anchor="w", pady=(0, 8))
        
        # Show each land type's resistance
        resistance_map = {
            "Arid": "Fire",
            "Polar": "Cold", 
            "Temperate": "Lightning",
            "Tropical": "Poison"
        }
        
        for variant in variants:
            land_type = variant.name.replace("Circle of the Land (", "").replace(")", "")
            resistance = resistance_map.get(land_type, "Unknown")
            
            resist_frame = ctk.CTkFrame(desc_frame, fg_color="transparent")
            resist_frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(
                resist_frame, text=f"• {land_type}:",
                font=ctk.CTkFont(size=11, weight="bold"),
                width=100,
                anchor="w"
            ).pack(side="left")
            
            ctk.CTkLabel(
                resist_frame, text=f"Resistance to {resistance} damage",
                font=ctk.CTkFont(size=11),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(side="left")
    
    def _create_collapsible_subclass(self, subclass):
        """Create a collapsible subclass card with full feature details."""
        # Main container
        card = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        card.pack(fill="x", pady=5)
        
        # Header (clickable to expand/collapse)
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=10)
        
        # Expand/collapse indicator and name
        expand_indicator = ctk.CTkLabel(
            header_frame, text="▶",
            font=ctk.CTkFont(size=12),
            width=20
        )
        expand_indicator.pack(side="left")
        
        name_label = ctk.CTkLabel(
            header_frame, text=subclass.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        )
        name_label.pack(side="left", padx=5)
        
        # Edit and Delete buttons for custom subclasses only
        if self.current_class and subclass.is_custom:
            ctk.CTkButton(
                header_frame, text="Delete",
                fg_color=self.theme.get_current_color('button_danger'),
                hover_color=self.theme.get_current_color('button_danger_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                height=24, width=60,
                command=lambda s=subclass, c=self.current_class: self._delete_subclass(c, s)
            ).pack(side="right", padx=(5, 0))
            
            ctk.CTkButton(
                header_frame, text="Edit",
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                height=24, width=60,
                command=lambda s=subclass, c=self.current_class: self._open_subclass_editor(c, s)
            ).pack(side="right", padx=(10, 0))
        
        if subclass.source:
            ctk.CTkLabel(
                header_frame, text=f"Source: {subclass.source}",
                font=ctk.CTkFont(size=10),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(side="right")
        
        # Lazy loading: content_frame and content created on first expand
        expanded_state = {"is_expanded": False, "content_created": False, "content_frame": None}
        
        def toggle_expand():
            if expanded_state["is_expanded"]:
                # Collapse
                if expanded_state["content_frame"]:
                    expanded_state["content_frame"].pack_forget()
                expand_indicator.configure(text="▶")
                expanded_state["is_expanded"] = False
            else:
                # Expand - create content on first expand
                if not expanded_state["content_created"]:
                    content_frame = ctk.CTkFrame(card, fg_color="transparent")
                    expanded_state["content_frame"] = content_frame
                    self._populate_subclass_content(content_frame, subclass)
                    expanded_state["content_created"] = True
                expanded_state["content_frame"].pack(fill="x", padx=15, pady=(0, 15))
                expand_indicator.configure(text="▼")
                expanded_state["is_expanded"] = True
        
        # Make header clickable
        header_frame.bind("<Button-1>", lambda e: toggle_expand())
        expand_indicator.bind("<Button-1>", lambda e: toggle_expand())
        name_label.bind("<Button-1>", lambda e: toggle_expand())
        
        # Register the subclass card for navigation
        self._subclass_cards[subclass.name] = (card, toggle_expand, expanded_state)
    
    def _populate_subclass_content(self, content_frame, subclass):
        """Populate a subclass content frame with description and features."""
        # Description with dynamic resizing
        if subclass.description:
            from ui.rich_text_utils import DynamicText
            dt = DynamicText(
                content_frame, self.theme,
                font_size=11,
                bg_color='bg_primary'
            )
            dt.set_text(subclass.description)
            dt.pack(fill="x", expand=True, pady=(0, 15))
        
        # Features with full details
        for feature in subclass.features:
            self._create_subclass_feature_detail(content_frame, feature)
    
    def _create_subclass_spell_list(self, parent, subclass):
        """Create a spell list section for subclasses that grant spells."""
        # Spell list section
        spell_section = ctk.CTkFrame(parent, fg_color="transparent")
        spell_section.pack(fill="x", pady=(0, 15))
        
        # Determine title based on parent class
        title = "Expanded Spells"
        if subclass.parent_class == "Cleric":
            title = "Domain Spells"
        elif subclass.parent_class == "Paladin":
            title = "Oath Spells"
        elif subclass.parent_class == "Warlock":
            title = "Expanded Spells"
        
        ctk.CTkLabel(
            spell_section, text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        ).pack(anchor="w", pady=(0, 8))
        
        # Group spells by level gained
        spells_by_level = {}
        for spell in subclass.subclass_spells:
            level = spell.level_gained
            if level not in spells_by_level:
                spells_by_level[level] = []
            spells_by_level[level].append(spell.spell_name)
        
        # Create a table-like structure with headers
        table_frame = ctk.CTkFrame(
            spell_section,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=6
        )
        table_frame.pack(fill="x", pady=3)
        
        # Header row
        header_frame = ctk.CTkFrame(
            table_frame,
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=0
        )
        header_frame.pack(fill="x")
        
        # Determine header text based on class
        level_header = "Paladin Level" if subclass.parent_class == "Paladin" else "Cleric Level" if subclass.parent_class == "Cleric" else "Level"
        
        ctk.CTkLabel(
            header_frame, text=level_header,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
            width=100,
            anchor="w"
        ).pack(side="left", padx=6, pady=3)
        
        ctk.CTkLabel(
            header_frame, text="Spells",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
            anchor="w"
        ).pack(side="left", padx=6, pady=3)
        
        # Data rows for each level
        for row_idx, level in enumerate(sorted(spells_by_level.keys())):
            row_bg = "transparent" if row_idx % 2 == 0 else self.theme.get_current_color('bg_tertiary')
            
            row_frame = ctk.CTkFrame(table_frame, fg_color=row_bg)
            row_frame.pack(fill="x")
            
            # Level column
            ctk.CTkLabel(
                row_frame, text=str(level),
                font=ctk.CTkFont(size=11),
                width=100,
                anchor="w"
            ).pack(side="left", padx=6, pady=2)
            
            # Spells column - use clickable spell labels
            spells_container = ctk.CTkFrame(row_frame, fg_color="transparent")
            spells_container.pack(side="left", padx=6, pady=2, fill="x", expand=True)
            
            spell_names = spells_by_level[level]
            for idx, spell_name in enumerate(spell_names):
                # Create clickable label for each spell
                display_text = spell_name + ("," if idx < len(spell_names) - 1 else "")
                spell_label = ctk.CTkLabel(
                    spells_container,
                    text=display_text,
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.get_current_color('accent_primary'),
                    cursor="hand2"
                )
                spell_label.pack(side="left", padx=(0, 3))
                
                # Bind click to show spell popup
                clean_name = spell_name.strip()
                def make_click_handler(name):
                    return lambda e: self._show_spell_popup(name)
                spell_label.bind("<Button-1>", make_click_handler(clean_name))
                
                # Hover effect
                def make_enter_handler(lbl):
                    return lambda e: lbl.configure(font=ctk.CTkFont(size=11, underline=True))
                def make_leave_handler(lbl):
                    return lambda e: lbl.configure(font=ctk.CTkFont(size=11))
                spell_label.bind("<Enter>", make_enter_handler(spell_label))
                spell_label.bind("<Leave>", make_leave_handler(spell_label))
    
    def _create_subclass_feature_detail(self, parent, feature):
        """Create a detailed subclass feature entry."""
        feature_frame = ctk.CTkFrame(parent, fg_color="transparent")
        feature_frame.pack(fill="x", pady=(0, 12))
        
        # Feature title with level - styled heading with background
        title_frame = ctk.CTkFrame(
            feature_frame,
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5
        )
        title_frame.pack(anchor="w")
        
        ctk.CTkLabel(
            title_frame,
            text=f"Level {feature.level}: {feature.title}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white"
        ).pack(anchor="w", padx=8, pady=4)
        
        # Feature description
        if feature.description.strip():
            desc_frame = ctk.CTkFrame(feature_frame, fg_color="transparent")
            desc_frame.pack(fill="x", pady=(6, 0), padx=5)
            self._render_formatted_description(desc_frame, feature.description.strip())
        
        # Render any tables associated with this feature
        if hasattr(feature, 'tables') and feature.tables:
            for table_data in feature.tables:
                self._render_subclass_feature_table(feature_frame, table_data)
    
    def _calculate_column_widths(self, columns: list, rows: list) -> list:
        """Calculate optimal column widths based on content."""
        num_cols = len(columns)
        widths = []
        
        for i in range(num_cols):
            # Get max content length in this column
            header_len = len(columns[i]) if columns[i] else 0
            max_data_len = max((len(str(row[i])) if i < len(row) else 0 for row in rows), default=0)
            max_len = max(header_len, max_data_len)
            
            # Calculate width based on content (roughly 7px per character + padding)
            # With minimums and maximums for readability
            if columns[i].lower() in ("level", "lvl", "slot", "#"):
                widths.append(50)  # Narrow for level columns
            elif "spell" in columns[i].lower():
                widths.append(min(280, max(120, max_len * 6)))  # Flexible for spell names
            elif max_len <= 5:
                widths.append(50)  # Very short content
            elif max_len <= 15:
                widths.append(80)  # Short content
            elif max_len <= 30:
                widths.append(140)  # Medium content
            else:
                widths.append(min(220, max_len * 5))  # Longer content with cap
        
        return widths
    
    def _render_compact_table(self, parent, columns: list, rows: list, 
                              title: str = "", is_spell_table: bool = False,
                              spell_col_index: int = -1):
        """Render a compact, reusable table."""
        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.pack(fill="x", pady=(8, 5), padx=5)
        
        # Table title if present
        if title:
            ctk.CTkLabel(
                table_frame,
                text=title,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.theme.get_current_color('accent_primary')
            ).pack(anchor="w", pady=(0, 4))
        
        if not columns or not rows:
            return
        
        # Calculate optimal widths
        col_widths = self._calculate_column_widths(columns, rows)
        
        # Determine if this is a simple list (no headers)
        is_simple_list = all(c == "" for c in columns)
        
        if is_simple_list:
            self._render_simple_list(table_frame, rows)
        else:
            self._render_full_table(table_frame, columns, rows, col_widths, 
                                   is_spell_table, spell_col_index)
    
    def _render_simple_list(self, parent, rows: list):
        """Render a simple multi-column list without headers."""
        list_frame = ctk.CTkFrame(
            parent, 
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=6
        )
        list_frame.pack(fill="x", pady=3)
        
        for row in rows:
            row_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=8, pady=1)
            
            for cell in row:
                if cell:  # Only render non-empty cells
                    ctk.CTkLabel(
                        row_frame,
                        text=cell,
                        font=ctk.CTkFont(size=10),
                        width=140,
                        anchor="w"
                    ).pack(side="left", padx=3)
    
    def _render_full_table(self, parent, columns: list, rows: list, 
                          col_widths: list, is_spell_table: bool, spell_col_index: int):
        """Render a full table with headers and data rows."""
        table_container = ctk.CTkFrame(
            parent,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=6
        )
        table_container.pack(fill="x", pady=3)
        
        # Configure grid columns for proper alignment
        for i in range(len(columns)):
            table_container.grid_columnconfigure(i, minsize=col_widths[i], weight=0)
        
        # Header row using grid
        for i, col in enumerate(columns):
            header_cell = ctk.CTkFrame(
                table_container,
                fg_color=self.theme.get_current_color('accent_primary'),
                corner_radius=0
            )
            header_cell.grid(row=0, column=i, sticky="nsew")
            ctk.CTkLabel(
                header_cell,
                text=col,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="white",
                anchor="w"
            ).pack(side="left", padx=6, pady=3, fill="x")
        
        # Data rows using grid for proper column alignment
        for row_idx, row in enumerate(rows):
            row_bg = "transparent" if row_idx % 2 == 0 else self.theme.get_current_color('bg_tertiary')
            
            for i, cell in enumerate(row):
                width = col_widths[i] if i < len(col_widths) else 100
                
                cell_frame = ctk.CTkFrame(table_container, fg_color=row_bg)
                cell_frame.grid(row=row_idx + 1, column=i, sticky="nsew")
                
                # Check if this is a spell column - make spells clickable
                if is_spell_table and i == spell_col_index:
                    self._render_clickable_spells(cell_frame, cell, width, font_size=11)
                else:
                    ctk.CTkLabel(
                        cell_frame,
                        text=cell,
                        font=ctk.CTkFont(size=11),
                        anchor="w",
                        wraplength=width - 10 if width > 50 else 0,
                        justify="left"
                    ).pack(side="left", padx=6, pady=2)
    
    def _render_subclass_feature_table(self, parent, table_data: dict):
        """Render a table within a subclass feature description."""
        title = table_data.get("title", "")
        # Support both 'headers' and 'columns' keys for backwards compatibility
        columns = table_data.get("headers", table_data.get("columns", []))
        rows = table_data.get("rows", [])
        
        if not columns or not rows:
            return
        
        # Check if this is a spell list table (has "Spells" column)
        is_spell_table = any("Spells" in col or "Spell" in col for col in columns)
        spell_col_index = next((i for i, col in enumerate(columns) if "Spells" in col or "Spell" in col), -1)
        
        self._render_compact_table(parent, columns, rows, title, is_spell_table, spell_col_index)
    
    def _render_clickable_spells(self, parent, cell_text: str, width: int, font_size: int = 11):
        """Render a cell with clickable spell names."""
        # Container for spell links - allow height to grow with content
        spells_frame = ctk.CTkFrame(parent, fg_color="transparent")
        spells_frame.pack(side="left", padx=6, pady=2, anchor="w")
        
        # Parse spell names (comma-separated)
        spell_names = [s.strip() for s in cell_text.split(',')]
        
        # Inner frame for wrapping - use grid for better flow
        inner_frame = ctk.CTkFrame(spells_frame, fg_color="transparent")
        inner_frame.pack(fill="both", anchor="w")
        
        for idx, spell_name in enumerate(spell_names):
            if not spell_name:
                continue
            
            # Create clickable label for each spell
            display_text = spell_name + ("," if idx < len(spell_names) - 1 else "")
            spell_label = ctk.CTkLabel(
                inner_frame,
                text=display_text,
                font=ctk.CTkFont(size=font_size),
                text_color=self.theme.get_current_color('accent_primary'),
                cursor="hand2"
            )
            spell_label.pack(side="left", padx=(0, 3))
            
            # Store the spell name for the click handler
            clean_name = spell_name.strip()
            
            # Bind click to show spell popup - use a proper closure
            def make_click_handler(name):
                return lambda e: self._show_spell_popup(name)
            spell_label.bind("<Button-1>", make_click_handler(clean_name))
            
            # Hover effect - use proper closures
            def make_enter_handler(lbl, fs):
                return lambda e: lbl.configure(font=ctk.CTkFont(size=fs, underline=True))
            def make_leave_handler(lbl, fs):
                return lambda e: lbl.configure(font=ctk.CTkFont(size=fs))
            spell_label.bind("<Enter>", make_enter_handler(spell_label, font_size))
            spell_label.bind("<Leave>", make_leave_handler(spell_label, font_size))
    
    def _show_spell_popup(self, spell_name: str):
        """Show a popup with spell details."""
        spell_manager = get_spell_manager()
        spell = spell_manager.get_spell(spell_name)
        
        if spell:
            from ui.spell_detail import SpellPopupDialog
            popup = SpellPopupDialog(self, spell)
            popup.focus()
    
    def _show_feature_popup(self, feature):
        """Show a popup with feature details."""
        popup = FeatureDetailPopup(self, feature.title, feature.description)
        popup.focus()


class FeatureDetailPopup(ctk.CTkToplevel):
    """Popup dialog showing feature details."""
    
    def __init__(self, parent, title: str, description: str):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        
        self.title(title)
        self.geometry("500x400")
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 400) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_content(title, description)
    
    def _create_content(self, title: str, description: str):
        """Create the popup content."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        ctk.CTkLabel(
            container, text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        ).pack(anchor="w", pady=(0, 15))
        
        # Description in scrollable text area
        text_frame = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        text_frame.pack(fill="both", expand=True)
        
        text_box = ctk.CTkTextbox(
            text_frame,
            font=ctk.CTkFont(size=12),
            wrap="word",
            fg_color="transparent",
            text_color=self.theme.get_current_color('text_primary')
        )
        text_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Insert text and disable editing
        text_box.insert("1.0", description)
        text_box.configure(state="disabled")
        
        # Close button
        ctk.CTkButton(
            container, text="Close",
            width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(pady=(15, 0))
