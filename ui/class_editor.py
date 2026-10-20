"""
Class and Subclass Editor Dialogs for D&D Spellbook Application.
Allows users to create and edit custom classes and subclasses.
"""

from ui.window_utils import add_cancel_save
import customtkinter as ctk
from typography import ui_font
from tkinter import messagebox
from typing import Optional, List, Dict, Callable
from theme import get_theme_manager
from character_class import (
    get_class_manager, CharacterClassDefinition, ClassLevel, ClassAbility, ASI_FEATURE, EPIC_BOON_FEATURE,
    SubclassDefinition, SubclassFeature, SubclassSpell, TrackableFeature
)
from ui.editor_host import DialogWindow, EmbeddedWindow



def default_subclass_levels(subclass_level: int) -> List[int]:
    """The levels a class usually gives subclass features at, for a subclass chosen at ``subclass_level``
    (3 -> 3, 6, 10, 14, as most classes do)."""
    first = max(1, min(int(subclass_level or 3), 20))
    return [first] + [lvl for lvl in (6, 10, 14) if lvl >= first + 2]



def subclass_feature_levels(parent_class) -> List[int]:
    """The levels a class gives its subclass features at: the levels that carry a subclass placeholder
    ("Fighter Subclass feature"); a class without any falls back on the usual pattern for its subclass level."""
    levels = sorted(lvl for lvl, level_obj in parent_class.levels.items()
                    if any(a.is_subclass_feature for a in level_obj.abilities))
    return levels or default_subclass_levels(getattr(parent_class, "subclass_level", 3))


def standard_features(level: int) -> List[ClassAbility]:
    """What nearly every class gets at a level (a new class starts with these filled in; delete what does not fit)."""
    if level in (4, 8, 12, 16):
        return [ClassAbility(title=ASI_FEATURE[0], description=ASI_FEATURE[1])]
    if level == 19:
        return [ClassAbility(title=EPIC_BOON_FEATURE[0], description=EPIC_BOON_FEATURE[1])]
    return []


# Spell slot progressions
FULL_CASTER_SLOTS = {
    1: {"1": 2},
    2: {"1": 3},
    3: {"1": 4, "2": 2},
    4: {"1": 4, "2": 3},
    5: {"1": 4, "2": 3, "3": 2},
    6: {"1": 4, "2": 3, "3": 3},
    7: {"1": 4, "2": 3, "3": 3, "4": 1},
    8: {"1": 4, "2": 3, "3": 3, "4": 2},
    9: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    10: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
    11: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
    12: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
    13: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
    14: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
    15: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
    16: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
    17: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1, "9": 1},
    18: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 1, "7": 1, "8": 1, "9": 1},
    19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 1, "8": 1, "9": 1},
    20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 3, "6": 2, "7": 2, "8": 1, "9": 1},
}

HALF_CASTER_SLOTS = {
    1: {},
    2: {"1": 2},
    3: {"1": 3},
    4: {"1": 3},
    5: {"1": 4, "2": 2},
    6: {"1": 4, "2": 2},
    7: {"1": 4, "2": 3},
    8: {"1": 4, "2": 3},
    9: {"1": 4, "2": 3, "3": 2},
    10: {"1": 4, "2": 3, "3": 2},
    11: {"1": 4, "2": 3, "3": 3},
    12: {"1": 4, "2": 3, "3": 3},
    13: {"1": 4, "2": 3, "3": 3, "4": 1},
    14: {"1": 4, "2": 3, "3": 3, "4": 1},
    15: {"1": 4, "2": 3, "3": 3, "4": 2},
    16: {"1": 4, "2": 3, "3": 3, "4": 2},
    17: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    18: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
    20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
}


class _FeatureDialogBase(ctk.CTkToplevel):
    """What the class editor's feature dialogs share: a modal window, the title / description / roll-effect fields
    and the two-field check on save. A subclass sets ``theme`` and ``result`` and then calls ``_open``."""

    def _open(self, parent, title: str, size: tuple, min_size: tuple, feature=None):
        self.title(title)
        self.geometry(f"{size[0]}x{size[1]}")
        self.minsize(*min_size)
        self.resizable(True, True)

        self.transient(parent)
        self.grab_set()

        self._create_widgets()

        if feature:
            self._populate_from_feature(feature)

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - size[0]) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - size[1]) // 2
        self.geometry(f"+{x}+{y}")

    def _add_title_entry(self, container, placeholder: str):
        ctk.CTkLabel(container, text="Feature Title *", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.title_entry = ctk.CTkEntry(container, height=35, placeholder_text=placeholder)
        self.title_entry.pack(fill="x", pady=(0, 15))

    def _add_description_editor(self, container):
        """The description box with its rich-text toolbar."""
        from ui.rich_text_utils import RichTextEditor

        ctk.CTkLabel(container, text="Description *", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))

        self.description_text = ctk.CTkTextbox(container, height=180, font=ui_font("body"))
        self._rich_editor = RichTextEditor(self, self.description_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(container)
        toolbar.pack(fill="x", pady=(0, 5))

        self.description_text.pack(fill="both", expand=True, pady=(0, 15))

    def _add_roll_effects_editor(self, container):
        from ui.roll_effects_editor import RollEffectsEditor
        self.roll_editor = RollEffectsEditor(container)
        self.roll_editor.pack(fill="x", pady=(0, 15))

    def _add_buttons(self, container, pady=0):
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=pady)
        add_cancel_save(btn_frame, self.theme, self.destroy, self._on_save)

    def _title_and_description(self):
        """The trimmed ``(title, description)``, or None (after a warning) when either is missing."""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Warning", "Please enter a feature title.", parent=self)
            return None

        description = self.description_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showwarning("Warning", "Please enter a description.", parent=self)
            return None
        return title, description


class FeatureEditorDialog(_FeatureDialogBase):
    """Dialog for adding/editing a single feature at a level."""

    def __init__(self, parent, title: str = "Add Feature", feature: Optional[ClassAbility] = None):
        super().__init__(parent)

        self.theme = get_theme_manager()
        self.result: Optional[ClassAbility] = None
        self._feature = feature

        self._open(parent, title, (600, 550), (500, 450), feature)

    def _create_widgets(self):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        self._add_title_entry(container, "e.g., Extra Attack")
        self._add_description_editor(container)

        # Is Subclass Feature checkbox
        self.is_subclass_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            container, text="Is Subclass Feature (placeholder for subclass abilities)",
            variable=self.is_subclass_var, font=ui_font("body")
        ).pack(fill="x", pady=(0, 15))

        self._add_roll_effects_editor(container)
        self._add_buttons(container)

    def _populate_from_feature(self, feature: ClassAbility):
        """Populate from existing feature."""
        self.title_entry.insert(0, feature.title)
        self.description_text.insert("1.0", feature.description)
        self.is_subclass_var.set(feature.is_subclass_feature)
        self.roll_editor.set(feature.roll_effects)
    
    def _on_save(self):
        """Save the feature."""
        fields = self._title_and_description()
        if not fields:
            return
        title, description = fields

        # Preserve tables and subclass_name from original feature if editing
        tables = self._feature.tables if self._feature else []
        subclass_name = self._feature.subclass_name if self._feature else ""
        
        self.result = ClassAbility(
            title=title,
            description=description,
            is_subclass_feature=self.is_subclass_var.get(),
            subclass_name=subclass_name,
            tables=tables,
            roll_effects=self.roll_editor.get()
        )
        self.destroy()


class TrackableFeatureEditorDialog(_FeatureDialogBase):
    """Dialog for adding/editing a trackable feature."""

    def __init__(self, parent, feature: Optional[TrackableFeature] = None):
        super().__init__(parent)

        self.theme = get_theme_manager()
        self.result: Optional[TrackableFeature] = None

        self._open(parent, "Edit Trackable Feature" if feature else "Add Trackable Feature", (500, 550), (450, 500),
                   feature)

    def _create_widgets(self):
        """Create dialog widgets."""
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        self._add_title_entry(scroll, "e.g., Rage")
        
        # Description
        ctk.CTkLabel(scroll, text="Description", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.desc_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="Brief description")
        self.desc_entry.pack(fill="x", pady=(0, 15))
        
        # Tracked Value Label
        ctk.CTkLabel(scroll, text="Tracked Value Label", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.tracked_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Uses, Dice, Points")
        self.tracked_entry.pack(fill="x", pady=(0, 15))
        
        # Max Uses
        uses_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        uses_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(uses_frame, text="Max Uses:", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.max_uses_entry = ctk.CTkEntry(uses_frame, width=80, height=35, placeholder_text="0")
        self.max_uses_entry.pack(side="left", padx=(10, 0))
        
        # Recharge
        recharge_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        recharge_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(recharge_frame, text="Recharge:", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.recharge_var = ctk.StringVar(value="long_rest")
        self.recharge_combo = ctk.CTkComboBox(
            recharge_frame, variable=self.recharge_var,
            values=["short_rest", "long_rest", "dawn", "never"],
            width=150
        )
        self.recharge_combo.pack(side="left", padx=(10, 0))
        
        # Level Scaling Note
        ctk.CTkLabel(
            scroll, text="Level scaling can be configured after saving.",
            font=ui_font("small"),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(fill="x", pady=(0, 15))
        
        self._add_buttons(scroll, pady=(20, 0))
    
    def _populate_from_feature(self, feature: TrackableFeature):
        """Populate from existing feature."""
        self.title_entry.insert(0, feature.title)
        self.desc_entry.insert(0, feature.description)
        self.tracked_entry.insert(0, feature.tracked_value)
        self.max_uses_entry.insert(0, str(feature.max_uses))
        self.recharge_var.set(feature.recharge)
    
    def _on_save(self):
        """Save the feature."""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Warning", "Please enter a feature title.", parent=self)
            return
        
        try:
            max_uses = int(self.max_uses_entry.get() or "0")
        except ValueError:
            messagebox.showwarning("Warning", "Max uses must be a number.", parent=self)
            return
        
        self.result = TrackableFeature(
            title=title,
            description=self.desc_entry.get().strip(),
            tracked_value=self.tracked_entry.get().strip() or "Uses",
            has_uses=max_uses > 0,
            max_uses=max_uses,
            current_uses=max_uses,
            recharge=self.recharge_var.get()
        )
        self.destroy()


class ClassEditorBody:
    """Dialog for creating or editing a character class. (the form; see ui/editor_host.py)"""
    
    # All D&D 5e Skills
    ALL_SKILLS = [
        "Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception",
        "History", "Insight", "Intimidation", "Investigation", "Medicine",
        "Nature", "Perception", "Performance", "Persuasion", "Religion",
        "Sleight of Hand", "Stealth", "Survival"
    ]
    
    def __init__(self, parent, class_def: Optional[CharacterClassDefinition] = None, on_save: Optional[Callable] = None):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[CharacterClassDefinition] = None
        self._editing = class_def is not None
        self._class_def = class_def
        self._on_save = on_save
        
        # Store level features
        self._level_data: Dict[int, Dict] = {}
        self._trackable_features: List[TrackableFeature] = []
        self._custom_columns: List[str] = []
        self._subclass_levels: set = set()  # Levels that have subclass features
        
        if class_def:
            # Copy existing data
            for lvl, level_obj in class_def.levels.items():
                self._level_data[lvl] = {
                    "features": list(level_obj.abilities),
                    "class_specific": dict(level_obj.class_specific)
                }
                # Check if this level has subclass features
                for ability in level_obj.abilities:
                    if ability.is_subclass_feature:
                        self._subclass_levels.add(lvl)
            self._trackable_features = list(class_def.trackable_features)
            self._custom_columns = list(class_def.class_table_columns)
        else:
            # Initialize the levels: the features every class gets are filled in, and the levels where a subclass
            # gives features are marked (they follow the Subclass Level on the Basic Info tab)
            for lvl in range(1, 21):
                self._level_data[lvl] = {"features": standard_features(lvl), "class_specific": {}}
            self._subclass_levels = set(default_subclass_levels(3))
        self._subclass_touched = bool(class_def)       # set once the user ticks or unticks a level by hand
        self._subclass_vars: Dict[int, ctk.BooleanVar] = {}
        self.level_sections = None
        
        self.title("Edit Class" if class_def else "Create New Class")
        self.geometry("900x750")
        self.minsize(800, 650)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # If editing, create all tabs upfront (needed for _populate_from_class)
        # If creating new, tabs are lazy-loaded for performance
        if class_def:
            self._ensure_all_tabs_created()
            self._populate_from_class(class_def)
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 900) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 750) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create all dialog widgets."""
        # Create tabview for organization
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(15, 0))
        
        # Create tabs (empty initially for lazy loading)
        self.tabview.add("Basic Info")
        self.tabview.add("Spellcasting")
        self.tabview.add("Level Features")
        self.tabview.add("Class Features Widget")
        self.tabview.add("Custom Columns")
        self.tabview.add("Column Values")
        
        # Track which tabs have been created
        self._tabs_created = {
            "Basic Info": False,
            "Spellcasting": False,
            "Level Features": False,
            "Class Features Widget": False,
            "Custom Columns": False,
            "Column Values": False,
        }
        
        # Create first tab immediately (Basic Info is usually needed)
        self._create_basic_info_tab()
        self._tabs_created["Basic Info"] = True
        
        # Bind tab change event for lazy loading
        self.tabview.configure(command=self._on_tab_change)
        
        # Button frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)
        
        
        add_cancel_save(btn_frame, self.theme, self._finish, self._on_save_class, confirm_text="Save Class", confirm_width=120)
    
    def _on_tab_change(self, tab_name: str):
        """Handle tab change - lazy load tab content if not yet created."""
        if tab_name not in self._tabs_created or self._tabs_created[tab_name]:
            return
        
        # Create tab content based on tab name
        if tab_name == "Spellcasting":
            self._create_spellcasting_tab()
        elif tab_name == "Level Features":
            self._create_level_features_tab()
        elif tab_name == "Class Features Widget":
            self._create_class_features_tab()
        elif tab_name == "Custom Columns":
            self._create_custom_columns_tab()
        elif tab_name == "Column Values":
            self._create_column_values_tab()
        
        self._tabs_created[tab_name] = True
        self.update_idletasks()
    
    def _ensure_all_tabs_created(self):
        """Ensure all tabs are created. Used when editing existing class."""
        for tab_name in self._tabs_created:
            if not self._tabs_created[tab_name]:
                self._on_tab_change(tab_name)
    
    def _create_basic_info_tab(self):
        """Create the basic info tab."""
        tab = self.tabview.tab("Basic Info")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        # Name
        ctk.CTkLabel(scroll, text="Class Name *", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Fighter")
        self.name_entry.pack(fill="x", pady=(0, 15))
        
        # Hit Die
        hit_die_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        hit_die_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(hit_die_frame, text="Hit Die *", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.hit_die_var = ctk.StringVar(value="d8")
        self.hit_die_combo = ctk.CTkComboBox(
            hit_die_frame, variable=self.hit_die_var,
            values=["d6", "d8", "d10", "d12"],
            width=100
        )
        self.hit_die_combo.pack(side="left", padx=(15, 0))
        
        # Primary Ability
        ctk.CTkLabel(scroll, text="Primary Ability", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.primary_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Strength or Dexterity")
        self.primary_entry.pack(fill="x", pady=(0, 15))
        
        # Saving Throws
        ctk.CTkLabel(scroll, text="Saving Throw Proficiencies", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        
        saves_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        saves_frame.pack(fill="x", pady=(0, 15))
        
        self.save_vars = {}
        for save in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
            var = ctk.BooleanVar(value=False)
            self.save_vars[save] = var
            ctk.CTkCheckBox(saves_frame, text=save, variable=var, width=70).pack(side="left", padx=(0, 10))
        
        # Armor Proficiencies
        ctk.CTkLabel(scroll, text="Armor Proficiencies (comma-separated)", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.armor_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Light armor, Medium armor, Shields")
        self.armor_entry.pack(fill="x", pady=(0, 15))
        
        # Weapon Proficiencies
        ctk.CTkLabel(scroll, text="Weapon Proficiencies (comma-separated)", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.weapon_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Simple weapons, Martial weapons")
        self.weapon_entry.pack(fill="x", pady=(0, 15))
        
        # Tool Proficiencies
        ctk.CTkLabel(scroll, text="Tool Proficiencies (comma-separated)", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.tool_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Thieves' Tools")
        self.tool_entry.pack(fill="x", pady=(0, 15))
        
        # Skill choices
        skill_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        skill_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(skill_frame, text="Number of Skill Choices:", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.skill_choices_entry = ctk.CTkEntry(skill_frame, width=60, height=35, placeholder_text="2")
        self.skill_choices_entry.pack(side="left", padx=(10, 0))
        
        # Skill Options - Checkboxes
        ctk.CTkLabel(scroll, text="Available Skill Options", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        
        skill_options_frame = ctk.CTkFrame(scroll, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        skill_options_frame.pack(fill="x", pady=(0, 5))
        
        # Select All / Clear All buttons
        skill_btn_frame = ctk.CTkFrame(skill_options_frame, fg_color="transparent")
        skill_btn_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            skill_btn_frame, text="Select All", width=80, height=25,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            command=self._select_all_skills
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            skill_btn_frame, text="Clear All", width=80, height=25,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            command=self._clear_all_skills
        ).pack(side="left")
        
        # Skills grid (3 columns)
        skills_grid = ctk.CTkFrame(skill_options_frame, fg_color="transparent")
        skills_grid.pack(fill="x", padx=10, pady=(0, 10))
        skills_grid.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.skill_vars = {}
        for idx, skill in enumerate(self.ALL_SKILLS):
            var = ctk.BooleanVar(value=False)
            self.skill_vars[skill] = var
            cb = ctk.CTkCheckBox(skills_grid, text=skill, variable=var, width=150,
                                 font=ui_font("small"))
            cb.grid(row=idx // 3, column=idx % 3, sticky="w", padx=5, pady=2)
        
        # Subclass Level
        subclass_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        subclass_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(subclass_frame, text="Subclass Level:", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.subclass_level_var = ctk.StringVar(value="3")
        self.subclass_level_combo = ctk.CTkComboBox(
            subclass_frame, variable=self.subclass_level_var,
            values=[str(i) for i in range(1, 11)],
            width=80, command=self._on_subclass_level_changed
        )
        self.subclass_level_combo.pack(side="left", padx=(10, 0))
        
        ctk.CTkLabel(subclass_frame, text="Subclass Name:", font=ui_font("subheading", 13, bold=True)).pack(side="left", padx=(30, 0))
        self.subclass_name_entry = ctk.CTkEntry(subclass_frame, width=200, height=35, placeholder_text="e.g., Martial Archetype")
        self.subclass_name_entry.pack(side="left", padx=(10, 0))
        
        # Description with rich text toolbar
        ctk.CTkLabel(scroll, text="Description", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        
        from ui.rich_text_utils import RichTextEditor
        
        self.description_text = ctk.CTkTextbox(scroll, height=120, font=ui_font("body"))
        self._class_desc_rich_editor = RichTextEditor(self, self.description_text, self.theme)
        class_desc_toolbar = self._class_desc_rich_editor.create_toolbar(scroll)
        class_desc_toolbar.pack(fill="x", pady=(0, 5))
        
        self.description_text.pack(fill="x", pady=(0, 15))
        
        # Source
        ctk.CTkLabel(scroll, text="Source", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.source_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Player's Handbook (2024)")
        self.source_entry.pack(fill="x", pady=(0, 15))
    
    def _create_spellcasting_tab(self):
        """Create the spellcasting configuration tab."""
        tab = self.tabview.tab("Spellcasting")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        # Is Spellcaster toggle
        self.is_caster_var = ctk.BooleanVar(value=False)
        caster_cb = ctk.CTkCheckBox(
            scroll, text="This class is a spellcaster",
            variable=self.is_caster_var,
            font=ui_font("subheading", bold=True),
            command=self._on_caster_toggle
        )
        caster_cb.pack(fill="x", pady=(0, 20))
        
        # Spellcasting options frame (enabled/disabled based on toggle)
        self.spell_options_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.spell_options_frame.pack(fill="both", expand=True)
        
        # Spellcasting Ability
        ability_frame = ctk.CTkFrame(self.spell_options_frame, fg_color="transparent")
        ability_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(ability_frame, text="Spellcasting Ability:", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.spell_ability_var = ctk.StringVar(value="INT")
        self.spell_ability_combo = ctk.CTkComboBox(
            ability_frame, variable=self.spell_ability_var,
            values=["INT", "WIS", "CHA"],
            width=100
        )
        self.spell_ability_combo.pack(side="left", padx=(15, 0))
        
        # Spell Slot Progression
        ctk.CTkLabel(
            self.spell_options_frame, text="Spell Slot Progression:",
            font=ui_font("subheading", 13, bold=True)
        ).pack(fill="x", pady=(0, 10))
        
        self.slot_progression_var = ctk.StringVar(value="none")
        
        prog_frame = ctk.CTkFrame(self.spell_options_frame, fg_color="transparent")
        prog_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkRadioButton(
            prog_frame, text="Full Caster (Wizard/Cleric/etc.)",
            variable=self.slot_progression_var, value="full",
            font=ui_font("body")
        ).pack(anchor="w", pady=3)
        
        ctk.CTkRadioButton(
            prog_frame, text="Half Caster (Paladin/Ranger)",
            variable=self.slot_progression_var, value="half",
            font=ui_font("body")
        ).pack(anchor="w", pady=3)
        
        ctk.CTkRadioButton(
            prog_frame, text="Custom (configure manually)",
            variable=self.slot_progression_var, value="custom",
            font=ui_font("body")
        ).pack(anchor="w", pady=3)
        
        # Note about custom
        ctk.CTkLabel(
            self.spell_options_frame,
            text="Note: Custom spell slots can be configured in the Level Features tab.",
            font=ui_font("small"),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(fill="x", pady=(0, 15))
        
        # Initialize disabled state
        self._on_caster_toggle()
    
    def _on_caster_toggle(self):
        """Handle spellcaster toggle."""
        is_caster = self.is_caster_var.get()
        state = "normal" if is_caster else "disabled"
        
        for child in self.spell_options_frame.winfo_children():
            try:
                child.configure(state=state)
            except Exception:
                pass
    
    def _create_level_features_tab(self):
        """Create the level features tab: a section for every level, each with its features as cards."""
        from ui.feature_sections import FeatureSections
        tab = self.tabview.tab("Level Features")
        features = {lvl: list(self._level_data.get(lvl, {}).get("features", [])) for lvl in range(1, 21)}
        self._subclass_vars = {}

        def level_title(level: int) -> str:
            return f"Level {level}  ·  Proficiency +{2 + (level - 1) // 4}"

        def level_extra(parent, level: int):
            var = ctk.BooleanVar(value=level in self._subclass_levels)
            self._subclass_vars[level] = var
            return ctk.CTkCheckBox(
                parent, text="Subclass feature", variable=var, width=130, font=ui_font("small"),
                command=lambda l=level: self._toggle_subclass_level(l))

        def edit_details(feature):
            dialog = FeatureEditorDialog(self, "Edit Feature", feature)
            self.wait_window(dialog)
            return dialog.result

        self.level_sections = FeatureSections(
            tab, levels=range(1, 21), features=features,
            new_feature=lambda level: ClassAbility(title="", description=""),
            level_title=level_title, level_extra=level_extra, edit_details=edit_details,
            hidden=lambda f: f.is_subclass_feature, open_levels=(1,),
            hint="Every level is ready to fill in: open one and add its features. Tick \"Subclass feature\" on the "
                 "levels where a subclass gives features (they follow the Subclass Level on the Basic Info tab until "
                 "you change one by hand). Ability Score Improvement and Epic Boon are filled in for you; edit or "
                 "remove them as you like. Details... opens the full editor for tables and roll effects.")
        self.level_sections.pack(fill="both", expand=True)

    def _toggle_subclass_level(self, level: int):
        self._subclass_touched = True
        if self._subclass_vars[level].get():
            self._subclass_levels.add(level)
        else:
            self._subclass_levels.discard(level)

    def _on_subclass_level_changed(self, value=None):
        """Moving the Subclass Level moves the usual subclass feature levels with it (until set by hand)."""
        if self._subclass_touched:
            return
        try:
            levels = set(default_subclass_levels(int(self.subclass_level_var.get())))
        except ValueError:
            return
        self._subclass_levels = levels
        for lvl, var in self._subclass_vars.items():
            var.set(lvl in levels)

    def _sync_features(self, strict: bool = False):
        """Read the feature cards back into ``_level_data`` (levels never opened keep what they had)."""
        if self.level_sections is None:
            return
        for lvl, feats in self.level_sections.get_features(strict=strict).items():
            self._level_data.setdefault(lvl, {"features": [], "class_specific": {}})["features"] = feats

    def _push_features(self):
        """Show ``_level_data``'s features in the sections (after the form is filled in from a class)."""
        if self.level_sections is not None:
            self.level_sections.set_features({lvl: d["features"] for lvl, d in self._level_data.items()})
            for lvl, var in self._subclass_vars.items():
                var.set(lvl in self._subclass_levels)

    def _create_class_features_tab(self):
        """Create the class features widget configuration tab."""
        tab = self.tabview.tab("Class Features Widget")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            scroll, text="Trackable Features (max 3)",
            font=ui_font("heading", 16, bold=True)
        ).pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            scroll,
            text="These features appear in the Class Features widget on the character sheet.",
            font=ui_font("body"),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(fill="x", pady=(0, 15))
        
        # Add button
        btn_text = self.theme.get_current_color('text_primary')
        ctk.CTkButton(
            scroll, text="+ Add Trackable Feature", width=180,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._add_trackable_feature
        ).pack(anchor="w", pady=(0, 15))
        
        # Features list
        self.trackable_frame = ctk.CTkFrame(
            scroll, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.trackable_frame.pack(fill="x")
        
        self._refresh_trackable_features()
    
    def _refresh_trackable_features(self):
        """Refresh the trackable features list."""
        for widget in self.trackable_frame.winfo_children():
            widget.destroy()
        
        if not self._trackable_features:
            ctk.CTkLabel(
                self.trackable_frame,
                text="No trackable features defined.",
                font=ui_font("body"),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=15)
            return
        
        for idx, feature in enumerate(self._trackable_features):
            row = ctk.CTkFrame(self.trackable_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(
                row, text=f"{feature.title} ({feature.tracked_value})",
                font=ui_font("subheading", 13, bold=True),
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            
            btn_text = self.theme.get_current_color('text_primary')
            
            ctk.CTkButton(
                row, text="Edit", width=60,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=btn_text,
                command=lambda i=idx: self._edit_trackable_feature(i)
            ).pack(side="right", padx=(5, 0))
            
            ctk.CTkButton(
                row, text="Delete", width=60,
                fg_color=self.theme.get_current_color('button_danger'),
                hover_color=self.theme.get_current_color('button_danger_hover'),
                text_color=btn_text,
                command=lambda i=idx: self._delete_trackable_feature(i)
            ).pack(side="right")
    
    def _add_trackable_feature(self):
        """Add a new trackable feature."""
        if len(self._trackable_features) >= 3:
            messagebox.showwarning("Warning", "Maximum of 3 trackable features allowed.", parent=self)
            return
        
        dialog = TrackableFeatureEditorDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            self._trackable_features.append(dialog.result)
            self._refresh_trackable_features()
    
    def _edit_trackable_feature(self, idx: int):
        """Edit a trackable feature."""
        dialog = TrackableFeatureEditorDialog(self, self._trackable_features[idx])
        self.wait_window(dialog)
        
        if dialog.result:
            self._trackable_features[idx] = dialog.result
            self._refresh_trackable_features()
    
    def _delete_trackable_feature(self, idx: int):
        """Delete a trackable feature."""
        if messagebox.askyesno("Confirm Delete", "Delete this trackable feature?", parent=self):
            del self._trackable_features[idx]
            self._refresh_trackable_features()
    
    def _create_custom_columns_tab(self):
        """Create the custom columns configuration tab."""
        tab = self.tabview.tab("Custom Columns")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            scroll, text="Custom Feature Table Columns",
            font=ui_font("heading", 16, bold=True)
        ).pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            scroll,
            text="Add custom columns to the class features table (e.g., Rage Damage, Martial Arts Die).",
            font=ui_font("body"),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(fill="x", pady=(0, 15))
        
        # Add column section
        add_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        add_frame.pack(fill="x", pady=(0, 15))
        
        self.new_column_entry = ctk.CTkEntry(add_frame, height=35, placeholder_text="Column name")
        self.new_column_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_text = self.theme.get_current_color('text_primary')
        ctk.CTkButton(
            add_frame, text="Add Column", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._add_column
        ).pack(side="right")
        
        # Columns list
        self.columns_frame = ctk.CTkFrame(
            scroll, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.columns_frame.pack(fill="x")
        
        self._refresh_columns()
    
    def _refresh_columns(self):
        """Refresh the columns list."""
        for widget in self.columns_frame.winfo_children():
            widget.destroy()
        
        if not self._custom_columns:
            ctk.CTkLabel(
                self.columns_frame,
                text="No custom columns defined.",
                font=ui_font("body"),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=15)
            return
        
        for idx, col_name in enumerate(self._custom_columns):
            row = ctk.CTkFrame(self.columns_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(
                row, text=col_name,
                font=ui_font("subheading", 13, bold=True),
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            
            btn_text = self.theme.get_current_color('text_primary')
            ctk.CTkButton(
                row, text="Delete", width=60,
                fg_color=self.theme.get_current_color('button_danger'),
                hover_color=self.theme.get_current_color('button_danger_hover'),
                text_color=btn_text,
                command=lambda i=idx: self._delete_column(i)
            ).pack(side="right")
    
    def _add_column(self):
        """Add a new column."""
        name = self.new_column_entry.get().strip()
        if not name:
            return
        
        if name in self._custom_columns:
            messagebox.showwarning("Warning", "Column already exists.", parent=self)
            return
        
        self._custom_columns.append(name)
        self.new_column_entry.delete(0, "end")
        self._refresh_columns()
        
        # Add to all level data
        for lvl in range(1, 21):
            if lvl not in self._level_data:
                self._level_data[lvl] = {"features": [], "class_specific": {}}
            self._level_data[lvl]["class_specific"][name] = "-"
        
        # Refresh column values if that tab exists
        if hasattr(self, '_column_values_frame'):
            self._refresh_column_values()
    
    def _delete_column(self, idx: int):
        """Delete a column."""
        if messagebox.askyesno("Confirm Delete", "Delete this column?", parent=self):
            col_name = self._custom_columns[idx]
            del self._custom_columns[idx]
            
            # Remove from all level data
            for lvl in range(1, 21):
                if lvl in self._level_data and col_name in self._level_data[lvl]["class_specific"]:
                    del self._level_data[lvl]["class_specific"][col_name]
            
            self._refresh_columns()
            
            # Refresh column values tab
            if hasattr(self, '_column_values_frame'):
                self._refresh_column_values()
    
    def _select_all_skills(self):
        """Select all skill checkboxes."""
        for var in self.skill_vars.values():
            var.set(True)
    
    def _clear_all_skills(self):
        """Clear all skill checkboxes."""
        for var in self.skill_vars.values():
            var.set(False)
    
    def _create_column_values_tab(self):
        """Create the column values editor tab - allows editing all level values at once."""
        tab = self.tabview.tab("Column Values")
        
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            scroll, text="Column Values by Level",
            font=ui_font("heading", 16, bold=True)
        ).pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            scroll,
            text="Set values for each custom column across all levels. This is easier than editing each level individually.",
            font=ui_font("body"),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(fill="x", pady=(0, 15))
        
        # Container for column value editors
        self._column_values_frame = ctk.CTkFrame(
            scroll, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self._column_values_frame.pack(fill="both", expand=True)
        
        self._column_value_entries = {}  # {column_name: {level: entry}}
        self._refresh_column_values()
    
    def _refresh_column_values(self):
        """Refresh the column values editor."""
        for widget in self._column_values_frame.winfo_children():
            widget.destroy()
        
        self._column_value_entries = {}
        
        if not self._custom_columns:
            ctk.CTkLabel(
                self._column_values_frame,
                text="No custom columns defined. Add columns in the 'Custom Columns' tab first.",
                font=ui_font("body"),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=15)
            return
        
        # Create a section for each column
        for col_name in self._custom_columns:
            self._create_column_value_section(col_name)
    
    def _create_column_value_section(self, col_name: str):
        """Create a section for editing a single column's values across all levels."""
        section = ctk.CTkFrame(self._column_values_frame, fg_color="transparent")
        section.pack(fill="x", padx=10, pady=10)
        
        # Column header
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            header, text=col_name,
            font=ui_font("subheading", bold=True),
            text_color=self.theme.get_current_color('accent_primary')
        ).pack(side="left")
        
        # Fill pattern helper
        fill_frame = ctk.CTkFrame(header, fg_color="transparent")
        fill_frame.pack(side="right")
        
        ctk.CTkLabel(fill_frame, text="Fill:", font=ui_font("small")).pack(side="left", padx=(0, 5))
        
        fill_entry = ctk.CTkEntry(fill_frame, width=60, height=25, placeholder_text="value")
        fill_entry.pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            fill_frame, text="Fill All", width=60, height=25,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            command=lambda c=col_name, e=fill_entry: self._fill_all_column_values(c, e.get())
        ).pack(side="left")
        
        # Grid of level inputs (4 columns x 5 rows)
        grid_frame = ctk.CTkFrame(section, fg_color="transparent")
        grid_frame.pack(fill="x", pady=5)
        
        self._column_value_entries[col_name] = {}
        
        for lvl in range(1, 21):
            row = (lvl - 1) % 5
            col = (lvl - 1) // 5
            
            cell = ctk.CTkFrame(grid_frame, fg_color="transparent")
            cell.grid(row=row, column=col, padx=5, pady=2, sticky="w")
            
            ctk.CTkLabel(cell, text=f"L{lvl}:", font=ui_font("small"), width=30).pack(side="left")
            
            # Get current value
            current_val = "-"
            if lvl in self._level_data:
                current_val = self._level_data[lvl].get("class_specific", {}).get(col_name, "-")
            
            entry = ctk.CTkEntry(cell, width=60, height=25)
            entry.insert(0, current_val)
            entry.pack(side="left")
            
            # Bind to save on change
            entry.bind("<FocusOut>", lambda e, c=col_name, l=lvl: self._save_column_value(c, l))
            entry.bind("<Return>", lambda e, c=col_name, l=lvl: self._save_column_value(c, l))
            
            self._column_value_entries[col_name][lvl] = entry
        
        # Separator
        ctk.CTkFrame(
            section, height=1,
            fg_color=self.theme.get_current_color('border')
        ).pack(fill="x", pady=(10, 0))
    
    def _save_column_value(self, col_name: str, level: int):
        """Save a column value from the entry."""
        if col_name in self._column_value_entries and level in self._column_value_entries[col_name]:
            entry = self._column_value_entries[col_name][level]
            value = entry.get().strip() or "-"
            
            if level not in self._level_data:
                self._level_data[level] = {"features": [], "class_specific": {}}
            
            self._level_data[level]["class_specific"][col_name] = value
    
    def _fill_all_column_values(self, col_name: str, value: str):
        """Fill all levels with the same value for a column."""
        value = value.strip() or "-"
        
        for lvl in range(1, 21):
            if lvl not in self._level_data:
                self._level_data[lvl] = {"features": [], "class_specific": {}}
            
            self._level_data[lvl]["class_specific"][col_name] = value
            
            # Update entry
            if col_name in self._column_value_entries and lvl in self._column_value_entries[col_name]:
                entry = self._column_value_entries[col_name][lvl]
                entry.delete(0, "end")
                entry.insert(0, value)

    def _populate_from_class(self, class_def: CharacterClassDefinition):
        """Populate all fields from an existing class."""
        self.name_entry.insert(0, class_def.name)
        self.hit_die_var.set(class_def.hit_die)
        self.primary_entry.insert(0, class_def.primary_ability)
        
        # Saving throws
        for save in class_def.saving_throw_proficiencies:
            if save in self.save_vars:
                self.save_vars[save].set(True)
        
        self.armor_entry.insert(0, ", ".join(class_def.armor_proficiencies))
        self.weapon_entry.insert(0, ", ".join(class_def.weapon_proficiencies))
        self.tool_entry.insert(0, ", ".join(class_def.tool_proficiencies))
        
        self.skill_choices_entry.insert(0, str(class_def.skill_proficiency_choices))
        # Set skill checkboxes
        for skill in class_def.skill_proficiency_options:
            if skill in self.skill_vars:
                self.skill_vars[skill].set(True)
        
        self.subclass_level_var.set(str(class_def.subclass_level))
        self.subclass_name_entry.insert(0, class_def.subclass_name)
        
        self.description_text.insert("1.0", class_def.description)
        self.source_entry.insert(0, class_def.source)
        
        # Spellcasting
        self.is_caster_var.set(class_def.is_spellcaster)
        if class_def.spellcasting_ability:
            self.spell_ability_var.set(class_def.spellcasting_ability)
        self._on_caster_toggle()
        
        self._push_features()

        # Refresh trackable features and columns
        self._refresh_trackable_features()
        self._refresh_columns()
        
        # Refresh column values tab if it's been created
        if hasattr(self, '_column_values_frame'):
            self._refresh_column_values()
    
    def build_result(self, strict: bool = True) -> CharacterClassDefinition:
        """The class the form describes (strict: ValueError if incomplete; otherwise gaps are filled in).

        The Spellcasting tab is only built when it is first opened; until then its settings are the class's own
        (or a non-caster's)."""
        name = self.name_entry.get().strip()
        if not name and strict:
            raise ValueError("Please enter a class name.")
        self._sync_features(strict)

        def number(text, default):
            try:
                return int(text)
            except (TypeError, ValueError):
                return default

        # Build levels dict
        levels = {}
        if hasattr(self, "is_caster_var"):
            is_caster = self.is_caster_var.get()
            progression = self.slot_progression_var.get()
            spell_ability = self.spell_ability_var.get()
        else:
            old = self._class_def
            is_caster = bool(old.is_spellcaster) if old else False
            progression = "none"
            spell_ability = old.spellcasting_ability if old else ""
        
        for lvl in range(1, 21):
            data = self._level_data.get(lvl, {"features": [], "class_specific": {}})
            
            # Determine spell slots
            spell_slots = {}
            if is_caster:
                if progression == "full":
                    spell_slots = {int(k): v for k, v in FULL_CASTER_SLOTS.get(lvl, {}).items()}
                elif progression == "half":
                    spell_slots = {int(k): v for k, v in HALF_CASTER_SLOTS.get(lvl, {}).items()}
            
            prof_bonus = 2 + (lvl - 1) // 4
            
            # Get features and add subclass feature placeholder if this level has one
            features = list(data["features"])
            
            # If this level has subclass feature, add a placeholder
            if lvl in self._subclass_levels:
                # Check if there's already a subclass feature placeholder
                has_subclass_placeholder = any(f.is_subclass_feature for f in features)
                if not has_subclass_placeholder:
                    subclass_name = self.subclass_name_entry.get().strip() or "Subclass"
                    features.append(ClassAbility(
                        title=f"{subclass_name} feature",
                        description="Feature granted by your chosen subclass.",
                        is_subclass_feature=True
                    ))
            
            levels[lvl] = ClassLevel(
                level=lvl,
                abilities=features,
                proficiency_bonus=prof_bonus,
                spell_slots=spell_slots,
                class_specific=data["class_specific"]
            )
        
        # Build class definition
        saving_throws = [save for save, var in self.save_vars.items() if var.get()]
        
        class_def = CharacterClassDefinition(
            name=name,
            hit_die=self.hit_die_var.get(),
            primary_ability=self.primary_entry.get().strip(),
            armor_proficiencies=[p.strip() for p in self.armor_entry.get().split(",") if p.strip()],
            weapon_proficiencies=[p.strip() for p in self.weapon_entry.get().split(",") if p.strip()],
            tool_proficiencies=[p.strip() for p in self.tool_entry.get().split(",") if p.strip()],
            saving_throw_proficiencies=saving_throws,
            skill_proficiency_choices=number(self.skill_choices_entry.get() or "2", 2),
            skill_proficiency_options=[skill for skill, var in self.skill_vars.items() if var.get()],
            description=self.description_text.get("1.0", "end-1c").strip(),
            is_spellcaster=is_caster,
            spellcasting_ability=spell_ability if is_caster else "",
            subclass_level=number(self.subclass_level_var.get(), 3),
            subclass_name=self.subclass_name_entry.get().strip(),
            subclasses=self._class_def.subclasses if self._class_def else [],
            levels=levels,
            trackable_features=self._trackable_features,
            class_table_columns=self._custom_columns,
            is_custom=True,
            source=self.source_entry.get().strip() or "Custom"
        )
        return class_def

    def _on_save_class(self):
        """Save the class."""
        try:
            class_def = self.build_result(strict=True)
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self)
            return
        self.result = class_def
        if not self.EMBEDDED:
            # Save to manager
            manager = get_class_manager()
            manager.add_class(class_def)

            if self._on_save:
                self._on_save(class_def)

        self._finish()


class ClassEditorDialog(ClassEditorBody, DialogWindow):
    """Dialog for creating or editing a character class."""


class ClassEditorPanel(ClassEditorBody, EmbeddedWindow):
    """The class form inside the Homebrew Studio."""


class SubclassEditorBody:
    """Dialog for creating or editing a subclass. (the form; see ui/editor_host.py)"""
    
    def __init__(self, parent, parent_class: CharacterClassDefinition,
                 subclass: Optional[SubclassDefinition] = None, on_save: Optional[Callable] = None):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[SubclassDefinition] = None
        self._parent_class = parent_class
        self._editing = subclass is not None
        self._subclass = subclass
        self._on_save = on_save
        
        # Store features and spells
        self._features: List[SubclassFeature] = []
        self._spells: List[SubclassSpell] = []
        
        if subclass:
            self._features = list(subclass.features)
            self._spells = list(subclass.subclass_spells)
        
        self.title("Edit Subclass" if subclass else "Create New Subclass")
        self.geometry("800x700")
        self.minsize(700, 600)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        if subclass:
            self._populate_from_subclass(subclass)
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 800) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 700) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create all dialog widgets."""
        # Create tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(15, 0))
        
        self.tabview.add("Basic Info")
        self.tabview.add("Features")
        self.tabview.add("Spell List")
        
        self._create_basic_tab()
        self._create_features_tab()
        self._create_spells_tab()
        
        # Button frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)
        
        
        add_cancel_save(btn_frame, self.theme, self._finish, self._on_save_subclass, confirm_text="Save Subclass", confirm_width=120)
    
    def _create_basic_tab(self):
        """Create the basic info tab."""
        tab = self.tabview.tab("Basic Info")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        # Name
        ctk.CTkLabel(scroll, text="Subclass Name *", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Path of the Berserker")
        self.name_entry.pack(fill="x", pady=(0, 15))
        
        # Parent Class (read-only)
        ctk.CTkLabel(scroll, text="Parent Class", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        parent_label = ctk.CTkLabel(
            scroll, text=self._parent_class.name,
            font=ui_font("subheading"),
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=6, height=35
        )
        parent_label.pack(fill="x", pady=(0, 15))
        
        # Description
        ctk.CTkLabel(scroll, text="Description", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        
        from ui.rich_text_utils import RichTextEditor
        
        self.description_text = ctk.CTkTextbox(scroll, height=150, font=ui_font("body"))
        self._desc_rich_editor = RichTextEditor(self, self.description_text, self.theme)
        desc_toolbar = self._desc_rich_editor.create_toolbar(scroll)
        desc_toolbar.pack(fill="x", pady=(0, 5))
        
        self.description_text.pack(fill="x", pady=(0, 15))
        
        # Source
        ctk.CTkLabel(scroll, text="Source", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.source_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Player's Handbook (2024)")
        self.source_entry.pack(fill="x", pady=(0, 15))
    
    def _create_features_tab(self):
        """The Features tab: a section for every level the parent class gives subclass features at."""
        from ui.feature_sections import FeatureSections
        tab = self.tabview.tab("Features")
        detected = subclass_feature_levels(self._parent_class)
        self._detected_levels = detected
        extra = sorted({f.level for f in self._features} - set(detected))
        levels = sorted(set(detected) | set(extra))
        by_level: Dict[int, List[SubclassFeature]] = {lvl: [] for lvl in levels}
        for feature in self._features:
            by_level[feature.level].append(feature)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        where = ", ".join(str(lvl) for lvl in detected)
        class_name = self._parent_class.name
        ctk.CTkLabel(
            header, anchor="w", justify="left", wraplength=520, font=ui_font("small"),
            text_color=self.theme.get_current_color('text_secondary'),
            text=f"{class_name} gives subclass features at levels {where} - read from the class, so those "
                 f"sections are ready below. Open one and add its features."
        ).pack(side="left", fill="x", expand=True)
        spare = [str(lvl) for lvl in range(1, 21) if lvl not in levels]
        self._add_level_var = ctk.StringVar(value="Add a level")
        self._add_level_menu = ctk.CTkOptionMenu(
            header, values=spare or ["-"], variable=self._add_level_var, width=110, height=28,
            command=self._add_extra_level)
        self._add_level_menu.pack(side="right")

        def level_title(level: int) -> str:
            note = "" if level in detected else "  (not one of the class's subclass levels)"
            return f"Level {level}{note}"

        def edit_details(feature):
            dialog = SubclassFeatureEditorDialog(self, 1, feature)
            self.wait_window(dialog)
            if dialog.result is not None:
                dialog.result.level = feature.level                       # the section decides the level
            return dialog.result

        self.feature_sections = FeatureSections(
            tab, levels=levels, features=by_level,
            new_feature=lambda level: SubclassFeature(level=level, title="", description=""),
            level_title=level_title, edit_details=edit_details, blank_cards=True, open_levels=levels)
        self.feature_sections.pack(fill="both", expand=True)

    def _add_extra_level(self, value: str):
        """Add a section for a level the class does not list (a feature at an unusual level)."""
        try:
            level = int(value)
        except ValueError:
            return
        self.feature_sections.add_level(level)
        spare = [str(lvl) for lvl in range(1, 21) if lvl not in self.feature_sections.levels()]
        self._add_level_menu.configure(values=spare or ["-"])
        self._add_level_var.set("Add a level")

    def _sync_features(self, strict: bool = False):
        """Read the feature cards back into ``_features``."""
        sections = getattr(self, "feature_sections", None)
        if sections is None:
            return
        features: List[SubclassFeature] = []
        for level, feats in sections.get_features(strict=strict).items():
            for feature in feats:
                feature.level = level
                features.append(feature)
        self._features = features

    def _refresh_features(self):
        """Show ``_features`` in the sections (after the form is filled in from a subclass)."""
        sections = getattr(self, "feature_sections", None)
        if sections is None:
            return
        by_level: Dict[int, List[SubclassFeature]] = {}
        for feature in self._features:
            by_level.setdefault(feature.level, []).append(feature)
        sections.set_features(by_level)

    def _create_spells_tab(self):
        """Create the spell list tab."""
        tab = self.tabview.tab("Spell List")
        
        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, text="Subclass Spells (Always Prepared)",
            font=ui_font("heading", 16, bold=True)
        ).pack(side="left")
        
        btn_text = self.theme.get_current_color('text_primary')
        ctk.CTkButton(
            header, text="+ Add Spell", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._add_spell
        ).pack(side="right")
        
        ctk.CTkLabel(
            tab,
            text="These spells are always prepared and don't count against the character's prepared spell limit.",
            font=ui_font("small"),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(fill="x", pady=(0, 10))
        
        # Spells list
        self.spells_scroll = ctk.CTkScrollableFrame(
            tab, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.spells_scroll.pack(fill="both", expand=True)
        
        self._refresh_spells()
    
    def _refresh_spells(self):
        """Refresh the spells list."""
        for widget in self.spells_scroll.winfo_children():
            widget.destroy()
        
        if not self._spells:
            ctk.CTkLabel(
                self.spells_scroll,
                text="No spells defined. Click '+ Add Spell' to add one.",
                font=ui_font("body"),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=20)
            return
        
        # Sort by level gained
        sorted_spells = sorted(self._spells, key=lambda s: s.level_gained)
        
        for idx, spell in enumerate(sorted_spells):
            row = ctk.CTkFrame(self.spells_scroll, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=3)
            
            ctk.CTkLabel(
                row, text=f"Level {spell.level_gained}: {spell.spell_name}",
                font=ui_font("body"),
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            
            btn_text = self.theme.get_current_color('text_primary')
            orig_idx = self._spells.index(spell)
            
            ctk.CTkButton(
                row, text="Delete", width=60,
                fg_color=self.theme.get_current_color('button_danger'),
                hover_color=self.theme.get_current_color('button_danger_hover'),
                text_color=btn_text,
                command=lambda i=orig_idx: self._delete_spell(i)
            ).pack(side="right")
    
    def _add_spell(self):
        """Add a new spell."""
        dialog = SubclassSpellEditorDialog(self, self._parent_class.subclass_level)
        self.wait_window(dialog)
        
        if dialog.result:
            self._spells.append(dialog.result)
            self._refresh_spells()
    
    def _delete_spell(self, idx: int):
        """Delete a spell."""
        del self._spells[idx]
        self._refresh_spells()
    
    def _populate_from_subclass(self, subclass: SubclassDefinition):
        """Populate from existing subclass."""
        self.name_entry.insert(0, subclass.name)
        self.description_text.insert("1.0", subclass.description)
        self.source_entry.insert(0, subclass.source)
        
        self._refresh_features()
        self._refresh_spells()
    
    def build_result(self, strict: bool = True) -> SubclassDefinition:
        """The subclass the form describes (strict: ValueError if incomplete; otherwise gaps are filled in)."""
        name = self.name_entry.get().strip()
        if not name and strict:
            raise ValueError("Please enter a subclass name.")
        self._sync_features(strict)

        return SubclassDefinition(
            name=name,
            parent_class=self._parent_class.name,
            description=self.description_text.get("1.0", "end-1c").strip(),
            features=self._features,
            subclass_spells=self._spells,
            source=self.source_entry.get().strip() or "Custom",
            is_custom=True
        )

    def _on_save_subclass(self):
        """Save the subclass."""
        try:
            subclass = self.build_result(strict=True)
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self)
            return
        self.result = subclass

        if not self.EMBEDDED:
            # Update parent class
            manager = get_class_manager()
            parent = manager.get_class(self._parent_class.name)

            if parent:
                # Remove existing subclass with same name if editing
                if self._editing and self._subclass:
                    parent.subclasses = [s for s in parent.subclasses if s.name != self._subclass.name]

                # Add new/updated subclass
                parent.subclasses.append(subclass)
                manager.add_class(parent)

            if self._on_save:
                self._on_save(subclass)

        self._finish()


class SubclassEditorDialog(SubclassEditorBody, DialogWindow):
    """Dialog for creating or editing a subclass."""


class SubclassEditorPanel(SubclassEditorBody, EmbeddedWindow):
    """The subclass form inside the Homebrew Studio."""


class SubclassFeatureEditorDialog(_FeatureDialogBase):
    """Dialog for editing a single subclass feature."""

    def __init__(self, parent, min_level: int = 1, feature: Optional[SubclassFeature] = None):
        super().__init__(parent)

        self.theme = get_theme_manager()
        self.result: Optional[SubclassFeature] = None
        self._min_level = min_level
        self._feature = feature  # Store original feature to preserve tables

        self._open(parent, "Edit Feature" if feature else "Add Feature", (600, 500), (500, 400), feature)

    def _create_widgets(self):
        """Create dialog widgets."""
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Level
        level_frame = ctk.CTkFrame(container, fg_color="transparent")
        level_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(level_frame, text="Level *", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.level_var = ctk.StringVar(value=str(self._min_level))
        self.level_combo = ctk.CTkComboBox(
            level_frame, variable=self.level_var,
            values=[str(i) for i in range(self._min_level, 21)],
            width=80
        )
        self.level_combo.pack(side="left", padx=(15, 0))
        
        self._add_title_entry(container, "e.g., Frenzy")
        self._add_description_editor(container)
        self._add_roll_effects_editor(container)
        self._add_buttons(container)

    def _populate_from_feature(self, feature: SubclassFeature):
        """Populate from existing feature."""
        self.level_var.set(str(feature.level))
        self.title_entry.insert(0, feature.title)
        self.description_text.insert("1.0", feature.description)
        self.roll_editor.set(feature.roll_effects)

    def _on_save(self):
        """Save the feature."""
        fields = self._title_and_description()
        if not fields:
            return
        title, description = fields

        # Preserve tables from original feature if editing
        tables = self._feature.tables if self._feature else []
        
        self.result = SubclassFeature(
            level=int(self.level_var.get()),
            title=title,
            description=description,
            tables=tables,
            roll_effects=self.roll_editor.get()
        )
        self.destroy()


class SubclassSpellEditorDialog(ctk.CTkToplevel):
    """Dialog for adding a subclass spell."""
    
    def __init__(self, parent, min_level: int = 1):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[SubclassSpell] = None
        self._min_level = min_level
        
        self.title("Add Spell")
        self.geometry("400x250")
        self.minsize(350, 220)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 250) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Spell Name
        ctk.CTkLabel(container, text="Spell Name *", font=ui_font("subheading", 13, bold=True)).pack(fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(container, height=35, placeholder_text="e.g., Bless")
        self.name_entry.pack(fill="x", pady=(0, 15))
        
        # Level Gained
        level_frame = ctk.CTkFrame(container, fg_color="transparent")
        level_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(level_frame, text="Level Gained *", font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.level_var = ctk.StringVar(value=str(self._min_level))
        self.level_combo = ctk.CTkComboBox(
            level_frame, variable=self.level_var,
            values=[str(i) for i in range(self._min_level, 21)],
            width=80
        )
        self.level_combo.pack(side="left", padx=(15, 0))
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))
        
        
        add_cancel_save(btn_frame, self.theme, self.destroy, self._on_save, confirm_text="Add")
    
    def _on_save(self):
        """Save the spell."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a spell name.", parent=self)
            return
        
        self.result = SubclassSpell(
            spell_name=name,
            level_gained=int(self.level_var.get())
        )
        self.destroy()
