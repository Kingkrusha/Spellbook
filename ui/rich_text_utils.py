"""
Rich Text Utilities for D&D 5e Spellbook Application.
Provides global utilities for rendering formatted text, tables, and spell popups.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import re
from typing import Optional, List, Callable, Tuple
from theme import get_theme_manager


def preprocess_html_to_markdown(text: str) -> str:
    """
    Convert HTML-style formatting to markdown formatting.
    Supports legacy HTML tags from import files.
    
    Conversions:
    - <b>text</b> -> **text**
    - <i>text</i> -> *text*
    - <spell>Name</spell> -> [[Name]]
    - <table>...</table> -> markdown tables
    """
    if not text:
        return text
    
    # Handle <b>**text**</b> (HTML wrapping markdown) - remove outer HTML and keep markdown
    text = re.sub(r'<b>\*\*([^*]+)\*\*</b>', r'**\1**', text)
    
    # Handle **<b>text</b>** (markdown wrapping HTML) - remove outer markdown and convert HTML
    text = re.sub(r'\*\*<b>([^<]+)</b>\*\*', r'**\1**', text)
    
    # Convert bold: <b>text</b> -> **text** (allow nested tags like <spell>)
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text)
    
    # Convert italic: <i>text</i> -> *text* (allow nested tags)
    text = re.sub(r'<i>(.*?)</i>', r'*\1*', text)
    
    # Convert spell links: <spell>Name</spell> -> [[Name]]
    text = re.sub(r'<spell>([^<]+)</spell>', r'[[\1]]', text)
    
    # Clean up any duplicate asterisks from double-formatting
    # ****text**** -> **text** (4 asterisks on each side)
    text = re.sub(r'\*{4,}([^*]+)\*{4,}', r'**\1**', text)
    # ***text*** -> **text** or *text* depending on context - keep it as bold
    text = re.sub(r'\*{3}([^*]+)\*{3}', r'**\1**', text)
    
    # Convert HTML tables to markdown tables
    def convert_table(match):
        table_html = match.group(0)
        
        # Extract headers - allow inner tags
        headers = re.findall(r'<th>(.*?)</th>', table_html)
        
        # Extract data rows
        rows = []
        # Find all <tr>...</tr> that contain <td> (data rows, not header rows)
        row_matches = re.findall(r'<tr>((?:<td>.*?</td>)+)</tr>', table_html, re.DOTALL)
        for row_content in row_matches:
            # Skip header rows
            if '<th>' in row_content:
                continue
            # Extract cells - allow any content inside
            cells = re.findall(r'<td>(.*?)</td>', row_content, re.DOTALL)
            if cells:
                # Clean up cell content (remove extra whitespace)
                cells = [cell.strip() for cell in cells]
                rows.append(cells)
        
        if not headers or not rows:
            return table_html  # Return unchanged if parsing fails
        
        lines = []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            # Pad row if needed
            while len(row) < len(headers):
                row.append("")
            # Escape pipes in cell content and join
            escaped_cells = [cell.replace("|", "\\|") for cell in row[:len(headers)]]
            lines.append("| " + " | ".join(escaped_cells) + " |")
        
        return "\n".join(lines)
    
    text = re.sub(r'<table>.*?</table>', convert_table, text, flags=re.DOTALL)
    
    return text


class RichTextRenderer:
    """
    Utility class for rendering rich text with markdown formatting, tables, and spell links.
    
    Supported markdown:
    - **text** for bold
    - *text* for italic/bold
    - Markdown tables (| col | col |)
    - Spell links (clickable spell names)
    """
    
    def __init__(self, theme=None):
        self.theme = theme or get_theme_manager()
        self._spell_cache = {}  # Cache for spell lookups
    
    def parse_markdown_table(self, lines: list) -> Tuple[Optional[list], Optional[list], int]:
        """
        Parse markdown table lines into headers and rows.
        
        Args:
            lines: List of text lines starting from potential table
            
        Returns:
            (headers, rows, lines_consumed) or (None, None, 0) if not a table
        """
        if not lines or not lines[0].strip().startswith('|'):
            return None, None, 0
        
        table_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('|'):
                table_lines.append(stripped)
            elif table_lines:  # End of table
                break
        
        if len(table_lines) < 2:
            return None, None, 0
        
        # Parse header
        header_line = table_lines[0]
        headers = [cell.strip() for cell in header_line.split('|')[1:-1]]
        
        # Skip separator line (|---|---|)
        start_row = 1
        if len(table_lines) > 1 and all(c in '-| :' for c in table_lines[1]):
            start_row = 2
        
        # Parse rows
        rows = []
        for row_line in table_lines[start_row:]:
            cells = [cell.strip() for cell in row_line.split('|')[1:-1]]
            if cells:
                rows.append(cells)
        
        return headers, rows, len(table_lines)
    
    def is_spell_name(self, text: str) -> bool:
        """Check if text matches a spell name in the database."""
        text = text.strip()
        if text in self._spell_cache:
            return self._spell_cache[text]
        
        try:
            from database import SpellDatabase
            db = SpellDatabase()
            spell = db.get_spell_by_name(text)
            result = spell is not None
            self._spell_cache[text] = result
            return result
        except Exception:
            return False
    
    def get_spell(self, spell_name: str):
        """Get a Spell object from name."""
        from database import SpellDatabase
        from spell import Spell, CharacterClass
        
        db = SpellDatabase()
        spell_dict = db.get_spell_by_name(spell_name.strip())
        if not spell_dict:
            return None
        
        # Convert dict to Spell object
        classes = []
        for class_name in spell_dict.get('classes', []):
            try:
                classes.append(CharacterClass.from_string(class_name))
            except ValueError:
                pass
        
        return Spell(
            name=spell_dict['name'],
            level=spell_dict['level'],
            casting_time=spell_dict['casting_time'],
            ritual=spell_dict.get('ritual', False),
            range_value=spell_dict['range_value'],
            components=spell_dict['components'],
            duration=spell_dict['duration'],
            concentration=spell_dict.get('concentration', False),
            classes=classes,
            description=spell_dict.get('description', ''),
            source=spell_dict.get('source', ''),
            tags=spell_dict.get('tags', []),
            is_modified=spell_dict.get('is_modified', False),
            original_name=spell_dict.get('original_name', ''),
            is_legacy=spell_dict.get('is_legacy', False)
        )
    
    def show_spell_popup(self, parent, spell_name: str):
        """Show a popup dialog for a spell. Shows error message if spell not found."""
        from ui.spell_detail import SpellPopupDialog
        
        spell = self.get_spell(spell_name)
        if spell:
            popup = SpellPopupDialog(parent.winfo_toplevel(), spell)
            popup.focus()
        else:
            # Spell not found - show a warning message
            messagebox.showwarning(
                "Spell Not Found",
                f"The spell '{spell_name}' was not found in the database.\n\n"
                "It may have been removed or renamed.",
                parent=parent.winfo_toplevel()
            )
    
    def render_table(self, parent, headers: list, rows: list, 
                     on_spell_click: Optional[Callable[[str], None]] = None):
        """
        Render a table with headers and rows using grid layout.
        Supports spell links in format [[SpellName]] within cells.
        
        Args:
            parent: Parent widget
            headers: List of column header strings
            rows: List of row data (each row is a list of cell values)
            on_spell_click: Optional callback when a spell name is clicked
        """
        table_frame = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_tertiary'), 
                                   corner_radius=6)
        table_frame.pack(fill="x", pady=6, padx=4)
        
        col_count = len(headers)
        
        # Calculate column weights based on content length (for proportional sizing)
        col_weights = []
        for i in range(col_count):
            max_len = len(headers[i]) if i < len(headers) else 5
            for row in rows:
                if i < len(row):
                    # Strip [[]] from spell links for length calculation
                    cell_text = str(row[i])
                    cell_text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', cell_text)
                    max_len = max(max_len, len(cell_text))
            col_weights.append(max(5, max_len))
        
        # Calculate total weight for minimum widths
        total_weight = sum(col_weights)
        
        # Configure grid columns with weights for proportional sizing
        for col_idx in range(col_count):
            table_frame.grid_columnconfigure(col_idx, weight=col_weights[col_idx], uniform="tablecol", minsize=80)
        
        # Header row
        for col_idx, col_name in enumerate(headers):
            header_cell = ctk.CTkFrame(table_frame, fg_color=self.theme.get_current_color('bg_secondary'))
            header_cell.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=(2, 1))
            
            ctk.CTkLabel(
                header_cell, text=col_name,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
                justify="left"
            ).pack(fill="x", padx=8, pady=6, anchor="w")
        
        # Data rows
        spell_pattern = r'\[\[([^\]]+)\]\]'
        
        for row_idx, row_data in enumerate(rows):
            row_bg = "transparent" if row_idx % 2 == 0 else self.theme.get_current_color('bg_secondary')
            
            for col_idx, cell in enumerate(row_data):
                cell_text = str(cell)
                cell_frame = ctk.CTkFrame(table_frame, fg_color=row_bg)
                cell_frame.grid(row=row_idx + 1, column=col_idx, sticky="nsew", 
                               padx=1, pady=0)
                
                # Check for spell link patterns [[SpellName]] in the cell
                spell_matches = re.findall(spell_pattern, cell_text)
                
                if spell_matches:
                    # Cell contains spell links - render with clickable spans
                    self._render_table_cell_with_spells(cell_frame, cell_text, spell_pattern, on_spell_click, parent)
                elif self.is_spell_name(cell_text.strip()):
                    # Entire cell is a spell name
                    callback = on_spell_click if on_spell_click else lambda s, p=parent: self.show_spell_popup(p, s)
                    btn = ctk.CTkButton(
                        cell_frame, text=cell_text,
                        font=ctk.CTkFont(size=11),
                        fg_color="transparent",
                        hover_color=self.theme.get_current_color('button_hover'),
                        text_color=self.theme.get_current_color('accent_primary'),
                        anchor="w",
                        height=32,
                        command=lambda s=cell_text.strip(): callback(s)
                    )
                    btn.pack(fill="x", padx=6, pady=6, anchor="w")
                else:
                    # Plain text cell
                    ctk.CTkLabel(
                        cell_frame, text=cell_text,
                        font=ctk.CTkFont(size=11),
                        anchor="w",
                        justify="left"
                    ).pack(fill="x", padx=8, pady=8, anchor="w")
        
        return table_frame
    
    def _render_table_cell_with_spells(self, cell_frame, cell_text: str, spell_pattern: str, 
                                        on_spell_click: Optional[Callable], parent):
        """Render a table cell containing spell links."""
        # Use a Text widget for mixed content
        text_widget = tk.Text(
            cell_frame,
            wrap="word",
            font=ctk.CTkFont(size=11),
            bg=self.theme.get_current_color('bg_tertiary'),
            fg=self.theme.get_current_color('text_primary'),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=6,
            pady=6,
            height=1,
            cursor="arrow"
        )
        
        # Configure tags
        text_widget.tag_configure("normal", font=ctk.CTkFont(size=11))
        
        parts = re.split(spell_pattern, cell_text)
        spell_counter = 0
        
        for i, part in enumerate(parts):
            if not part:
                continue
            if i % 2 == 1:
                # This is a spell name
                spell_tag = f"spell_{spell_counter}"
                spell_counter += 1
                text_widget.tag_configure(
                    spell_tag, 
                    font=ctk.CTkFont(size=11),
                    foreground=self.theme.get_current_color('accent_primary'),
                    underline=True
                )
                text_widget.insert("end", part, spell_tag)
                
                # Bind click handler
                callback = on_spell_click if on_spell_click else lambda s, p=parent: self.show_spell_popup(p, s)
                text_widget.tag_bind(spell_tag, "<Button-1>", lambda e, s=part: callback(s))
                text_widget.tag_bind(spell_tag, "<Enter>", lambda e: text_widget.config(cursor="hand2"))
                text_widget.tag_bind(spell_tag, "<Leave>", lambda e: text_widget.config(cursor="arrow"))
            else:
                text_widget.insert("end", part, "normal")
        
        # Calculate required height
        content = text_widget.get("1.0", "end").strip()
        num_lines = max(1, len(content) // 40 + 1)
        text_widget.configure(state="disabled", height=num_lines)
        text_widget.pack(fill="x", expand=True)
    
    def _preprocess_html_to_markdown(self, text: str) -> str:
        """
        Convert HTML-style formatting to markdown formatting.
        Uses the standalone function for consistency.
        """
        return preprocess_html_to_markdown(text)
    
    def render_formatted_text(self, parent, text: str, 
                              on_spell_click: Optional[Callable[[str], None]] = None,
                              wraplength: int = 480,
                              bold_pattern: str = r'\*\*([^*]+)\*\*'):
        """
        Render text with markdown formatting, tables, and spell links.
        
        Args:
            parent: Parent widget to render into
            text: Text to render (may contain markdown or HTML tags)
            on_spell_click: Optional callback when a spell name is clicked
            wraplength: Maximum width for text wrapping
            bold_pattern: Regex pattern for bold text (default: **text**)
        """
        # Preprocess HTML tags to markdown
        text = self._preprocess_html_to_markdown(text)
        
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for table
            if line.strip().startswith('|'):
                remaining_lines = lines[i:]
                headers, rows, consumed = self.parse_markdown_table(remaining_lines)
                if headers and rows:
                    self.render_table(parent, headers, rows, on_spell_click)
                    i += consumed
                    continue
            
            # Skip empty lines but add spacing
            if not line.strip():
                i += 1
                continue
            
            # Regular text line
            line = line.strip()
            
            # Check for bold patterns
            parts = re.split(bold_pattern, line)
            
            if len(parts) == 1:
                # No bold formatting - check for spell links
                self._render_text_line(parent, line, on_spell_click, wraplength)
            else:
                # Has bold formatting - use a Text widget
                self._render_formatted_line(parent, parts, on_spell_click, wraplength)
            
            i += 1
    
    def _render_text_line(self, parent, text: str, on_spell_click: Optional[Callable], wraplength: int):
        """Render a simple text line, detecting spell links."""
        # Check for spell link patterns [[SpellName]]
        spell_pattern = r'\[\[([^\]]+)\]\]'
        parts = re.split(spell_pattern, text)
        
        if len(parts) == 1:
            # No spell links - simple label
            label = ctk.CTkLabel(
                parent,
                text=text,
                font=ctk.CTkFont(size=12),
                wraplength=wraplength,
                justify="left",
                anchor="w"
            )
            label.pack(anchor="w", pady=(2, 2))
        else:
            # Has spell links - use text widget with clickable links
            self._render_line_with_spells(parent, parts, on_spell_click, wraplength)
    
    def _render_formatted_line(self, parent, parts: list, on_spell_click: Optional[Callable], wraplength: int):
        """Render a line with bold formatting and spell links."""
        # Try to get the proper background color from the parent or theme
        try:
            # Try to get color from parent frame first
            parent_bg = parent.cget('bg') if hasattr(parent, 'cget') else None
            if parent_bg is None or parent_bg == 'SystemButtonFace':
                bg_color = self.theme.get_current_color('bg_primary')
            else:
                bg_color = parent_bg
        except Exception:
            bg_color = self.theme.get_current_color('bg_primary')
        
        text_widget = tk.Text(
            parent,
            wrap="word",
            font=ctk.CTkFont(size=12),
            bg=bg_color,
            fg=self.theme.get_current_color('text_primary'),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=2,
            cursor="arrow"
        )
        
        # Configure tags
        text_widget.tag_configure("bold", font=ctk.CTkFont(size=12, weight="bold"))
        text_widget.tag_configure("normal", font=ctk.CTkFont(size=12))
        text_widget.tag_configure("spell", font=ctk.CTkFont(size=12), 
                                  foreground=self.theme.get_current_color('accent_primary'),
                                  underline=True)
        text_widget.tag_configure("bold_spell", font=ctk.CTkFont(size=12, weight="bold"), 
                                  foreground=self.theme.get_current_color('accent_primary'),
                                  underline=True)
        
        spell_pattern = r'\[\[([^\]]+)\]\]'
        spell_counter = 0
        
        # Insert parts with formatting
        for j, part in enumerate(parts):
            if not part:
                continue
            is_bold = (j % 2 == 1)
            base_tag = "bold" if is_bold else "normal"
            
            # Check for spell links within this part
            spell_parts = re.split(spell_pattern, part)
            if len(spell_parts) == 1:
                # No spell links
                text_widget.insert("end", part, base_tag)
            else:
                # Has spell links
                for k, spell_part in enumerate(spell_parts):
                    if not spell_part:
                        continue
                    if k % 2 == 1:
                        # This is a spell name
                        spell_tag = f"spell_{spell_counter}"
                        spell_counter += 1
                        tag_style = "bold_spell" if is_bold else "spell"
                        text_widget.tag_configure(spell_tag, font=ctk.CTkFont(size=12, weight="bold" if is_bold else "normal"),
                                                  foreground=self.theme.get_current_color('accent_primary'),
                                                  underline=True)
                        text_widget.insert("end", spell_part, spell_tag)
                        
                        # Bind click handler
                        callback = on_spell_click if on_spell_click else lambda s, p=parent: self.show_spell_popup(p, s)
                        text_widget.tag_bind(spell_tag, "<Button-1>", lambda e, s=spell_part: callback(s))
                        text_widget.tag_bind(spell_tag, "<Enter>", lambda e: text_widget.config(cursor="hand2"))
                        text_widget.tag_bind(spell_tag, "<Leave>", lambda e: text_widget.config(cursor="arrow"))
                    else:
                        text_widget.insert("end", spell_part, base_tag)
        
        # Calculate height
        total_chars = sum(len(p) for p in parts if p)
        estimated_lines = max(1, (total_chars // 55) + 1)
        
        text_widget.configure(state="disabled", height=estimated_lines)
        text_widget.pack(fill="x", anchor="w", pady=(2, 2))
    
    def _render_line_with_spells(self, parent, parts: list, on_spell_click: Optional[Callable], wraplength: int):
        """Render a line containing spell links [[SpellName]]."""
        # Try to get the proper background color from the parent or theme
        try:
            parent_bg = parent.cget('bg') if hasattr(parent, 'cget') else None
            if parent_bg is None or parent_bg == 'SystemButtonFace':
                bg_color = self.theme.get_current_color('bg_primary')
            else:
                bg_color = parent_bg
        except Exception:
            bg_color = self.theme.get_current_color('bg_primary')
        
        text_widget = tk.Text(
            parent,
            wrap="word",
            font=ctk.CTkFont(size=12),
            bg=bg_color,
            fg=self.theme.get_current_color('text_primary'),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=2,
            cursor="arrow"
        )
        
        # Configure tags
        text_widget.tag_configure("normal", font=ctk.CTkFont(size=12))
        
        spell_counter = 0
        
        # Insert parts - odd indices are spell names
        for i, part in enumerate(parts):
            if not part:
                continue
            if i % 2 == 1:
                # This is a spell name
                spell_tag = f"spell_{spell_counter}"
                spell_counter += 1
                text_widget.tag_configure(spell_tag, font=ctk.CTkFont(size=12),
                                          foreground=self.theme.get_current_color('accent_primary'),
                                          underline=True)
                text_widget.insert("end", part, spell_tag)
                
                # Bind click handler
                callback = on_spell_click if on_spell_click else lambda s, p=parent: self.show_spell_popup(p, s)
                text_widget.tag_bind(spell_tag, "<Button-1>", lambda e, s=part: callback(s))
                text_widget.tag_bind(spell_tag, "<Enter>", lambda e: text_widget.config(cursor="hand2"))
                text_widget.tag_bind(spell_tag, "<Leave>", lambda e: text_widget.config(cursor="arrow"))
            else:
                text_widget.insert("end", part, "normal")
        
        # Calculate height
        total_chars = sum(len(p) for p in parts if p)
        estimated_lines = max(1, (total_chars // 55) + 1)
        
        text_widget.configure(state="disabled", height=estimated_lines)
        text_widget.pack(fill="x", anchor="w", pady=(2, 2))


class SpellSelectorDialog(ctk.CTkToplevel):
    """Dialog for selecting a spell from the database."""
    
    def __init__(self, parent, title: str = "Select Spell"):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[str] = None  # Selected spell name
        
        self.title(title)
        self.geometry("500x600")
        self.minsize(400, 500)
        self.resizable(True, True)
        
        # Use winfo_toplevel to get actual toplevel parent
        toplevel_parent = parent.winfo_toplevel()
        self.transient(toplevel_parent)
        
        self._all_spells = []
        self._filtered_spells = []
        
        self._create_widgets()
        self._load_spells()
        
        # Center on parent and ensure visibility
        self.update_idletasks()
        x = toplevel_parent.winfo_rootx() + (toplevel_parent.winfo_width() - self.winfo_width()) // 2
        y = toplevel_parent.winfo_rooty() + (toplevel_parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        # Ensure dialog appears on top and grabs focus
        self.lift()
        self.focus_force()
        self.grab_set()
        self.search_entry.focus()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_primary'))
        container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, text="Select a Spell",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
        
        # Close button
        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right")
        
        # Search
        search_frame = ctk.CTkFrame(container, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(search_frame, text="🔍", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 5))
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_entry = ctk.CTkEntry(
            search_frame, 
            textvariable=self.search_var,
            placeholder_text="Search spells...",
            height=35
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        
        # Level filter
        filter_frame = ctk.CTkFrame(container, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(filter_frame, text="Level:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        
        self.level_var = ctk.StringVar(value="All")
        level_options = ["All", "Cantrip", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        self.level_combo = ctk.CTkComboBox(
            filter_frame, values=level_options, variable=self.level_var,
            width=100, command=self._on_filter_changed
        )
        self.level_combo.pack(side="left")
        
        self.count_label = ctk.CTkLabel(
            filter_frame, text="0 spells",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_current_color('text_secondary')
        )
        self.count_label.pack(side="right")
        
        # Spell list
        self.spell_list_frame = ctk.CTkScrollableFrame(
            container, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.spell_list_frame.pack(fill="both", expand=True)
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(15, 0))
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        self.select_btn = ctk.CTkButton(
            btn_frame, text="Select", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_select,
            state="disabled"
        )
        self.select_btn.pack(side="right")
    
    def _load_spells(self):
        """Load all spells from database."""
        try:
            from database import SpellDatabase
            db = SpellDatabase()
            spell_dicts = db.get_all_spells()
            self._all_spells = [(s['name'], s['level']) for s in spell_dicts]
            self._all_spells.sort(key=lambda x: (x[1], x[0].lower()))
            self._filter_spells()
        except Exception as e:
            print(f"Error loading spells: {e}")
    
    def _on_search_changed(self, *args):
        """Handle search text change."""
        self._filter_spells()
    
    def _on_filter_changed(self, *args):
        """Handle filter change."""
        self._filter_spells()
    
    def _filter_spells(self):
        """Filter and display spells."""
        search = self.search_var.get().lower().strip()
        level_str = self.level_var.get()
        
        # Determine level filter
        level_filter = None
        if level_str == "Cantrip":
            level_filter = 0
        elif level_str != "All":
            try:
                level_filter = int(level_str)
            except ValueError:
                pass
        
        # Filter spells
        self._filtered_spells = []
        for name, level in self._all_spells:
            if search and search not in name.lower():
                continue
            if level_filter is not None and level != level_filter:
                continue
            self._filtered_spells.append((name, level))
        
        self._refresh_list()
    
    def _refresh_list(self):
        """Refresh the spell list display."""
        # Clear existing
        for widget in self.spell_list_frame.winfo_children():
            widget.destroy()
        
        self._selected_spell = None
        self.select_btn.configure(state="disabled")
        
        self.count_label.configure(text=f"{len(self._filtered_spells)} spells")
        
        if not self._filtered_spells:
            ctk.CTkLabel(
                self.spell_list_frame, text="No spells found",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(pady=20)
            return
        
        self._spell_buttons = []
        for name, level in self._filtered_spells:
            level_text = "Cantrip" if level == 0 else f"Level {level}"
            
            btn = ctk.CTkButton(
                self.spell_list_frame,
                text=f"{name}  ({level_text})",
                font=ctk.CTkFont(size=12),
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                anchor="w",
                height=32,
                command=lambda n=name: self._select_spell(n)
            )
            btn.pack(fill="x", padx=5, pady=2)
            self._spell_buttons.append((name, btn))
    
    def _select_spell(self, name: str):
        """Handle spell selection."""
        self._selected_spell = name
        self.select_btn.configure(state="normal")
        
        # Update button highlighting
        for spell_name, btn in self._spell_buttons:
            if spell_name == name:
                btn.configure(fg_color=self.theme.get_current_color('accent_primary'))
            else:
                btn.configure(fg_color="transparent")
    
    def _on_select(self):
        """Confirm selection."""
        if self._selected_spell:
            # Format as [[SpellName]] for detection by renderer
            self.result = f"[[{self._selected_spell}]]"
            self.destroy()


class TableEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing a markdown table."""
    
    def __init__(self, parent, existing_table: str = ""):
        super().__init__(parent)
        
        self.theme = get_theme_manager()
        self.result: Optional[str] = None  # Markdown table string
        
        self.title("Insert Table")
        self.geometry("600x500")
        self.minsize(500, 400)
        self.resizable(True, True)
        
        # Use winfo_toplevel to get actual toplevel parent
        toplevel_parent = parent.winfo_toplevel()
        self.transient(toplevel_parent)
        
        self._rows_data = []  # List of lists for table data
        
        self._create_widgets()
        
        if existing_table:
            self._parse_existing_table(existing_table)
        else:
            # Default 2x2 table
            self._rows_data = [["Header 1", "Header 2"], ["Cell 1", "Cell 2"]]
            self._refresh_table()
        
        # Center on parent and ensure visibility
        self.update_idletasks()
        x = toplevel_parent.winfo_rootx() + (toplevel_parent.winfo_width() - self.winfo_width()) // 2
        y = toplevel_parent.winfo_rooty() + (toplevel_parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        # Ensure dialog appears on top and grabs focus
        self.lift()
        self.focus_force()
        self.grab_set()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_primary'))
        container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, text="Table Editor",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")
        
        # Table size controls
        size_frame = ctk.CTkFrame(container, fg_color="transparent")
        size_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(
            size_frame, text="+ Row", width=80,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            command=self._add_row
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            size_frame, text="- Row", width=80,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._remove_row
        ).pack(side="left", padx=(0, 15))
        
        ctk.CTkButton(
            size_frame, text="+ Column", width=80,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            command=self._add_column
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            size_frame, text="- Column", width=80,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._remove_column
        ).pack(side="left", padx=(0, 15))
        
        ctk.CTkButton(
            size_frame, text="✨ Insert Spell", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._insert_spell_to_cell
        ).pack(side="left")
        
        # Table editing area
        self.table_frame = ctk.CTkScrollableFrame(
            container, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.table_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Preview
        ctk.CTkLabel(
            container, text="Preview:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w")
        
        self.preview_text = ctk.CTkTextbox(container, height=80, state="disabled")
        self.preview_text.pack(fill="x", pady=(5, 10))
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Insert", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_insert
        ).pack(side="right")
    
    def _parse_existing_table(self, table_str: str):
        """Parse an existing markdown table string."""
        lines = table_str.strip().split('\n')
        self._rows_data = []
        
        for line in lines:
            line = line.strip()
            if not line.startswith('|'):
                continue
            # Skip separator lines
            if all(c in '-| :' for c in line):
                continue
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if cells:
                self._rows_data.append(cells)
        
        if not self._rows_data:
            self._rows_data = [["Header 1", "Header 2"], ["Cell 1", "Cell 2"]]
        
        self._refresh_table()
    
    def _refresh_table(self):
        """Refresh the table editor display."""
        # Clear existing
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        
        self._cell_entries = []
        self._focused_entry = None  # Track currently focused entry
        
        if not self._rows_data:
            return
        
        num_cols = len(self._rows_data[0]) if self._rows_data else 0
        
        for row_idx, row_data in enumerate(self._rows_data):
            row_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            is_header = (row_idx == 0)
            row_entries = []
            
            for col_idx in range(num_cols):
                cell_value = row_data[col_idx] if col_idx < len(row_data) else ""
                
                entry = ctk.CTkEntry(
                    row_frame, width=120,
                    font=ctk.CTkFont(size=12, weight="bold" if is_header else "normal")
                )
                entry.insert(0, cell_value)
                entry.pack(side="left", padx=2)
                entry.bind("<KeyRelease>", self._on_cell_changed)
                entry.bind("<FocusIn>", lambda e, ent=entry: self._on_entry_focus(ent))
                row_entries.append(entry)
            
            self._cell_entries.append(row_entries)
        
        self._update_preview()
    
    def _on_entry_focus(self, entry):
        """Track the currently focused entry."""
        self._focused_entry = entry
    
    def _on_cell_changed(self, event=None):
        """Handle cell content change."""
        # Update data from entries
        for row_idx, row_entries in enumerate(self._cell_entries):
            for col_idx, entry in enumerate(row_entries):
                if row_idx < len(self._rows_data):
                    while col_idx >= len(self._rows_data[row_idx]):
                        self._rows_data[row_idx].append("")
                    self._rows_data[row_idx][col_idx] = entry.get()
        
        self._update_preview()
    
    def _add_row(self):
        """Add a new row."""
        num_cols = len(self._rows_data[0]) if self._rows_data else 2
        self._rows_data.append([""] * num_cols)
        self._refresh_table()
    
    def _remove_row(self):
        """Remove the last row (keep at least 2)."""
        if len(self._rows_data) > 2:
            self._rows_data.pop()
            self._refresh_table()
    
    def _add_column(self):
        """Add a new column."""
        for row in self._rows_data:
            row.append("")
        self._refresh_table()
    
    def _remove_column(self):
        """Remove the last column (keep at least 2)."""
        if self._rows_data and len(self._rows_data[0]) > 2:
            for row in self._rows_data:
                if row:
                    row.pop()
            self._refresh_table()
    
    def _update_preview(self):
        """Update the markdown preview."""
        # Don't call _on_cell_changed here to avoid recursion
        # Data is already synchronized when this is called
        
        markdown = self._generate_markdown()
        
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", markdown)
        self.preview_text.configure(state="disabled")
    
    def _generate_markdown(self) -> str:
        """Generate markdown table string."""
        if not self._rows_data or len(self._rows_data) < 1:
            return ""
        
        lines = []
        
        # Header row
        headers = self._rows_data[0]
        lines.append("| " + " | ".join(headers) + " |")
        
        # Separator
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # Data rows
        for row in self._rows_data[1:]:
            # Pad row if needed
            while len(row) < len(headers):
                row.append("")
            lines.append("| " + " | ".join(row[:len(headers)]) + " |")
        
        return "\n".join(lines)
    
    def _on_insert(self):
        """Insert the table."""
        self._on_cell_changed()  # Ensure data is current
        self.result = self._generate_markdown()
        self.destroy()
    
    def _insert_spell_to_cell(self):
        """Open spell selector and insert result into focused cell."""
        if not hasattr(self, '_focused_entry') or self._focused_entry is None:
            # No cell is focused, find the first data cell
            if self._cell_entries and len(self._cell_entries) > 1:
                self._focused_entry = self._cell_entries[1][0]  # First data cell
            elif self._cell_entries:
                self._focused_entry = self._cell_entries[0][0]  # Header cell
            else:
                return
        
        # Temporarily release grab to allow spell dialog to work
        self.grab_release()
        
        dialog = SpellSelectorDialog(self, "Insert Spell into Cell")
        self.wait_window(dialog)
        
        # Re-grab after dialog closes
        self.grab_set()
        
        if dialog.result:
            # Insert at cursor position in the entry
            try:
                cursor_pos = self._focused_entry.index(tk.INSERT)
                current_text = self._focused_entry.get()
                new_text = current_text[:cursor_pos] + dialog.result + current_text[cursor_pos:]
                self._focused_entry.delete(0, tk.END)
                self._focused_entry.insert(0, new_text)
                self._on_cell_changed()
            except Exception:
                # Fallback: append to current text
                current_text = self._focused_entry.get()
                self._focused_entry.delete(0, tk.END)
                self._focused_entry.insert(0, current_text + dialog.result)
                self._on_cell_changed()


class RichTextEditor:
    """
    Helper class for adding rich text insertion capabilities to text editors.
    Provides buttons/menu items for inserting tables and spell references.
    """
    
    def __init__(self, parent, text_widget: ctk.CTkTextbox, theme=None):
        """
        Initialize the rich text editor helper.
        
        Args:
            parent: Parent window for dialogs
            text_widget: The CTkTextbox to insert into
            theme: Optional theme manager
        """
        self.parent = parent
        self.text_widget = text_widget
        self.theme = theme or get_theme_manager()
        self.renderer = RichTextRenderer(self.theme)
    
    def create_toolbar(self, toolbar_parent) -> ctk.CTkFrame:
        """
        Create a toolbar with rich text buttons.
        
        Args:
            toolbar_parent: Parent widget for the toolbar
            
        Returns:
            The toolbar frame
        """
        toolbar = ctk.CTkFrame(toolbar_parent, fg_color="transparent")
        
        ctk.CTkButton(
            toolbar, text="📊 Table", width=80,
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.insert_table
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            toolbar, text="✨ Spell", width=80,
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.insert_spell
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            toolbar, text="**Bold**", width=70,
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.insert_bold
        ).pack(side="left")
        
        return toolbar
    
    def insert_table(self):
        """Open table editor and insert result."""
        dialog = TableEditorDialog(self.parent)
        self.parent.wait_window(dialog)
        
        if dialog.result:
            self._insert_text("\n" + dialog.result + "\n")
    
    def insert_spell(self):
        """Open spell selector and insert result."""
        dialog = SpellSelectorDialog(self.parent, "Insert Spell Reference")
        self.parent.wait_window(dialog)
        
        if dialog.result:
            self._insert_text(dialog.result)
    
    def insert_bold(self):
        """Insert bold markers or wrap selection."""
        try:
            # Try to get selection
            selection = self.text_widget.selection_get()
            # Replace selection with bold version
            self.text_widget.delete("sel.first", "sel.last")
            self._insert_text(f"**{selection}**")
        except tk.TclError:
            # No selection, just insert markers
            self._insert_text("**text**")
    
    def _insert_text(self, text: str):
        """Insert text at cursor position."""
        self.text_widget.insert("insert", text)
        self.text_widget.focus()


class DynamicText(ctk.CTkFrame):
    """
    A text container that dynamically resizes and re-wraps text to match
    the width of its parent container. Supports bold text formatting.
    
    Usage:
        dt = DynamicText(parent, theme)
        dt.set_text("This is **bold** and normal text.")
        dt.pack(fill="x", expand=True)
    """
    
    def __init__(self, parent, theme=None, on_spell_click=None, font_size: int = 12,
                 bg_color: Optional[str] = None, min_height: int = 1):
        self.theme = theme or get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        
        self.on_spell_click = on_spell_click
        self.font_size = font_size
        self.min_height = min_height
        self._text_content = ""
        self._text_parts = []  # List of (text, is_bold) tuples
        self._resize_job = None
        self._bold_pattern = r'\*\*([^*]+)\*\*'  # Default pattern
        
        # Store the background color key for theme changes
        # If it's a theme key like 'bg_primary' or 'bg_secondary', we can look it up later
        self._bg_color_key = None
        if bg_color is None:
            self._bg_color_key = 'bg_primary'
            bg_color = self.theme.get_current_color('bg_primary')
        elif bg_color in ('bg_primary', 'bg_secondary', 'bg_tertiary', 'description_bg'):
            self._bg_color_key = bg_color
            bg_color = self.theme.get_current_color(bg_color)
        # If it's a hex color, we just use it as-is (won't change with theme)
        self._bg_color = bg_color
        
        # Create the text widget
        self.text_widget = tk.Text(
            self,
            wrap="word",
            font=ctk.CTkFont(size=font_size),
            bg=bg_color,
            fg=self.theme.get_current_color('text_primary'),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=2,
            cursor="arrow"
        )
        self.text_widget.pack(fill="x", expand=True)
        
        # Configure tags
        self.text_widget.tag_configure("bold", font=ctk.CTkFont(size=font_size, weight="bold"))
        self.text_widget.tag_configure("normal", font=ctk.CTkFont(size=font_size))
        self.text_widget.tag_configure(
            "spell", 
            font=ctk.CTkFont(size=font_size),
            foreground=self.theme.get_current_color('accent_primary'),
            underline=True
        )
        
        # Bind to resize
        self.bind("<Configure>", self._on_resize)
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Update colors when theme changes."""
        # Use stored color key if available, otherwise keep current color
        if self._bg_color_key:
            bg = self.theme.get_current_color(self._bg_color_key)
        else:
            bg = self._bg_color
        
        fg = self.theme.get_current_color('text_primary')
        accent = self.theme.get_current_color('accent_primary')
        
        # Handle theme color which can be a string or tuple
        bg_color = bg[1] if isinstance(bg, tuple) else bg
        fg_color = fg[1] if isinstance(fg, tuple) else fg
        
        self.text_widget.configure(bg=bg_color, fg=fg_color)  # type: ignore
        self.text_widget.tag_configure("normal", foreground=fg_color)
        self.text_widget.tag_configure("bold", foreground=fg_color)
        self.text_widget.tag_configure("spell", foreground=accent)
    
    def _on_resize(self, event=None):
        """Handle resize - debounce to avoid excessive updates."""
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(50, self._do_resize)
    
    def _do_resize(self):
        """Actually perform the resize."""
        width = self.winfo_width()
        if width > 20:
            # Calculate height based on content and width
            self._update_height(width)
    
    def _update_height(self, width: int):
        """Update text widget height based on content and width."""
        if not self._text_content:
            self.text_widget.configure(height=self.min_height)
            return
        
        # Approximate chars per line (assuming ~7-8 pixels per char)
        chars_per_line = max(1, width // 8)
        total_chars = len(self._text_content)
        lines = max(self.min_height, (total_chars // chars_per_line) + 1)
        
        # Account for line breaks in the text
        line_breaks = self._text_content.count('\n')
        lines += line_breaks
        
        self.text_widget.configure(height=lines)
    
    def set_text(self, text: str, bold_pattern: str = r'\*\*([^*]+)\*\*'):
        """
        Set the text content with bold text and spell link support.
        
        Args:
            text: The text to display
            bold_pattern: Regex pattern for bold text (default: **text**)
        """
        self._text_content = text
        
        # Preprocess HTML tags to markdown
        text = preprocess_html_to_markdown(text)
        
        # Clear existing content
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        
        if not text:
            self.text_widget.configure(state="disabled", height=self.min_height)
            return
        
        # Parse bold patterns first
        import re
        bold_parts = re.split(bold_pattern, text)
        self._text_parts = []
        
        spell_pattern = r'\[\[([^\]]+)\]\]'
        spell_counter = 0
        
        for i, part in enumerate(bold_parts):
            if not part:
                continue
            is_bold = (i % 2 == 1)
            
            # Check for spell links within this part
            spell_parts = re.split(spell_pattern, part)
            if len(spell_parts) == 1:
                # No spell links
                self._text_parts.append((part, is_bold, False))
                tag = "bold" if is_bold else "normal"
                self.text_widget.insert("end", part, tag)
            else:
                # Has spell links
                for k, spell_part in enumerate(spell_parts):
                    if not spell_part:
                        continue
                    if k % 2 == 1:
                        # This is a spell name - make it clickable
                        spell_tag = f"spell_{spell_counter}"
                        spell_counter += 1
                        self.text_widget.tag_configure(
                            spell_tag, 
                            font=ctk.CTkFont(size=self.font_size, weight="bold" if is_bold else "normal"),
                            foreground=self.theme.get_current_color('accent_primary'),
                            underline=True
                        )
                        self.text_widget.insert("end", spell_part, spell_tag)
                        self._text_parts.append((spell_part, is_bold, True))
                        
                        # Bind click handler
                        click_handler = self.on_spell_click
                        if click_handler:
                            self.text_widget.tag_bind(spell_tag, "<Button-1>", lambda e, s=spell_part, h=click_handler: h(s))
                        else:
                            # Default: show spell popup
                            self.text_widget.tag_bind(spell_tag, "<Button-1>", lambda e, s=spell_part: self._default_spell_click(s))
                        self.text_widget.tag_bind(spell_tag, "<Enter>", lambda e: self.text_widget.config(cursor="hand2"))
                        self.text_widget.tag_bind(spell_tag, "<Leave>", lambda e: self.text_widget.config(cursor="arrow"))
                    else:
                        self._text_parts.append((spell_part, is_bold, False))
                        tag = "bold" if is_bold else "normal"
                        self.text_widget.insert("end", spell_part, tag)
        
        self.text_widget.configure(state="disabled")
        
        # Update height
        self._on_resize()
    
    def _default_spell_click(self, spell_name: str):
        """Default handler for spell clicks - shows a popup or error if not found."""
        from ui.spell_detail import SpellPopupDialog
        from database import SpellDatabase
        from spell import Spell, CharacterClass
        
        db = SpellDatabase()
        spell_dict = db.get_spell_by_name(spell_name.strip())
        if not spell_dict:
            # Spell not found - show a warning message
            messagebox.showwarning(
                "Spell Not Found",
                f"The spell '{spell_name}' was not found in the database.\n\n"
                "It may have been removed or renamed.",
                parent=self.winfo_toplevel()
            )
            return
        
        # Convert dict to Spell object
        classes = []
        for class_name in spell_dict.get('classes', []):
            try:
                classes.append(CharacterClass.from_string(class_name))
            except ValueError:
                pass
        
        spell = Spell(
            name=spell_dict['name'],
            level=spell_dict['level'],
            casting_time=spell_dict['casting_time'],
            ritual=spell_dict.get('ritual', False),
            range_value=spell_dict['range_value'],
            components=spell_dict['components'],
            duration=spell_dict['duration'],
            concentration=spell_dict.get('concentration', False),
            classes=classes,
            description=spell_dict.get('description', ''),
            source=spell_dict.get('source', ''),
            tags=spell_dict.get('tags', []),
            is_modified=spell_dict.get('is_modified', False),
            original_name=spell_dict.get('original_name', ''),
            is_legacy=spell_dict.get('is_legacy', False)
        )
        
        popup = SpellPopupDialog(self.winfo_toplevel(), spell)
        popup.focus()
    
    def destroy(self):
        """Clean up on destruction."""
        try:
            self.theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()


def render_dynamic_text(parent, text: str, theme=None, on_spell_click=None,
                        font_size: int = 12, bg_color: Optional[str] = None) -> DynamicText:
    """
    Convenience function to create a DynamicText widget.
    
    Args:
        parent: Parent widget
        text: Text to display (supports **bold** markdown)
        theme: Theme manager (optional)
        on_spell_click: Callback when a spell name is clicked
        font_size: Font size (default: 12)
        bg_color: Background color (optional)
    
    Returns:
        DynamicText widget instance
    """
    dt = DynamicText(parent, theme, on_spell_click, font_size, bg_color)
    dt.set_text(text)
    return dt


# Convenience function for creating a renderer
def get_rich_text_renderer(theme=None) -> RichTextRenderer:
    """Get a RichTextRenderer instance."""
    return RichTextRenderer(theme)


def render_description(parent, text: str, theme=None, wraplength: int = 500,
                       bold_pattern: str = r'\*\*([^*]+)\*\*') -> ctk.CTkFrame:
    """
    Global function for rendering description text with table, spell link, and bold support.
    
    This is the standard way to render description text across all editors and views.
    Supports:
    - Markdown tables (| col | col |)
    - Spell links ([[SpellName]])
    - Bold text (**text** or custom pattern)
    
    Args:
        parent: Parent widget to render into
        text: Description text to render
        theme: Optional theme manager
        wraplength: Maximum width for text wrapping (default: 500)
        bold_pattern: Regex pattern for bold text (default: **text**)
    
    Returns:
        The container frame containing the rendered description
    """
    from theme import get_theme_manager
    
    if theme is None:
        theme = get_theme_manager()
    
    # Create container frame
    container = ctk.CTkFrame(parent, fg_color="transparent")
    
    if not text:
        return container
    
    # Render using RichTextRenderer
    renderer = RichTextRenderer(theme)
    renderer.render_formatted_text(
        container, text,
        on_spell_click=lambda s: renderer.show_spell_popup(container, s),
        wraplength=wraplength,
        bold_pattern=bold_pattern
    )
    
    return container
