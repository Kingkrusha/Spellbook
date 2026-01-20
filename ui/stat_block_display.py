"""
Stat Block Display Widget for D&D Spellbook Application.
Shows creature stat blocks in traditional D&D 5e style.
"""

import customtkinter as ctk
from typing import Optional, Callable, List
from stat_block import StatBlock, AbilityScores
from theme import get_theme_manager


class StatBlockDisplay(ctk.CTkFrame):
    """
    A widget that displays a D&D 5e creature stat block.
    Styled to match the traditional PHB/MM appearance.
    """
    
    def __init__(self, parent, stat_block: Optional[StatBlock] = None,
                 on_edit: Optional[Callable[[StatBlock], None]] = None,
                 on_delete: Optional[Callable[[StatBlock], None]] = None,
                 collapsed: bool = False):
        super().__init__(parent, corner_radius=8)
        
        self._stat_block = stat_block
        self.on_edit = on_edit
        self.on_delete = on_delete
        self._is_collapsed = collapsed
        
        self._create_widgets()
        if stat_block:
            self.set_stat_block(stat_block)
        
        # Apply initial collapsed state
        if collapsed:
            self._collapse_content()
    
    def _create_widgets(self):
        """Create the stat block display widgets."""
        theme = get_theme_manager()
        
        # Main container with parchment-like background
        self.container = ctk.CTkFrame(self, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
        self.container.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Header with creature name (always visible)
        self.header_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Toggle button for collapse/expand
        self.toggle_btn = ctk.CTkButton(
            self.header_frame,
            text="▼",
            width=24, height=24,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self.toggle_collapse
        )
        self.toggle_btn.pack(side="left", padx=(0, 5))
        
        self.name_label = ctk.CTkLabel(
            self.header_frame, 
            text="",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        self.name_label.pack(side="left", fill="x", expand=True)
        
        # Edit/Delete buttons (optional)
        self.btn_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.btn_frame.pack(side="right")
        
        self.edit_btn = ctk.CTkButton(
            self.btn_frame, text="Edit", width=50, height=24,
            font=ctk.CTkFont(size=11),
            command=self._on_edit_click
        )
        
        self.delete_btn = ctk.CTkButton(
            self.btn_frame, text="Delete", width=60, height=24,
            font=ctk.CTkFont(size=11),
            fg_color="darkred", hover_color="red",
            command=self._on_delete_click
        )
        
        # Collapsible content frame (contains everything except header)
        self.content_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.content_frame.pack(fill="x")
        
        # Type line (e.g., "Medium Undead, Neutral") - with wrapping support
        self.type_label = ctk.CTkLabel(
            self.content_frame, text="",
            font=ctk.CTkFont(size=12, slant="italic"),
            anchor="w",
            wraplength=450,
            justify="left"
        )
        self.type_label.pack(fill="x", padx=10, pady=(0, 5))
        
        # Separator
        self._create_separator(self.content_frame)
        
        # Core stats frame (AC, HP, Speed)
        self.core_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.core_frame.pack(fill="x", padx=10, pady=5)
        
        self.ac_label = self._create_stat_row(self.core_frame, "Armor Class")
        self.hp_label = self._create_stat_row(self.core_frame, "Hit Points")
        self.speed_label = self._create_stat_row(self.core_frame, "Speed")
        
        # Separator
        self._create_separator(self.content_frame)
        
        # Ability scores
        self.abilities_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.abilities_frame.pack(fill="x", padx=10, pady=5)
        
        # Create ability score headers
        abilities = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        self.ability_labels = {}
        
        for i, ability in enumerate(abilities):
            col_frame = ctk.CTkFrame(self.abilities_frame, fg_color="transparent")
            col_frame.pack(side="left", expand=True, fill="x")
            
            ctk.CTkLabel(
                col_frame, text=ability,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="center"
            ).pack()
            
            self.ability_labels[ability] = ctk.CTkLabel(
                col_frame, text="10 (+0)",
                font=ctk.CTkFont(size=11),
                anchor="center"
            )
            self.ability_labels[ability].pack()
        
        # Separator
        self._create_separator(self.content_frame)
        
        # Defenses, senses, languages, CR
        self.details_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.details_frame.pack(fill="x", padx=10, pady=5)
        
        self.resistances_label = self._create_stat_row(self.details_frame, "Damage Resistances", hide_if_empty=True)
        self.immunities_label = self._create_stat_row(self.details_frame, "Damage Immunities", hide_if_empty=True)
        self.condition_immunities_label = self._create_stat_row(self.details_frame, "Condition Immunities", hide_if_empty=True)
        self.senses_label = self._create_stat_row(self.details_frame, "Senses", hide_if_empty=True)
        self.languages_label = self._create_stat_row(self.details_frame, "Languages", hide_if_empty=True)
        self.cr_label = self._create_stat_row(self.details_frame, "Challenge", hide_if_empty=True)
        
        # Separator
        self._create_separator(self.content_frame)
        
        # Features section (traits, actions, etc.)
        self.features_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.features_frame.pack(fill="x", padx=10, pady=5)
    
    def _create_separator(self, parent):
        """Create a horizontal separator line."""
        theme = get_theme_manager()
        sep = ctk.CTkFrame(parent, height=2, fg_color=theme.get_current_color('border'))
        sep.pack(fill="x", padx=10, pady=5)
    
    def _create_stat_row(self, parent, label_text: str, hide_if_empty: bool = False) -> ctk.CTkLabel:
        """Create a label row for a stat (e.g., 'Armor Class: 13')."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)
        
        label = ctk.CTkLabel(
            row, text=f"{label_text}:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", width=140
        )
        label.pack(side="left")
        
        value = ctk.CTkLabel(
            row, text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        value.pack(side="left", fill="x", expand=True)
        
        if hide_if_empty:
            row._hide_if_empty = True  # type: ignore[attr-defined]
            row._value_label = value  # type: ignore[attr-defined]
        
        return value
    
    def _create_feature_section(self, parent, title: str, features: list, is_section_header: bool = True):
        """Create a section for traits/actions/etc."""
        if not features:
            return
        
        # Section header (optional)
        if is_section_header and title:
            header = ctk.CTkLabel(
                parent, text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w"
            )
            header.pack(fill="x", pady=(10, 3))
        
        # Features
        for feature in features:
            feature_frame = ctk.CTkFrame(parent, fg_color="transparent")
            feature_frame.pack(fill="x", pady=(3, 3))
            
            name = feature.get('name', '') if isinstance(feature, dict) else feature.name
            desc = feature.get('description', '') if isinstance(feature, dict) else feature.description
            
            # Create a text widget approach - name and description in one label with formatting
            # Format: "Name. Description" where Name is conceptually bold/italic
            combined_text = f"{name}.  {desc}"
            
            # Use a single label with the combined text, wrapping enabled
            combined_label = ctk.CTkLabel(
                feature_frame, 
                text=combined_text,
                font=ctk.CTkFont(size=12),
                anchor="w", 
                wraplength=450, 
                justify="left"
            )
            combined_label.pack(fill="x", expand=True)
            
            # Store reference to name for potential styling
            feature_frame._feature_name = name  # type: ignore[attr-defined]
    
    def set_stat_block(self, stat_block: Optional[StatBlock]):
        """Update the display with a new stat block."""
        self._stat_block = stat_block
        
        if not stat_block:
            self.name_label.configure(text="No stat block")
            return
        
        # Update name and type
        self.name_label.configure(text=stat_block.name)
        self.type_label.configure(text=stat_block.get_type_line())
        
        # Update core stats
        self.ac_label.configure(text=stat_block.armor_class)
        self.hp_label.configure(text=stat_block.hit_points)
        self.speed_label.configure(text=stat_block.speed)
        
        # Update ability scores
        if stat_block.abilities:
            abilities = stat_block.abilities
            self.ability_labels["STR"].configure(text=abilities.strength.display())
            self.ability_labels["DEX"].configure(text=abilities.dexterity.display())
            self.ability_labels["CON"].configure(text=abilities.constitution.display())
            self.ability_labels["INT"].configure(text=abilities.intelligence.display())
            self.ability_labels["WIS"].configure(text=abilities.wisdom.display())
            self.ability_labels["CHA"].configure(text=abilities.charisma.display())
        
        # Update defenses and details
        self._update_conditional_label(self.resistances_label, stat_block.damage_resistances)
        self._update_conditional_label(self.immunities_label, stat_block.damage_immunities)
        self._update_conditional_label(self.condition_immunities_label, stat_block.condition_immunities)
        self._update_conditional_label(self.senses_label, stat_block.senses)
        self._update_conditional_label(self.languages_label, stat_block.languages)
        self._update_conditional_label(self.cr_label, stat_block.challenge_rating)
        
        # Clear and rebuild features
        for widget in self.features_frame.winfo_children():
            widget.destroy()
        
        # Add traits (no header for traits, they come first)
        if stat_block.traits:
            self._create_feature_section(self.features_frame, "", stat_block.traits, is_section_header=False)
        
        # Add actions
        if stat_block.actions:
            self._create_feature_section(self.features_frame, "Actions", stat_block.actions)
        
        # Add bonus actions
        if stat_block.bonus_actions:
            self._create_feature_section(self.features_frame, "Bonus Actions", stat_block.bonus_actions)
        
        # Add reactions
        if stat_block.reactions:
            self._create_feature_section(self.features_frame, "Reactions", stat_block.reactions)
        
        # Add legendary actions
        if stat_block.legendary_actions:
            self._create_feature_section(self.features_frame, "Legendary Actions", stat_block.legendary_actions)
        
        # Show/hide edit buttons based on callbacks
        if self.on_edit:
            self.edit_btn.pack(side="left", padx=2)
        else:
            self.edit_btn.pack_forget()
        
        if self.on_delete:
            self.delete_btn.pack(side="left", padx=2)
        else:
            self.delete_btn.pack_forget()
    
    def _update_conditional_label(self, label: ctk.CTkLabel, value: str):
        """Update a label and hide its row if value is empty."""
        label.configure(text=value or "")
        parent = label.master
        if hasattr(parent, '_hide_if_empty') and parent._hide_if_empty:  # type: ignore[union-attr]
            if value:
                parent.pack(fill="x", pady=1)  # type: ignore[union-attr]
            else:
                parent.pack_forget()  # type: ignore[union-attr]
    
    def _on_edit_click(self):
        """Handle edit button click."""
        if self.on_edit and self._stat_block:
            self.on_edit(self._stat_block)
    
    def _on_delete_click(self):
        """Handle delete button click."""
        if self.on_delete and self._stat_block:
            self.on_delete(self._stat_block)
    
    def _collapse_content(self):
        """Collapse the stat block to show only the header."""
        self._is_collapsed = True
        self.content_frame.pack_forget()
        self.toggle_btn.configure(text="▶")
    
    def _expand_content(self):
        """Expand the stat block to show full content."""
        self._is_collapsed = False
        self.content_frame.pack(fill="x")
        self.toggle_btn.configure(text="▼")
    
    def toggle_collapse(self):
        """Toggle between collapsed and expanded state."""
        if self._is_collapsed:
            self._expand_content()
        else:
            self._collapse_content()


class CollapsibleStatBlockSection(ctk.CTkFrame):
    """
    A collapsible section that contains stat blocks.
    Used in the spell detail panel.
    """
    
    def __init__(self, parent, stat_blocks: Optional[List[StatBlock]] = None,
                 on_add: Optional[Callable[[], None]] = None,
                 on_edit: Optional[Callable[[StatBlock], None]] = None,
                 on_delete: Optional[Callable[[StatBlock], None]] = None):
        super().__init__(parent, fg_color="transparent")
        
        self._stat_blocks = stat_blocks or []
        self._is_expanded = False
        self.on_add = on_add
        self.on_edit = on_edit
        self.on_delete = on_delete
        
        self._create_widgets()
        self._update_display()
    
    def _create_widgets(self):
        """Create the collapsible section widgets."""
        theme = get_theme_manager()
        
        # Header bar (clickable to expand/collapse)
        self.header = ctk.CTkFrame(self, fg_color=theme.get_current_color('bg_secondary'), corner_radius=6)
        self.header.pack(fill="x", pady=(0, 5))
        
        # Expand/collapse indicator
        self.expand_label = ctk.CTkLabel(
            self.header, text="▶",
            font=ctk.CTkFont(size=12),
            width=20
        )
        self.expand_label.pack(side="left", padx=(10, 5), pady=8)
        
        # Section title
        self.title_label = ctk.CTkLabel(
            self.header, text="Stat Blocks",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.title_label.pack(side="left", fill="x", expand=True, pady=8)
        
        # Count badge
        self.count_label = ctk.CTkLabel(
            self.header, text="(0)",
            font=ctk.CTkFont(size=12),
            text_color=theme.get_text_secondary()
        )
        self.count_label.pack(side="right", padx=10, pady=8)
        
        # Make header clickable
        for widget in [self.header, self.expand_label, self.title_label, self.count_label]:
            widget.bind("<Button-1>", lambda e: self.toggle())
            widget.configure(cursor="hand2")
        
        # Content frame (hidden by default)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        
        # Add button
        self.add_btn_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.add_btn_frame.pack(fill="x", pady=(0, 10))
        
        self.add_btn = ctk.CTkButton(
            self.add_btn_frame, text="+ Add Stat Block",
            font=ctk.CTkFont(size=12),
            height=28,
            command=self._on_add_click
        )
        self.add_btn.pack(side="left")
        
        # Container for stat block displays
        self.blocks_container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.blocks_container.pack(fill="both", expand=True)
    
    def toggle(self):
        """Toggle expanded/collapsed state."""
        self._is_expanded = not self._is_expanded
        self._update_display()
    
    def expand(self):
        """Expand the section."""
        self._is_expanded = True
        self._update_display()
    
    def collapse(self):
        """Collapse the section."""
        self._is_expanded = False
        self._update_display()
    
    def set_stat_blocks(self, stat_blocks: List[StatBlock]):
        """Update the stat blocks to display."""
        self._stat_blocks = stat_blocks or []
        self._update_display()
    
    def _update_display(self):
        """Update the visual display."""
        # Update expand indicator
        self.expand_label.configure(text="▼" if self._is_expanded else "▶")
        
        # Update count
        count = len(self._stat_blocks)
        self.count_label.configure(text=f"({count})")
        
        # Show/hide content
        if self._is_expanded:
            self.content.pack(fill="both", expand=True, padx=10)
            self._rebuild_stat_blocks()
        else:
            self.content.pack_forget()
    
    def _rebuild_stat_blocks(self):
        """Rebuild the stat block display widgets."""
        # Clear existing
        for widget in self.blocks_container.winfo_children():
            widget.destroy()
        
        if not self._stat_blocks:
            empty_label = ctk.CTkLabel(
                self.blocks_container, 
                text="No stat blocks. Click '+ Add Stat Block' to create one.",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color=get_theme_manager().get_text_secondary()
            )
            empty_label.pack(pady=20)
            return
        
        # Create display for each stat block
        for stat_block in self._stat_blocks:
            display = StatBlockDisplay(
                self.blocks_container,
                stat_block=stat_block,
                on_edit=self.on_edit,
                on_delete=self.on_delete
            )
            display.pack(fill="x", pady=(0, 10))
    
    def _on_add_click(self):
        """Handle add button click."""
        if self.on_add:
            self.on_add()
    
    def has_stat_blocks(self) -> bool:
        """Check if there are any stat blocks."""
        return len(self._stat_blocks) > 0
