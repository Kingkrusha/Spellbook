"""Dialog shown when a newer Spellbook release is available.

Downloads the matching build into the Downloads folder, verifies it against the
release's SHA256SUMS when one is published, then either installs it in place and
restarts (packaged builds) or reveals the file for a manual install.
"""

from __future__ import annotations

import threading
from tkinter import messagebox
from typing import Callable, Optional

import customtkinter as ctk

from theme import get_theme_manager
from updater import (
    UpdateCheckError,
    UpdateInfo,
    apply_update,
    can_self_update,
    download_asset,
    fetch_expected_hash,
    open_release_page,
    reveal_in_file_manager,
)
from version import __version__


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class UpdateDialog(ctk.CTkToplevel):
    """Modal-ish 'update available' window.

    ``on_skip`` (if given) is called with ``info.version`` when the user chooses
    "Skip This Version", so the caller can persist that and stop nagging.

    ``on_restart`` (if given) is called after :func:`updater.apply_update` has
    spawned its helper; it must quit the app promptly so the helper can swap the
    executable. When omitted, the dialog invokes the parent window's
    ``WM_DELETE_WINDOW`` handler (the normal graceful-quit path).
    """

    def __init__(
        self,
        parent,
        info: UpdateInfo,
        on_skip: Optional[Callable[[str], None]] = None,
        on_restart: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)

        self._parent = parent
        self._info = info
        self._on_skip = on_skip
        self._on_restart = on_restart
        self._downloading = False
        self._verified: Optional[bool] = None
        self._theme = get_theme_manager()

        self.title("Update Available")
        self.geometry("520x500")
        self.minsize(460, 420)
        self.transient(parent)

        try:
            self.configure(fg_color=self._theme.get_current_color("bg_primary"))
        except Exception:
            pass

        self._build()

        # Centre on the parent window.
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

        self.lift()
        self.after(100, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    # --- UI ----------------------------------------------------------------

    def _build(self):
        theme = self._theme
        text_secondary = theme.get_text_secondary()
        btn_text = theme.get_current_color("text_primary")
        btn_normal = theme.get_current_color("button_normal")
        btn_hover = theme.get_current_color("button_hover")

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container,
            text=f"Spellbook {self._info.version} is available",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            container,
            text=f"You have version {__version__}.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary,
        ).pack(anchor="w", pady=(2, 12))

        notes_header = "What's new" if self._info.notes else "Release"
        ctk.CTkLabel(
            container,
            text=notes_header,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w")

        notes_box = ctk.CTkTextbox(
            container,
            wrap="word",
            font=ctk.CTkFont(size=12),
            fg_color=theme.get_current_color("bg_secondary"),
            text_color=theme.get_current_color("text_primary"),
        )
        notes_box.pack(fill="both", expand=True, pady=(4, 12))
        notes_box.insert(
            "1.0",
            self._info.notes or "No release notes were provided.",
        )
        notes_box.configure(state="disabled")

        # Status / progress area (hidden until a download starts).
        self._status_label = ctk.CTkLabel(
            container,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=text_secondary,
            anchor="w",
            justify="left",
        )
        self._progress = ctk.CTkProgressBar(container, height=8)
        self._progress.set(0)

        # Buttons.
        buttons = ctk.CTkFrame(container, fg_color="transparent")
        buttons.pack(fill="x", pady=(4, 0))

        self._later_btn = ctk.CTkButton(
            buttons, text="Later", width=80,
            fg_color=btn_normal, hover_color=btn_hover, text_color=btn_text,
            command=self._on_later,
        )
        self._later_btn.pack(side="right")

        self._skip_btn = ctk.CTkButton(
            buttons, text="Skip This Version", width=140,
            fg_color=btn_normal, hover_color=btn_hover, text_color=btn_text,
            command=self._on_skip_clicked,
        )
        self._skip_btn.pack(side="right", padx=(0, 10))

        if self._info.has_download:
            self._primary_btn = ctk.CTkButton(
                buttons, text="Download", width=110,
                text_color=btn_text,
                command=self._on_download,
            )
        else:
            self._primary_btn = ctk.CTkButton(
                buttons, text="View on GitHub", width=130,
                text_color=btn_text,
                command=self._on_view,
            )
        self._primary_btn.pack(side="right", padx=(0, 10))

        self._github_btn = ctk.CTkButton(
            buttons, text="Release Notes", width=120,
            fg_color=btn_normal, hover_color=btn_hover, text_color=btn_text,
            command=self._on_view,
        )
        if self._info.has_download:
            self._github_btn.pack(side="left")

    # --- actions ---------------------------------------------------------

    def _on_view(self):
        open_release_page(self._info)

    def _on_later(self):
        if not self._downloading:
            self.destroy()

    def _on_skip_clicked(self):
        if self._downloading:
            return
        if self._on_skip:
            try:
                self._on_skip(self._info.version)
            except Exception:
                pass
        self.destroy()

    def _on_download(self):
        if self._downloading or self._info.asset is None:
            return
        self._downloading = True
        self._primary_btn.configure(state="disabled")
        self._skip_btn.configure(state="disabled")
        self._later_btn.configure(state="disabled")

        self._status_label.pack(fill="x", pady=(0, 4))
        self._progress.pack(fill="x", pady=(0, 10))
        self._progress.set(0)
        self._status_label.configure(text=f"Downloading {self._info.asset.name}...")

        thread = threading.Thread(target=self._download_worker, daemon=True)
        thread.start()

    def _download_worker(self):
        try:
            # Best-effort integrity check: if the release publishes SHA256SUMS,
            # download_asset() verifies against it and raises on a mismatch.
            expected = fetch_expected_hash(self._info)
            path = download_asset(
                self._info,
                progress_cb=self._on_progress,
                expected_sha256=expected,
            )
        except UpdateCheckError as exc:
            self.after(0, lambda: self._download_failed(str(exc)))
        except Exception as exc:  # noqa: BLE001 - surface anything else too
            self.after(0, lambda: self._download_failed(str(exc)))
        else:
            self._verified = expected is not None
            self.after(0, lambda: self._download_done(path))

    def _on_progress(self, done: int, total: int):
        def apply():
            if total > 0:
                self._progress.set(done / total)
                self._status_label.configure(
                    text=f"Downloading... {_human_size(done)} of {_human_size(total)}"
                )
            else:
                self._status_label.configure(
                    text=f"Downloading... {_human_size(done)}"
                )
        try:
            self.after(0, apply)
        except Exception:
            pass

    def _download_done(self, path: str):
        self._downloading = False
        self._downloaded_path = path
        self._progress.set(1)

        integrity = (
            "Verified against the release checksum."
            if self._verified
            else "Downloaded (no checksum published for this release)."
        )

        can_install, why_not = can_self_update()
        if can_install:
            self._status_label.configure(
                text=f"{integrity}\nSpellbook will close and reopen to finish installing."
            )
            self._primary_btn.configure(
                text="Install & Restart", state="normal", command=self._on_install
            )
            self._later_btn.configure(text="Not Now", state="normal")
            try:
                self._skip_btn.destroy()
            except Exception:
                pass
        else:
            reveal_in_file_manager(path)
            self._status_label.configure(
                text=f"{integrity}\nSaved to {path}\n{why_not}\n"
                     "Close Spellbook, then run the downloaded file to update."
            )
            self._primary_btn.configure(
                text="Show File", state="normal",
                command=lambda: reveal_in_file_manager(path),
            )
            self._later_btn.configure(text="Close", state="normal")
            try:
                self._skip_btn.destroy()
            except Exception:
                pass

    def _on_install(self):
        path = getattr(self, "_downloaded_path", None)
        if not path:
            return
        if not messagebox.askyesno(
            "Install update",
            "Spellbook will close and reopen to finish updating.\n\nContinue?",
            parent=self,
        ):
            return

        self._primary_btn.configure(state="disabled")
        self._later_btn.configure(state="disabled")
        self._status_label.configure(text="Installing update...")
        self.update_idletasks()

        try:
            apply_update(path)
        except UpdateCheckError as exc:
            self._status_label.configure(
                text=f"Could not install automatically: {exc}\n"
                     "The download is in your Downloads folder - run it manually."
            )
            reveal_in_file_manager(path)
            self._primary_btn.configure(
                text="Show File", state="normal",
                command=lambda: reveal_in_file_manager(path),
            )
            self._later_btn.configure(text="Close", state="normal")
            return

        # Helper is now waiting for us to exit. Quit the app.
        self._graceful_quit()

    def _graceful_quit(self):
        if self._on_restart:
            try:
                self._on_restart()
                return
            except Exception:
                pass
        # Invoke the parent window's close handler (saves data, then exits).
        try:
            top = self._parent.winfo_toplevel()
            token = top.protocol("WM_DELETE_WINDOW")
            if token:
                top.tk.call(token)
                return
            top.destroy()
        except Exception:
            import os
            os._exit(0)

    def _download_failed(self, message: str):
        self._downloading = False
        try:
            self._progress.pack_forget()
        except Exception:
            pass
        self._status_label.configure(
            text=f"Download failed: {message}\n"
                 "Use \"Release Notes\" to download it from GitHub instead."
        )
        self._primary_btn.configure(state="normal")
        try:
            self._skip_btn.configure(state="normal")
        except Exception:
            pass
        self._later_btn.configure(state="normal")
