"""
Global Search Widget for D&D Spellbook Application.
Provides a search bar with overlay dropdown showing results from all collections.
"""

import customtkinter as ctk
from tkinter import ttk
from typing import Optional, Callable, List, Dict
from theme import get_theme_manager


class GlobalSearchBar(ctk.CTkFrame):
    """Search bar with overlaying dropdown results."""
    
    def __init__(self, parent, on_result_selected: Optional[Callable[[str, str, int], None]] = None):
        """
        Initialize the global search bar.
        
        Args:
            parent: Parent widget
            on_result_selected: Callback when a result is selected. 
                               Args: (section, name, id)
        """
        super().__init__(parent, fg_color="transparent")
        
        self.on_result_selected = on_result_selected
        self.theme = get_theme_manager()
        self._db = None
        self._results: List[Dict] = []
        self._dropdown_visible = False
        self._result_widgets = []
        
        self._create_widgets()
        self._bind_events()
    
    @property
    def db(self):
        """Get database instance."""
        if self._db is None:
            from database import SpellDatabase
            self._db = SpellDatabase()
            self._db.initialize()
        return self._db
    
    def _create_widgets(self):
        """Create the search bar UI."""
        # Search container
        self.search_container = ctk.CTkFrame(self, fg_color="transparent")
        self.search_container.pack(fill="x", expand=True)
        
        # Search bar colors
        self._search_bg_color = "#0A0959"  # Dark blue
        self._search_text_color = "#ffffff"  # White
        self._search_placeholder_color = "#888888"  # Grey
        
        # Search icon and entry - store as instance var for theme updates
        self.search_frame = ctk.CTkFrame(
            self.search_container, 
            fg_color=self._search_bg_color,
            border_width=1,
            border_color=self.theme.get_current_color('border'),
            corner_radius=8
        )
        self.search_frame.pack(fill="x", pady=5)
        
        # Search icon
        self.search_icon = ctk.CTkLabel(
            self.search_frame, 
            text="🔍", 
            font=ctk.CTkFont(size=16),
            text_color=self._search_text_color,
            width=30
        )
        self.search_icon.pack(side="left", padx=(10, 0))
        
        # Search entry
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="Search all collections...",
            placeholder_text_color=self._search_placeholder_color,
            border_width=0,
            fg_color="transparent",
            text_color=self._search_text_color,
            height=36,
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        
        # Clear button (hidden initially)
        self.clear_btn = ctk.CTkButton(
            self.search_frame,
            text="✕",
            width=30,
            height=30,
            fg_color="transparent",
            text_color=self._search_text_color,
            hover_color="#1a1a8a",
            command=self._clear_search
        )
        # Pack will be controlled by search text presence
    
    def _bind_events(self):
        """Bind keyboard and focus events."""
        self.search_entry.bind('<KeyRelease>', self._on_search_changed)
        self.search_entry.bind('<FocusIn>', self._on_focus_in)
        self.search_entry.bind('<FocusOut>', self._on_focus_out)
        self.search_entry.bind('<Return>', self._on_enter)
        self.search_entry.bind('<Down>', self._on_arrow_down)
        self.search_entry.bind('<Escape>', self._on_escape)
    
    def _on_search_changed(self, event=None):
        """Handle search text change."""
        query = self.search_entry.get().strip()
        
        # Show/hide clear button
        if query:
            self.clear_btn.pack(side="right", padx=5)
        else:
            self.clear_btn.pack_forget()
        
        # Perform search
        if len(query) >= 1:
            self._perform_search(query)
        else:
            self._hide_dropdown()
    
    def _perform_search(self, query: str):
        """Search the database and show results."""
        self._results = self.db.global_search(query, limit=50)
        
        if self._results:
            self._show_dropdown()
        else:
            self._hide_dropdown()
    
    def _show_dropdown(self):
        """Show the dropdown with search results."""
        if self._dropdown_visible:
            self._update_dropdown()
            return
        
        # Create dropdown as a toplevel window for overlay effect
        self._dropdown = ctk.CTkToplevel(self)
        self._dropdown.withdraw()  # Hide initially while configuring
        self._dropdown.overrideredirect(True)  # No window decorations
        self._dropdown.attributes('-topmost', True)
        
        # Create scrollable frame for results
        self._dropdown_inner = ctk.CTkScrollableFrame(
            self._dropdown,
            fg_color=self._search_bg_color,
            corner_radius=8,
            border_width=1,
            border_color=self.theme.get_current_color('border')
        )
        self._dropdown_inner.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Capture scroll events to prevent scrolling the parent page
        self._dropdown_inner.bind('<Enter>', self._on_dropdown_enter)
        self._dropdown_inner.bind('<Leave>', self._on_dropdown_leave)
        
        # Position dropdown below search bar
        self._position_dropdown()
        
        # Populate results
        self._update_dropdown()
        
        self._dropdown.deiconify()
        self._dropdown_visible = True
        
        # Bind click outside to close
        self._dropdown.bind('<FocusOut>', self._check_focus_out)
    
    def _position_dropdown(self):
        """Position the dropdown below the search bar."""
        # Get search entry absolute position
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        width = self.winfo_width()
        
        # Max height for dropdown (shows ~8 results)
        max_height = min(350, len(self._results) * 45 + 20)
        
        self._dropdown.geometry(f"{width}x{max_height}+{x}+{y}")
    
    def _update_dropdown(self):
        """Update the dropdown content with current results."""
        # Clear existing widgets
        for widget in self._result_widgets:
            widget.destroy()
        self._result_widgets = []
        
        # Create result items
        for i, result in enumerate(self._results):
            result_frame = ctk.CTkFrame(
                self._dropdown_inner,
                fg_color="transparent",
                height=40
            )
            result_frame.pack(fill="x", padx=5, pady=2)
            result_frame.pack_propagate(False)
            
            # Result text: "Name In Section"
            name = result.get('name', '')
            section = result.get('section', '')
            display_text = f"{name}"
            section_text = f"in {section}"
            
            # Name label
            name_label = ctk.CTkLabel(
                result_frame,
                text=display_text,
                font=ctk.CTkFont(size=14),
                text_color=self._search_text_color,
                anchor="w"
            )
            name_label.pack(side="left", padx=10)
            
            # Section label (smaller, muted)
            section_label = ctk.CTkLabel(
                result_frame,
                text=section_text,
                font=ctk.CTkFont(size=12),
                text_color=self._search_placeholder_color,
                anchor="w"
            )
            section_label.pack(side="left", padx=5)
            
            # Bind click to select
            for widget in [result_frame, name_label, section_label]:
                widget.bind('<Button-1>', lambda e, r=result: self._select_result(r))
                widget.bind('<Enter>', lambda e, f=result_frame: self._highlight_result(f, True))
                widget.bind('<Leave>', lambda e, f=result_frame: self._highlight_result(f, False))
            
            self._result_widgets.append(result_frame)
        
        # Update dropdown position after content change
        self._position_dropdown()
    
    def _highlight_result(self, frame, is_hovered: bool):
        """Highlight or unhighlight a result row."""
        if is_hovered:
            frame.configure(fg_color="#1a1a8a")  # Lighter blue on hover
        else:
            frame.configure(fg_color="transparent")
    
    def _select_result(self, result: dict):
        """Handle selection of a search result."""
        # Store callback info before cleanup
        section = result.get('section', '')
        name = result.get('name', '')
        result_id = result.get('id', 0)
        
        # Clean up search bar
        self.cleanup()
        
        if self.on_result_selected:
            self.on_result_selected(section, name, result_id)
    
    def _hide_dropdown(self):
        """Hide the dropdown."""
        if self._dropdown_visible and hasattr(self, '_dropdown'):
            self._dropdown.destroy()
            self._dropdown_visible = False
            self._result_widgets = []
    
    def _clear_search(self):
        """Clear the search entry."""
        self.search_entry.delete(0, 'end')
        self.clear_btn.pack_forget()
        self._hide_dropdown()
    
    def _on_focus_in(self, event=None):
        """Handle focus entering search entry."""
        query = self.search_entry.get().strip()
        if query and len(query) >= 1:
            self._perform_search(query)
    
    def _on_focus_out(self, event=None):
        """Handle focus leaving search entry."""
        # Delay to allow click on dropdown
        self.after(200, self._check_focus_out)
    
    def _check_focus_out(self, event=None):
        """Check if dropdown should close after focus lost."""
        # Only hide if focus isn't on dropdown or search entry
        try:
            focused = self.focus_get()
            if focused is None:
                self._hide_dropdown()
            elif self._dropdown_visible and hasattr(self, '_dropdown'):
                # Check if focus is on dropdown widgets
                focus_str = str(focused)
                dropdown_str = str(self._dropdown)
                search_str = str(self.search_entry)
                if not focus_str.startswith(dropdown_str) and focus_str != search_str:
                    self._hide_dropdown()
        except:
            pass
    
    def cleanup(self):
        """Clean up the search bar - hide dropdown and clear search."""
        self._hide_dropdown()
        self.search_entry.delete(0, 'end')
        self.clear_btn.pack_forget()
    
    def _on_enter(self, event=None):
        """Handle Enter key - select first result."""
        if self._results:
            self._select_result(self._results[0])
    
    def _on_arrow_down(self, event=None):
        """Handle arrow down - move focus to dropdown."""
        if self._dropdown_visible and self._result_widgets:
            self._result_widgets[0].focus_set()
    
    def _on_escape(self, event=None):
        """Handle Escape key - close dropdown."""
        self._hide_dropdown()
        self.search_entry.delete(0, 'end')
    
    def _on_dropdown_enter(self, event=None):
        """Handle mouse entering dropdown - capture scroll."""
        if hasattr(self, '_dropdown_inner'):
            # Bind mousewheel to dropdown's internal canvas to capture scroll
            self._dropdown_inner.bind_all('<MouseWheel>', self._on_dropdown_scroll)
            self._dropdown_inner.bind_all('<Button-4>', self._on_dropdown_scroll)  # Linux
            self._dropdown_inner.bind_all('<Button-5>', self._on_dropdown_scroll)  # Linux
    
    def _on_dropdown_leave(self, event=None):
        """Handle mouse leaving dropdown - release scroll capture."""
        if hasattr(self, '_dropdown_inner'):
            self._dropdown_inner.unbind_all('<MouseWheel>')
            self._dropdown_inner.unbind_all('<Button-4>')
            self._dropdown_inner.unbind_all('<Button-5>')
    
    def _on_dropdown_scroll(self, event):
        """Handle scroll within dropdown."""
        if hasattr(self, '_dropdown_inner'):
            # Get the internal canvas of the scrollable frame
            try:
                # CTkScrollableFrame has an internal _parent_canvas
                canvas = self._dropdown_inner._parent_canvas
                if event.num == 4 or event.delta > 0:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5 or event.delta < 0:
                    canvas.yview_scroll(1, "units")
            except:
                pass
        return "break"  # Prevent event from propagating to parent
    
    def update_colors(self):
        """Update colors to match current theme."""
        # Update search frame border only (bg stays dark blue)
        self.search_frame.configure(
            fg_color=self._search_bg_color,
            border_color=self.theme.get_current_color('border')
        )
        
        # Search icon stays white
        self.search_icon.configure(text_color=self._search_text_color)
        
        # Search entry stays white text
        self.search_entry.configure(
            text_color=self._search_text_color,
            placeholder_text_color=self._search_placeholder_color
        )
        
        # Clear button stays white
        self.clear_btn.configure(
            text_color=self._search_text_color,
            hover_color="#1a1a8a"
        )
        
        # If dropdown is visible, update its colors too
        if self._dropdown_visible and hasattr(self, '_dropdown_inner'):
            self._dropdown_inner.configure(
                fg_color=self._search_bg_color,
                border_color=self.theme.get_current_color('border')
            )
