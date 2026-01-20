"""
Stat Block Editor Dialog for D&D Spellbook Application.
Dialog for creating and editing creature stat blocks.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, List
from stat_block import StatBlock, AbilityScores, Ability, StatBlockFeature
from theme import get_theme_manager


class FeatureEditorDialog(ctk.CTkToplevel):
    """Dialog for editing a single feature (trait, action, etc.)."""
    
    def __init__(self, parent, title: str = "Edit Feature", 
                 feature: Optional[StatBlockFeature] = None):
        super().__init__(parent)
        
        self.result: Optional[StatBlockFeature] = None
        
        self.title(title)
        self.geometry("500x300")
        self.minsize(400, 250)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets(feature)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self, feature: Optional[StatBlockFeature]):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Name
        ctk.CTkLabel(container, text="Name:", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(container, height=35, placeholder_text="e.g., Multiattack")
        self.name_entry.pack(fill="x", pady=(0, 15))
        
        # Description
        ctk.CTkLabel(container, text="Description:", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(0, 5))
        self.desc_text = ctk.CTkTextbox(container, height=100)
        self.desc_text.pack(fill="both", expand=True, pady=(0, 15))
        
        # Populate if editing
        if feature:
            self.name_entry.insert(0, feature.name)
            self.desc_text.insert("1.0", feature.description)
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(btn_frame, text="Cancel", width=80, command=self.destroy).pack(side="right", padx=(10, 0))
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self._on_save).pack(side="right")
    
    def _on_save(self):
        """Save the feature."""
        name = self.name_entry.get().strip()
        description = self.desc_text.get("1.0", "end").strip()
        
        if not name:
            messagebox.showerror("Validation Error", "Name is required.", parent=self)
            return
        
        self.result = StatBlockFeature(name=name, description=description)
        self.destroy()


class FeatureListEditor(ctk.CTkFrame):
    """Widget for editing a list of features."""
    
    def __init__(self, parent, title: str, features: Optional[List[StatBlockFeature]] = None):
        super().__init__(parent, fg_color="transparent")
        
        self._features = features or []
        self._title = title
        
        self._create_widgets()
        self._update_list()
    
    def _create_widgets(self):
        """Create widgets."""
        # Header with title and add button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(header, text=f"{self._title}:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add", width=60, height=24, command=self._add_feature).pack(side="right")
        
        # List of features
        self.list_frame = ctk.CTkScrollableFrame(self, height=100)
        self.list_frame.pack(fill="both", expand=True)
    
    def _update_list(self):
        """Update the feature list display."""
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        
        if not self._features:
            ctk.CTkLabel(
                self.list_frame, 
                text=f"No {self._title.lower()}",
                text_color=get_theme_manager().get_text_secondary()
            ).pack(pady=10)
            return
        
        for i, feature in enumerate(self._features):
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            ctk.CTkLabel(
                row, text=feature.name,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w", width=150
            ).pack(side="left")
            
            ctk.CTkButton(
                row, text="Edit", width=50, height=22,
                command=lambda idx=i: self._edit_feature(idx)
            ).pack(side="right", padx=2)
            
            ctk.CTkButton(
                row, text="×", width=30, height=22,
                fg_color="darkred", hover_color="red",
                command=lambda idx=i: self._delete_feature(idx)
            ).pack(side="right", padx=2)
    
    def _add_feature(self):
        """Add a new feature."""
        dialog = FeatureEditorDialog(self.winfo_toplevel(), f"Add {self._title[:-1] if self._title.endswith('s') else self._title}")
        self.wait_window(dialog)
        
        if dialog.result:
            self._features.append(dialog.result)
            self._update_list()
    
    def _edit_feature(self, index: int):
        """Edit an existing feature."""
        dialog = FeatureEditorDialog(
            self.winfo_toplevel(), 
            f"Edit {self._title[:-1] if self._title.endswith('s') else self._title}",
            self._features[index]
        )
        self.wait_window(dialog)
        
        if dialog.result:
            self._features[index] = dialog.result
            self._update_list()
    
    def _delete_feature(self, index: int):
        """Delete a feature."""
        del self._features[index]
        self._update_list()
    
    def get_features(self) -> List[StatBlockFeature]:
        """Get the current list of features."""
        return self._features.copy()


class StatBlockEditorDialog(ctk.CTkToplevel):
    """Dialog for creating or editing a creature stat block."""
    
    def __init__(self, parent, title: str = "Edit Stat Block", 
                 stat_block: Optional[StatBlock] = None,
                 spell_id: Optional[int] = None):
        super().__init__(parent)
        
        self.result: Optional[StatBlock] = None
        self._original = stat_block
        self._spell_id = spell_id or (stat_block.spell_id if stat_block else None)
        
        self.title(title)
        self.geometry("700x800")
        self.minsize(600, 700)
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        if stat_block:
            self._populate_from_stat_block(stat_block)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create all dialog widgets."""
        # Main scrollable container
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=15, pady=(15, 5))
        
        container = scroll
        
        # === Identity Section ===
        self._create_section_header(container, "Identity")
        
        # Name
        ctk.CTkLabel(container, text="Creature Name *", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(5, 2))
        self.name_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., Bestial Spirit")
        self.name_entry.pack(fill="x", pady=(0, 10))
        
        # Size and Type row
        row1 = ctk.CTkFrame(container, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))
        
        size_frame = ctk.CTkFrame(row1, fg_color="transparent")
        size_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(size_frame, text="Size", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.size_combo = ctk.CTkComboBox(
            size_frame, 
            values=["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"],
            height=32
        )
        self.size_combo.set("Medium")
        self.size_combo.pack(fill="x")
        
        type_frame = ctk.CTkFrame(row1, fg_color="transparent")
        type_frame.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(type_frame, text="Creature Type", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.type_entry = ctk.CTkEntry(type_frame, height=32, placeholder_text="e.g., Beast, Fiend")
        self.type_entry.pack(fill="x")
        
        # Subtype and Alignment row
        row2 = ctk.CTkFrame(container, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 10))
        
        subtype_frame = ctk.CTkFrame(row2, fg_color="transparent")
        subtype_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(subtype_frame, text="Subtype (optional)", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.subtype_entry = ctk.CTkEntry(subtype_frame, height=32, placeholder_text="e.g., Celestial, Fey, or Fiend")
        self.subtype_entry.pack(fill="x")
        
        align_frame = ctk.CTkFrame(row2, fg_color="transparent")
        align_frame.pack(side="left", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(align_frame, text="Alignment", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.alignment_entry = ctk.CTkEntry(align_frame, height=32, placeholder_text="e.g., Neutral")
        self.alignment_entry.insert(0, "Neutral")
        self.alignment_entry.pack(fill="x")
        
        # === Core Stats Section ===
        self._create_section_header(container, "Core Stats")
        
        # AC, HP, Speed
        ctk.CTkLabel(container, text="Armor Class", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(5, 2))
        self.ac_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., 11 + the spell's level")
        self.ac_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(container, text="Hit Points", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        self.hp_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., 30 + 10 for each spell level above 3")
        self.hp_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(container, text="Speed", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        self.speed_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., 30 ft., Fly 60 ft.")
        self.speed_entry.pack(fill="x", pady=(0, 10))
        
        # === Ability Scores Section ===
        self._create_section_header(container, "Ability Scores")
        
        abilities_frame = ctk.CTkFrame(container, fg_color="transparent")
        abilities_frame.pack(fill="x", pady=(5, 10))
        
        self.ability_entries = {}
        for ability in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
            col = ctk.CTkFrame(abilities_frame, fg_color="transparent")
            col.pack(side="left", expand=True, fill="x", padx=2)
            ctk.CTkLabel(col, text=ability, font=ctk.CTkFont(size=11, weight="bold")).pack()
            entry = ctk.CTkEntry(col, height=28, width=50, justify="center")
            entry.insert(0, "10")
            entry.pack()
            self.ability_entries[ability] = entry
        
        # === Defenses Section ===
        self._create_section_header(container, "Defenses")
        
        ctk.CTkLabel(container, text="Damage Resistances", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(5, 2))
        self.resistances_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., Fire, Necrotic")
        self.resistances_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(container, text="Damage Immunities", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        self.immunities_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., Poison; Poisoned")
        self.immunities_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(container, text="Condition Immunities", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        self.cond_immunities_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., Charmed, Frightened")
        self.cond_immunities_entry.pack(fill="x", pady=(0, 10))
        
        # === Senses & Languages Section ===
        self._create_section_header(container, "Senses & Languages")
        
        ctk.CTkLabel(container, text="Senses", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(5, 2))
        self.senses_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., Darkvision 60 ft., Passive Perception 10")
        self.senses_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(container, text="Languages", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        self.languages_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., understands the languages you know")
        self.languages_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(container, text="Challenge Rating", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(0, 2))
        self.cr_entry = ctk.CTkEntry(container, height=32, placeholder_text="e.g., None (XP 0; PB equals your Proficiency Bonus)")
        self.cr_entry.pack(fill="x", pady=(0, 10))
        
        # === Features Section ===
        self._create_section_header(container, "Features")
        
        self.traits_editor = FeatureListEditor(container, "Traits")
        self.traits_editor.pack(fill="x", pady=(5, 10))
        
        self.actions_editor = FeatureListEditor(container, "Actions")
        self.actions_editor.pack(fill="x", pady=(0, 10))
        
        self.bonus_actions_editor = FeatureListEditor(container, "Bonus Actions")
        self.bonus_actions_editor.pack(fill="x", pady=(0, 10))
        
        self.reactions_editor = FeatureListEditor(container, "Reactions")
        self.reactions_editor.pack(fill="x", pady=(0, 10))
        
        # Button frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkButton(btn_frame, text="Cancel", width=100, command=self.destroy).pack(side="right", padx=(10, 0))
        ctk.CTkButton(btn_frame, text="Save", width=100, command=self._on_save).pack(side="right")
    
    def _create_section_header(self, parent, text: str):
        """Create a section header with a line."""
        theme = get_theme_manager()
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(15, 5))
        
        ctk.CTkLabel(
            frame, text=text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=theme.get_current_color('accent_primary')
        ).pack(side="left")
        
        sep = ctk.CTkFrame(frame, height=2, fg_color=theme.get_current_color('border'))
        sep.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=8)
    
    def _populate_from_stat_block(self, sb: StatBlock):
        """Populate fields from an existing stat block."""
        self.name_entry.insert(0, sb.name)
        self.size_combo.set(sb.size)
        self.type_entry.insert(0, sb.creature_type)
        self.subtype_entry.insert(0, sb.creature_subtype)
        
        self.alignment_entry.delete(0, "end")
        self.alignment_entry.insert(0, sb.alignment)
        
        self.ac_entry.insert(0, sb.armor_class)
        self.hp_entry.insert(0, sb.hit_points)
        self.speed_entry.insert(0, sb.speed)
        
        if sb.abilities:
            self.ability_entries["STR"].delete(0, "end")
            self.ability_entries["STR"].insert(0, str(sb.abilities.strength.score))
            self.ability_entries["DEX"].delete(0, "end")
            self.ability_entries["DEX"].insert(0, str(sb.abilities.dexterity.score))
            self.ability_entries["CON"].delete(0, "end")
            self.ability_entries["CON"].insert(0, str(sb.abilities.constitution.score))
            self.ability_entries["INT"].delete(0, "end")
            self.ability_entries["INT"].insert(0, str(sb.abilities.intelligence.score))
            self.ability_entries["WIS"].delete(0, "end")
            self.ability_entries["WIS"].insert(0, str(sb.abilities.wisdom.score))
            self.ability_entries["CHA"].delete(0, "end")
            self.ability_entries["CHA"].insert(0, str(sb.abilities.charisma.score))
        
        self.resistances_entry.insert(0, sb.damage_resistances)
        self.immunities_entry.insert(0, sb.damage_immunities)
        self.cond_immunities_entry.insert(0, sb.condition_immunities)
        self.senses_entry.insert(0, sb.senses)
        self.languages_entry.insert(0, sb.languages)
        self.cr_entry.insert(0, sb.challenge_rating)
        
        # Set features
        self.traits_editor._features = list(sb.traits)
        self.traits_editor._update_list()
        self.actions_editor._features = list(sb.actions)
        self.actions_editor._update_list()
        self.bonus_actions_editor._features = list(sb.bonus_actions)
        self.bonus_actions_editor._update_list()
        self.reactions_editor._features = list(sb.reactions)
        self.reactions_editor._update_list()
    
    def _on_save(self):
        """Validate and save the stat block."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Validation Error", "Creature name is required.", parent=self)
            return
        
        # Parse ability scores
        try:
            abilities = AbilityScores.from_scores(
                str_=int(self.ability_entries["STR"].get() or 10),
                dex=int(self.ability_entries["DEX"].get() or 10),
                con=int(self.ability_entries["CON"].get() or 10),
                int_=int(self.ability_entries["INT"].get() or 10),
                wis=int(self.ability_entries["WIS"].get() or 10),
                cha=int(self.ability_entries["CHA"].get() or 10)
            )
        except ValueError:
            messagebox.showerror("Validation Error", "Ability scores must be numbers.", parent=self)
            return
        
        self.result = StatBlock(
            id=self._original.id if self._original else None,
            spell_id=self._spell_id,
            name=name,
            size=self.size_combo.get(),
            creature_type=self.type_entry.get().strip(),
            creature_subtype=self.subtype_entry.get().strip(),
            alignment=self.alignment_entry.get().strip() or "Neutral",
            armor_class=self.ac_entry.get().strip(),
            hit_points=self.hp_entry.get().strip(),
            speed=self.speed_entry.get().strip(),
            abilities=abilities,
            damage_resistances=self.resistances_entry.get().strip(),
            damage_immunities=self.immunities_entry.get().strip(),
            condition_immunities=self.cond_immunities_entry.get().strip(),
            senses=self.senses_entry.get().strip(),
            languages=self.languages_entry.get().strip(),
            challenge_rating=self.cr_entry.get().strip(),
            traits=self.traits_editor.get_features(),
            actions=self.actions_editor.get_features(),
            bonus_actions=self.bonus_actions_editor.get_features(),
            reactions=self.reactions_editor.get_features()
        )
        
        self.destroy()
