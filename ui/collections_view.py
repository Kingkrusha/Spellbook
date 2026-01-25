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
            ("⚔️ Feats", "feats", False, "Character feats and abilities"),
            ("🧬 Lineages", "lineages", False, "Races and species options"),
            ("✨ Magic Items", "magic_items", False, "Magical equipment and artifacts"),
            ("🎭 Classes", "classes", True, "Character class definitions"),
            ("📖 Backgrounds", "backgrounds", False, "Character background options"),
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
    """Dialog for importing content."""
    
    def __init__(self, parent, spell_manager=None):
        super().__init__(parent)
        
        self.spell_manager = spell_manager
        self.theme = get_theme_manager()
        
        self.title("Import Content")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 300) // 2
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
            text="Choose what type of content to import:",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_text_secondary()
        ).pack(anchor="w", pady=(0, 20))
        
        # Import options
        options = [
            ("📜 Import Spells from Text File", self._import_spells_txt),
            ("📜 Import Spells from JSON", self._import_spells_json),
        ]
        
        for text, command in options:
            btn = ctk.CTkButton(
                container, text=text,
                width=300, height=40,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                anchor="w",
                command=command
            )
            btn.pack(pady=5)
        
        # Cancel button
        ctk.CTkButton(
            container, text="Cancel",
            width=100,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(pady=(20, 0))
    
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
                self.destroy()
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import spells:\n{e}", parent=self)
    
    def _import_spells_json(self):
        """Import spells from a JSON file."""
        file_path = filedialog.askopenfilename(
            title="Select Spell JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        
        if file_path and self.spell_manager:
            try:
                count = self.spell_manager.import_from_json(file_path)
                messagebox.showinfo("Import Complete", f"Successfully imported {count} spells.", parent=self)
                self.destroy()
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import spells:\n{e}", parent=self)


class ExportDialog(ctk.CTkToplevel):
    """Dialog for exporting content."""
    
    def __init__(self, parent, spell_manager=None):
        super().__init__(parent)
        
        self.spell_manager = spell_manager
        self.theme = get_theme_manager()
        
        self.title("Export Content")
        self.geometry("400x300")
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 300) // 2
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
            text="Choose what content to export:",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_text_secondary()
        ).pack(anchor="w", pady=(0, 20))
        
        # Export options
        options = [
            ("📜 Export All Spells to JSON", self._export_all_spells),
            ("📜 Export Custom Spells Only", self._export_custom_spells),
        ]
        
        for text, command in options:
            btn = ctk.CTkButton(
                container, text=text,
                width=300, height=40,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                anchor="w",
                command=command
            )
            btn.pack(pady=5)
        
        # Cancel button
        ctk.CTkButton(
            container, text="Cancel",
            width=100,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(pady=(20, 0))
    
    def _export_all_spells(self):
        """Export all spells to JSON."""
        file_path = filedialog.asksaveasfilename(
            title="Export Spells",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        
        if file_path and self.spell_manager:
            try:
                count = self.spell_manager.export_to_json(file_path)
                messagebox.showinfo("Export Complete", f"Successfully exported {count} spells.", parent=self)
                self.destroy()
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export spells:\n{e}", parent=self)
    
    def _export_custom_spells(self):
        """Export only custom (non-official) spells."""
        file_path = filedialog.asksaveasfilename(
            title="Export Custom Spells",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )
        
        if file_path and self.spell_manager:
            try:
                # Filter to custom spells only
                custom_spells = [s for s in self.spell_manager.spells if not s.is_official]
                count = self.spell_manager.export_to_json(file_path, spells=custom_spells)
                messagebox.showinfo("Export Complete", f"Successfully exported {count} custom spells.", parent=self)
                self.destroy()
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export spells:\n{e}", parent=self)
