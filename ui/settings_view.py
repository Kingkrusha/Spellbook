"""
Settings View for D&D Spellbook Application.
Displays and manages application settings.
"""

import customtkinter as ctk
from typing import Callable, Optional
from settings import SettingsManager
from theme import get_theme_manager

# Theme editor removed: this build supports only appearance modes (Light/Dark/System)


class SettingsView(ctk.CTkFrame):
    """Settings page for configuring application preferences."""
    
    def __init__(self, parent, settings_manager: SettingsManager,
                 on_appearance_changed: Optional[Callable[[str], None]] = None,
                 spell_manager=None):
        super().__init__(parent, fg_color="transparent")
        
        self.settings_manager = settings_manager
        self.spell_manager = spell_manager
        self.theme_manager = get_theme_manager()
        self.on_appearance_changed = on_appearance_changed
        
        # Variables for settings
        self._appearance_var = ctk.StringVar(value=settings_manager.settings.appearance_mode)
        # Handle backwards compatibility: use theme_name if available, otherwise use use_custom_theme
        theme_name = getattr(settings_manager.settings, 'theme_name', None)
        if theme_name is None:
            theme_name = 'custom' if settings_manager.settings.use_custom_theme else 'default'
        # If theme is 'default' map it to appearance mode for display (we don't show 'Default' in UI)
        if theme_name == 'default':
            display_theme = settings_manager.settings.appearance_mode.capitalize()
        else:
            display_theme = theme_name.capitalize() if theme_name else 'System'
        self._theme_var = ctk.StringVar(value=display_theme)
        self._spell_added_var = ctk.BooleanVar(value=settings_manager.settings.show_spell_added_notification)
        self._rest_notif_var = ctk.BooleanVar(value=settings_manager.settings.show_rest_notification)
        self._warn_cantrips_var = ctk.BooleanVar(value=settings_manager.settings.warn_too_many_cantrips)
        self._warn_class_var = ctk.BooleanVar(value=settings_manager.settings.warn_wrong_class)
        self._warn_level_var = ctk.BooleanVar(value=settings_manager.settings.warn_spell_too_high_level)
        self._warn_prepared_var = ctk.BooleanVar(value=settings_manager.settings.warn_too_many_prepared)
        self._comparison_var = ctk.BooleanVar(value=settings_manager.settings.show_comparison_highlights)
        
        # Apply theme from settings
        theme_name = getattr(settings_manager.settings, 'theme_name', None)
        if theme_name is None:
            # Backwards compatibility: use use_custom_theme
            theme_name = 'custom' if settings_manager.settings.use_custom_theme else 'default'
        self.theme_manager.set_theme(theme_name)
        
        self._create_widgets()
        # Listen for theme changes to update text colors live
        try:
            self.theme_manager.add_listener(self._on_theme_changed)
        except Exception:
            pass
    
    def _create_widgets(self):
        """Create the settings UI."""
        # Main scrollable container
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(self.container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header, text="Settings",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left")
        
        # Reset button (use themed danger color)
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        self.reset_defaults_btn = ctk.CTkButton(
            header, text="Reset to Defaults", width=140,
            fg_color=danger, hover_color=danger_hover,
            text_color=btn_text,
            command=self._on_reset_defaults
        )
        self.reset_defaults_btn.pack(side="right")
        
        # === Appearance Section ===
        self._create_section(self.container, "Appearance")
        
        appearance_frame = ctk.CTkFrame(self.container, corner_radius=10)
        appearance_frame.pack(fill="x", pady=(0, 20))
        
        appearance_content = ctk.CTkFrame(appearance_frame, fg_color="transparent")
        appearance_content.pack(fill="x", padx=20, pady=15)
        
        # Appearance mode row
        mode_row = ctk.CTkFrame(appearance_content, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            mode_row, text="Appearance Mode:",
            font=ctk.CTkFont(size=14)
        ).pack(side="left")
        
        appearance_options = ctk.CTkFrame(mode_row, fg_color="transparent")
        appearance_options.pack(side="right")
        
        for mode in ["Dark", "Light", "System"]:
            ctk.CTkRadioButton(
                appearance_options, text=mode,
                variable=self._appearance_var, value=mode.lower(),
                command=self._on_appearance_change
            ).pack(side="left", padx=10)
        
        # Only appearance mode is supported now (Light/Dark/System)
        # Note: some appearance changes require restarting certain widgets to fully apply.
        note_text = "Note: Some appearance changes may require restarting the app to fully apply."
        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            appearance_content,
            text=note_text,
            font=ctk.CTkFont(size=11),
            text_color=text_secondary
        ).pack(fill="x", pady=(8, 0))
        
        # === Notifications Section ===
        self._create_section(self.container, "Notifications")
        
        notif_frame = ctk.CTkFrame(self.container, corner_radius=10)
        notif_frame.pack(fill="x", pady=(0, 20))
        
        notif_content = ctk.CTkFrame(notif_frame, fg_color="transparent")
        notif_content.pack(fill="x", padx=20, pady=15)
        
        self._create_toggle_row(
            notif_content,
            "Show confirmation when adding spells to characters",
            self._spell_added_var,
            self._on_setting_change
        )
        
        self._create_toggle_row(
            notif_content,
            "Show notification after long/short rest",
            self._rest_notif_var,
            self._on_setting_change,
            pady=(10, 0)
        )
        
        # === Spell Warnings Section ===
        self._create_section(self.container, "Spell List Warnings")
        
        warnings_frame = ctk.CTkFrame(self.container, corner_radius=10)
        warnings_frame.pack(fill="x", pady=(0, 20))
        
        warnings_content = ctk.CTkFrame(warnings_frame, fg_color="transparent")
        warnings_content.pack(fill="x", padx=20, pady=15)
        
        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            warnings_content,
            text="Show warnings when adding spells that may be incompatible:",
            font=ctk.CTkFont(size=13),
            text_color=text_secondary
        ).pack(anchor="w", pady=(0, 15))
        
        self._create_toggle_row(
            warnings_content,
            "Warn when adding too many cantrips",
            self._warn_cantrips_var,
            self._on_setting_change
        )
        
        self._create_toggle_row(
            warnings_content,
            "Warn when spell is not in character's class list",
            self._warn_class_var,
            self._on_setting_change,
            pady=(10, 0)
        )
        
        self._create_toggle_row(
            warnings_content,
            "Warn when spell level is too high for character",
            self._warn_level_var,
            self._on_setting_change,
            pady=(10, 0)
        )
        
        self._create_toggle_row(
            warnings_content,
            "Warn when preparing more spells than allowed",
            self._warn_prepared_var,
            self._on_setting_change,
            pady=(10, 0)
        )
        
        # === Comparison Mode Section ===
        self._create_section(self.container, "Comparison Mode")
        
        compare_frame = ctk.CTkFrame(self.container, corner_radius=10)
        compare_frame.pack(fill="x", pady=(0, 20))
        
        compare_content = ctk.CTkFrame(compare_frame, fg_color="transparent")
        compare_content.pack(fill="x", padx=20, pady=15)
        
        self._create_toggle_row(
            compare_content,
            "Show color highlights in View & Compare mode",
            self._comparison_var,
            self._on_setting_change
        )
        
        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            compare_content,
            text="When enabled, better values are highlighted green and worse values red.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # === Character Sheet Section ===
        self._create_section(self.container, "Character Sheets")
        
        charsheet_frame = ctk.CTkFrame(self.container, corner_radius=10)
        charsheet_frame.pack(fill="x", pady=(0, 20))
        
        charsheet_content = ctk.CTkFrame(charsheet_frame, fg_color="transparent")
        charsheet_content.pack(fill="x", padx=20, pady=15)
        
        self._auto_calc_hp_var = ctk.BooleanVar(
            value=self.settings_manager.settings.auto_calculate_hp
        )
        
        self._create_toggle_row(
            charsheet_content,
            "Automatically calculate hit point maximum",
            self._auto_calc_hp_var,
            self._on_setting_change
        )
        
        ctk.CTkLabel(
            charsheet_content,
            text="When enabled, calculates HP based on class levels\n(first level max, others average) + CON modifier.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # Auto calculate AC
        self._auto_calc_ac_var = ctk.BooleanVar(
            value=self.settings_manager.settings.auto_calculate_ac
        )
        
        self._create_toggle_row(
            charsheet_content,
            "Automatically calculate armor class",
            self._auto_calc_ac_var,
            self._on_setting_change,
            pady=(15, 0)
        )
        
        ctk.CTkLabel(
            charsheet_content,
            text="When enabled, AC is calculated from armor and shield selections\nplus DEX modifier and special abilities (like Unarmored Defense).",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        self._auto_fill_prof_var = ctk.BooleanVar(
            value=self.settings_manager.settings.auto_fill_proficiencies
        )
        
        self._create_toggle_row(
            charsheet_content,
            "Automatically fill proficiencies for new sheets",
            self._auto_fill_prof_var,
            self._on_setting_change
        )
        
        ctk.CTkLabel(
            charsheet_content,
            text="When enabled, new character sheets will automatically fill 'Other Proficiencies'\nwith the default proficiencies for the character's class.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # Auto apply saving throws
        self._auto_apply_saves_var = ctk.BooleanVar(
            value=self.settings_manager.settings.auto_apply_saving_throws
        )
        
        self._create_toggle_row(
            charsheet_content,
            "Automatically apply saving throw proficiencies",
            self._auto_apply_saves_var,
            self._on_setting_change,
            pady=(15, 0)
        )
        
        ctk.CTkLabel(
            charsheet_content,
            text="When enabled, adding a starting class automatically marks its\nsaving throw proficiencies on the character sheet.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # Multiclass removal warning toggle
        self._warn_multiclass_var = ctk.BooleanVar(
            value=self.settings_manager.settings.warn_multiclass_removal
        )
        
        self._create_toggle_row(
            charsheet_content,
            "Warn when removing a multiclass",
            self._warn_multiclass_var,
            self._on_setting_change,
            pady=(15, 0)
        )
        
        ctk.CTkLabel(
            charsheet_content,
            text="When enabled, shows a confirmation dialog before removing a class\nby setting its level to 0.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # Long rest hit dice restoration
        dice_row = ctk.CTkFrame(charsheet_content, fg_color="transparent")
        dice_row.pack(fill="x", pady=(15, 0))
        
        ctk.CTkLabel(
            dice_row, text="Long rest hit dice restoration:",
            font=ctk.CTkFont(size=14)
        ).pack(side="left")
        
        self._hit_dice_rest_var = ctk.StringVar(
            value=self.settings_manager.settings.long_rest_hit_dice
        )
        
        dice_options = ctk.CTkFrame(dice_row, fg_color="transparent")
        dice_options.pack(side="right")
        
        for mode in [("All", "all"), ("Half", "half"), ("None", "none")]:
            ctk.CTkRadioButton(
                dice_options, text=mode[0],
                variable=self._hit_dice_rest_var, value=mode[1],
                command=self._on_setting_change
            ).pack(side="left", padx=10)
        
        ctk.CTkLabel(
            charsheet_content,
            text="Controls how many hit dice are restored on a long rest.\n• All: Restore all hit dice to maximum\n• Half: Restore half of total hit dice\n• None: Do not restore any hit dice",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # === Official Spells Section ===
        self._create_section(self.container, "Official Spells")
        
        official_frame = ctk.CTkFrame(self.container, corner_radius=10)
        official_frame.pack(fill="x", pady=(0, 20))
        
        official_content = ctk.CTkFrame(official_frame, fg_color="transparent")
        official_content.pack(fill="x", padx=20, pady=15)
        
        self._allow_delete_official_var = ctk.BooleanVar(
            value=self.settings_manager.settings.allow_delete_official_spells
        )
        
        self._create_toggle_row(
            official_content,
            "Allow deletion of official spells",
            self._allow_delete_official_var,
            self._on_setting_change
        )
        
        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            official_content,
            text="When disabled, spells tagged as 'Official' cannot be deleted.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # Restore all official spells button
        restore_frame = ctk.CTkFrame(official_content, fg_color="transparent")
        restore_frame.pack(fill="x", pady=(15, 0))
        
        self._restore_all_btn = ctk.CTkButton(
            restore_frame,
            text="Restore All Official Spells",
            width=200,
            fg_color=self.theme_manager.get_current_color('button_normal'),
            hover_color=self.theme_manager.get_current_color('button_hover'),
            text_color=self.theme_manager.get_current_color('text_primary'),
            command=self._on_restore_all_spells
        )
        self._restore_all_btn.pack(side="left")
        
        ctk.CTkLabel(
            official_content,
            text="Restores all modified official spells to their original versions.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # === Legacy Content Section ===
        self._create_section(self.container, "Legacy Content")
        
        legacy_frame = ctk.CTkFrame(self.container, corner_radius=10)
        legacy_frame.pack(fill="x", pady=(0, 20))
        
        legacy_content = ctk.CTkFrame(legacy_frame, fg_color="transparent")
        legacy_content.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            legacy_content,
            text="Control how 2014 (legacy) D&D content is displayed:",
            font=ctk.CTkFont(size=13),
            text_color=text_secondary
        ).pack(anchor="w", pady=(0, 15))
        
        self._legacy_filter_var = ctk.StringVar(
            value=self.settings_manager.settings.legacy_content_filter
        )
        
        legacy_options = [
            ("Show All Content", "show_all", "Display both 2014 and 2024 content"),
            ("Show Unupdated", "show_unupdated", "Show 2024 content, plus 2014 content only if no 2024 version exists"),
            ("No Legacy Content", "no_legacy", "Hide all 2014 content"),
            ("Legacy Only", "legacy_only", "Show only 2014 content"),
        ]
        
        for label, value, description in legacy_options:
            option_frame = ctk.CTkFrame(legacy_content, fg_color="transparent")
            option_frame.pack(fill="x", pady=2)
            
            ctk.CTkRadioButton(
                option_frame, text=label,
                variable=self._legacy_filter_var, value=value,
                command=self._on_setting_change
            ).pack(side="left")
            
            ctk.CTkLabel(
                option_frame,
                text=f"  - {description}",
                font=ctk.CTkFont(size=11),
                text_color=text_secondary
            ).pack(side="left", padx=(10, 0))
        
        # === About Section ===
        self._create_section(self.container, "About")
        
        about_frame = ctk.CTkFrame(self.container, corner_radius=10)
        about_frame.pack(fill="x", pady=(0, 20))
        
        about_content = ctk.CTkFrame(about_frame, fg_color="transparent")
        about_content.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            about_content,
            text="D&D Spellbook Manager",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")
        
        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            about_content,
            text="A tool for managing D&D 5e spells character sheets and player information.",
            font=ctk.CTkFont(size=13),
            text_color=text_secondary
        ).pack(anchor="w", pady=(5, 0))
        
        ctk.CTkLabel(
            about_content,
            text="Version 1.3 • Data stored in SQLite database",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
    
    def _create_section(self, parent, title: str):
        """Create a section header."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(10, 8))
        
        ctk.CTkLabel(
            header, text=title,
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
    
    def _create_toggle_row(self, parent, text: str, variable: ctk.BooleanVar,
                           command: Callable, pady=(0, 0)):
        """Create a toggle switch row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=pady)
        
        ctk.CTkLabel(
            row, text=text,
            font=ctk.CTkFont(size=14)
        ).pack(side="left")
        
        ctk.CTkSwitch(
            row, text="",
            variable=variable,
            command=command,
            width=46
        ).pack(side="right")
    
    def _on_appearance_change(self):
        """Handle appearance mode change."""
        new_mode = self._appearance_var.get()
        self.settings_manager.update(appearance_mode=new_mode)
        
        # Apply the theme change
        ctk.set_appearance_mode(new_mode)
        
        if self.on_appearance_changed:
            self.on_appearance_changed(new_mode)

        # No-op: we no longer show theme preset radios
    
    def _on_theme_change(self, value: Optional[str] = None):
        """Legacy hook removed — only appearance mode is supported.

        If called with a recognized appearance ('light','dark','system'), apply it.
        """
        sel = (value if value is not None else self._theme_var.get())
        theme_name = sel.lower() if isinstance(sel, str) else ''
        if theme_name in ("light", "dark", "system"):
            ctk.set_appearance_mode(theme_name)
            self.settings_manager.update(appearance_mode=theme_name)
            if self.on_appearance_changed:
                self.on_appearance_changed(theme_name)

    def _update_theme_radio_labels(self):
        # No-op: theme presets removed
        return
    
    def _update_theme_editor_visibility(self):
        # No-op: theme editor removed
        return
    
    def _open_theme_editor(self):
        # Theme editor removed
        return

    def _open_more_themes(self):
        # Theme presets removed
        return

    def _select_preset(self, name: str):
        # Theme presets removed
        return
    
    def _on_theme_colors_changed(self):
        # Theme editor removed
        return
    
    def _on_setting_change(self):
        """Handle any setting change."""
        self.settings_manager.update(
            show_spell_added_notification=self._spell_added_var.get(),
            show_rest_notification=self._rest_notif_var.get(),
            warn_too_many_cantrips=self._warn_cantrips_var.get(),
            warn_wrong_class=self._warn_class_var.get(),
            warn_spell_too_high_level=self._warn_level_var.get(),
            warn_too_many_prepared=self._warn_prepared_var.get(),
            show_comparison_highlights=self._comparison_var.get(),
            allow_delete_official_spells=self._allow_delete_official_var.get(),
            auto_calculate_hp=self._auto_calc_hp_var.get(),
            auto_calculate_ac=self._auto_calc_ac_var.get(),
            auto_fill_proficiencies=self._auto_fill_prof_var.get(),
            auto_apply_saving_throws=self._auto_apply_saves_var.get(),
            warn_multiclass_removal=self._warn_multiclass_var.get(),
            long_rest_hit_dice=self._hit_dice_rest_var.get(),
            legacy_content_filter=self._legacy_filter_var.get()
        )
    
    def _on_restore_all_spells(self):
        """Restore all modified official spells to their defaults."""
        from tkinter import messagebox
        
        if not self.spell_manager:
            messagebox.showerror("Error", "Spell manager not available.", parent=self.winfo_toplevel())
            return
        
        # Count modified spells first
        modified_count = sum(1 for s in self.spell_manager.spells if s.is_official and s.is_modified)
        
        if modified_count == 0:
            messagebox.showinfo("No Modified Spells", 
                "No official spells have been modified.", 
                parent=self.winfo_toplevel())
            return
        
        # Confirm with user
        if messagebox.askyesno(
            "Restore All Official Spells",
            f"This will restore {modified_count} modified official spell(s) to their original versions.\n\n"
            "Are you sure you want to continue?",
            parent=self.winfo_toplevel()
        ):
            restored = self.spell_manager.restore_all_official_spells()
            if restored > 0:
                messagebox.showinfo("Success", 
                    f"Restored {restored} official spell(s) to their default versions.",
                    parent=self.winfo_toplevel())
            else:
                messagebox.showerror("Error", 
                    "Failed to restore spells. Please try again.",
                    parent=self.winfo_toplevel())
    
    def _on_reset_defaults(self):
        """Reset all settings to defaults."""
        self.settings_manager.reset_to_defaults()
        self.theme_manager.reset_custom_theme()
        self.theme_manager.set_theme("default")
        
        # Update UI variables
        settings = self.settings_manager.settings
        self._appearance_var.set(settings.appearance_mode)
        theme_name = getattr(settings, 'theme_name', 'default')
        self._theme_var.set(theme_name.capitalize())
        self._spell_added_var.set(settings.show_spell_added_notification)
        self._rest_notif_var.set(settings.show_rest_notification)
        self._warn_cantrips_var.set(settings.warn_too_many_cantrips)
        self._warn_class_var.set(settings.warn_wrong_class)
        self._warn_level_var.set(settings.warn_spell_too_high_level)
        self._warn_prepared_var.set(settings.warn_too_many_prepared)
        self._comparison_var.set(settings.show_comparison_highlights)
        self._allow_delete_official_var.set(settings.allow_delete_official_spells)
        self._auto_calc_hp_var.set(settings.auto_calculate_hp)
        self._auto_calc_ac_var.set(settings.auto_calculate_ac)
        self._auto_fill_prof_var.set(settings.auto_fill_proficiencies)
        self._auto_apply_saves_var.set(settings.auto_apply_saving_throws)
        self._warn_multiclass_var.set(settings.warn_multiclass_removal)
        self._hit_dice_rest_var.set(settings.long_rest_hit_dice)
        self._legacy_filter_var.set(settings.legacy_content_filter)
        
        # Update edit button visibility
        self._update_theme_editor_visibility()
        
        # Apply appearance
        ctk.set_appearance_mode(settings.appearance_mode)
        if self.on_appearance_changed:
            self.on_appearance_changed(settings.appearance_mode)
    
    def refresh_from_settings(self):
        """Refresh UI from current settings (call when view becomes visible)."""
        settings = self.settings_manager.settings
        self._appearance_var.set(settings.appearance_mode)
        theme_name = getattr(settings, 'theme_name', 'default')
        self._theme_var.set(theme_name.capitalize())
        self._spell_added_var.set(settings.show_spell_added_notification)
        self._rest_notif_var.set(settings.show_rest_notification)
        self._warn_cantrips_var.set(settings.warn_too_many_cantrips)
        self._warn_class_var.set(settings.warn_wrong_class)
        self._warn_level_var.set(settings.warn_spell_too_high_level)
        self._warn_prepared_var.set(settings.warn_too_many_prepared)
        self._comparison_var.set(settings.show_comparison_highlights)
        self._auto_calc_hp_var.set(settings.auto_calculate_hp)
        self._auto_calc_ac_var.set(settings.auto_calculate_ac)
        self._auto_fill_prof_var.set(settings.auto_fill_proficiencies)
        self._auto_apply_saves_var.set(settings.auto_apply_saving_throws)
        self._warn_multiclass_var.set(settings.warn_multiclass_removal)
        self._hit_dice_rest_var.set(settings.long_rest_hit_dice)
        self._legacy_filter_var.set(settings.legacy_content_filter)
        self._update_theme_editor_visibility()

    def _on_theme_changed(self):
        """Update dynamic label/input colors when the appearance changes."""
        try:
            theme = self.theme_manager
            text_secondary = theme.get_text_secondary()

            # Walk container and update CTkLabel text colors where appropriate
            for child in self.container.winfo_children():
                def _update_labels(widget):
                    for w in widget.winfo_children():
                        try:
                            if isinstance(w, ctk.CTkLabel):
                                w.configure(text_color=text_secondary)
                        except Exception:
                            pass
                        try:
                            _update_labels(w)
                        except Exception:
                            pass
                try:
                    _update_labels(child)
                except Exception:
                    pass

            # Update input-like widgets
            input_bg = theme.get_current_color('bg_input')
            input_text = theme.get_current_color('text_primary')
            border_col = theme.get_current_color('border')

            def _update_inputs(widget):
                for w in widget.winfo_children():
                    try:
                        if isinstance(w, ctk.CTkEntry) or isinstance(w, ctk.CTkTextbox):
                            try:
                                w.configure(fg_color=input_bg, text_color=input_text, border_color=border_col)
                            except Exception:
                                pass
                        if isinstance(w, ctk.CTkScrollableFrame):
                            try:
                                w.configure(fg_color="transparent")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        _update_inputs(w)
                    except Exception:
                        pass

            try:
                _update_inputs(self.container)
            except Exception:
                pass
        except Exception:
            pass

    def destroy(self):
        """Remove theme listener when view is destroyed."""
        try:
            self.theme_manager.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()