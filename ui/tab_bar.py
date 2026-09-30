"""
Draggable Tab Bar Widget for D&D Spellbook Application.
Browser-style tabs: a "+" button opens a new tab, tabs close with their x (or a
middle click), drag to reorder, right-click for more. The Settings tab is pinned
to the right and cannot be closed.
"""

import sys
import customtkinter as ctk
from typography import ui_font
from tkinter import Menu
from typing import Optional, Callable, List
from theme import get_theme_manager
from ui.platform_compat import bind_right_click
import uuid


class TabWidget(ctk.CTkFrame):
    """A single tab widget with optional close button and drag support."""
    
    # Tab size constraints
    MIN_TAB_WIDTH = 60
    MAX_TAB_WIDTH = 180
    CLOSE_BTN_WIDTH = 25
    
    def __init__(
        self, 
        parent, 
        tab_id: str,
        tab_type: str,
        display_text: str,
        is_closable: bool = False,
        on_click: Optional[Callable[['TabWidget'], None]] = None,
        on_close: Optional[Callable[['TabWidget'], None]] = None,
        on_drag_start: Optional[Callable[['TabWidget', int], None]] = None,
        on_drag_motion: Optional[Callable[['TabWidget', int], None]] = None,
        on_drag_end: Optional[Callable[['TabWidget'], None]] = None,
        on_right_click: Optional[Callable[['TabWidget', int, int], None]] = None
    ):
        """
        Initialize a tab widget.
        
        Args:
            parent: Parent widget
            tab_id: Unique identifier for this tab
            tab_type: "settings" for the pinned settings tab, otherwise the kind of page
                the tab was opened on (the owner tracks what it shows now)
            display_text: Text to display on the tab
            is_closable: Whether tab can be closed
            on_click: Callback when tab is clicked
            on_close: Callback when close button is clicked
            on_drag_start: Callback when drag starts
            on_drag_motion: Callback during drag
            on_drag_end: Callback when drag ends
            on_right_click: Callback for right-click (x, y coords)
        """
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent", corner_radius=8, height=34)
        
        self.tab_id = tab_id
        self.tab_type = tab_type
        self.display_text = display_text
        self.full_text = display_text  # Full untruncated text for tooltip
        self.is_closable = is_closable
        self.is_active = False
        self._current_width = self.MAX_TAB_WIDTH
        
        # Callbacks
        self.on_click = on_click
        self.on_close = on_close
        self.on_drag_start = on_drag_start
        self.on_drag_motion = on_drag_motion
        self.on_drag_end = on_drag_end
        self.on_right_click = on_right_click
        
        # Drag state
        self._drag_start_x = 0
        self._is_dragging = False
        
        # Tooltip
        self._tooltip = None
        self._tooltip_id = None
        
        self._create_widgets()
        self._bind_events()
    
    def _create_widgets(self):
        """Create the tab UI components."""
        self.pack_propagate(False)
        
        # Start with max width
        self.configure(width=self._current_width)
        
        # Inner container for content
        self.inner_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=8)
        self.inner_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Tab label
        self.label = ctk.CTkLabel(
            self.inner_frame,
            text=self.display_text,
            font=ui_font("body", 13),
            text_color=self.theme.get_current_color('text_primary')
        )
        self.label.pack(side="left", padx=(10, 5), pady=5)
        
        # Close button (only for closable tabs)
        if self.is_closable:
            self.close_btn = ctk.CTkButton(
                self.inner_frame,
                text="×",
                width=20,
                height=20,
                corner_radius=4,
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_text_secondary(),
                font=ui_font("subheading"),
                command=self._on_close_click
            )
            self.close_btn.pack(side="right", padx=(0, 5), pady=5)
    
    def _bind_events(self):
        """Bind mouse events for interaction."""
        # Click to select
        for widget in [self, self.inner_frame, self.label]:
            widget.bind('<Button-1>', self._on_click)
            bind_right_click(widget, self._on_right_click_event)
            widget.bind('<B1-Motion>', self._on_drag)
            widget.bind('<ButtonRelease-1>', self._on_drag_release)
            if sys.platform != "darwin":  # on macOS <Button-2> is the secondary click
                widget.bind('<Button-2>', self._on_middle_click)
            # Tooltip events
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
    
    def _on_enter(self, event=None):
        """Show tooltip on hover."""
        # Only show tooltip if text is truncated
        if self.display_text != self.full_text:
            self._tooltip_id = self.after(500, self._show_tooltip)
    
    def _on_leave(self, event=None):
        """Hide tooltip on leave."""
        if self._tooltip_id:
            self.after_cancel(self._tooltip_id)
            self._tooltip_id = None
        self._hide_tooltip()
    
    def _show_tooltip(self):
        """Display tooltip with full text."""
        if self._tooltip:
            return
        
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 5
        
        self._tooltip = ctk.CTkToplevel(self)
        self._tooltip.withdraw()
        self._tooltip.overrideredirect(True)
        self._tooltip.attributes('-topmost', True)
        
        label = ctk.CTkLabel(
            self._tooltip,
            text=self.full_text,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=4,
            padx=8,
            pady=4
        )
        label.pack()
        
        self._tooltip.geometry(f"+{x}+{y}")
        self._tooltip.deiconify()
    
    def _hide_tooltip(self):
        """Hide and destroy tooltip."""
        if self._tooltip:
            try:
                self._tooltip.destroy()
            except:
                pass
            self._tooltip = None
    
    def _on_click(self, event):
        """Handle left click on tab."""
        self._drag_start_x = event.x_root
        if self.on_click:
            self.on_click(self)
    
    def _on_right_click_event(self, event):
        """Handle right click on tab."""
        if self.on_right_click:
            self.on_right_click(self, event.x_root, event.y_root)
    
    def _on_drag(self, event):
        """Handle drag motion."""
        if not self._is_dragging:
            # Check if we've moved enough to start a drag
            if abs(event.x_root - self._drag_start_x) > 10:
                self._is_dragging = True
                if self.on_drag_start:
                    self.on_drag_start(self, event.x_root)
        
        if self._is_dragging and self.on_drag_motion:
            self.on_drag_motion(self, event.x_root)
    
    def _on_drag_release(self, event):
        """Handle drag release."""
        if self._is_dragging:
            self._is_dragging = False
            if self.on_drag_end:
                self.on_drag_end(self)
    
    def _on_close_click(self):
        """Handle close button click."""
        if self.on_close:
            self.on_close(self)

    def _on_middle_click(self, event=None):
        """Middle-click closes the tab, like in a browser."""
        if self.is_closable:
            self._on_close_click()
    
    def set_active(self, active: bool):
        """Set the active state of the tab."""
        self.is_active = active
        if active:
            self.inner_frame.configure(fg_color=self.theme.get_current_color('accent_primary'))
        else:
            self.inner_frame.configure(fg_color="transparent")
    
    def update_colors(self):
        """Update colors to match current theme."""
        self.label.configure(text_color=self.theme.get_current_color('text_primary'))
        if self.is_closable:
            self.close_btn.configure(
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_text_secondary()
            )
        if self.is_active:
            self.inner_frame.configure(fg_color=self.theme.get_current_color('accent_primary'))
        else:
            self.inner_frame.configure(fg_color="transparent")
    
    def set_width(self, width: int):
        """Set the tab width and truncate text if needed."""
        self._current_width = max(self.MIN_TAB_WIDTH, min(width, self.MAX_TAB_WIDTH))
        self.configure(width=self._current_width)
        
        # Calculate available text width
        padding = 20  # Left padding
        close_space = self.CLOSE_BTN_WIDTH if self.is_closable else 0
        available_width = self._current_width - padding - close_space
        
        # Truncate text if needed (roughly 7 pixels per character)
        chars_that_fit = max(3, available_width // 7)
        
        if len(self.full_text) > chars_that_fit:
            self.display_text = self.full_text[:chars_that_fit - 2] + "…"
        else:
            self.display_text = self.full_text
        
        self.label.configure(text=self.display_text)
    
    def set_text(self, text: str):
        """Update the tab's display text."""
        self.full_text = text
        # Re-apply current width to handle truncation
        self.set_width(self._current_width)
    
    def get_preferred_width(self) -> int:
        """Get the preferred width based on full text."""
        base_width = len(self.full_text) * 8 + 25
        if self.is_closable:
            base_width += self.CLOSE_BTN_WIDTH
        return max(self.MIN_TAB_WIDTH, min(base_width, self.MAX_TAB_WIDTH))


class DraggableTabBar(ctk.CTkFrame):
    """A browser-style tab bar: "+" for a new tab, closable and draggable tabs."""

    NEW_TAB_BTN_WIDTH = 32

    def __init__(
        self,
        parent,
        on_tab_selected: Optional[Callable[[str, str], None]] = None,
        on_tab_closed: Optional[Callable[[str], None]] = None,
        on_tabs_changed: Optional[Callable[[], None]] = None,
        on_new_tab: Optional[Callable[[Optional[int]], None]] = None,
        on_duplicate_tab: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize the tab bar.

        Args:
            parent: Parent widget
            on_tab_selected: Callback when a tab is selected (tab_id, tab_type)
            on_tab_closed: Callback when a tab is closed (tab_id)
            on_tabs_changed: Callback when tabs are added/removed/reordered
            on_new_tab: Callback to open a new tab (the "+" button, or the context menu
                with the position to insert at); the owner calls add_tab
            on_duplicate_tab: Callback to open a copy of a tab (tab_id)
        """
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('tab_bar'), corner_radius=0, height=50)
        
        self.on_tab_selected = on_tab_selected
        self.on_tab_closed = on_tab_closed
        self.on_tabs_changed = on_tabs_changed
        self.on_new_tab = on_new_tab
        self.on_duplicate_tab = on_duplicate_tab

        # Tab state (the pinned settings tab, if any, is always last in the list)
        self._tabs: List[TabWidget] = []
        self._active_tab_id: Optional[str] = None
        
        # Drag state
        self._drag_tab: Optional[TabWidget] = None
        self._drag_indicator: Optional[ctk.CTkFrame] = None
        self._drag_insert_index: int = 0
        
        self._create_widgets()
        self._create_context_menu()
        
        # Bind resize event
        self.bind('<Configure>', self._on_resize)
        self._resize_pending = False
    
    def _create_widgets(self):
        """Create the tab bar UI."""
        self.pack_propagate(False)
        
        # Left side: main tabs (will shrink to accommodate settings)
        self.tabs_container = ctk.CTkFrame(self, fg_color="transparent")
        self.tabs_container.pack(side="left", padx=(10, 5), pady=8, fill="x", expand=True)

        # "+" opens a new tab; it always sits right after the last tab
        self.new_tab_btn = ctk.CTkButton(
            self.tabs_container,
            text="+",
            width=self.NEW_TAB_BTN_WIDTH,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            font=ui_font("heading", 18),
            command=self._request_new_tab
        )
        self.new_tab_btn.pack(side="left")
        
        # Right side: settings tab (always stays on right, fixed size)
        self.settings_container = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_container.pack(side="right", padx=(5, 15), pady=8)
    
    def _on_resize(self, event=None):
        """Handle window resize - recalculate tab widths."""
        # Debounce resize events
        if self._resize_pending:
            return
        self._resize_pending = True
        self.after(50, self._recalculate_tab_widths)
    
    def _recalculate_tab_widths(self):
        """Recalculate and apply tab widths based on available space."""
        self._resize_pending = False
        
        # Get main tabs (non-settings)
        main_tabs = [t for t in self._tabs if t.tab_type != "settings"]
        if not main_tabs:
            self._set_new_tab_enabled(True)
            return
        
        # Calculate available width for main tabs
        total_width = self.winfo_width()
        settings_width = self.settings_container.winfo_width() + 30  # Include padding
        available_width = total_width - settings_width - 25  # Extra padding
        available_width -= self.NEW_TAB_BTN_WIDTH + 5  # The "+" button

        if available_width <= 0:
            return
        
        # Calculate how much width each tab needs vs available
        num_tabs = len(main_tabs)
        spacing = 5 * (num_tabs - 1) if num_tabs > 1 else 0  # 5px between tabs
        usable_width = available_width - spacing
        
        # Tabs stop shrinking at MIN_TAB_WIDTH, so past this many the bar would overflow
        capacity = max(1, (available_width + 5) // (TabWidget.MIN_TAB_WIDTH + 5))
        self._set_new_tab_enabled(num_tabs < capacity)

        # Check if we have enough space at preferred widths
        total_preferred = sum(t.get_preferred_width() for t in main_tabs)
        
        if total_preferred <= usable_width:
            # Enough space - use preferred widths
            for tab in main_tabs:
                tab.set_width(tab.get_preferred_width())
        else:
            # Not enough space - distribute evenly with min constraint
            width_per_tab = usable_width // num_tabs
            width_per_tab = max(TabWidget.MIN_TAB_WIDTH, width_per_tab)
            for tab in main_tabs:
                tab.set_width(width_per_tab)
    
    def _set_new_tab_enabled(self, enabled: bool):
        """Grey out "+" when there is no room left for another tab."""
        self.new_tab_btn.configure(state="normal" if enabled else "disabled")

    def _request_new_tab(self, index: Optional[int] = None):
        """Ask the owner to open a new tab (at ``index`` in the tab order, default: the end)."""
        if self.on_new_tab:
            self.on_new_tab(index)

    def _create_context_menu(self):
        """Create the right-click context menu."""
        self.context_menu = Menu(self, tearoff=0)
        self._update_context_menu_colors()
    
    def _update_context_menu_colors(self):
        """Update context menu colors to match theme."""
        self.context_menu.configure(
            bg=self.theme.get_current_color('bg_secondary'),
            fg=self.theme.get_current_color('text_primary'),
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=self.theme.get_current_color('text_on_accent')
        )
    
    def add_tab(
        self,
        tab_type: str,
        display_text: str,
        is_closable: bool = False,
        is_settings: bool = False,
        select: bool = True,
        index: Optional[int] = None
    ) -> str:
        """
        Add a new tab to the bar.

        Args:
            tab_type: "settings" for the pinned settings tab, otherwise the kind of page
                the tab was opened on
            display_text: Text to display
            is_closable: Whether tab can be closed
            is_settings: Whether this is the settings tab (goes on right)
            select: Whether to select this tab after adding
            index: Position among the regular tabs (default: after the last one)

        Returns:
            The tab_id of the created tab
        """
        tab_id = str(uuid.uuid4())
        
        # Choose parent container
        parent_container = self.settings_container if is_settings else self.tabs_container
        
        tab = TabWidget(
            parent_container,
            tab_id=tab_id,
            tab_type=tab_type,
            display_text=display_text,
            is_closable=is_closable,
            on_click=self._on_tab_click,
            on_close=self._on_tab_close,
            on_drag_start=self._on_tab_drag_start,
            on_drag_motion=self._on_tab_drag_motion,
            on_drag_end=self._on_tab_drag_end,
            on_right_click=self._on_tab_right_click
        )
        if is_settings:
            tab.pack(side="left", padx=(0, 5))
            self._tabs.append(tab)
        else:
            tab.pack(side="left", padx=(0, 5), before=self.new_tab_btn)
            # Regular tabs go before the pinned settings tab in the list
            regular = sum(1 for t in self._tabs if t.tab_type != "settings")
            self._tabs.insert(regular, tab)
            if index is not None and index < regular:
                self._reorder_tab(tab, index)

        if select:
            self.select_tab(tab_id)
        
        # Recalculate widths after adding
        self.after(10, self._recalculate_tab_widths)
        
        return tab_id
    
    def update_tab_text(self, tab_id: str, text: str):
        """Update the text of a specific tab."""
        for tab in self._tabs:
            if tab.tab_id == tab_id:
                tab.set_text(text)
                # Recalculate widths after text change
                self.after(10, self._recalculate_tab_widths)
                return
    
    def select_tab(self, tab_id: str):
        """Select a tab by its ID."""
        for tab in self._tabs:
            if tab.tab_id == tab_id:
                tab.set_active(True)
                self._active_tab_id = tab_id
                if self.on_tab_selected:
                    self.on_tab_selected(tab_id, tab.tab_type)
            else:
                tab.set_active(False)
    
    def get_tab_ids(self) -> List[str]:
        """Ids of the regular (non-settings) tabs, left to right."""
        return [t.tab_id for t in self._tabs if t.tab_type != "settings"]

    def get_tab_index(self, tab_id: str) -> int:
        """Position of a tab in the tab order (settings tab last)."""
        for i, tab in enumerate(self._tabs):
            if tab.tab_id == tab_id:
                return i
        return len(self._tabs)
    
    def get_active_tab(self) -> Optional[TabWidget]:
        """Get the currently active tab."""
        for tab in self._tabs:
            if tab.tab_id == self._active_tab_id:
                return tab
        return None
    
    def _on_tab_click(self, tab: TabWidget):
        """Handle tab click."""
        self.select_tab(tab.tab_id)
    
    def _on_tab_close(self, tab: TabWidget):
        """Handle tab close."""
        # The pinned settings tab cannot be closed
        if not tab.is_closable:
            return
        
        tab_id = tab.tab_id
        
        # Find index of tab
        tab_index = self._tabs.index(tab)
        
        # Remove tab
        self._tabs.remove(tab)
        tab.destroy()
        
        # Notify main window to clean up view
        if self.on_tab_closed:
            self.on_tab_closed(tab_id)
        
        # Recalculate widths after removal
        self.after(10, self._recalculate_tab_widths)

        # Closing the last tab leaves a fresh new one (there is always something open)
        if not any(t.tab_type != "settings" for t in self._tabs):
            self._active_tab_id = None
            self._request_new_tab()
            if self.on_tabs_changed:
                self.on_tabs_changed()
            return

        # If this was the active tab, select another
        if tab_id == self._active_tab_id:
            if self._tabs:
                # Select previous tab, or first if none
                new_index = max(0, tab_index - 1)
                while new_index >= 0 and self._tabs[new_index].tab_type == "settings":
                    new_index -= 1
                if new_index >= 0:
                    self.select_tab(self._tabs[new_index].tab_id)
        
        if self.on_tabs_changed:
            self.on_tabs_changed()
    
    def _on_tab_right_click(self, tab: TabWidget, x: int, y: int):
        """Handle right-click on tab to show context menu."""
        # The pinned settings tab has nothing to offer here
        if tab.tab_type == "settings":
            return

        # Clear and rebuild context menu
        self.context_menu.delete(0, "end")
        self.context_menu.add_command(
            label="New Tab",
            command=lambda: self._request_new_tab(self._tabs.index(tab) + 1)
        )
        self.context_menu.add_command(
            label="Duplicate Tab",
            command=lambda: self.on_duplicate_tab(tab.tab_id) if self.on_duplicate_tab else None
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Close Tab",
            command=lambda: self._on_tab_close(tab)
        )
        others = [t for t in self._tabs if t is not tab and t.is_closable]
        self.context_menu.add_command(
            label="Close Other Tabs",
            state="normal" if others else "disabled",
            command=lambda: self._close_others(tab)
        )

        self._update_context_menu_colors()
        self.context_menu.tk_popup(x, y)

    def _close_others(self, keep: TabWidget):
        """Close every closable tab except ``keep``."""
        self.select_tab(keep.tab_id)
        for tab in [t for t in self._tabs if t is not keep and t.is_closable]:
            self._on_tab_close(tab)

    def _on_tab_drag_start(self, tab: TabWidget, x: int):
        """Handle start of tab drag."""
        self._drag_tab = tab
        
        # Create drag indicator
        self._drag_indicator = ctk.CTkFrame(
            self.tabs_container,
            fg_color=self.theme.get_current_color('accent_primary'),
            width=3,
            height=30
        )
    
    def _on_tab_drag_motion(self, tab: TabWidget, x: int):
        """Handle tab drag motion."""
        if not self._drag_tab:
            return
        
        # Find insert position based on x coordinate
        insert_index = 0
        for i, t in enumerate(self._tabs):
            if t.tab_type == "settings":
                continue
            tab_x = t.winfo_rootx()
            tab_width = t.winfo_width()
            if x > tab_x + tab_width / 2:
                insert_index = i + 1
        
        self._drag_insert_index = insert_index
        
        # Position indicator (visual feedback)
        if self._drag_indicator:
            # For now, just update cursor
            pass
    
    def _on_tab_drag_end(self, tab: TabWidget):
        """Handle end of tab drag."""
        if not self._drag_tab:
            return
        
        # Clean up indicator
        if self._drag_indicator:
            self._drag_indicator.destroy()
            self._drag_indicator = None
        
        # Reorder tab. The insert index counts the dragged tab itself, so it
        # shifts down by one when the tab moves to the right.
        current_index = self._tabs.index(tab)
        target = self._drag_insert_index
        if target > current_index:
            target -= 1
        if target != current_index:
            self._reorder_tab(tab, target)
            if self.on_tabs_changed:
                self.on_tabs_changed()
        
        self._drag_tab = None
    
    def _reorder_tab(self, tab: TabWidget, new_index: int):
        """Reorder a tab to a new position."""
        # Remove from current position
        self._tabs.remove(tab)
        
        # Insert at new position
        new_index = min(new_index, len(self._tabs))
        self._tabs.insert(new_index, tab)
        
        # Repack all tabs in order (the "+" button stays last)
        for t in self._tabs:
            if t.tab_type != "settings":
                t.pack_forget()

        for t in self._tabs:
            if t.tab_type != "settings":
                t.pack(side="left", padx=(0, 5), before=self.new_tab_btn)
    
    def update_colors(self):
        """Update all colors to match current theme."""
        self.configure(fg_color=self.theme.get_current_color('tab_bar'))
        self._update_context_menu_colors()
        self.new_tab_btn.configure(
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary')
        )
        for tab in self._tabs:
            tab.update_colors()
    
    def get_tabs_by_type(self, tab_type: str) -> List[TabWidget]:
        """Get all tabs of a specific type."""
        return [t for t in self._tabs if t.tab_type == tab_type]
