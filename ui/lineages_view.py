"""
Lineages View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of lineages with details panel.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Callable
from lineage import Lineage, LineageTrait, LineageManager, get_lineage_manager
from theme import get_theme_manager
from settings import get_settings_manager


class LineageListPanel(ctk.CTkFrame):
    """A scrollable list panel for displaying and selecting lineages."""
    
    # Batch size for progressive loading - smaller batches = smoother UI
    BATCH_SIZE = 15
    BATCH_DELAY_MS = 5  # Milliseconds between batches
    
    def __init__(self, parent, on_select: Callable[[Optional[Lineage]], None],
                 on_right_click: Optional[Callable[[Lineage, int, int], None]] = None):
        super().__init__(parent, corner_radius=10)
        
        self.on_select = on_select
        self.on_right_click = on_right_click
        self._lineages: List[Lineage] = []
        self._selected_index: Optional[int] = None
        self._lineage_buttons: List[ctk.CTkButton] = []
        self._pending_after_id: Optional[str] = None  # Track pending after() calls
        self.theme = get_theme_manager()
        
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self._refresh_buttons()
    
    def _create_widgets(self):
        """Create the scrollable lineage list."""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header_frame, text="Lineages", 
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        text_secondary = self.theme.get_text_secondary()
        self.count_label = ctk.CTkLabel(header_frame, text="0 lineages",
                                         font=ctk.CTkFont(size=12),
                                         text_color=text_secondary)
        self.count_label.pack(side="right")
        
        # Scrollable frame for lineage list
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _create_lineage_button(self, lineage: Lineage, index: int) -> ctk.CTkButton:
        """Create a button for a lineage."""
        display_name = lineage.name
        if lineage.is_custom:
            display_name = f"* {display_name}"
        
        btn = ctk.CTkButton(
            self.scroll_frame,
            text=display_name,
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color=("transparent" if index != self._selected_index 
                      else self.theme.get_current_color('accent_primary')),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            font=ctk.CTkFont(size=13),
            command=lambda i=index: self._on_lineage_click(i)
        )
        btn.pack(fill="x", pady=2)
        
        # Bind right-click event
        if self.on_right_click:
            btn.bind("<Button-3>", lambda e, i=index: self._on_lineage_right_click(e, i))
            for child in btn.winfo_children():
                child.bind("<Button-3>", lambda e, i=index: self._on_lineage_right_click(e, i))
        
        return btn
    
    def _on_lineage_right_click(self, event, index: int):
        """Handle right-click on a lineage button - show context menu only."""
        if self.on_right_click and 0 <= index < len(self._lineages):
            self.on_right_click(self._lineages[index], event.x_root, event.y_root)
    
    def _on_lineage_click(self, index: int):
        """Handle lineage selection."""
        if self._selected_index is not None and self._selected_index < len(self._lineage_buttons):
            self._lineage_buttons[self._selected_index].configure(fg_color="transparent")
        
        self._selected_index = index
        if index < len(self._lineage_buttons):
            self._lineage_buttons[index].configure(
                fg_color=self.theme.get_current_color('accent_primary')
            )
        
        if 0 <= index < len(self._lineages):
            self.on_select(self._lineages[index])
        else:
            self.on_select(None)
    
    def _update_lineage_button(self, btn: ctk.CTkButton, lineage: Lineage, index: int):
        """Update an existing button with new lineage data."""
        display_name = lineage.name
        if lineage.is_custom:
            display_name = f"* {display_name}"
        
        btn.configure(
            text=display_name,
            fg_color=("transparent" if index != self._selected_index 
                      else self.theme.get_current_color('accent_primary')),
            command=lambda i=index: self._on_lineage_click(i)
        )
        
        # Rebind right-click events with new index
        if self.on_right_click:
            btn.unbind("<Button-3>")
            btn.bind("<Button-3>", lambda e, i=index: self._on_lineage_right_click(e, i))
            for child in btn.winfo_children():
                child.unbind("<Button-3>")
                child.bind("<Button-3>", lambda e, i=index: self._on_lineage_right_click(e, i))
    
    def _cancel_pending_load(self):
        """Cancel any pending progressive load operation."""
        if self._pending_after_id is not None:
            try:
                self.after_cancel(self._pending_after_id)
            except Exception:
                pass
            self._pending_after_id = None
    
    def set_lineages(self, lineages: List[Lineage], reset_scroll: bool = True, 
                     preserve_selection: Optional[str] = None):
        """Update the list of lineages.
        
        Uses progressive loading to prevent UI freezing - processes buttons
        in batches with UI updates between batches.
        """
        # Cancel any pending progressive load
        self._cancel_pending_load()
        
        self._lineages = lineages
        
        # Find preserved selection
        new_selected_index = None
        if preserve_selection:
            for i, lineage in enumerate(lineages):
                if lineage.name == preserve_selection:
                    new_selected_index = i
                    break
        
        self._selected_index = new_selected_index
        self._preserve_selection_name = preserve_selection
        
        # Update count immediately
        self.count_label.configure(text=f"{len(lineages)} lineage{'s' if len(lineages) != 1 else ''}")
        
        # Reset scroll position to top
        if reset_scroll and self.scroll_frame.winfo_children():
            try:
                self.scroll_frame._parent_canvas.yview_moveto(0)
            except Exception:
                pass
        
        # Start progressive loading from index 0
        self._load_lineages_batch(0)
    
    def _load_lineages_batch(self, start_index: int):
        """Load a batch of lineage buttons progressively."""
        if not self.winfo_exists():
            return
        
        current_button_count = len(self._lineage_buttons)
        new_lineage_count = len(self._lineages)
        end_index = min(start_index + self.BATCH_SIZE, new_lineage_count)
        
        # Process this batch
        for i in range(start_index, end_index):
            if i < current_button_count:
                # Reuse existing button - make sure it's visible
                btn = self._lineage_buttons[i]
                self._update_lineage_button(btn, self._lineages[i], i)
                # Re-pack if it was previously hidden
                if not btn.winfo_ismapped():
                    btn.pack(fill="x", pady=2)
            else:
                # Create new button
                btn = self._create_lineage_button(self._lineages[i], i)
                self._lineage_buttons.append(btn)
        
        # If we've processed all lineages, hide excess buttons (don't destroy)
        if end_index >= new_lineage_count:
            # Hide excess buttons instead of destroying them
            for i in range(new_lineage_count, current_button_count):
                self._lineage_buttons[i].pack_forget()
            # Restore selection if found
            if self._selected_index is not None:
                self._on_lineage_click(self._selected_index)
            self._pending_after_id = None
        else:
            # Schedule next batch
            self._pending_after_id = self.after(self.BATCH_DELAY_MS, lambda: self._load_lineages_batch(end_index))
    
    def _refresh_buttons(self):
        """Refresh button colors after theme change."""
        for i, btn in enumerate(self._lineage_buttons):
            if i == self._selected_index:
                btn.configure(fg_color=self.theme.get_current_color('accent_primary'))
            else:
                btn.configure(fg_color="transparent")
            btn.configure(
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary')
            )
    
    def get_selected_lineage(self) -> Optional[Lineage]:
        """Get the currently selected lineage."""
        if self._selected_index is not None and self._selected_index < len(self._lineages):
            return self._lineages[self._selected_index]
        return None
    
    def select_lineage(self, name: str) -> bool:
        """Select a lineage by name. Returns True if found."""
        for i, lineage in enumerate(self._lineages):
            if lineage.name.lower() == name.lower():
                self._on_lineage_click(i)
                return True
        return False


class LineageDetailPanel(ctk.CTkFrame):
    """Panel displaying detailed information about a lineage."""
    
    def __init__(self, parent):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self._current_lineage: Optional[Lineage] = None
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self._update_colors()
    
    def _create_widgets(self):
        """Create the detail view widgets."""
        # Scrollable content
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Lineage name
        self.name_label = ctk.CTkLabel(
            self.scroll_frame, text="Select a lineage",
            font=ctk.CTkFont(size=24, weight="bold"),
            wraplength=800
        )
        self.name_label.pack(anchor="w", pady=(0, 5))
        
        # Source info
        self.source_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_text_secondary()
        )
        self.source_label.pack(anchor="w", pady=(0, 10))
        
        # Stats frame (creature type, size, speed)
        self.stats_frame = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        
        self.stats_inner = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        self.stats_inner.pack(fill="x", padx=10, pady=8)
        
        # Create stats labels - left aligned
        self.creature_type_label = ctk.CTkLabel(
            self.stats_inner, text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.creature_type_label.pack(fill="x", anchor="w", pady=1)
        
        self.size_label = ctk.CTkLabel(
            self.stats_inner, text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.size_label.pack(fill="x", anchor="w", pady=1)
        
        self.speed_label = ctk.CTkLabel(
            self.stats_inner, text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.speed_label.pack(fill="x", anchor="w", pady=1)
        
        # Description
        self.desc_header = ctk.CTkLabel(
            self.scroll_frame, text="Description",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        
        # Description container for rich text rendering
        self.description_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._desc_widgets = []
        
        # Traits section
        self.traits_header = ctk.CTkLabel(
            self.scroll_frame, text="Traits",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        
        # Container for trait widgets
        self.traits_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._trait_widgets = []
    
    def _update_colors(self):
        """Update colors after theme change."""
        self.stats_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
    
    def _clear_traits(self):
        """Clear all trait widgets."""
        for widget in self._trait_widgets:
            widget.destroy()
        self._trait_widgets = []
    
    def _get_renderer(self):
        """Get or create the rich text renderer."""
        if not hasattr(self, '_renderer'):
            from ui.rich_text_utils import RichTextRenderer
            self._renderer = RichTextRenderer(self.theme)
        return self._renderer
    
    def _render_trait(self, trait: LineageTrait):
        """Render a single trait with support for markdown tables and spell links."""
        # Trait frame
        trait_frame = ctk.CTkFrame(
            self.traits_container,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        trait_frame.pack(fill="x", pady=2)
        self._trait_widgets.append(trait_frame)
        
        inner = ctk.CTkFrame(trait_frame, fg_color="transparent")
        inner.pack(fill="x", expand=True, padx=10, pady=6)
        
        # Trait name
        name_label = ctk.CTkLabel(
            inner, text=trait.name,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        name_label.pack(fill="x", anchor="w")
        
        # Trait description with dynamic resizing
        if trait.description:
            from ui.rich_text_utils import DynamicText
            dt = DynamicText(
                inner, self.theme,
                bg_color='bg_secondary'  # Use theme color key
            )
            dt.set_text(trait.description)
            dt.pack(fill="x", expand=True)
    
    def _clear_description(self):
        """Clear all description widgets."""
        for widget in self._desc_widgets:
            widget.destroy()
        self._desc_widgets = []
    
    def _render_description(self, text: str):
        """Render description with bold text and dynamic resizing."""
        from ui.rich_text_utils import DynamicText
        
        self._clear_description()
        
        if not text:
            return
        
        dt = DynamicText(
            self.description_container, self.theme,
            bg_color='bg_primary'  # Use theme color key
        )
        dt.set_text(text)
        dt.pack(fill="x", expand=True)
        self._desc_widgets.append(dt)
    
    def show_lineage(self, lineage: Optional[Lineage]):
        """Display details for a lineage."""
        self._current_lineage = lineage
        
        if lineage is None:
            self.name_label.configure(text="Select a lineage")
            self.source_label.configure(text="")
            self.stats_frame.pack_forget()
            self.desc_header.pack_forget()
            self._clear_description()
            self.description_container.pack_forget()
            self.traits_header.pack_forget()
            self.traits_container.pack_forget()
            self._clear_traits()
            return
        
        # Name (with custom indicator)
        name_text = f"* {lineage.name}" if lineage.is_custom else lineage.name
        self.name_label.configure(text=name_text)
        
        # Source
        if lineage.source:
            source_text = f"Source: {lineage.source}"
            if not lineage.is_official:
                source_text += " (Unofficial)"
            if lineage.is_legacy:
                source_text += " [Legacy]"
            self.source_label.configure(text=source_text)
        else:
            self.source_label.configure(text="")
        
        # Stats
        self.creature_type_label.configure(text=f"Creature Type: {lineage.creature_type}")
        self.size_label.configure(text=f"Size: {lineage.size}")
        self.speed_label.configure(text=f"Speed: {lineage.speed} feet")
        self.stats_frame.pack(fill="x", pady=(0, 15))
        
        # Description - render with RichTextRenderer for bold and spell popups
        if lineage.description:
            self.desc_header.pack(anchor="w", pady=(10, 5))
            self._render_description(lineage.description)
            self.description_container.pack(fill="x", pady=(0, 10))
        else:
            self.desc_header.pack_forget()
            self._clear_description()
            self.description_container.pack_forget()
        
        # Traits
        self._clear_traits()
        if lineage.traits:
            self.traits_header.pack(anchor="w", pady=(10, 5))
            self.traits_container.pack(fill="x")
            for trait in lineage.traits:
                self._render_trait(trait)
        else:
            self.traits_header.pack_forget()
            self.traits_container.pack_forget()


class LineagesView(ctk.CTkFrame):
    """Main view for browsing and managing lineages."""
    
    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        
        self.lineage_manager = get_lineage_manager()
        self.character_manager = character_manager
        self.settings_manager = get_settings_manager()
        self.on_back = on_back
        self._all_lineages: List[Lineage] = []
        self._filtered_lineages: List[Lineage] = []
        self._compare_mode = False
        self._compare_lineage: Optional[Lineage] = None
        self._context_lineage: Optional[Lineage] = None
        
        # Debouncing for filter changes
        self._filter_debounce_id: Optional[str] = None
        self._filter_debounce_delay = 150  # ms for text input
        
        self._create_widgets()
        self._create_context_menu()
        self._create_compare_panel()
        self._load_lineages()
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._update_context_menu_colors()
        if hasattr(self, 'paned'):
            self._update_paned_colors()
    
    def _update_context_menu_colors(self):
        """Update context menu colors for theme."""
        if not hasattr(self, 'context_menu'):
            return
        bg_color = self.theme.get_current_color('bg_secondary')
        fg_color = self.theme.get_current_color('text_primary')
        self.context_menu.configure(
            bg=bg_color,
            fg=fg_color,
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=fg_color
        )
    
    def _create_widgets(self):
        """Create the main layout."""
        # Top bar with search and filters
        self._create_filter_bar()
        
        # Main content area with list and detail panels
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Create a PanedWindow for resizable panels
        self.paned = tk.PanedWindow(
            self.content,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            handlesize=0,
            opaqueresize=False,
            sashcursor="sb_h_double_arrow"
        )
        self.paned.pack(fill="both", expand=True)
        self._update_paned_colors()
        
        # Left container to hold list or compare panel
        self.left_container = ctk.CTkFrame(self.paned, fg_color="transparent")
        
        # Lineage list panel (left)
        self.list_panel = LineageListPanel(
            self.left_container, 
            on_select=self._on_lineage_selected,
            on_right_click=self._on_lineage_right_click
        )
        self.list_panel.pack(fill="both", expand=True)
        
        # Lineage detail panel (right)
        self.detail_panel = LineageDetailPanel(self.paned)
        
        # Add panes with minimum sizes
        self.paned.add(self.left_container, minsize=280, stretch="always")
        self.paned.add(self.detail_panel, minsize=400, stretch="always")
        
        # Set initial sash position (roughly 1:2 ratio)
        self.after(100, lambda: self.paned.sash_place(0, 320, 0))
    
    def _update_paned_colors(self):
        """Update PanedWindow sash colors based on current theme."""
        sash_color = self.theme.get_current_color("pane_sash")
        self.paned.configure(bg=sash_color)
    
    def _create_filter_bar(self):
        """Create the filter bar at the top."""
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)
        
        # Back button to return to collections
        if self.on_back:
            back_btn = ctk.CTkButton(
                filter_bar, text="← Collections", width=110,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                command=self.on_back
            )
            back_btn.pack(side="left", padx=(0, 15))
        
        # Search box
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        
        search_entry = ctk.CTkEntry(
            filter_bar, width=250, height=35,
            placeholder_text="Search lineages...",
            textvariable=self.search_var
        )
        search_entry.pack(side="left", padx=(0, 15))
        
        # Size filter dropdown
        ctk.CTkLabel(filter_bar, text="Size:").pack(side="left", padx=(0, 5))
        
        self.size_var = ctk.StringVar(value="All Sizes")
        self.size_combo = ctk.CTkComboBox(
            filter_bar, width=150, height=35,
            values=["All Sizes"],
            variable=self.size_var,
            command=lambda _: self._on_filter_changed(immediate=True),
            state="readonly"
        )
        self.size_combo.pack(side="left", padx=(0, 15))
        
        # Creature type filter
        ctk.CTkLabel(filter_bar, text="Type:").pack(side="left", padx=(0, 5))
        
        self.type_var = ctk.StringVar(value="All Types")
        self.type_combo = ctk.CTkComboBox(
            filter_bar, width=150, height=35,
            values=["All Types"],
            variable=self.type_var,
            command=lambda _: self._on_filter_changed(immediate=True),
            state="readonly"
        )
        self.type_combo.pack(side="left", padx=(0, 15))
        
        # Add lineage button (right side)
        add_btn = ctk.CTkButton(
            filter_bar, text="+ Add Lineage",
            width=120, height=35,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_add_lineage
        )
        add_btn.pack(side="right")
        
        # Edit/Delete buttons
        self.delete_btn = ctk.CTkButton(
            filter_bar, text="Delete",
            width=80, height=35,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._on_delete_lineage
        )
        self.delete_btn.pack(side="right", padx=(0, 5))
        
        self.edit_btn = ctk.CTkButton(
            filter_bar, text="Edit",
            width=80, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_edit_lineage
        )
        self.edit_btn.pack(side="right", padx=(0, 5))
    
    def _create_context_menu(self):
        """Create the right-click context menu for lineages."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self._update_context_menu_colors()
        self.context_menu.add_command(
            label="Set as Character Lineage",
            command=self._context_set_lineage
        )
        self.context_menu.add_command(
            label="Compare",
            command=self._context_compare
        )
    
    def _create_compare_panel(self):
        """Create the compare lineage panel (hidden initially)."""
        self.compare_container = ctk.CTkFrame(self.left_container, corner_radius=10)
        
        # Header with close button
        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text="Compare Lineages",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")
        
        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._close_compare
        ).pack(side="right")
        
        # Compare detail panel
        self.compare_detail = LineageDetailPanel(self.compare_container)
        self.compare_detail.pack(fill="both", expand=True, padx=5, pady=5)
    
    def _load_lineages(self):
        """Load all lineages from manager."""
        self._all_lineages = self.lineage_manager.lineages.copy()
        self._update_filter_options()
        self._on_filter_changed(immediate=True)
    
    def _on_filter_changed(self, immediate: bool = False):
        """Called when any filter value changes with debouncing."""
        if self._filter_debounce_id is not None:
            self.after_cancel(self._filter_debounce_id)
            self._filter_debounce_id = None
        
        if immediate:
            self._filter_debounce_id = self.after(10, self._apply_filters)
        else:
            self._filter_debounce_id = self.after(self._filter_debounce_delay, self._apply_filters)
    
    def _update_filter_options(self):
        """Update filter dropdown options based on loaded lineages."""
        # Update size options
        sizes = self.lineage_manager.get_all_sizes()
        size_options = ["All Sizes"] + sizes
        self.size_combo.configure(values=size_options)
        
        # Update type options
        types = self.lineage_manager.get_all_creature_types()
        type_options = ["All Types"] + types
        self.type_combo.configure(values=type_options)
    
    def _apply_filters(self):
        """Apply current filters to the lineage list."""
        search = self.search_var.get().lower()
        size_filter = self.size_var.get()
        type_filter = self.type_var.get()
        
        filtered = []
        for lineage in self._all_lineages:
            # Search filter
            if search and search not in lineage.name.lower():
                if not any(search in t.name.lower() for t in lineage.traits):
                    continue
            
            # Size filter
            if size_filter != "All Sizes" and lineage.size != size_filter:
                # Handle "Small or Medium" type sizes
                if size_filter not in lineage.size:
                    continue
            
            # Type filter
            if type_filter != "All Types" and lineage.creature_type != type_filter:
                continue
            
            filtered.append(lineage)
        
        self._filtered_lineages = filtered
        
        # Preserve selection if possible
        current = self.list_panel.get_selected_lineage()
        preserve = current.name if current else None
        
        self.list_panel.set_lineages(filtered, preserve_selection=preserve)
    
    def _on_lineage_selected(self, lineage: Optional[Lineage]):
        """Handle lineage selection."""
        self.detail_panel.show_lineage(lineage)
    
    def _on_lineage_right_click(self, lineage: Lineage, x: int, y: int):
        """Handle right-click on lineage - show context menu."""
        self._context_lineage = lineage
        self.context_menu.tk_popup(x, y)
    
    def _context_set_lineage(self):
        """Set lineage for current character from context menu."""
        if self._context_lineage and self.character_manager:
            char = self.character_manager.get_active_character()
            if char:
                char.lineage = self._context_lineage.name
                self.character_manager.save_characters()
                messagebox.showinfo(
                    "Lineage Set",
                    f"Set {char.name}'s lineage to {self._context_lineage.name}.",
                    parent=self
                )
            else:
                messagebox.showwarning(
                    "No Character",
                    "No active character selected.",
                    parent=self
                )
    
    def _context_compare(self):
        """Show compare panel from context menu."""
        if self._context_lineage:
            self._show_compare(self._context_lineage)
    
    def _show_compare(self, lineage: Lineage):
        """Show compare panel with the given lineage."""
        self._compare_mode = True
        self._compare_lineage = lineage
        
        # Hide list, show compare
        self.list_panel.pack_forget()
        self.compare_container.pack(fill="both", expand=True)
        self.compare_detail.show_lineage(lineage)
    
    def _close_compare(self):
        """Close the compare panel."""
        self._compare_mode = False
        self._compare_lineage = None
        
        self.compare_container.pack_forget()
        self.list_panel.pack(fill="both", expand=True)
    
    def _on_add_lineage(self):
        """Open dialog to add a new lineage."""
        dialog = LineageEditorDialog(self.winfo_toplevel(), self.lineage_manager)
        dialog.grab_set()
        self.wait_window(dialog)
        
        if dialog.result:
            self._load_lineages()
            self.list_panel.select_lineage(dialog.result.name)
    
    def _on_edit_lineage(self):
        """Edit the selected lineage."""
        lineage = self.list_panel.get_selected_lineage()
        if not lineage:
            messagebox.showwarning("No Selection", "Please select a lineage to edit.", parent=self)
            return
        
        if lineage.is_official and not lineage.is_custom:
            messagebox.showwarning(
                "Cannot Edit",
                "Official lineages cannot be edited. You can create a copy instead.",
                parent=self
            )
            return
        
        dialog = LineageEditorDialog(
            self.winfo_toplevel(), self.lineage_manager, lineage=lineage
        )
        dialog.grab_set()
        self.wait_window(dialog)
        
        if dialog.result:
            self._load_lineages()
            self.list_panel.select_lineage(dialog.result.name)
    
    def _on_delete_lineage(self):
        """Delete the selected lineage."""
        lineage = self.list_panel.get_selected_lineage()
        if not lineage:
            messagebox.showwarning("No Selection", "Please select a lineage to delete.", parent=self)
            return
        
        if lineage.is_official and not lineage.is_custom:
            messagebox.showwarning(
                "Cannot Delete",
                "Official lineages cannot be deleted.",
                parent=self
            )
            return
        
        if messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{lineage.name}'?",
            parent=self
        ):
            self.lineage_manager.remove_lineage(lineage.name)
            self._load_lineages()
    
    def refresh(self):
        """Refresh the lineage list."""
        self._load_lineages()
    
    def select_lineage(self, name: str) -> bool:
        """Select a lineage by name. Returns True if found."""
        return self.list_panel.select_lineage(name)


class LineageEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing lineages."""
    
    def __init__(self, parent, lineage_manager: LineageManager, lineage: Optional[Lineage] = None):
        super().__init__(parent)
        
        self.lineage_manager = lineage_manager
        self.editing_lineage = lineage
        self.result: Optional[Lineage] = None
        self.theme = get_theme_manager()
        self._trait_entries = []  # List of (name_entry, desc_entry, frame) tuples
        
        self.title("Edit Lineage" if lineage else "Add Lineage")
        self.geometry("700x700")
        self.minsize(600, 500)
        
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 700) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_widgets()
        
        if lineage:
            self._populate_from_lineage(lineage)
    
    def _create_widgets(self):
        """Create the editor UI."""
        # Main scrollable container
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Name
        ctk.CTkLabel(self.scroll, text="Name:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(self.scroll, width=400, height=35)
        self.name_entry.pack(fill="x", pady=(5, 15))
        
        # Row for creature type, size, speed
        stats_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 15))
        
        # Creature Type
        type_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        type_frame.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(type_frame, text="Creature Type:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.creature_type_entry = ctk.CTkEntry(type_frame, width=150, height=35)
        self.creature_type_entry.pack()
        self.creature_type_entry.insert(0, "Humanoid")
        
        # Size
        size_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        size_frame.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(size_frame, text="Size:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.size_combo = ctk.CTkComboBox(
            size_frame, width=150, height=35,
            values=["Small", "Medium", "Large", "Small or Medium"],
            state="readonly"
        )
        self.size_combo.pack()
        self.size_combo.set("Medium")
        
        # Speed
        speed_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        speed_frame.pack(side="left")
        ctk.CTkLabel(speed_frame, text="Speed (feet):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.speed_entry = ctk.CTkEntry(speed_frame, width=80, height=35)
        self.speed_entry.pack()
        self.speed_entry.insert(0, "30")
        
        # Source
        ctk.CTkLabel(self.scroll, text="Source:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.source_entry = ctk.CTkEntry(self.scroll, width=300, height=35)
        self.source_entry.pack(anchor="w", pady=(5, 15))
        
        # Description
        ctk.CTkLabel(self.scroll, text="Description:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        
        self.desc_text = ctk.CTkTextbox(self.scroll, height=100)
        
        # Add rich text toolbar for description
        from ui.rich_text_utils import RichTextEditor
        self._desc_rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        desc_toolbar = self._desc_rich_editor.create_toolbar(self.scroll)
        desc_toolbar.pack(fill="x", pady=(5, 5))
        
        self.desc_text.pack(fill="x", pady=(0, 15))
        
        # Traits section
        traits_header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        traits_header.pack(fill="x", pady=(10, 5))
        
        ctk.CTkLabel(traits_header, text="Traits:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        ctk.CTkButton(
            traits_header, text="+ Add Trait", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            command=self._add_trait
        ).pack(side="right")
        
        # Container for trait entries
        self.traits_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.traits_container.pack(fill="x", pady=(5, 15))
        
        # Buttons
        btn_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save",
            width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_secondary'),
            command=self._save
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_frame, text="Cancel",
            width=100,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(side="left")
    
    def _add_trait(self, name: str = "", description: str = ""):
        """Add a trait entry."""
        from ui.rich_text_utils import RichTextEditor
        
        frame = ctk.CTkFrame(
            self.traits_container,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=10)
        
        # Header with remove button
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(header, text="Trait Name:", font=ctk.CTkFont(size=12)).pack(side="left")
        
        remove_btn = ctk.CTkButton(
            header, text="✕", width=25, height=25,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=lambda f=frame: self._remove_trait(f)
        )
        remove_btn.pack(side="right")
        
        name_entry = ctk.CTkEntry(inner, height=30)
        name_entry.pack(fill="x", pady=(5, 10))
        name_entry.insert(0, name)
        
        ctk.CTkLabel(inner, text="Description:", font=ctk.CTkFont(size=12)).pack(anchor="w")
        
        desc_entry = ctk.CTkTextbox(inner, height=80)
        
        # Add rich text toolbar
        rich_editor = RichTextEditor(self, desc_entry, self.theme)
        toolbar = rich_editor.create_toolbar(inner)
        toolbar.pack(fill="x", pady=(5, 5))
        
        desc_entry.pack(fill="x", pady=(0, 0))
        desc_entry.insert("1.0", description)
        
        self._trait_entries.append((name_entry, desc_entry, frame))
    
    def _remove_trait(self, frame):
        """Remove a trait entry."""
        for i, (name_e, desc_e, f) in enumerate(self._trait_entries):
            if f == frame:
                frame.destroy()
                del self._trait_entries[i]
                break
    
    def _populate_from_lineage(self, lineage: Lineage):
        """Populate fields from existing lineage."""
        self.name_entry.insert(0, lineage.name)
        self.creature_type_entry.delete(0, "end")
        self.creature_type_entry.insert(0, lineage.creature_type)
        self.size_combo.set(lineage.size)
        self.speed_entry.delete(0, "end")
        self.speed_entry.insert(0, str(lineage.speed))
        self.source_entry.insert(0, lineage.source)
        self.desc_text.insert("1.0", lineage.description)
        
        for trait in lineage.traits:
            self._add_trait(trait.name, trait.description)
    
    def _save(self):
        """Save the lineage."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Name is required.", parent=self)
            return
        
        try:
            speed = int(self.speed_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Speed must be a number.", parent=self)
            return
        
        # Gather traits
        traits = []
        for name_entry, desc_entry, _ in self._trait_entries:
            trait_name = name_entry.get().strip()
            trait_desc = desc_entry.get("1.0", "end-1c").strip()
            if trait_name:
                traits.append(LineageTrait(name=trait_name, description=trait_desc))
        
        lineage = Lineage(
            name=name,
            description=self.desc_text.get("1.0", "end-1c").strip(),
            creature_type=self.creature_type_entry.get().strip() or "Humanoid",
            size=self.size_combo.get(),
            speed=speed,
            traits=traits,
            source=self.source_entry.get().strip(),
            is_official=False,
            is_custom=True,
            is_legacy=False
        )
        
        self.lineage_manager.add_lineage(lineage)
        self.result = lineage
        self.destroy()
