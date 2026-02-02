"""
Base UI components for D&D 5e Spellbook Application.
Provides reusable widgets to reduce code duplication across views.
"""

import customtkinter as ctk
import tkinter as tk
from typing import TypeVar, Generic, List, Optional, Callable, Any
from theme import get_theme_manager

T = TypeVar('T')


class SelectableListPanel(ctk.CTkFrame, Generic[T]):
    """
    A reusable scrollable list panel with selection support.
    
    Generic type T is the item type being displayed.
    
    Usage:
        panel = SelectableListPanel[Lineage](
            parent,
            header_text="Lineages",
            on_select=self._on_lineage_selected,
            display_formatter=lambda l: f"{l.name} ({l.size})"
        )
        panel.set_items(lineages)
    """
    
    def __init__(
        self,
        parent,
        header_text: str,
        on_select: Callable[[Optional[T]], None],
        on_right_click: Optional[Callable[[T, int, int], None]] = None,
        display_formatter: Optional[Callable[[T], str]] = None,
        name_getter: Optional[Callable[[T], str]] = None,
        show_custom_indicator: bool = True,
        **kwargs
    ):
        """
        Initialize the list panel.
        
        Args:
            parent: Parent widget
            header_text: Text to display in the header
            on_select: Callback when an item is selected
            on_right_click: Optional callback for right-click (item, x, y)
            display_formatter: Optional function to format item display text
            name_getter: Optional function to get item name (default: item.name)
            show_custom_indicator: Whether to show * for custom items
        """
        super().__init__(parent, corner_radius=10, **kwargs)
        
        self.header_text = header_text
        self.on_select = on_select
        self.on_right_click = on_right_click
        self.display_formatter = display_formatter or (lambda x: str(getattr(x, 'name', x)))
        self.name_getter = name_getter or (lambda x: getattr(x, 'name', str(x)))
        self.show_custom_indicator = show_custom_indicator
        
        self._items: List[T] = []
        self._selected_index: Optional[int] = None
        self._item_buttons: List[ctk.CTkButton] = []
        self.theme = get_theme_manager()
        
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self._refresh_buttons()
    
    def _create_widgets(self):
        """Create the scrollable list."""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(
            header_frame, 
            text=self.header_text,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")
        
        text_secondary = self.theme.get_text_secondary()
        self.count_label = ctk.CTkLabel(
            header_frame, 
            text=f"0 items",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        )
        self.count_label.pack(side="right")
        
        # Scrollable frame for list
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _create_item_button(self, item: T, index: int) -> ctk.CTkButton:
        """Create a button for an item."""
        display_text = self.display_formatter(item)
        
        # Add custom indicator if needed
        if self.show_custom_indicator and hasattr(item, 'is_custom') and getattr(item, 'is_custom', False):
            display_text = f"* {display_text}"
        
        btn = ctk.CTkButton(
            self.scroll_frame,
            text=display_text,
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color=("transparent" if index != self._selected_index 
                      else self.theme.get_current_color('accent_primary')),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            font=ctk.CTkFont(size=13),
            command=lambda i=index: self._on_item_click(i)
        )
        btn.pack(fill="x", pady=2)
        
        # Bind right-click event
        if self.on_right_click:
            btn.bind("<Button-3>", lambda e, i=index: self._on_item_right_click(e, i))
            for child in btn.winfo_children():
                child.bind("<Button-3>", lambda e, i=index: self._on_item_right_click(e, i))
        
        return btn
    
    def _on_item_right_click(self, event, index: int):
        """Handle right-click on an item button."""
        if self.on_right_click and 0 <= index < len(self._items):
            self._on_item_click(index)
            self.on_right_click(self._items[index], event.x_root, event.y_root)
    
    def _on_item_click(self, index: int):
        """Handle item selection."""
        if self._selected_index is not None and self._selected_index < len(self._item_buttons):
            self._item_buttons[self._selected_index].configure(fg_color="transparent")
        
        self._selected_index = index
        if index < len(self._item_buttons):
            self._item_buttons[index].configure(
                fg_color=self.theme.get_current_color('accent_primary')
            )
        
        if 0 <= index < len(self._items):
            self.on_select(self._items[index])
        else:
            self.on_select(None)
    
    def set_items(self, items: List[T], reset_scroll: bool = True, 
                  preserve_selection: Optional[str] = None):
        """
        Update the list of items.
        
        Args:
            items: New list of items
            reset_scroll: Whether to scroll to top
            preserve_selection: Name of item to keep selected
        """
        self._items = items
        
        # Find preserved selection
        new_selected_index = None
        if preserve_selection:
            for i, item in enumerate(items):
                if self.name_getter(item) == preserve_selection:
                    new_selected_index = i
                    break
        
        self._selected_index = new_selected_index
        
        # Clear existing buttons
        for btn in self._item_buttons:
            btn.destroy()
        self._item_buttons = []
        
        # Create new buttons
        for i, item in enumerate(items):
            btn = self._create_item_button(item, i)
            self._item_buttons.append(btn)
        
        # Update count
        count = len(items)
        item_word = self.header_text.rstrip('s').lower()
        self.count_label.configure(text=f"{count} {item_word}{'s' if count != 1 else ''}")
        
        # Restore selection if found
        if new_selected_index is not None:
            self._on_item_click(new_selected_index)
        elif reset_scroll and self.scroll_frame.winfo_children():
            try:
                self.scroll_frame._parent_canvas.yview_moveto(0)
            except:
                pass
    
    def _refresh_buttons(self):
        """Refresh button colors after theme change."""
        for i, btn in enumerate(self._item_buttons):
            if i == self._selected_index:
                btn.configure(fg_color=self.theme.get_current_color('accent_primary'))
            else:
                btn.configure(fg_color="transparent")
            btn.configure(
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary')
            )
        self.count_label.configure(text_color=self.theme.get_text_secondary())
    
    def get_selected(self) -> Optional[T]:
        """Get the currently selected item."""
        if self._selected_index is not None and 0 <= self._selected_index < len(self._items):
            return self._items[self._selected_index]
        return None
    
    def select_by_name(self, name: str) -> bool:
        """Select an item by name. Returns True if found."""
        for i, item in enumerate(self._items):
            if self.name_getter(item) == name:
                self._on_item_click(i)
                return True
        return False
    
    def clear_selection(self):
        """Clear the current selection."""
        if self._selected_index is not None and self._selected_index < len(self._item_buttons):
            self._item_buttons[self._selected_index].configure(fg_color="transparent")
        self._selected_index = None
        self.on_select(None)


def render_rich_text(parent: ctk.CTkFrame, text: str, theme, wrap_length: int = 480) -> List[tk.Widget]:
    """
    Render text with **bold** markdown formatting.
    
    Args:
        parent: Parent widget to add text widgets to
        text: Text with **bold** markers
        theme: Theme manager instance
        wrap_length: Wrap length for text
    
    Returns:
        List of created widgets
    """
    import re
    
    widgets = []
    
    # Split by double newlines to get paragraphs
    paragraphs = text.split('\n\n')
    
    for para_idx, paragraph in enumerate(paragraphs):
        lines = paragraph.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            pady = (4, 2) if para_idx > 0 else (2, 2)
            
            # Find all **text** patterns for bold
            pattern = r'\*\*([^*]+)\*\*'
            parts = re.split(pattern, line)
            
            if len(parts) == 1:
                # No formatting found
                label = ctk.CTkLabel(
                    parent,
                    text=line,
                    font=ctk.CTkFont(size=12),
                    wraplength=wrap_length,
                    justify="left"
                )
                label.pack(anchor="w", pady=pady)
                widgets.append(label)
            else:
                # Has bold formatting - use a Text widget
                text_widget = tk.Text(
                    parent,
                    wrap="word",
                    font=ctk.CTkFont(size=12),
                    bg=theme.get_current_color('bg_secondary'),
                    fg=theme.get_current_color('text_primary'),
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
                
                # Insert parts with formatting
                for i, part in enumerate(parts):
                    if not part:
                        continue
                    is_bold = (i % 2 == 1)
                    tag = "bold" if is_bold else "normal"
                    text_widget.insert("end", part, tag)
                
                # Calculate height
                total_chars = sum(len(p) for p in parts if p)
                chars_per_line = max(1, wrap_length // 7)  # Approximate
                estimated_lines = max(1, (total_chars // chars_per_line) + 1)
                
                text_widget.configure(state="disabled", height=estimated_lines)
                text_widget.pack(fill="x", anchor="w", pady=pady)
                widgets.append(text_widget)
    
    return widgets


def create_context_menu(parent, items: List[tuple], theme) -> tk.Menu:
    """
    Create a themed context menu.
    
    Args:
        parent: Parent widget
        items: List of (label, command) tuples
        theme: Theme manager instance
    
    Returns:
        Configured tk.Menu
    """
    menu = tk.Menu(parent, tearoff=0)
    menu.configure(
        bg=theme.get_current_color('bg_secondary'),
        fg=theme.get_current_color('text_primary'),
        activebackground=theme.get_current_color('accent_primary'),
        activeforeground=theme.get_current_color('text_primary')
    )
    
    for label, command in items:
        if label == "-":
            menu.add_separator()
        else:
            menu.add_command(label=label, command=command)
    
    return menu


def show_context_menu(menu: tk.Menu, event):
    """Show a context menu at the event position."""
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


class FilterBar(ctk.CTkFrame):
    """
    A reusable filter bar with search and dropdown filters.
    """
    
    def __init__(self, parent, on_filter_changed: Callable[[], None], **kwargs):
        """
        Initialize the filter bar.
        
        Args:
            parent: Parent widget
            on_filter_changed: Callback when any filter changes
        """
        super().__init__(parent, **kwargs)
        
        self.on_filter_changed = on_filter_changed
        self.theme = get_theme_manager()
        self._filter_widgets = {}
    
    def add_search(self, placeholder: str = "Search...", width: int = 200) -> ctk.CTkEntry:
        """Add a search entry field."""
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            width=width,
            textvariable=search_var
        )
        search_entry.pack(side="left", padx=(0, 10))
        search_var.trace_add("write", lambda *args: self.on_filter_changed())
        
        self._filter_widgets['search'] = search_var
        return search_entry
    
    def add_dropdown(self, name: str, label: str, values: List[str], 
                     width: int = 120, default: str = "All") -> ctk.CTkComboBox:
        """Add a dropdown filter."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(side="left", padx=5)
        
        ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=11)).pack(anchor="w")
        
        var = ctk.StringVar(value=default)
        combo = ctk.CTkComboBox(
            frame,
            values=values,
            variable=var,
            width=width,
            command=lambda _: self.on_filter_changed()
        )
        combo.pack()
        
        self._filter_widgets[name] = var
        return combo
    
    def add_checkbox(self, name: str, label: str, default: bool = False) -> ctk.CTkCheckBox:
        """Add a checkbox filter."""
        var = ctk.BooleanVar(value=default)
        checkbox = ctk.CTkCheckBox(
            self,
            text=label,
            variable=var,
            command=self.on_filter_changed
        )
        checkbox.pack(side="left", padx=10)
        
        self._filter_widgets[name] = var
        return checkbox
    
    def get_value(self, name: str) -> Any:
        """Get the value of a filter widget."""
        if name in self._filter_widgets:
            return self._filter_widgets[name].get()
        return None
    
    def get_search(self) -> str:
        """Get the search text."""
        return self.get_value('search') or ""
    
    def set_dropdown_values(self, name: str, values: List[str], combo: ctk.CTkComboBox):
        """Update the values in a dropdown."""
        combo.configure(values=values)
