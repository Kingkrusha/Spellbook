"""
Class and Subclass Editor Dialogs for D&D Spellbook Application.
Allows users to create and edit custom classes and subclasses.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, List, Dict, Callable
from theme import get_theme_manager
from character_class import (
    get_class_manager, CharacterClassDefinition, ClassLevel, ClassAbility,
    SubclassDefinition, SubclassFeature, SubclassSpell, TrackableFeature
)


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


class FeatureEditorDialog(ctk.CTkToplevel):
    """Dialog for adding/editing a single feature at a level."""
    
    def __init__(self, parent, title: str = "Add Feature", feature: Optional[ClassAbility] = None):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[ClassAbility] = None
        self._feature = feature
        
        self.title(title)
        self.geometry("600x550")
        self.minsize(500, 450)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        if feature:
            self._populate_from_feature(feature)
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 600) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 550) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets."""
        from ui.rich_text_utils import RichTextEditor
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        ctk.CTkLabel(
            container, text="Feature Title *",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(fill="x", pady=(0, 5))
        
        self.title_entry = ctk.CTkEntry(container, height=35, placeholder_text="e.g., Extra Attack")
        self.title_entry.pack(fill="x", pady=(0, 15))
        
        # Description
        ctk.CTkLabel(
            container, text="Description *",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(fill="x", pady=(0, 5))
        
        # Rich text toolbar
        self.description_text = ctk.CTkTextbox(container, height=180, font=ctk.CTkFont(size=12))
        self._rich_editor = RichTextEditor(self, self.description_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(container)
        toolbar.pack(fill="x", pady=(0, 5))
        
        self.description_text.pack(fill="both", expand=True, pady=(0, 15))
        
        # Is Subclass Feature checkbox
        self.is_subclass_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            container, text="Is Subclass Feature (placeholder for subclass abilities)",
            variable=self.is_subclass_var, font=ctk.CTkFont(size=12)
        ).pack(fill="x", pady=(0, 15))
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        btn_text = self.theme.get_current_color('text_primary')
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_save
        ).pack(side="right")
    
    def _populate_from_feature(self, feature: ClassAbility):
        """Populate from existing feature."""
        self.title_entry.insert(0, feature.title)
        self.description_text.insert("1.0", feature.description)
        self.is_subclass_var.set(feature.is_subclass_feature)
    
    def _on_save(self):
        """Save the feature."""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Warning", "Please enter a feature title.", parent=self)
            return
        
        description = self.description_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showwarning("Warning", "Please enter a description.", parent=self)
            return
        
        self.result = ClassAbility(
            title=title,
            description=description,
            is_subclass_feature=self.is_subclass_var.get(),
            subclass_name="",
            tables=[]
        )
        self.destroy()


class LevelFeaturesEditorDialog(ctk.CTkToplevel):
    """Dialog for editing features at a specific level."""
    
    def __init__(self, parent, level: int, features: List[ClassAbility], class_specific: Dict[str, str]):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[Dict] = None
        self._level = level
        self._features = list(features)  # Copy
        self._class_specific = dict(class_specific)  # Copy
        
        self.title(f"Edit Level {level} Features")
        self.geometry("700x600")
        self.minsize(600, 500)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._refresh_features_list()
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            header, text=f"Level {self._level} Features",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        ).pack(side="left")
        
        btn_text = self.theme.get_current_color('text_primary')
        ctk.CTkButton(
            header, text="+ Add Feature", width=120,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._add_feature
        ).pack(side="right")
        
        # Features list
        self.features_frame = ctk.CTkScrollableFrame(
            container, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8, height=300
        )
        self.features_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        # Class-specific values section
        ctk.CTkLabel(
            container, text="Class-Specific Table Values",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", pady=(0, 10))
        
        self.class_specific_frame = ctk.CTkFrame(
            container, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.class_specific_frame.pack(fill="x", pady=(0, 15))
        
        self._create_class_specific_widgets()
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_save
        ).pack(side="right")
    
    def _create_class_specific_widgets(self):
        """Create widgets for class-specific values."""
        for widget in self.class_specific_frame.winfo_children():
            widget.destroy()
        
        if not self._class_specific:
            ctk.CTkLabel(
                self.class_specific_frame,
                text="No class-specific columns defined.",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=15)
            return
        
        self._class_specific_entries = {}
        for col_name, value in self._class_specific.items():
            row = ctk.CTkFrame(self.class_specific_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=5)
            
            ctk.CTkLabel(
                row, text=f"{col_name}:",
                font=ctk.CTkFont(size=12, weight="bold"),
                width=150, anchor="w"
            ).pack(side="left")
            
            entry = ctk.CTkEntry(row, width=150, height=30)
            entry.insert(0, value)
            entry.pack(side="left", padx=(10, 0))
            self._class_specific_entries[col_name] = entry
    
    def _refresh_features_list(self):
        """Refresh the features list display."""
        for widget in self.features_frame.winfo_children():
            widget.destroy()
        
        if not self._features:
            ctk.CTkLabel(
                self.features_frame,
                text="No features at this level. Click '+ Add Feature' to add one.",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=20)
            return
        
        for idx, feature in enumerate(self._features):
            self._create_feature_row(feature, idx)
    
    def _create_feature_row(self, feature: ClassAbility, idx: int):
        """Create a row for a feature."""
        row = ctk.CTkFrame(self.features_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=5)
        
        # Feature title
        title_text = feature.title
        if feature.is_subclass_feature:
            title_text += " (Subclass)"
        
        ctk.CTkLabel(
            row, text=title_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(side="left", fill="x", expand=True)
        
        btn_text = self.theme.get_current_color('text_primary')
        
        # Edit button
        ctk.CTkButton(
            row, text="Edit", width=60,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=lambda i=idx: self._edit_feature(i)
        ).pack(side="right", padx=(5, 0))
        
        # Delete button
        ctk.CTkButton(
            row, text="Delete", width=60,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            text_color=btn_text,
            command=lambda i=idx: self._delete_feature(i)
        ).pack(side="right")
    
    def _add_feature(self):
        """Add a new feature."""
        dialog = FeatureEditorDialog(self, "Add Feature")
        self.wait_window(dialog)
        
        if dialog.result:
            self._features.append(dialog.result)
            self._refresh_features_list()
    
    def _edit_feature(self, idx: int):
        """Edit an existing feature."""
        feature = self._features[idx]
        dialog = FeatureEditorDialog(self, "Edit Feature", feature)
        self.wait_window(dialog)
        
        if dialog.result:
            self._features[idx] = dialog.result
            self._refresh_features_list()
    
    def _delete_feature(self, idx: int):
        """Delete a feature."""
        if messagebox.askyesno("Confirm Delete", "Delete this feature?", parent=self):
            del self._features[idx]
            self._refresh_features_list()
    
    def _on_save(self):
        """Save all changes."""
        # Update class-specific values
        if hasattr(self, '_class_specific_entries'):
            for col_name, entry in self._class_specific_entries.items():
                self._class_specific[col_name] = entry.get().strip()
        
        self.result = {
            "features": self._features,
            "class_specific": self._class_specific
        }
        self.destroy()


class TrackableFeatureEditorDialog(ctk.CTkToplevel):
    """Dialog for adding/editing a trackable feature."""
    
    def __init__(self, parent, feature: Optional[TrackableFeature] = None):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[TrackableFeature] = None
        
        self.title("Edit Trackable Feature" if feature else "Add Trackable Feature")
        self.geometry("500x550")
        self.minsize(450, 500)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        if feature:
            self._populate_from_feature(feature)
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 550) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets."""
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        ctk.CTkLabel(scroll, text="Feature Title *", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.title_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Rage")
        self.title_entry.pack(fill="x", pady=(0, 15))
        
        # Description
        ctk.CTkLabel(scroll, text="Description", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.desc_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="Brief description")
        self.desc_entry.pack(fill="x", pady=(0, 15))
        
        # Tracked Value Label
        ctk.CTkLabel(scroll, text="Tracked Value Label", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.tracked_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Uses, Dice, Points")
        self.tracked_entry.pack(fill="x", pady=(0, 15))
        
        # Max Uses
        uses_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        uses_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(uses_frame, text="Max Uses:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.max_uses_entry = ctk.CTkEntry(uses_frame, width=80, height=35, placeholder_text="0")
        self.max_uses_entry.pack(side="left", padx=(10, 0))
        
        # Recharge
        recharge_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        recharge_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(recharge_frame, text="Recharge:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
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
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(fill="x", pady=(0, 15))
        
        # Buttons
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))
        
        btn_text = self.theme.get_current_color('text_primary')
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_save
        ).pack(side="right")
    
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


class ClassEditorDialog(ctk.CTkToplevel):
    """Dialog for creating or editing a character class."""
    
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
        
        if class_def:
            # Copy existing data
            for lvl, level_obj in class_def.levels.items():
                self._level_data[lvl] = {
                    "features": list(level_obj.abilities),
                    "class_specific": dict(level_obj.class_specific)
                }
            self._trackable_features = list(class_def.trackable_features)
            self._custom_columns = list(class_def.class_table_columns)
        else:
            # Initialize empty levels
            for lvl in range(1, 21):
                self._level_data[lvl] = {"features": [], "class_specific": {}}
        
        self.title("Edit Class" if class_def else "Create New Class")
        self.geometry("900x750")
        self.minsize(800, 650)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        if class_def:
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
        
        # Create tabs
        self.tabview.add("Basic Info")
        self.tabview.add("Spellcasting")
        self.tabview.add("Level Features")
        self.tabview.add("Class Features Widget")
        self.tabview.add("Custom Columns")
        
        self._create_basic_info_tab()
        self._create_spellcasting_tab()
        self._create_level_features_tab()
        self._create_class_features_tab()
        self._create_custom_columns_tab()
        
        # Button frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)
        
        btn_text = self.theme.get_current_color('text_primary')
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save Class", width=120,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_save_class
        ).pack(side="right")
    
    def _create_basic_info_tab(self):
        """Create the basic info tab."""
        tab = self.tabview.tab("Basic Info")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        # Name
        ctk.CTkLabel(scroll, text="Class Name *", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Fighter")
        self.name_entry.pack(fill="x", pady=(0, 15))
        
        # Hit Die
        hit_die_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        hit_die_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(hit_die_frame, text="Hit Die *", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.hit_die_var = ctk.StringVar(value="d8")
        self.hit_die_combo = ctk.CTkComboBox(
            hit_die_frame, variable=self.hit_die_var,
            values=["d6", "d8", "d10", "d12"],
            width=100
        )
        self.hit_die_combo.pack(side="left", padx=(15, 0))
        
        # Primary Ability
        ctk.CTkLabel(scroll, text="Primary Ability", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.primary_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Strength or Dexterity")
        self.primary_entry.pack(fill="x", pady=(0, 15))
        
        # Saving Throws
        ctk.CTkLabel(scroll, text="Saving Throw Proficiencies", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        
        saves_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        saves_frame.pack(fill="x", pady=(0, 15))
        
        self.save_vars = {}
        for save in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
            var = ctk.BooleanVar(value=False)
            self.save_vars[save] = var
            ctk.CTkCheckBox(saves_frame, text=save, variable=var, width=70).pack(side="left", padx=(0, 10))
        
        # Armor Proficiencies
        ctk.CTkLabel(scroll, text="Armor Proficiencies (comma-separated)", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.armor_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Light armor, Medium armor, Shields")
        self.armor_entry.pack(fill="x", pady=(0, 15))
        
        # Weapon Proficiencies
        ctk.CTkLabel(scroll, text="Weapon Proficiencies (comma-separated)", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.weapon_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Simple weapons, Martial weapons")
        self.weapon_entry.pack(fill="x", pady=(0, 15))
        
        # Tool Proficiencies
        ctk.CTkLabel(scroll, text="Tool Proficiencies (comma-separated)", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.tool_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Thieves' Tools")
        self.tool_entry.pack(fill="x", pady=(0, 15))
        
        # Skill choices
        skill_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        skill_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(skill_frame, text="Skill Choices:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.skill_choices_entry = ctk.CTkEntry(skill_frame, width=60, height=35, placeholder_text="2")
        self.skill_choices_entry.pack(side="left", padx=(10, 0))
        
        ctk.CTkLabel(scroll, text="Skill Options (comma-separated)", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.skill_options_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Acrobatics, Athletics, Intimidation")
        self.skill_options_entry.pack(fill="x", pady=(0, 15))
        
        # Subclass Level
        subclass_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        subclass_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(subclass_frame, text="Subclass Level:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.subclass_level_var = ctk.StringVar(value="3")
        self.subclass_level_combo = ctk.CTkComboBox(
            subclass_frame, variable=self.subclass_level_var,
            values=[str(i) for i in range(1, 11)],
            width=80
        )
        self.subclass_level_combo.pack(side="left", padx=(10, 0))
        
        ctk.CTkLabel(subclass_frame, text="Subclass Name:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(30, 0))
        self.subclass_name_entry = ctk.CTkEntry(subclass_frame, width=200, height=35, placeholder_text="e.g., Martial Archetype")
        self.subclass_name_entry.pack(side="left", padx=(10, 0))
        
        # Description
        ctk.CTkLabel(scroll, text="Description", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.description_text = ctk.CTkTextbox(scroll, height=120, font=ctk.CTkFont(size=12))
        self.description_text.pack(fill="x", pady=(0, 15))
        
        # Source
        ctk.CTkLabel(scroll, text="Source", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
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
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_caster_toggle
        )
        caster_cb.pack(fill="x", pady=(0, 20))
        
        # Spellcasting options frame (enabled/disabled based on toggle)
        self.spell_options_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.spell_options_frame.pack(fill="both", expand=True)
        
        # Spellcasting Ability
        ability_frame = ctk.CTkFrame(self.spell_options_frame, fg_color="transparent")
        ability_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(ability_frame, text="Spellcasting Ability:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
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
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(fill="x", pady=(0, 10))
        
        self.slot_progression_var = ctk.StringVar(value="none")
        
        prog_frame = ctk.CTkFrame(self.spell_options_frame, fg_color="transparent")
        prog_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkRadioButton(
            prog_frame, text="Full Caster (Wizard/Cleric/etc.)",
            variable=self.slot_progression_var, value="full",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=3)
        
        ctk.CTkRadioButton(
            prog_frame, text="Half Caster (Paladin/Ranger)",
            variable=self.slot_progression_var, value="half",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=3)
        
        ctk.CTkRadioButton(
            prog_frame, text="Custom (configure manually)",
            variable=self.slot_progression_var, value="custom",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=3)
        
        # Note about custom
        ctk.CTkLabel(
            self.spell_options_frame,
            text="Note: Custom spell slots can be configured in the Level Features tab.",
            font=ctk.CTkFont(size=11),
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
        """Create the level features tab."""
        tab = self.tabview.tab("Level Features")
        
        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, text="Click a level to edit its features",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(side="left")
        
        # Levels grid
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        # Create 4 columns of 5 levels each
        scroll.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.level_buttons = {}
        for lvl in range(1, 21):
            row = (lvl - 1) % 5
            col = (lvl - 1) // 5
            
            btn = ctk.CTkButton(
                scroll, text=f"Level {lvl}",
                fg_color=self.theme.get_current_color('bg_secondary'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                height=40,
                command=lambda l=lvl: self._edit_level(l)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            self.level_buttons[lvl] = btn
    
    def _edit_level(self, level: int):
        """Open editor for a specific level."""
        data = self._level_data.get(level, {"features": [], "class_specific": {}})
        
        # Include custom columns in class_specific
        for col in self._custom_columns:
            if col not in data["class_specific"]:
                data["class_specific"][col] = "-"
        
        dialog = LevelFeaturesEditorDialog(
            self, level,
            data["features"],
            data["class_specific"]
        )
        self.wait_window(dialog)
        
        if dialog.result:
            self._level_data[level] = dialog.result
            # Update button color to show it has features
            if dialog.result["features"]:
                self.level_buttons[level].configure(
                    fg_color=self.theme.get_current_color('accent_primary')
                )
    
    def _create_class_features_tab(self):
        """Create the class features widget configuration tab."""
        tab = self.tabview.tab("Class Features Widget")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            scroll, text="Trackable Features (max 3)",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            scroll,
            text="These features appear in the Class Features widget on the character sheet.",
            font=ctk.CTkFont(size=12),
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
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=15)
            return
        
        for idx, feature in enumerate(self._trackable_features):
            row = ctk.CTkFrame(self.trackable_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(
                row, text=f"{feature.title} ({feature.tracked_value})",
                font=ctk.CTkFont(size=13, weight="bold"),
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
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            scroll,
            text="Add custom columns to the class features table (e.g., Rage Damage, Martial Arts Die).",
            font=ctk.CTkFont(size=12),
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
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=15)
            return
        
        for idx, col_name in enumerate(self._custom_columns):
            row = ctk.CTkFrame(self.columns_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(
                row, text=col_name,
                font=ctk.CTkFont(size=13, weight="bold"),
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
        self.skill_options_entry.insert(0, ", ".join(class_def.skill_proficiency_options))
        
        self.subclass_level_var.set(str(class_def.subclass_level))
        self.subclass_name_entry.insert(0, class_def.subclass_name)
        
        self.description_text.insert("1.0", class_def.description)
        self.source_entry.insert(0, class_def.source)
        
        # Spellcasting
        self.is_caster_var.set(class_def.is_spellcaster)
        if class_def.spellcasting_ability:
            self.spell_ability_var.set(class_def.spellcasting_ability)
        self._on_caster_toggle()
        
        # Update level buttons
        for lvl, data in self._level_data.items():
            if data["features"]:
                self.level_buttons[lvl].configure(
                    fg_color=self.theme.get_current_color('accent_primary')
                )
        
        # Refresh trackable features and columns
        self._refresh_trackable_features()
        self._refresh_columns()
    
    def _on_save_class(self):
        """Save the class."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a class name.", parent=self)
            return
        
        # Build levels dict
        levels = {}
        is_caster = self.is_caster_var.get()
        progression = self.slot_progression_var.get()
        
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
            
            levels[lvl] = ClassLevel(
                level=lvl,
                abilities=data["features"],
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
            skill_proficiency_choices=int(self.skill_choices_entry.get() or "2"),
            skill_proficiency_options=[s.strip() for s in self.skill_options_entry.get().split(",") if s.strip()],
            description=self.description_text.get("1.0", "end-1c").strip(),
            is_spellcaster=is_caster,
            spellcasting_ability=self.spell_ability_var.get() if is_caster else "",
            subclass_level=int(self.subclass_level_var.get()),
            subclass_name=self.subclass_name_entry.get().strip(),
            subclasses=self._class_def.subclasses if self._class_def else [],
            levels=levels,
            trackable_features=self._trackable_features,
            class_table_columns=self._custom_columns,
            is_custom=True,
            source=self.source_entry.get().strip() or "Custom"
        )
        
        self.result = class_def
        
        # Save to manager
        manager = get_class_manager()
        manager.add_class(class_def)
        
        if self._on_save:
            self._on_save(class_def)
        
        self.destroy()


class SubclassEditorDialog(ctk.CTkToplevel):
    """Dialog for creating or editing a subclass."""
    
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
        
        btn_text = self.theme.get_current_color('text_primary')
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save Subclass", width=120,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_save_subclass
        ).pack(side="right")
    
    def _create_basic_tab(self):
        """Create the basic info tab."""
        tab = self.tabview.tab("Basic Info")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        # Name
        ctk.CTkLabel(scroll, text="Subclass Name *", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Path of the Berserker")
        self.name_entry.pack(fill="x", pady=(0, 15))
        
        # Parent Class (read-only)
        ctk.CTkLabel(scroll, text="Parent Class", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        parent_label = ctk.CTkLabel(
            scroll, text=self._parent_class.name,
            font=ctk.CTkFont(size=14),
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=6, height=35
        )
        parent_label.pack(fill="x", pady=(0, 15))
        
        # Description
        ctk.CTkLabel(scroll, text="Description", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.description_text = ctk.CTkTextbox(scroll, height=150, font=ctk.CTkFont(size=12))
        self.description_text.pack(fill="x", pady=(0, 15))
        
        # Source
        ctk.CTkLabel(scroll, text="Source", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.source_entry = ctk.CTkEntry(scroll, height=35, placeholder_text="e.g., Player's Handbook (2024)")
        self.source_entry.pack(fill="x", pady=(0, 15))
    
    def _create_features_tab(self):
        """Create the features tab."""
        tab = self.tabview.tab("Features")
        
        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, text="Subclass Features",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
        
        btn_text = self.theme.get_current_color('text_primary')
        ctk.CTkButton(
            header, text="+ Add Feature", width=120,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._add_subclass_feature
        ).pack(side="right")
        
        # Features list
        self.features_scroll = ctk.CTkScrollableFrame(
            tab, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.features_scroll.pack(fill="both", expand=True)
        
        self._refresh_features()
    
    def _refresh_features(self):
        """Refresh the features list."""
        for widget in self.features_scroll.winfo_children():
            widget.destroy()
        
        if not self._features:
            ctk.CTkLabel(
                self.features_scroll,
                text="No features defined. Click '+ Add Feature' to add one.",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(padx=15, pady=20)
            return
        
        # Sort by level
        sorted_features = sorted(self._features, key=lambda f: f.level)
        
        for idx, feature in enumerate(sorted_features):
            row = ctk.CTkFrame(self.features_scroll, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(
                row, text=f"Level {feature.level}: {feature.title}",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            ).pack(side="left", fill="x", expand=True)
            
            btn_text = self.theme.get_current_color('text_primary')
            
            # Find original index
            orig_idx = self._features.index(feature)
            
            ctk.CTkButton(
                row, text="Edit", width=60,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=btn_text,
                command=lambda i=orig_idx: self._edit_subclass_feature(i)
            ).pack(side="right", padx=(5, 0))
            
            ctk.CTkButton(
                row, text="Delete", width=60,
                fg_color=self.theme.get_current_color('button_danger'),
                hover_color=self.theme.get_current_color('button_danger_hover'),
                text_color=btn_text,
                command=lambda i=orig_idx: self._delete_subclass_feature(i)
            ).pack(side="right")
    
    def _add_subclass_feature(self):
        """Add a new subclass feature."""
        dialog = SubclassFeatureEditorDialog(self, self._parent_class.subclass_level)
        self.wait_window(dialog)
        
        if dialog.result:
            self._features.append(dialog.result)
            self._refresh_features()
    
    def _edit_subclass_feature(self, idx: int):
        """Edit a subclass feature."""
        dialog = SubclassFeatureEditorDialog(
            self, self._parent_class.subclass_level, self._features[idx]
        )
        self.wait_window(dialog)
        
        if dialog.result:
            self._features[idx] = dialog.result
            self._refresh_features()
    
    def _delete_subclass_feature(self, idx: int):
        """Delete a subclass feature."""
        if messagebox.askyesno("Confirm Delete", "Delete this feature?", parent=self):
            del self._features[idx]
            self._refresh_features()
    
    def _create_spells_tab(self):
        """Create the spell list tab."""
        tab = self.tabview.tab("Spell List")
        
        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, text="Subclass Spells (Always Prepared)",
            font=ctk.CTkFont(size=16, weight="bold")
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
            font=ctk.CTkFont(size=11),
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
                font=ctk.CTkFont(size=12),
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
                font=ctk.CTkFont(size=12),
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
    
    def _on_save_subclass(self):
        """Save the subclass."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a subclass name.", parent=self)
            return
        
        subclass = SubclassDefinition(
            name=name,
            parent_class=self._parent_class.name,
            description=self.description_text.get("1.0", "end-1c").strip(),
            features=self._features,
            subclass_spells=self._spells,
            source=self.source_entry.get().strip() or "Custom",
            is_custom=True
        )
        
        self.result = subclass
        
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
        
        self.destroy()


class SubclassFeatureEditorDialog(ctk.CTkToplevel):
    """Dialog for editing a single subclass feature."""
    
    def __init__(self, parent, min_level: int = 1, feature: Optional[SubclassFeature] = None):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[SubclassFeature] = None
        self._min_level = min_level
        
        self.title("Edit Feature" if feature else "Add Feature")
        self.geometry("600x500")
        self.minsize(500, 400)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        if feature:
            self._populate(feature)
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 600) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 500) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets."""
        from ui.rich_text_utils import RichTextEditor
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Level
        level_frame = ctk.CTkFrame(container, fg_color="transparent")
        level_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(level_frame, text="Level *", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.level_var = ctk.StringVar(value=str(self._min_level))
        self.level_combo = ctk.CTkComboBox(
            level_frame, variable=self.level_var,
            values=[str(i) for i in range(self._min_level, 21)],
            width=80
        )
        self.level_combo.pack(side="left", padx=(15, 0))
        
        # Title
        ctk.CTkLabel(container, text="Feature Title *", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.title_entry = ctk.CTkEntry(container, height=35, placeholder_text="e.g., Frenzy")
        self.title_entry.pack(fill="x", pady=(0, 15))
        
        # Description with rich text toolbar
        ctk.CTkLabel(container, text="Description *", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        
        self.description_text = ctk.CTkTextbox(container, height=180, font=ctk.CTkFont(size=12))
        self._rich_editor = RichTextEditor(self, self.description_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(container)
        toolbar.pack(fill="x", pady=(0, 5))
        
        self.description_text.pack(fill="both", expand=True, pady=(0, 15))
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        btn_text = self.theme.get_current_color('text_primary')
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_save
        ).pack(side="right")
    
    def _populate(self, feature: SubclassFeature):
        """Populate from existing feature."""
        self.level_var.set(str(feature.level))
        self.title_entry.insert(0, feature.title)
        self.description_text.insert("1.0", feature.description)
    
    def _on_save(self):
        """Save the feature."""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("Warning", "Please enter a feature title.", parent=self)
            return
        
        description = self.description_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showwarning("Warning", "Please enter a description.", parent=self)
            return
        
        self.result = SubclassFeature(
            level=int(self.level_var.get()),
            title=title,
            description=description,
            tables=[]
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
        ctk.CTkLabel(container, text="Spell Name *", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(container, height=35, placeholder_text="e.g., Bless")
        self.name_entry.pack(fill="x", pady=(0, 15))
        
        # Level Gained
        level_frame = ctk.CTkFrame(container, fg_color="transparent")
        level_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(level_frame, text="Level Gained *", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
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
        
        btn_text = self.theme.get_current_color('text_primary')
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Add", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_save
        ).pack(side="right")
    
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
