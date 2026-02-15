"""
Collections View for D&D Spellbook Application.
Provides access to various content collections (Spells, Feats, Classes, etc.)
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from typing import Optional, Callable
from theme import get_theme_manager
from ui.global_search import GlobalSearchBar

class ImportProgressSplash(ctk.CTkToplevel):
    """Progress splash screen shown during content import."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        
        # Configure window
        self.title("Importing...")
        self.geometry("400x200")
        self.resizable(False, False)
        
        # Remove window decorations for cleaner look
        self.overrideredirect(True)
        
        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 200) // 2
        self.geometry(f"400x200+{x}+{y}")
        
        # Keep on top
        self.attributes("-topmost", True)
        self.grab_set()
        
        self._create_widgets()
        self.lift()
        self.update()
    
    def _create_widgets(self):
        """Create splash screen widgets."""
        bg_color = self.theme.get_current_color('bg_secondary')
        
        self.container = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=12)
        self.container.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Add border effect
        border_frame = ctk.CTkFrame(
            self.container, 
            fg_color=self.theme.get_current_color('bg_primary'),
            corner_radius=10
        )
        border_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Title
        self.title_label = ctk.CTkLabel(
            border_frame,
            text="📥 Importing Content",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=(25, 15))
        
        # Status message
        self.status_label = ctk.CTkLabel(
            border_frame,
            text="Preparing import...",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_text_secondary()
        )
        self.status_label.pack(pady=(0, 12))
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(
            border_frame,
            width=320,
            height=12,
            progress_color=self.theme.get_current_color('accent_primary'),
            fg_color=self.theme.get_current_color('bg_tertiary'),
            corner_radius=6
        )
        self.progress.pack(pady=(0, 15))
        self.progress.set(0)
        
        # Item counter
        self.count_label = ctk.CTkLabel(
            border_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_text_secondary()
        )
        self.count_label.pack(pady=(0, 10))
    
    def set_status(self, message: str):
        """Update the status message."""
        self.status_label.configure(text=message)
        self.update()
    
    def set_progress(self, value: float):
        """Set progress bar value (0.0 to 1.0)."""
        self.progress.set(value)
        self.update()
    
    def set_count(self, current: int, total: int, item_type: str = "items"):
        """Update the item counter."""
        self.count_label.configure(text=f"{current} / {total} {item_type}")
        self.update()
    
    def update_progress(self, message: str, value: float, current: int = 0, total: int = 0, item_type: str = ""):
        """Update status, progress, and optionally count."""
        self.set_status(message)
        self.set_progress(value)
        if total > 0:
            self.set_count(current, total, item_type)
        self.update()

class CollectionsView(ctk.CTkFrame):
    """Main collections hub with buttons for different content types."""
    
    def __init__(self, parent, spell_manager=None, on_navigate: Optional[Callable[..., None]] = None):
        super().__init__(parent, fg_color="transparent")
        
        self.spell_manager = spell_manager
        self.on_navigate = on_navigate  # Callback for navigation to sub-pages
        self.theme = get_theme_manager()
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the collections UI."""
        # Main scrollable container
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header_frame, text="Collections",
            font=ctk.CTkFont(size=28, weight="bold")
        ).pack(side="left")
        
        # Import/Export buttons in header
        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.pack(side="right")
        
        # Character sheet import/export
        ctk.CTkButton(
            btn_frame, text="📋 Char Export",
            width=110,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_character_export
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, text="📋 Char Import",
            width=110,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_character_import
        ).pack(side="left", padx=5)
        
        # Content import/export
        ctk.CTkButton(
            btn_frame, text="📥 Import",
            width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_import
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, text="📤 Export",
            width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_export
        ).pack(side="left", padx=5)
        
        # Global search bar
        self.search_bar = GlobalSearchBar(
            self.container,
            on_result_selected=self._on_search_result_selected
        )
        self.search_bar.pack(fill="x", pady=(0, 15))
        
        # Description
        ctk.CTkLabel(
            self.container,
            text="Browse and manage your D&D 5e content collections.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.get_text_secondary()
        ).pack(anchor="w", pady=(0, 20))
        
        # Collection buttons grid
        collections_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        collections_frame.pack(fill="both", expand=True)
        
        # Configure grid
        for i in range(3):
            collections_frame.columnconfigure(i, weight=1, uniform="col")
        
        # Define collections with their status
        collections = [
            ("📜 Spells", "spells", True, "Browse and manage your spell database"),
            ("⚔️ Feats", "feats", True, "Character feats and abilities"),
            ("🧬 Lineages", "lineages", True, "Races and species options"),
            ("✨ Magic Items", "magic_items", False, "Magical equipment and artifacts"),
            ("🎭 Classes", "classes", True, "Character class definitions"),
            ("📖 Backgrounds", "backgrounds", True, "Character background options"),
            ("🛡️ Equipment", "equipment", False, "Mundane items and gear"),
            ("👹 Monsters", "monsters", False, "Creature stat blocks"),
            ("📚 Rules", "rules", False, "Game rules and references"),
        ]
        
        row = 0
        col = 0
        for title, key, is_active, description in collections:
            self._create_collection_card(
                collections_frame, title, key, is_active, description, row, col
            )
            col += 1
            if col >= 3:
                col = 0
                row += 1
    
    def _create_collection_card(self, parent, title: str, key: str, is_active: bool, 
                                 description: str, row: int, col: int):
        """Create a collection card button."""
        # Card frame
        card = ctk.CTkFrame(
            parent,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=12
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Inner padding frame
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_color = self.theme.get_current_color('text_primary') if is_active else self.theme.get_text_secondary()
        ctk.CTkLabel(
            inner, text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=title_color
        ).pack(anchor="w")
        
        # Description
        ctk.CTkLabel(
            inner, text=description,
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_text_secondary(),
            wraplength=200,
            justify="left"
        ).pack(anchor="w", pady=(5, 15))
        
        # Status or button
        if is_active:
            btn = ctk.CTkButton(
                inner, text="Browse →",
                width=120,
                fg_color=self.theme.get_current_color('accent_primary'),
                hover_color=self.theme.get_current_color('accent_secondary'),
                command=lambda k=key: self._navigate_to(k)
            )
            btn.pack(anchor="w")
        else:
            # Inactive status
            status_frame = ctk.CTkFrame(inner, fg_color="transparent")
            status_frame.pack(anchor="w")
            
            ctk.CTkLabel(
                status_frame,
                text="🚧 Incomplete",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_text_secondary()
            ).pack(side="left")
            
            # Disabled button
            btn = ctk.CTkButton(
                inner, text="Coming Soon",
                width=120,
                fg_color=self.theme.get_current_color('bg_tertiary'),
                hover_color=self.theme.get_current_color('bg_tertiary'),
                text_color=self.theme.get_text_secondary(),
                state="disabled"
            )
            btn.pack(anchor="w", pady=(10, 0))
    
    def _navigate_to(self, collection_key: str):
        """Navigate to a specific collection."""
        # Clean up search bar before navigating
        if hasattr(self, 'search_bar'):
            self.search_bar.cleanup()
        if self.on_navigate:
            self.on_navigate(collection_key)
    
    def _on_search_result_selected(self, section: str, name: str, result_id: int):
        """Handle selection of a search result."""
        # Map section names to navigation keys
        section_map = {
            'Spells': 'spells',
            'Feats': 'feats', 
            'Lineages': 'lineages',
            'Classes': 'classes',
            'Subclasses': 'classes',  # Subclasses navigate to classes
            'Backgrounds': 'backgrounds'
        }
        
        nav_key = section_map.get(section, section.lower())
        
        # Navigate with the item name to open
        if self.on_navigate:
            # Pass the name as a second argument for the view to open
            self.on_navigate(nav_key, name)
    
    def _on_import(self):
        """Handle import button click."""
        # Show import options dialog
        dialog = ImportDialog(
            self.winfo_toplevel(), 
            self.spell_manager,
            on_import_complete=self._on_import_complete
        )
        dialog.grab_set()
    
    def _on_import_complete(self):
        """Handle post-import refresh of all views and managers."""
        # Reload all managers to pick up new content
        from character_class import get_class_manager
        from feat import get_feat_manager
        from lineage import get_lineage_manager
        
        # Reload class manager (which also updates CharacterClass custom classes)
        class_manager = get_class_manager()
        class_manager.load()
        
        # Reload feat manager
        feat_manager = get_feat_manager()
        feat_manager.load()
        
        # Reload lineage manager
        lineage_manager = get_lineage_manager()
        lineage_manager.load_lineages()
        
        # Reload spell manager if available
        if self.spell_manager:
            self.spell_manager.load_spells()
        
        # Try to refresh the main window's class filter dropdown
        try:
            main_window = self.winfo_toplevel()
            if hasattr(main_window, 'refresh_class_filter'):
                main_window.refresh_class_filter()
        except Exception:
            pass
    
    def _on_character_export(self):
        """Handle character sheet export button click."""
        dialog = CharacterSheetExportDialog(self.winfo_toplevel())
        dialog.grab_set()
    
    def _on_character_import(self):
        """Handle character sheet import button click."""
        file_path = filedialog.askopenfilename(
            title="Import Character Sheets",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        
        if not file_path:
            return
        
        import json
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "character_sheets" not in data and "sheets" not in data:
                messagebox.showerror(
                    "Invalid File",
                    "This file does not contain character sheet data.",
                    parent=self
                )
                return
            
            # Get sheets data (support both formats)
            sheets_data = data.get("character_sheets", data.get("sheets", {}))
            
            if not sheets_data:
                messagebox.showinfo("No Data", "No character sheets found in file.", parent=self)
                return
            
            # Import character sheets with missing content validation
            from ui.character_sheet_view import get_sheet_manager
            from character_manager import CharacterManager
            
            sheet_manager = get_sheet_manager()
            char_manager = CharacterManager()
            char_manager.load_characters()
            
            imported = 0
            warnings = []
            
            for name, sheet_data in sheets_data.items():
                try:
                    from character_sheet import CharacterSheet
                    sheet = CharacterSheet.from_dict(sheet_data)
                    
                    # Check if character spell list exists
                    char_exists = char_manager.get_character(name) is not None
                    if not char_exists:
                        warnings.append(f"'{name}': No matching character spell list found")
                    
                    # Import the sheet
                    sheet_manager.update_sheet(name, sheet)
                    imported += 1
                except Exception as e:
                    warnings.append(f"'{name}': Import error - {e}")
            
            # Import character spell lists if present
            spell_lists_data = data.get("character_spell_lists", [])
            spell_list_imported = 0
            
            for char_data in spell_lists_data:
                try:
                    from character import CharacterSpellList
                    char = CharacterSpellList.from_dict(char_data)
                    
                    # Validate class references
                    from character_class import get_class_manager
                    class_manager = get_class_manager()
                    
                    for cl in char.classes:
                        class_name = cl.character_class.value if hasattr(cl.character_class, 'value') else str(cl.character_class)
                        if not class_manager.get_class(class_name):
                            warnings.append(f"'{char.name}': Class '{class_name}' not found in system")
                    
                    # Validate spell references
                    if self.spell_manager:
                        for spell_name in char.known_spells + char.prepared_spells:
                            if not self.spell_manager._db.get_spell_by_name(spell_name):
                                warnings.append(f"'{char.name}': Spell '{spell_name}' not found")
                    
                    # Add or update character
                    if char_manager.get_character(char.name):
                        char_manager.update_character(char.name, char)
                    else:
                        char_manager.add_character(char)
                    spell_list_imported += 1
                except Exception as e:
                    warnings.append(f"Character spell list error: {e}")
            
            # Show results
            msg = f"Successfully imported {imported} character sheet(s)"
            if spell_list_imported > 0:
                msg += f" and {spell_list_imported} character spell list(s)"
            msg += "."
            
            if warnings:
                msg += f"\n\nWarnings ({len(warnings)}):\n"
                msg += "\n".join(warnings[:10])  # Show first 10 warnings
                if len(warnings) > 10:
                    msg += f"\n... and {len(warnings) - 10} more"
                messagebox.showwarning("Import Complete with Warnings", msg, parent=self)
            else:
                messagebox.showinfo("Import Complete", msg, parent=self)
                
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Failed to parse file:\n{e}", parent=self)
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import:\n{e}", parent=self)
    
    def _on_export(self):
        """Handle export button click."""
        # Show export options dialog  
        dialog = ExportDialog(self.winfo_toplevel(), self.spell_manager)
        dialog.grab_set()


class ImportDialog(ctk.CTkToplevel):
    """Dialog for importing content with auto-detection."""
    
    def __init__(self, parent, spell_manager=None, on_import_complete: Optional[Callable] = None):
        super().__init__(parent)
        
        self.spell_manager = spell_manager
        self.on_import_complete = on_import_complete
        self.theme = get_theme_manager()
        
        self.title("Import Content")
        self.geometry("500x420")
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 420) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create import dialog UI."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            container, text="Import Content",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(
            container,
            text="Import content from JSON or text files.\nThe system will automatically detect the content type(s).",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_text_secondary(),
            justify="left"
        ).pack(anchor="w", pady=(0, 20))
        
        # Import buttons
        ctk.CTkLabel(container, text="Import Options:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 10))
        
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(
            btn_frame, text="📄 Import from JSON",
            width=200, height=40,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_secondary'),
            command=self._import_json
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_frame, text="📜 Import Spells from TXT",
            width=200, height=40,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._import_spells_txt
        ).pack(side="left")
        
        # Info text
        info_frame = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        info_frame.pack(fill="x", pady=(20, 0))
        
        ctk.CTkLabel(
            info_frame,
            text="ℹ️ JSON files can contain multiple content types:\n"
                 "   • Spells, Feats, Classes, Subclasses, Lineages, Backgrounds\n"
                 "   • All detected types will be imported automatically\n"
                 "   • Imported content is marked as custom (non-official)",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_text_secondary(),
            justify="left"
        ).pack(padx=15, pady=12)
        
        # Cancel button
        ctk.CTkButton(
            container, text="Close",
            width=100,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(pady=(20, 0))
    
    def _import_json(self):
        """Import content from a JSON file with auto-detection and progress tracking."""
        import json
        from feat import get_feat_manager
        from character_class import get_class_manager
        from lineage import get_lineage_manager
        
        file_path = filedialog.askopenfilename(
            title="Select JSON File to Import",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Calculate total items for progress
            total_items = 0
            if "spells" in data:
                total_items += len(data["spells"])
            if "feats" in data:
                total_items += len(data["feats"])
            if "classes" in data:
                total_items += len(data["classes"])
            if "subclasses" in data:
                total_items += len(data["subclasses"])
            if "lineages" in data:
                total_items += len(data["lineages"])
            if "backgrounds" in data:
                total_items += len(data["backgrounds"])
            
            if total_items == 0:
                messagebox.showwarning(
                    "No Content Found",
                    "No recognized content types found in the file.\n\n"
                    "Expected keys: spells, feats, classes, subclasses, lineages, backgrounds",
                    parent=self
                )
                return
            
            # Show progress splash
            progress_splash = ImportProgressSplash(self)
            current_item = 0
            results = []
            import_warnings = []  # Track missing references
            
            try:
                # Import classes FIRST (so custom class names are registered for spells)
                if "classes" in data:
                    class_manager = get_class_manager()
                    class_count = 0
                    spells_updated = 0
                    class_total = len(data["classes"])
                    for i, class_data in enumerate(data["classes"]):
                        from character_class import CharacterClassDefinition
                        cls = CharacterClassDefinition.from_dict(class_data)
                        cls.is_custom = True
                        class_manager.add_class(cls)
                        class_count += 1
                        
                        # Register custom class name with CharacterClass enum
                        from spell import CharacterClass
                        CharacterClass.register_custom_class(cls.name)
                        
                        current_item += 1
                        progress_splash.update_progress(
                            f"Importing class: {class_data.get('name', 'Unknown')}",
                            current_item / total_items,
                            i + 1, class_total, "classes"
                        )
                    
                    if class_count > 0:
                        results.append(f"{class_count} class(es)")
                
                # Import subclasses SECOND
                if "subclasses" in data:
                    class_manager = get_class_manager()
                    subclass_count = 0
                    subclass_total = len(data["subclasses"])
                    for i, subclass_data in enumerate(data["subclasses"]):
                        from character_class import SubclassDefinition
                        subclass = SubclassDefinition.from_dict(subclass_data)
                        subclass.is_custom = True
                        parent_class = class_manager.get_class(subclass.parent_class)
                        if parent_class:
                            # Check for missing subclass spells
                            if self.spell_manager and subclass.subclass_spells:
                                for spell in subclass.subclass_spells:
                                    spell_name = spell.spell_name if hasattr(spell, 'spell_name') else str(spell)
                                    if not self.spell_manager._db.get_spell_by_name(spell_name):
                                        import_warnings.append(f"Subclass '{subclass.name}': Spell '{spell_name}' not found")
                            
                            parent_class.subclasses.append(subclass)
                            class_manager.add_class(parent_class)
                            subclass_count += 1
                        else:
                            import_warnings.append(f"Subclass '{subclass.name}': Parent class '{subclass.parent_class}' not found")
                        current_item += 1
                        progress_splash.update_progress(
                            f"Importing subclass: {subclass_data.get('name', 'Unknown')}",
                            current_item / total_items,
                            i + 1, subclass_total, "subclasses"
                        )
                    if subclass_count > 0:
                        results.append(f"{subclass_count} subclass(es)")
                
                # Import spells THIRD (after classes are registered) - using bulk import
                if "spells" in data and self.spell_manager:
                    spell_total = len(data["spells"])
                    
                    # Convert all spell dicts to Spell objects first
                    spells_to_add = []
                    for i, spell_data in enumerate(data["spells"]):
                        try:
                            spell = self.spell_manager._dict_to_spell(spell_data)
                            spells_to_add.append(spell)
                        except Exception as e:
                            print(f"Error converting spell: {e}")
                        # Update progress every 20 spells during conversion
                        if (i + 1) % 20 == 0 or i == spell_total - 1:
                            progress_splash.update_progress(
                                f"Preparing spell {i + 1} of {spell_total}...",
                                current_item / total_items,
                                i + 1, spell_total, "spells"
                            )
                    
                    # Bulk add with progress callback
                    def spell_progress(current, total):
                        progress_splash.update_progress(
                            f"Saving spells to database ({current}/{total})...",
                            (current_item + current) / total_items,
                            current, total, "spells"
                        )
                    
                    spell_count = self.spell_manager.bulk_add_spells(spells_to_add, spell_progress)
                    current_item += spell_total
                    
                    if spell_count > 0:
                        results.append(f"{spell_count} spell(s)")
                
                # Now add class spell lists to existing spells
                if "classes" in data:
                    class_manager = get_class_manager()
                    spells_updated = 0
                    for class_data in data["classes"]:
                        cls = class_manager.get_class(class_data.get('name', ''))
                        if cls and cls.spell_list:
                            from database import SpellDatabase
                            db = SpellDatabase()
                            
                            # Check for missing spells before linking
                            if self.spell_manager:
                                for spell_name in cls.spell_list:
                                    if not self.spell_manager._db.get_spell_by_name(spell_name):
                                        import_warnings.append(f"Class '{cls.name}' spell list: '{spell_name}' not found")
                            
                            updated = db.add_class_to_spells(cls.name, cls.spell_list)
                            spells_updated += updated
                    
                    if spells_updated > 0:
                        results.append(f"({spells_updated} spells linked to classes)")
                        if self.spell_manager:
                            self.spell_manager.load_spells()
                
                # Import feats
                if "feats" in data:
                    feat_manager = get_feat_manager()
                    feat_count = 0
                    feat_total = len(data["feats"])
                    for i, feat_data in enumerate(data["feats"]):
                        from feat import Feat
                        feat = Feat.from_dict(feat_data)
                        feat.is_custom = True
                        feat.is_official = False
                        feat_manager.add_feat(feat)
                        feat_count += 1
                        current_item += 1
                        progress_splash.update_progress(
                            f"Importing feat: {feat_data.get('name', 'Unknown')}",
                            current_item / total_items,
                            i + 1, feat_total, "feats"
                        )
                    if feat_count > 0:
                        results.append(f"{feat_count} feat(s)")
                
                # Import lineages
                if "lineages" in data:
                    lineage_manager = get_lineage_manager()
                    lineage_count = 0
                    lineage_total = len(data["lineages"])
                    for i, lineage_data in enumerate(data["lineages"]):
                        from lineage import Lineage
                        lineage = Lineage.from_dict(lineage_data)
                        lineage.is_custom = True
                        lineage.is_official = False
                        lineage_manager.add_lineage(lineage)
                        lineage_count += 1
                        current_item += 1
                        progress_splash.update_progress(
                            f"Importing lineage: {lineage_data.get('name', 'Unknown')}",
                            current_item / total_items,
                            i + 1, lineage_total, "lineages"
                        )
                    if lineage_count > 0:
                        results.append(f"{lineage_count} lineage(s)")
                
                # Import backgrounds
                if "backgrounds" in data:
                    from background import get_background_manager, Background
                    background_manager = get_background_manager()
                    bg_count = 0
                    bg_total = len(data["backgrounds"])
                    for i, bg_data in enumerate(data["backgrounds"]):
                        background = Background.from_dict(bg_data)
                        background.is_custom = True
                        background.is_official = False
                        background_manager.add_background(background)
                        bg_count += 1
                        current_item += 1
                        progress_splash.update_progress(
                            f"Importing background: {bg_data.get('name', 'Unknown')}",
                            current_item / total_items,
                            i + 1, bg_total, "backgrounds"
                        )
                    if bg_count > 0:
                        results.append(f"{bg_count} background(s)")
                
                # Complete
                progress_splash.update_progress("Import complete!", 1.0)
                
            finally:
                progress_splash.destroy()
            
            if results:
                msg = f"Successfully imported:\n• " + "\n• ".join(results)
                
                if import_warnings:
                    msg += f"\n\nWarnings ({len(import_warnings)}):\n"
                    # Deduplicate and limit warnings
                    unique_warnings = list(dict.fromkeys(import_warnings))
                    msg += "\n".join(unique_warnings[:10])
                    if len(unique_warnings) > 10:
                        msg += f"\n... and {len(unique_warnings) - 10} more"
                    messagebox.showwarning("Import Complete with Warnings", msg, parent=self)
                else:
                    messagebox.showinfo("Import Complete", msg, parent=self)
                
                # Trigger post-import refresh callback
                if self.on_import_complete:
                    self.on_import_complete()
                
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import content:\n{e}", parent=self)
    
    def _import_spells_txt(self):
        """Import spells from a text file."""
        file_path = filedialog.askopenfilename(
            title="Select Spell Text File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            parent=self
        )
        
        if file_path and self.spell_manager:
            try:
                count = self.spell_manager.import_from_text_file(file_path)
                messagebox.showinfo("Import Complete", f"Successfully imported {count} spells.", parent=self)
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import spells:\n{e}", parent=self)


class ExportDialog(ctk.CTkToplevel):
    """Dialog for exporting content with type and source selection using dropdowns."""
    
    def __init__(self, parent, spell_manager=None):
        super().__init__(parent)
        
        self.spell_manager = spell_manager
        self.theme = get_theme_manager()
        
        self.title("Export Content")
        self.geometry("500x450")
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 450) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create export dialog UI."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            container, text="Export Content",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(
            container,
            text="Only custom (non-official) content can be exported.",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_text_secondary()
        ).pack(anchor="w", pady=(0, 20))
        
        # Content type selection dropdown
        type_frame = ctk.CTkFrame(container, fg_color="transparent")
        type_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(type_frame, text="Content Type:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        
        self.content_type_var = ctk.StringVar(value="All")
        content_types = ["All", "Spells", "Feats", "Classes", "Subclasses", "Lineages", "Backgrounds"]
        
        self.type_combo = ctk.CTkComboBox(
            type_frame, width=200, height=35,
            values=content_types,
            variable=self.content_type_var,
            command=lambda _: self._update_sources(),
            state="readonly"
        )
        self.type_combo.pack(side="left")
        
        # Source selection dropdown
        source_frame = ctk.CTkFrame(container, fg_color="transparent")
        source_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(source_frame, text="Source:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        
        self.source_var = ctk.StringVar(value="All Sources")
        self.source_combo = ctk.CTkComboBox(
            source_frame, width=250, height=35,
            values=["All Sources"],
            variable=self.source_var,
            command=lambda _: self._update_info(),
            state="readonly"
        )
        self.source_combo.pack(side="left")
        
        # Initialize sources
        self._update_sources()
        
        # Export preview info
        preview_frame = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        preview_frame.pack(fill="x", pady=(10, 0))
        
        self.info_label = ctk.CTkLabel(
            preview_frame,
            text="",
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        self.info_label.pack(padx=15, pady=12, anchor="w")
        self._update_info()
        
        # Export button
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(25, 0))
        
        ctk.CTkButton(
            btn_frame, text="📤 Export to JSON",
            width=150, height=40,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_secondary'),
            command=self._export
        ).pack(side="left")
        
        ctk.CTkButton(
            btn_frame, text="Cancel",
            width=100, height=40,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(side="right")
    
    def _get_all_unofficial_sources(self) -> list:
        """Get all unofficial sources across all content types."""
        from feat import get_feat_manager
        from character_class import get_class_manager
        from lineage import get_lineage_manager
        from background import get_background_manager
        
        sources = set()
        
        if self.spell_manager:
            sources.update(self.spell_manager.get_unofficial_sources())
        sources.update(get_feat_manager().get_unofficial_sources())
        sources.update(get_class_manager().get_unofficial_class_sources())
        sources.update(get_class_manager().get_unofficial_subclass_sources())
        sources.update(get_lineage_manager().get_unofficial_sources())
        sources.update(get_background_manager().get_unofficial_sources())
        
        return sorted(sources)
    
    def _update_sources(self):
        """Update source dropdown based on selected content type."""
        from feat import get_feat_manager
        from character_class import get_class_manager
        from lineage import get_lineage_manager
        from background import get_background_manager
        
        content_type = self.content_type_var.get()
        sources = []
        
        if content_type == "All":
            sources = self._get_all_unofficial_sources()
        elif content_type == "Spells" and self.spell_manager:
            sources = self.spell_manager.get_unofficial_sources()
        elif content_type == "Feats":
            sources = get_feat_manager().get_unofficial_sources()
        elif content_type == "Classes":
            sources = get_class_manager().get_unofficial_class_sources()
        elif content_type == "Subclasses":
            sources = get_class_manager().get_unofficial_subclass_sources()
        elif content_type == "Lineages":
            sources = get_lineage_manager().get_unofficial_sources()
        elif content_type == "Backgrounds":
            sources = get_background_manager().get_unofficial_sources()
        
        source_options = ["All Sources"] + sources
        self.source_combo.configure(values=source_options)
        self.source_var.set("All Sources")
        
        self._update_info()
    
    def _get_export_counts(self) -> dict:
        """Get counts of items that will be exported."""
        from feat import get_feat_manager
        from character_class import get_class_manager
        from lineage import get_lineage_manager
        from background import get_background_manager
        
        content_type = self.content_type_var.get()
        source = self.source_var.get()
        source_filter = None if source == "All Sources" else source
        
        counts = {}
        
        def filter_by_source(items, source_attr='source'):
            if source_filter is None:
                return items
            return [i for i in items if getattr(i, source_attr) == source_filter]
        
        if content_type in ["All", "Spells"] and self.spell_manager:
            items = [s for s in self.spell_manager.spells if not s.is_official]
            items = filter_by_source(items)
            if items:
                counts["Spells"] = len(items)
        
        if content_type in ["All", "Feats"]:
            items = get_feat_manager().get_unofficial_feats()
            items = filter_by_source(items)
            if items:
                counts["Feats"] = len(items)
        
        if content_type in ["All", "Classes"]:
            items = get_class_manager().get_unofficial_classes()
            items = filter_by_source(items)
            if items:
                counts["Classes"] = len(items)
        
        if content_type in ["All", "Subclasses"]:
            items = get_class_manager().get_unofficial_subclasses()
            items = filter_by_source(items)
            if items:
                counts["Subclasses"] = len(items)
        
        if content_type in ["All", "Lineages"]:
            items = get_lineage_manager().get_unofficial_lineages()
            items = filter_by_source(items)
            if items:
                counts["Lineages"] = len(items)
        
        if content_type in ["All", "Backgrounds"]:
            items = get_background_manager().get_unofficial_backgrounds()
            items = filter_by_source(items)
            if items:
                counts["Backgrounds"] = len(items)
        
        return counts
    
    def _update_info(self):
        """Update the info label with export preview."""
        counts = self._get_export_counts()
        
        if not counts:
            self.info_label.configure(text="No custom content available to export.")
        else:
            lines = ["Will export:"]
            total = 0
            for content_type, count in counts.items():
                lines.append(f"  • {count} {content_type.lower()}")
                total += count
            lines.append(f"\nTotal: {total} item(s)")
            self.info_label.configure(text="\n".join(lines))
    
    def _export(self):
        """Export selected content to JSON."""
        from feat import get_feat_manager
        from character_class import get_class_manager
        from lineage import get_lineage_manager
        from background import get_background_manager
        
        counts = self._get_export_counts()
        if not counts:
            messagebox.showwarning("Nothing to Export", "No custom content available to export.", parent=self)
            return
        
        content_type = self.content_type_var.get()
        source = self.source_var.get()
        source_filter = None if source == "All Sources" else source
        
        # Determine default filename
        if content_type == "All":
            default_name = "content_export.json"
        else:
            default_name = f"{content_type.lower()}_export.json"
        
        file_path = filedialog.asksaveasfilename(
            title="Export Content",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        
        if not file_path:
            return
        
        try:
            import json
            
            def filter_by_source(items, source_attr='source'):
                if source_filter is None:
                    return items
                return [i for i in items if getattr(i, source_attr) == source_filter]
            
            export_data = {}
            
            if content_type in ["All", "Spells"] and self.spell_manager:
                items = [s for s in self.spell_manager.spells if not s.is_official]
                items = filter_by_source(items)
                if items:
                    export_data["spells"] = [s.to_dict() for s in items]
            
            if content_type in ["All", "Feats"]:
                items = get_feat_manager().get_unofficial_feats()
                items = filter_by_source(items)
                if items:
                    export_data["feats"] = [f.to_dict() for f in items]
            
            if content_type in ["All", "Classes"]:
                items = get_class_manager().get_unofficial_classes()
                items = filter_by_source(items)
                if items:
                    export_data["classes"] = [c.to_dict() for c in items]
            
            if content_type in ["All", "Subclasses"]:
                items = get_class_manager().get_unofficial_subclasses()
                items = filter_by_source(items)
                if items:
                    export_data["subclasses"] = [s.to_dict() for s in items]
            
            if content_type in ["All", "Lineages"]:
                items = get_lineage_manager().get_unofficial_lineages()
                items = filter_by_source(items)
                if items:
                    export_data["lineages"] = [l.to_dict() for l in items]
            
            if content_type in ["All", "Backgrounds"]:
                items = get_background_manager().get_unofficial_backgrounds()
                items = filter_by_source(items)
                if items:
                    export_data["backgrounds"] = [b.to_dict() for b in items]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            # Build success message
            exported = []
            for key, items in export_data.items():
                exported.append(f"{len(items)} {key}")
            
            messagebox.showinfo(
                "Export Complete",
                f"Successfully exported:\n• " + "\n• ".join(exported),
                parent=self
            )
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export content:\n{e}", parent=self)


class CharacterSheetExportDialog(ctk.CTkToplevel):
    """Dialog for exporting character sheets with selection."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        
        self.title("Export Character Sheets")
        self.geometry("500x550")
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 550) // 2
        self.geometry(f"+{x}+{y}")
        
        self._selected_chars = {}  # character_name -> BooleanVar
        self._create_widgets()
    
    def _create_widgets(self):
        """Create export dialog UI."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            container, text="Export Character Sheets",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(
            container,
            text="Select characters to export. Both character sheet and spell list data will be included.",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_text_secondary(),
            wraplength=460
        ).pack(anchor="w", pady=(0, 15))
        
        # Select All / Deselect All buttons
        select_frame = ctk.CTkFrame(container, fg_color="transparent")
        select_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(
            select_frame, text="Select All", width=100, height=30,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._select_all
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            select_frame, text="Deselect All", width=100, height=30,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._deselect_all
        ).pack(side="left")
        
        # Character selection list
        list_frame = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        list_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        # Scrollable area
        self.scroll_frame = ctk.CTkScrollableFrame(
            list_frame, fg_color="transparent",
            height=250
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Load characters
        from character_manager import CharacterManager
        from ui.character_sheet_view import get_sheet_manager
        
        char_manager = CharacterManager()
        char_manager.load_characters()
        sheet_manager = get_sheet_manager()
        
        characters = char_manager.characters
        
        if not characters:
            ctk.CTkLabel(
                self.scroll_frame, text="No characters found.",
                text_color=self.theme.get_text_secondary()
            ).pack(pady=20)
        else:
            for char in characters:
                var = ctk.BooleanVar(value=True)  # Default to selected
                self._selected_chars[char.name] = var
                
                # Check if sheet exists
                sheet_exists = sheet_manager.get_sheet(char.name) is not None
                
                char_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
                char_frame.pack(fill="x", pady=2)
                
                cb = ctk.CTkCheckBox(
                    char_frame, text=char.name,
                    variable=var,
                    command=self._update_count
                )
                cb.pack(side="left", padx=5)
                
                # Class info
                if char.classes:
                    class_info = ", ".join([f"{cl.character_class.value} {cl.level}" for cl in char.classes])
                    ctk.CTkLabel(
                        char_frame, text=f"({class_info})",
                        text_color=self.theme.get_text_secondary(),
                        font=ctk.CTkFont(size=11)
                    ).pack(side="left", padx=5)
                
                # Sheet status
                status_text = "✓ Sheet" if sheet_exists else "○ No sheet"
                status_color = self.theme.get_current_color('success') if sheet_exists else self.theme.get_text_secondary()
                ctk.CTkLabel(
                    char_frame, text=status_text,
                    text_color=status_color,
                    font=ctk.CTkFont(size=10)
                ).pack(side="right", padx=10)
        
        # Count label
        self.count_label = ctk.CTkLabel(
            container, text="",
            font=ctk.CTkFont(size=12)
        )
        self.count_label.pack(anchor="w", pady=(0, 15))
        self._update_count()
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(
            btn_frame, text="📤 Export Selected",
            width=150, height=40,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_secondary'),
            command=self._export
        ).pack(side="left")
        
        ctk.CTkButton(
            btn_frame, text="Cancel",
            width=100, height=40,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(side="right")
    
    def _select_all(self):
        """Select all characters."""
        for var in self._selected_chars.values():
            var.set(True)
        self._update_count()
    
    def _deselect_all(self):
        """Deselect all characters."""
        for var in self._selected_chars.values():
            var.set(False)
        self._update_count()
    
    def _update_count(self):
        """Update the selection count label."""
        selected = sum(1 for var in self._selected_chars.values() if var.get())
        total = len(self._selected_chars)
        self.count_label.configure(text=f"Selected: {selected} of {total} character(s)")
    
    def _export(self):
        """Export selected characters."""
        selected_names = [name for name, var in self._selected_chars.items() if var.get()]
        
        if not selected_names:
            messagebox.showwarning("No Selection", "Please select at least one character to export.", parent=self)
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export Character Sheets",
            defaultextension=".json",
            initialfile="character_sheets_export.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        
        if not file_path:
            return
        
        try:
            import json
            from character_manager import CharacterManager
            from ui.character_sheet_view import get_sheet_manager
            
            char_manager = CharacterManager()
            char_manager.load_characters()
            sheet_manager = get_sheet_manager()
            
            export_data = {
                "character_sheets": {},
                "character_spell_lists": []
            }
            
            sheets_exported = 0
            spell_lists_exported = 0
            
            for name in selected_names:
                # Export character spell list
                char = char_manager.get_character(name)
                if char:
                    export_data["character_spell_lists"].append(char.to_dict())
                    spell_lists_exported += 1
                
                # Export character sheet
                sheet = sheet_manager.get_sheet(name)
                if sheet:
                    export_data["character_sheets"][name] = sheet.to_dict()
                    sheets_exported += 1
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo(
                "Export Complete",
                f"Successfully exported:\n• {spell_lists_exported} character spell list(s)\n• {sheets_exported} character sheet(s)",
                parent=self
            )
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{e}", parent=self)
