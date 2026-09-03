"""
Small platform-compatibility helpers for the Tk UI.

The one thing that genuinely differs between platforms for this app is the
right-click / secondary-click event:

* Windows / Linux - the right mouse button is ``<Button-3>``.
* macOS - a secondary click (right button, two-finger tap, or Control-click)
  arrives as ``<Button-2>``; ``<Control-Button-1>`` covers the Control-click
  case explicitly, and ``<Button-3>`` still fires for a genuine right button on
  a plugged-in mouse.

``RIGHT_CLICK_SEQUENCES`` is therefore platform-aware: on Windows and Linux it
stays exactly ``("<Button-3>",)`` so existing behaviour is byte-for-byte
unchanged (in particular middle-click is *not* repurposed), and only macOS gets
the extra bindings.
"""

import sys

if sys.platform == "darwin":
    RIGHT_CLICK_SEQUENCES = ("<Button-2>", "<Control-Button-1>", "<Button-3>")
else:
    RIGHT_CLICK_SEQUENCES = ("<Button-3>",)


def bind_right_click(widget, callback, add: bool = False) -> None:
    """Bind ``callback`` to the platform's secondary-click event(s) on ``widget``.

    ``add`` is passed through only when truthy: CustomTkinter's overridden
    ``bind`` rejects ``add=False`` (it accepts only ``'+'`` or ``True``), while
    plain Tk widgets are happy either way.
    """
    for seq in RIGHT_CLICK_SEQUENCES:
        if add:
            widget.bind(seq, callback, add=add)
        else:
            widget.bind(seq, callback)


def unbind_right_click(widget) -> None:
    """Remove any secondary-click bindings this module added to ``widget``."""
    for seq in RIGHT_CLICK_SEQUENCES:
        try:
            widget.unbind(seq)
        except Exception:
            pass
