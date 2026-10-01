"""
Settings View for D&D Spellbook Application.
Displays and manages application settings.
"""

import threading

import customtkinter as ctk
from typography import ui_font, get_font_manager
from ui.busy import run_busy
from ui.restyle import flush_restyle
from ui.typography_editor import TypographyEditor, GlobalTypographyModel
from typing import Callable, Optional
from settings import SettingsManager
from theme import get_theme_manager
from version import __version__


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

        # Colour theme selector. theme_name holds a theme key ("default",
        # "midnight", "custom:ab12cd34", ...); the dropdown shows its name.
        theme_key = self.theme_manager.normalize_key(getattr(settings_manager.settings, 'theme_name', None))
        self._theme_var = ctk.StringVar(value=self.theme_manager.display_name(theme_key))
        self._spell_added_var = ctk.BooleanVar(value=settings_manager.settings.show_spell_added_notification)
        self._rest_notif_var = ctk.BooleanVar(value=settings_manager.settings.show_rest_notification)
        self._warn_cantrips_var = ctk.BooleanVar(value=settings_manager.settings.warn_too_many_cantrips)
        self._warn_class_var = ctk.BooleanVar(value=settings_manager.settings.warn_wrong_class)
        self._warn_level_var = ctk.BooleanVar(value=settings_manager.settings.warn_spell_too_high_level)
        self._warn_prepared_var = ctk.BooleanVar(value=settings_manager.settings.warn_too_many_prepared)
        self._comparison_var = ctk.BooleanVar(value=settings_manager.settings.show_comparison_highlights)
        
        # Preload variables
        self._preload_classes_var = ctk.BooleanVar(value=settings_manager.settings.preload_classes)
        self._preload_feats_var = ctk.BooleanVar(value=settings_manager.settings.preload_feats)
        self._preload_lineages_var = ctk.BooleanVar(value=settings_manager.settings.preload_lineages)
        self._preload_backgrounds_var = ctk.BooleanVar(value=settings_manager.settings.preload_backgrounds)
        self._preload_equipment_var = ctk.BooleanVar(
            value=getattr(settings_manager.settings, 'preload_equipment', True))
        self._preload_magic_items_var = ctk.BooleanVar(
            value=getattr(settings_manager.settings, 'preload_magic_items', True))
        self._preload_sheets_var = ctk.BooleanVar(value=settings_manager.settings.preload_character_sheets)

        # Object linking - as-you-type suggestions, per content category. The
        # UI presents these as "Disable ..." checkboxes, so each var holds the
        # *disabled* state (the inverse of the link_suggest_* setting).
        self._link_disable_spells_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_spells', True))
        self._link_disable_feats_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_feats', True))
        self._link_disable_lineages_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_lineages', True))
        self._link_disable_backgrounds_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_backgrounds', True))
        self._link_disable_classes_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_classes', True))
        self._link_disable_equipment_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_equipment', True))
        self._link_disable_magic_items_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_magic_items', True))
        self._link_disable_monsters_var = ctk.BooleanVar(
            value=not getattr(settings_manager.settings, 'link_suggest_monsters', True))
        self._link_autocomplete_var = ctk.BooleanVar(
            value=getattr(settings_manager.settings, 'link_autocomplete_names', True))

        # Monsters
        self._show_spell_only_summons_var = ctk.BooleanVar(
            value=getattr(settings_manager.settings, 'show_spell_only_summons', False))

        # Startup
        self._restore_tabs_var = ctk.BooleanVar(
            value=getattr(settings_manager.settings, 'restore_tabs', True))

        # Updates
        self._auto_check_updates_var = ctk.BooleanVar(
            value=getattr(settings_manager.settings, 'auto_check_updates', True)
        )
        self._update_check_in_progress = False
        
        # Apply the saved colour theme.
        self.theme_manager.set_theme(theme_key)

        self._create_widgets()
        # Listen for theme changes to update text colors live
        try:
            self.theme_manager.add_listener(self._on_theme_changed)
        except Exception:
            pass
    
    def _create_widgets(self):
        """Create the settings UI."""
        # Section "card" frames are collected here so _on_theme_changed can
        # recolour them - CTkFrame(corner_radius=...) with no fg_color falls
        # back to CTk's own default theme, not ours, unless we set it.
        self._card_frames = []

        # Main scrollable container
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(self.container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header, text="Settings",
            font=ui_font("title", bold=True)
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
        
        appearance_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(appearance_frame)
        appearance_frame.pack(fill="x", pady=(0, 20))
        
        appearance_content = ctk.CTkFrame(appearance_frame, fg_color="transparent")
        appearance_content.pack(fill="x", padx=20, pady=15)
        
        # Appearance mode row
        mode_row = ctk.CTkFrame(appearance_content, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            mode_row, text="Appearance Mode:",
            font=ui_font("subheading")
        ).pack(side="left")
        
        appearance_options = ctk.CTkFrame(mode_row, fg_color="transparent")
        appearance_options.pack(side="right")
        
        for mode in ["Dark", "Light", "System"]:
            ctk.CTkRadioButton(
                appearance_options, text=mode,
                variable=self._appearance_var, value=mode.lower(),
                command=self._on_appearance_change
            ).pack(side="left", padx=10)

        # Colour theme row
        theme_row = ctk.CTkFrame(appearance_content, fg_color="transparent")
        theme_row.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            theme_row, text="Color Theme:",
            font=ui_font("subheading")
        ).pack(side="left")

        ctk.CTkButton(
            theme_row, text="Theme Studio…", width=120,
            command=self._open_theme_studio
        ).pack(side="right", padx=(8, 0))

        self._theme_menu = ctk.CTkOptionMenu(
            theme_row,
            values=self._theme_names(),
            variable=self._theme_var,
            command=self._on_color_theme_change,
            width=170,
        )
        self._theme_menu.pack(side="right")

        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            appearance_content,
            text="Pick a built-in theme, or open the Theme Studio to create and edit your own.",
            font=ui_font("small"),
            text_color=text_secondary, anchor="w", justify="left"
        ).pack(fill="x", pady=(8, 0))

        # The remaining sections are built a few milliseconds apart, so the tab appears
        # at once instead of after every switch and card has been created.
        self._loading_note = ctk.CTkLabel(
            self.container, text="Loading more settings\u2026", font=ui_font("small"),
            text_color=self.theme_manager.get_text_secondary())
        self._loading_note.pack(pady=10)
        self._pending_sections = [
            self._build_typography_section,
            self._build_notifications_section,
            self._build_spell_warnings_section,
            self._build_comparison_mode_section,
            self._build_character_sheet_section,
            self._build_official_spells_section,
            self._build_legacy_content_section,
            self._build_monsters_section,
            self._build_loading_options_section,
            self._build_object_linking_section,
            self._build_about_section,
        ]
        self.after(10, self._build_next_section)

    def _build_next_section(self):
        """Build one pending section, then schedule the next."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if not self._pending_sections:
            self._loading_note.destroy()
            return
        build = self._pending_sections.pop(0)
        try:
            self._loading_note.pack_forget()
            build()
        except Exception as e:
            print(f"Error building settings section: {e}")
        if self._pending_sections:
            self._loading_note.pack(pady=10)
        self.after(8, self._build_next_section)

    def build_all_sections_now(self):
        """Finish building every section immediately (used before things that need them all)."""
        while getattr(self, "_pending_sections", None):
            self._build_next_section_sync()

    def _build_next_section_sync(self):
        build = self._pending_sections.pop(0)
        build()
        if not self._pending_sections:
            self._loading_note.destroy()

    def _build_typography_section(self):
        """Build the Typography section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Typography Section ===
        self._create_section(self.container, "Typography")

        typography_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                        fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(typography_frame)
        typography_frame.pack(fill="x", pady=(0, 20))
        typography_content = ctk.CTkFrame(typography_frame, fg_color="transparent")
        typography_content.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(
            typography_content,
            text="Choose fonts for headings, subheadings, normal and small text. "
                 "Character sheets can override these on the sheet itself (Style button).",
            font=ui_font("small"), text_color=text_secondary, anchor="w", justify="left", wraplength=640
        ).pack(fill="x", pady=(0, 10))
        self._typography_editor = TypographyEditor(typography_content, GlobalTypographyModel())
        self._typography_editor.pack(fill="x")


    def _build_notifications_section(self):
        """Build the Notifications section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Notifications Section ===
        self._create_section(self.container, "Notifications")
        
        notif_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(notif_frame)
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
        


    def _build_spell_warnings_section(self):
        """Build the Spell Warnings section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Spell Warnings Section ===
        self._create_section(self.container, "Spell List Warnings")
        
        warnings_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(warnings_frame)
        warnings_frame.pack(fill="x", pady=(0, 20))
        
        warnings_content = ctk.CTkFrame(warnings_frame, fg_color="transparent")
        warnings_content.pack(fill="x", padx=20, pady=15)
        
        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            warnings_content,
            text="Show warnings when adding spells that may be incompatible:",
            font=ui_font("body", 13),
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
        


    def _build_comparison_mode_section(self):
        """Build the Comparison Mode section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Comparison Mode Section ===
        self._create_section(self.container, "Comparison Mode")
        
        compare_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(compare_frame)
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
            font=ui_font("body"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        


    def _build_character_sheet_section(self):
        """Build the Character Sheet section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Character Sheet Section ===
        self._create_section(self.container, "Character Sheets")
        
        charsheet_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(charsheet_frame)
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
            font=ui_font("body"),
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
            font=ui_font("body"),
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
            font=ui_font("body"),
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
            font=ui_font("body"),
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
            font=ui_font("body"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        
        # Long rest hit dice restoration
        dice_row = ctk.CTkFrame(charsheet_content, fg_color="transparent")
        dice_row.pack(fill="x", pady=(15, 0))
        
        ctk.CTkLabel(
            dice_row, text="Long rest hit dice restoration:",
            font=ui_font("subheading")
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
            font=ui_font("body"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))

        # Carry weight indicator toggle
        self._show_carry_weight_var = ctk.BooleanVar(
            value=self.settings_manager.settings.show_carry_weight_indicator
        )

        self._create_toggle_row(
            charsheet_content,
            "Show carrying capacity indicator on the inventory tab",
            self._show_carry_weight_var,
            self._on_setting_change,
            pady=(15, 0)
        )

        ctk.CTkLabel(
            charsheet_content,
            text="When enabled, the inventory tab totals the weight of linked equipment and\nmagic items against carrying capacity (STR score x 15, doubled with Powerful\nBuild) and drops speed to 5 ft when it's exceeded. Disabling this also turns\noff that speed reduction, not just the display.",
            font=ui_font("body"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))

        # Optional encumbrance variant rule toggle
        self._enable_encumbrance_var = ctk.BooleanVar(
            value=self.settings_manager.settings.enable_encumbrance_rule
        )

        self._create_toggle_row(
            charsheet_content,
            "Enable the optional Encumbrance variant rule",
            self._enable_encumbrance_var,
            self._on_setting_change,
            pady=(15, 0)
        )

        ctk.CTkLabel(
            charsheet_content,
            text="When enabled, carrying more than 5x STR score also reduces speed by 10 ft\n(on top of the indicator above). Has no effect if the indicator is off.",
            font=ui_font("body"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))


    def _build_official_spells_section(self):
        """Build the Official Spells section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Official Spells Section ===
        self._create_section(self.container, "Official Spells")
        
        official_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(official_frame)
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
            font=ui_font("body"),
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
            font=ui_font("body"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))
        


    def _build_legacy_content_section(self):
        """Build the Legacy Content section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Legacy Content Section ===
        self._create_section(self.container, "Legacy Content")
        
        legacy_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(legacy_frame)
        legacy_frame.pack(fill="x", pady=(0, 20))
        
        legacy_content = ctk.CTkFrame(legacy_frame, fg_color="transparent")
        legacy_content.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            legacy_content,
            text="Control how 2014 (legacy) D&D content is displayed:",
            font=ui_font("body", 13),
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
                font=ui_font("small"),
                text_color=text_secondary
            ).pack(side="left", padx=(10, 0))
        


    def _build_monsters_section(self):
        """Build the Monsters section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Monsters Section ===
        self._create_section(self.container, "Monsters")

        monsters_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                      fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(monsters_frame)
        monsters_frame.pack(fill="x", pady=(0, 20))

        monsters_content = ctk.CTkFrame(monsters_frame, fg_color="transparent")
        monsters_content.pack(fill="x", padx=20, pady=15)

        self._create_toggle_row(
            monsters_content,
            "Display spell only summons",
            self._show_spell_only_summons_var,
            self._on_setting_change
        )
        ctk.CTkLabel(
            monsters_content,
            text="Creatures that exist only to be summoned by a spell (Bestial Spirit, Fey Spirit, ...)\n"
                 "always appear on their spell's page. Turn this on to list them in the Monsters\n"
                 "collection as well, and to offer them as link suggestions.",
            font=ui_font("body"),
            text_color=text_secondary,
            justify="left"
        ).pack(anchor="w", pady=(10, 0))


    def _build_loading_options_section(self):
        """Build the Loading Options section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Loading Options Section ===
        self._create_section(self.container, "Loading Options")
        
        loading_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(loading_frame)
        loading_frame.pack(fill="x", pady=(0, 20))
        
        loading_content = ctk.CTkFrame(loading_frame, fg_color="transparent")
        loading_content.pack(fill="x", padx=20, pady=15)
        
        self._create_toggle_row(
            loading_content,
            "Reopen my tabs on startup",
            self._restore_tabs_var,
            self._on_setting_change
        )
        ctk.CTkLabel(
            loading_content,
            text="Start where you left off: the tabs that were open when you closed the app\n"
                 "(and the page each one was on) come back. When off, the app opens on Home.",
            font=ui_font("body"),
            text_color=text_secondary,
            justify="left"
        ).pack(anchor="w", pady=(8, 20))

        ctk.CTkLabel(
            loading_content,
            text="Preloading data in the background after startup can reduce loading times when\n"
                 "navigating to different sections, but may increase startup time and memory usage.\n"
                 "Enable preloading for collections you use frequently.",
            font=ui_font("body"),
            text_color=text_secondary,
            justify="left"
        ).pack(anchor="w", pady=(0, 15))
        
        self._create_toggle_row(
            loading_content,
            "Preload Classes",
            self._preload_classes_var,
            self._on_setting_change
        )
        
        self._create_toggle_row(
            loading_content,
            "Preload Feats",
            self._preload_feats_var,
            self._on_setting_change,
            pady=(10, 0)
        )
        
        self._create_toggle_row(
            loading_content,
            "Preload Lineages",
            self._preload_lineages_var,
            self._on_setting_change,
            pady=(10, 0)
        )
        
        self._create_toggle_row(
            loading_content,
            "Preload Backgrounds",
            self._preload_backgrounds_var,
            self._on_setting_change,
            pady=(10, 0)
        )
        
        self._create_toggle_row(
            loading_content,
            "Preload Equipment",
            self._preload_equipment_var,
            self._on_setting_change,
            pady=(10, 0)
        )

        self._create_toggle_row(
            loading_content,
            "Preload Magic Items",
            self._preload_magic_items_var,
            self._on_setting_change,
            pady=(10, 0)
        )

        self._create_toggle_row(
            loading_content,
            "Preload Character Sheet Data",
            self._preload_sheets_var,
            self._on_setting_change,
            pady=(10, 0)
        )

        ctk.CTkLabel(
            loading_content,
            text="Changes take effect on next app restart.",
            font=ui_font("small"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(15, 0))
        


    def _build_object_linking_section(self):
        """Build the Object Linking section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === Object Linking Section ===
        self._create_section(self.container, "Object Linking")

        linking_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                     fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(linking_frame)
        linking_frame.pack(fill="x", pady=(0, 20))

        linking_content = ctk.CTkFrame(linking_frame, fg_color="transparent")
        linking_content.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            linking_content,
            text="While typing in a description or notes field, matching objects are "
                 "suggested as clickable links. Disable suggestions per category below - "
                 "links already made, and the right-click \"Find Link Suggestions\"/"
                 "\"Unlink\" options, are unaffected.",
            font=ui_font("body", 13), text_color=text_secondary,
            wraplength=560, justify="left",
        ).pack(anchor="w", pady=(0, 15))

        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Spells",
            self._link_disable_spells_var, self._on_setting_change,
        )
        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Feats",
            self._link_disable_feats_var, self._on_setting_change, pady=(10, 0),
        )
        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Lineages",
            self._link_disable_lineages_var, self._on_setting_change, pady=(10, 0),
        )
        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Backgrounds",
            self._link_disable_backgrounds_var, self._on_setting_change, pady=(10, 0),
        )
        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Classes (and Subclasses)",
            self._link_disable_classes_var, self._on_setting_change, pady=(10, 0),
        )
        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Equipment",
            self._link_disable_equipment_var, self._on_setting_change, pady=(10, 0),
        )
        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Magic Items",
            self._link_disable_magic_items_var, self._on_setting_change, pady=(10, 0),
        )
        self._create_toggle_row(
            linking_content, "Disable linking suggestions for Monsters",
            self._link_disable_monsters_var, self._on_setting_change, pady=(10, 0),
        )

        sep = ctk.CTkFrame(linking_content, fg_color=self.theme_manager.get_current_color('bg_tertiary'), height=1)
        sep.pack(fill="x", pady=(15, 12))

        self._create_toggle_row(
            linking_content,
            "Autocomplete linked words to the object's exact name (e.g. \"fire\" -> \"Fire Bolt\")",
            self._link_autocomplete_var, self._on_setting_change,
        )


    def _build_about_section(self):
        """Build the About section (built after the window is up: see _build_remaining)."""
        text_secondary = self.theme_manager.get_text_secondary()
        danger = self.theme_manager.get_current_color('button_danger')
        danger_hover = self.theme_manager.get_current_color('button_danger_hover')
        btn_text = self.theme_manager.get_current_color('text_primary')
        # === About Section ===
        self._create_section(self.container, "About")
        
        about_frame = ctk.CTkFrame(self.container, corner_radius=10,
                                   fg_color=self.theme_manager.get_current_color('bg_secondary'))
        self._card_frames.append(about_frame)
        about_frame.pack(fill="x", pady=(0, 20))
        
        about_content = ctk.CTkFrame(about_frame, fg_color="transparent")
        about_content.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            about_content,
            text="D&D Spellbook Manager",
            font=ui_font("heading", 16, bold=True)
        ).pack(anchor="w")
        
        text_secondary = self.theme_manager.get_text_secondary()
        ctk.CTkLabel(
            about_content,
            text="A tool for managing D&D 5e resources character sheets and player information.",
            font=ui_font("body", 13),
            text_color=text_secondary
        ).pack(anchor="w", pady=(5, 0))
        
        ctk.CTkLabel(
            about_content,
            text=f"Version {__version__} • Data stored in SQLite database",
            font=ui_font("body"),
            text_color=text_secondary
        ).pack(anchor="w", pady=(10, 0))

        # --- Updates ---
        update_row = ctk.CTkFrame(about_content, fg_color="transparent")
        update_row.pack(fill="x", pady=(15, 0))

        self._check_updates_btn = ctk.CTkButton(
            update_row,
            text="Check for Updates",
            width=170,
            fg_color=self.theme_manager.get_current_color('button_normal'),
            hover_color=self.theme_manager.get_current_color('button_hover'),
            text_color=self.theme_manager.get_current_color('text_primary'),
            command=self._on_check_for_updates
        )
        self._check_updates_btn.pack(side="left")

        self._update_status_label = ctk.CTkLabel(
            update_row,
            text="",
            font=ui_font("body"),
            text_color=text_secondary
        )
        self._update_status_label.pack(side="left", padx=(12, 0))

        self._create_toggle_row(
            about_content,
            "Check for updates automatically on startup",
            self._auto_check_updates_var,
            self._on_setting_change,
            pady=(12, 0)
        )


    def _create_section(self, parent, title: str):
        """Create a section header."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(10, 8))
        
        ctk.CTkLabel(
            header, text=title,
            font=ui_font("heading", 16, bold=True)
        ).pack(side="left")
    
    def _create_toggle_row(self, parent, text: str, variable: ctk.BooleanVar,
                           command: Callable, pady=(0, 0)):
        """Create a toggle switch row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=pady)
        
        ctk.CTkLabel(
            row, text=text,
            font=ui_font("subheading")
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

        def apply():
            # Apply the theme change
            ctk.set_appearance_mode(new_mode)
            if self.on_appearance_changed:
                self.on_appearance_changed(new_mode)
            flush_restyle()

        run_busy("appearance", "Switching appearance…", apply)

    def _theme_names(self):
        return [name for _key, name, _custom in self.theme_manager.list_themes()]

    def _on_color_theme_change(self, display_name: str):
        """Apply and persist a colour theme chosen from the dropdown."""
        key = next((k for k, name, _c in self.theme_manager.list_themes() if name == display_name), "default")
        # set_theme() notifies every registered theme listener, so open views
        # (and the app-wide restyler) recolour immediately.
        def apply():
            self.theme_manager.set_theme(key)
            self.settings_manager.update(theme_name=key)
            # Also refresh the tk-based widgets (context menu, paned sashes, spell
            # description) that don't listen to the theme manager directly.
            if self.on_appearance_changed:
                self.on_appearance_changed(self.settings_manager.settings.appearance_mode)
            flush_restyle()

        run_busy("theme", "Applying theme…", apply)

    def _open_theme_studio(self):
        """Open (or raise) the Theme Studio window."""
        existing = getattr(self, '_theme_studio', None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except Exception:
            pass
        from ui.theme_studio import ThemeStudioDialog
        self._theme_studio = ThemeStudioDialog(self.winfo_toplevel(), on_theme_applied=self._sync_theme_menu)

    def _sync_theme_menu(self, _key=None):
        """Keep the dropdown in step with themes picked/renamed/deleted in the Studio."""
        try:
            key = self.theme_manager.current_theme_name
            self._theme_menu.configure(values=self._theme_names())
            self._theme_var.set(self.theme_manager.display_name(key))
        except Exception:
            pass

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
            show_carry_weight_indicator=self._show_carry_weight_var.get(),
            enable_encumbrance_rule=self._enable_encumbrance_var.get(),
            legacy_content_filter=self._legacy_filter_var.get(),
            preload_classes=self._preload_classes_var.get(),
            preload_feats=self._preload_feats_var.get(),
            preload_lineages=self._preload_lineages_var.get(),
            preload_backgrounds=self._preload_backgrounds_var.get(),
            preload_equipment=self._preload_equipment_var.get(),
            preload_magic_items=self._preload_magic_items_var.get(),
            preload_character_sheets=self._preload_sheets_var.get(),
            auto_check_updates=self._auto_check_updates_var.get(),
            restore_tabs=self._restore_tabs_var.get(),
            link_suggest_spells=not self._link_disable_spells_var.get(),
            link_suggest_feats=not self._link_disable_feats_var.get(),
            link_suggest_lineages=not self._link_disable_lineages_var.get(),
            link_suggest_backgrounds=not self._link_disable_backgrounds_var.get(),
            link_suggest_classes=not self._link_disable_classes_var.get(),
            link_suggest_equipment=not self._link_disable_equipment_var.get(),
            link_suggest_magic_items=not self._link_disable_magic_items_var.get(),
            link_suggest_monsters=not self._link_disable_monsters_var.get(),
            link_autocomplete_names=self._link_autocomplete_var.get(),
            show_spell_only_summons=self._show_spell_only_summons_var.get(),
        )

    def _on_check_for_updates(self):
        """Manually check GitHub for a newer release (runs off the UI thread)."""
        if self._update_check_in_progress:
            return
        self._update_check_in_progress = True
        self._check_updates_btn.configure(state="disabled")
        self._update_status_label.configure(text="Checking…")

        def worker():
            try:
                from updater import check_for_update
                info = check_for_update()
                self.after(0, lambda: self._on_update_check_done(info, None))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._on_update_check_done(None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_done(self, info, error):
        """Back on the UI thread with the result of a manual update check."""
        self._update_check_in_progress = False
        try:
            self._check_updates_btn.configure(state="normal")
        except Exception:
            return  # view was destroyed while checking

        if error:
            self._update_status_label.configure(text="Couldn't check for updates.")
            return

        if info is None:
            self._update_status_label.configure(text=f"You're up to date (v{__version__}).")
            return

        self._update_status_label.configure(text=f"Version {info.version} is available.")
        try:
            from ui.update_dialog import UpdateDialog
            UpdateDialog(
                self.winfo_toplevel(),
                info,
                on_skip=lambda v: self.settings_manager.update(skipped_update_version=v),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Could not open update dialog: {exc}")

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
        self.build_all_sections_now()      # the variables below live in the deferred sections
        self.settings_manager.reset_to_defaults()
        # Custom themes are the user's own work, so they are kept; only the
        # selection goes back to the default theme. Fonts return to stock.
        self.theme_manager.set_theme("default")
        get_font_manager().reset()
        editor = getattr(self, '_typography_editor', None)
        if editor is not None:
            editor.refresh()
        
        # Update UI variables
        settings = self.settings_manager.settings
        self._appearance_var.set(settings.appearance_mode)
        theme_key = self.theme_manager.normalize_key(getattr(settings, 'theme_name', 'default'))
        self._theme_menu.configure(values=self._theme_names())
        self._theme_var.set(self.theme_manager.display_name(theme_key))
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
        self._show_carry_weight_var.set(settings.show_carry_weight_indicator)
        self._enable_encumbrance_var.set(settings.enable_encumbrance_rule)
        self._legacy_filter_var.set(settings.legacy_content_filter)
        self._auto_check_updates_var.set(getattr(settings, 'auto_check_updates', True))
        self._restore_tabs_var.set(getattr(settings, 'restore_tabs', True))
        self._link_disable_spells_var.set(not getattr(settings, 'link_suggest_spells', True))
        self._link_disable_feats_var.set(not getattr(settings, 'link_suggest_feats', True))
        self._link_disable_lineages_var.set(not getattr(settings, 'link_suggest_lineages', True))
        self._link_disable_backgrounds_var.set(not getattr(settings, 'link_suggest_backgrounds', True))
        self._link_disable_classes_var.set(not getattr(settings, 'link_suggest_classes', True))
        self._link_disable_equipment_var.set(not getattr(settings, 'link_suggest_equipment', True))
        self._link_disable_magic_items_var.set(not getattr(settings, 'link_suggest_magic_items', True))
        self._link_disable_monsters_var.set(not getattr(settings, 'link_suggest_monsters', True))
        self._show_spell_only_summons_var.set(getattr(settings, 'show_spell_only_summons', False))
        self._link_autocomplete_var.set(getattr(settings, 'link_autocomplete_names', True))

        # Apply appearance
        ctk.set_appearance_mode(settings.appearance_mode)
        if self.on_appearance_changed:
            self.on_appearance_changed(settings.appearance_mode)
    
    def refresh_from_settings(self):
        """Refresh UI from current settings (call when view becomes visible)."""
        if getattr(self, "_pending_sections", None):
            # Still being built: sections not built yet read the current settings
            # when they are, so there is nothing stale to refresh.
            self._sync_theme_menu()
            return
        settings = self.settings_manager.settings
        self._appearance_var.set(settings.appearance_mode)
        theme_key = self.theme_manager.normalize_key(getattr(settings, 'theme_name', 'default'))
        self._theme_menu.configure(values=self._theme_names())
        self._theme_var.set(self.theme_manager.display_name(theme_key))
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
        self._show_carry_weight_var.set(settings.show_carry_weight_indicator)
        self._enable_encumbrance_var.set(settings.enable_encumbrance_rule)
        self._legacy_filter_var.set(settings.legacy_content_filter)
        self._preload_classes_var.set(settings.preload_classes)
        self._preload_feats_var.set(settings.preload_feats)
        self._preload_lineages_var.set(settings.preload_lineages)
        self._preload_backgrounds_var.set(settings.preload_backgrounds)
        self._preload_equipment_var.set(getattr(settings, 'preload_equipment', True))
        self._preload_magic_items_var.set(getattr(settings, 'preload_magic_items', True))
        self._preload_sheets_var.set(settings.preload_character_sheets)
        self._auto_check_updates_var.set(getattr(settings, 'auto_check_updates', True))
        self._restore_tabs_var.set(getattr(settings, 'restore_tabs', True))
        self._link_disable_spells_var.set(not getattr(settings, 'link_suggest_spells', True))
        self._link_disable_feats_var.set(not getattr(settings, 'link_suggest_feats', True))
        self._link_disable_lineages_var.set(not getattr(settings, 'link_suggest_lineages', True))
        self._link_disable_backgrounds_var.set(not getattr(settings, 'link_suggest_backgrounds', True))
        self._link_disable_classes_var.set(not getattr(settings, 'link_suggest_classes', True))
        self._link_disable_equipment_var.set(not getattr(settings, 'link_suggest_equipment', True))
        self._link_disable_magic_items_var.set(not getattr(settings, 'link_suggest_magic_items', True))
        self._link_disable_monsters_var.set(not getattr(settings, 'link_suggest_monsters', True))
        self._show_spell_only_summons_var.set(getattr(settings, 'show_spell_only_summons', False))
        self._link_autocomplete_var.set(getattr(settings, 'link_autocomplete_names', True))

    def _on_theme_changed(self):
        """Update dynamic label/input colors when the appearance changes."""
        try:
            theme = self.theme_manager
            text_secondary = theme.get_text_secondary()

            # Labels, inputs and everything else are recoloured by the
            # app-wide restyler (ui/restyle.py), from their theme roles.
            self._sync_theme_menu()
        except Exception:
            pass

    def destroy(self):
        """Remove theme listener when view is destroyed."""
        try:
            self.theme_manager.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()