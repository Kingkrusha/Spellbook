"""
Collections View for D&D Spellbook Application.
Provides access to various content collections (Spells, Feats, Classes, etc.)
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from typing import Optional, Callable
from theme import get_theme_manager


class CollectionsView(ctk.CTkFrame):
    """Main collections hub with buttons for different content types."""
    
    def __init__(self, parent, spell_manager=None, on_navigate: Optional[Callable[[str], None]] = None):
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
        if self.on_navigate:
            self.on_navigate(collection_key)
    
    def _on_import(self):
        """Handle import button click."""
        # Show import options dialog
        dialog = ImportDialog(self.winfo_toplevel(), self.spell_manager)
        dialog.grab_set()
    
    def _on_export(self):
        """Handle export button click."""
        # Show export options dialog  
        dialog = ExportDialog(self.winfo_toplevel(), self.spell_manager)
        dialog.grab_set()


class ImportDialog(ctk.CTkToplevel):
    """Dialog for importing content with auto-detection."""
    
    def __init__(self, parent, spell_manager=None):
        super().__init__(parent)
        
        self.spell_manager = spell_manager
        self.theme = get_theme_manager()
        
        self.title("Import Content")
        self.geometry("500x350")
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 350) // 2
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
                 "   • Spells, Feats, Classes, Subclasses, Lineages\n"
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
        """Import content from a JSON file with auto-detection."""
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
            
            results = []
            
            # Check for spells
            if "spells" in data and self.spell_manager:
                count = 0
                for spell_data in data["spells"]:
                    from spell import Spell
                    spell = Spell.from_dict(spell_data)
                    spell.is_custom = True
                    spell.is_official = False
                    self.spell_manager.add_spell(spell)
                    count += 1
                if count > 0:
                    results.append(f"{count} spell(s)")
            
            # Check for feats
            if "feats" in data:
                feat_manager = get_feat_manager()
                count = 0
                for feat_data in data["feats"]:
                    from feat import Feat
                    feat = Feat.from_dict(feat_data)
                    feat.is_custom = True
                    feat.is_official = False
                    feat_manager.add_feat(feat)
                    count += 1
                if count > 0:
                    results.append(f"{count} feat(s)")
            
            # Check for classes
            if "classes" in data:
                class_manager = get_class_manager()
                count = 0
                for class_data in data["classes"]:
                    from character_class import CharacterClassDefinition
                    cls = CharacterClassDefinition.from_dict(class_data)
                    cls.is_custom = True
                    cls.is_official = False
                    class_manager.add_class(cls)
                    count += 1
                if count > 0:
                    results.append(f"{count} class(es)")
            
            # Check for subclasses
            if "subclasses" in data:
                class_manager = get_class_manager()
                count = 0
                for subclass_data in data["subclasses"]:
                    from character_class import SubclassDefinition
                    subclass = SubclassDefinition.from_dict(subclass_data)
                    subclass.is_custom = True
                    subclass.is_official = False
                    class_manager.add_subclass(subclass)
                    count += 1
                if count > 0:
                    results.append(f"{count} subclass(es)")
            
            # Check for lineages
            if "lineages" in data:
                lineage_manager = get_lineage_manager()
                count = 0
                for lineage_data in data["lineages"]:
                    from lineage import Lineage
                    lineage = Lineage.from_dict(lineage_data)
                    lineage.is_custom = True
                    lineage.is_official = False
                    lineage_manager.add_lineage(lineage)
                    count += 1
                if count > 0:
                    results.append(f"{count} lineage(s)")
            
            if results:
                messagebox.showinfo(
                    "Import Complete",
                    f"Successfully imported:\n• " + "\n• ".join(results),
                    parent=self
                )
            else:
                messagebox.showwarning(
                    "No Content Found",
                    "No recognized content types found in the file.\n\n"
                    "Expected keys: spells, feats, classes, subclasses, lineages",
                    parent=self
                )
                
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
        content_types = ["All", "Spells", "Feats", "Classes", "Subclasses", "Lineages"]
        
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
        
        sources = set()
        
        if self.spell_manager:
            sources.update(self.spell_manager.get_unofficial_sources())
        sources.update(get_feat_manager().get_unofficial_sources())
        sources.update(get_class_manager().get_unofficial_class_sources())
        sources.update(get_class_manager().get_unofficial_subclass_sources())
        sources.update(get_lineage_manager().get_unofficial_sources())
        
        return sorted(sources)
    
    def _update_sources(self):
        """Update source dropdown based on selected content type."""
        from feat import get_feat_manager
        from character_class import get_class_manager
        from lineage import get_lineage_manager
        
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
        
        source_options = ["All Sources"] + sources
        self.source_combo.configure(values=source_options)
        self.source_var.set("All Sources")
        
        self._update_info()
    
    def _get_export_counts(self) -> dict:
        """Get counts of items that will be exported."""
        from feat import get_feat_manager
        from character_class import get_class_manager
        from lineage import get_lineage_manager
        
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
