"""
Stop listening to theme changes when a widget goes away.

A widget that restyles itself when the theme changes registers ``self._on_theme_changed`` with the theme
manager; the manager keeps every listener for the life of the app, so the widget must unregister when it is
destroyed or it leaks (and is called after it no longer exists). A dozen widgets each had the same ``destroy``
for that; it lives here once::

    class RuleTextView(ThemeListenerMixin, ctk.CTkFrame):
        def __init__(...):
            self.theme = get_theme_manager()
            self.theme.add_listener(self._on_theme_changed)

The mixin finds the manager in ``self.theme`` (or ``self._theme``).
"""


class ThemeListenerMixin:
    def destroy(self):
        """Unregister from the theme manager, then destroy the widget."""
        theme = getattr(self, "theme", None) or getattr(self, "_theme", None)
        if theme is not None:
            try:
                theme.remove_listener(self._on_theme_changed)
            except Exception:
                pass
        super().destroy()
