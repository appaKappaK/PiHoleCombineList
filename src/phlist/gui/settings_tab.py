"""Settings tab: two-column card layout with appearance, stats, log, and more."""

import logging
import shutil
import sqlite3
import subprocess
import threading
from collections import deque
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk

_log = logging.getLogger(__name__)

_POLL_INTERVAL_MS = 60_000   # silent re-check interval after first manual test

from ..database import Database, _DATA_DIR
from ..remote import check_connection as _check_connection
from .ctk_helpers import get_canvas, get_scrollbar
from .tooltip import Tooltip


def _format_bytes(n: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_count(n: int) -> str:
    """Compact domain count: 999 → '999', 1200 → '1.2k', 45500000 → '45.5m'."""
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k"
    return f"{n / 1_000_000:.1f}m"


def _card(parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
    """Create a labelled card frame with header and optional subtitle inside."""
    card = ctk.CTkFrame(parent, border_width=1, border_color=("gray75", "gray30"))
    card.pack(fill="x", padx=12, pady=(0, 10))
    ctk.CTkLabel(
        card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
    ).pack(anchor="w", padx=12, pady=(12, 0))
    if subtitle:
        ctk.CTkLabel(
            card, text=subtitle, font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
        ).pack(anchor="w", padx=12, pady=(2, 0))
    return card


class SettingsTab(ctk.CTkFrame):
    """The Settings tab: server port, appearance, stats, log, and more."""

    def __init__(self, parent,
                 db: Database,
                 refresh_library_cb: Optional[Callable[[], None]] = None,
                 refresh_push_btn_cb: Optional[Callable[[], None]] = None,
                 notify_server_reachable_cb: Optional[Callable[[bool], None]] = None,
                 refresh_credits_cb: Optional[Callable[[], None]] = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self._db = db
        self._refresh_library_cb = refresh_library_cb
        self._refresh_push_btn_cb = refresh_push_btn_cb
        self._notify_server_reachable_cb = notify_server_reachable_cb
        self._refresh_credits_cb = refresh_credits_cb
        self._build_ui()

    def _build_ui(self) -> None:
        # Scrollable wrapper so nothing clips on small windows
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        cols = ctk.CTkFrame(scroll, fg_color="transparent")
        cols.pack(fill="x")
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        # ── Left column ────────────────────────────────────────────
        left = ctk.CTkFrame(cols, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # ── REMOTE SERVER ──────────────────────────────────────────
        card = _card(left, "REMOTE SERVER")
        fields = ctk.CTkFrame(card, fg_color="transparent")
        fields.pack(fill="x", padx=12, pady=(10, 0))
        fields.columnconfigure(1, weight=1)

        ctk.CTkLabel(fields, text="Server URL:", width=90, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6))
        self._remote_url_entry = ctk.CTkEntry(fields, placeholder_text="http://device.ts.net:8765")
        saved_url = self._db.get_setting("remote_server_url", "")
        if saved_url:
            self._remote_url_entry.insert(0, saved_url)
        self._remote_url_entry.grid(row=0, column=1, sticky="ew")
        Tooltip(self._remote_url_entry, "Base URL of your phlist-server (LAN IP or Tailscale hostname).")

        ctk.CTkLabel(fields, text="API key:", width=90, anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 6))
        self._remote_key_entry = ctk.CTkEntry(fields, show="*")
        saved_key = self._db.get_setting("remote_server_key", "")
        if saved_key:
            self._remote_key_entry.insert(0, saved_key)
        self._remote_key_entry.grid(row=1, column=1, sticky="ew")
        self._remote_key_entry.bind("<Control-a>", lambda _: (
            self._remote_key_entry.select_range(0, "end"),
            self._remote_key_entry.icursor("end"),
            "break"
        )[-1])
        Tooltip(self._remote_key_entry, "Bearer token the server requires for PUT requests.")

        ctk.CTkLabel(fields, text="Push timeout (s):", width=90, anchor="w").grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=(6, 0))
        self._push_timeout_entry = ctk.CTkEntry(fields, width=80)
        self._push_timeout_entry.insert(0, self._db.get_setting("push_timeout", "300"))
        self._push_timeout_entry.grid(row=2, column=1, sticky="w")
        Tooltip(self._push_timeout_entry,
                "Seconds before a push to phlist-server times out. "
                "Increase for slow connections or very large lists.")

        action_row = ctk.CTkFrame(card, fg_color="transparent")
        action_row.pack(fill="x", padx=12, pady=(8, 12))
        self._test_conn_btn = ctk.CTkButton(
            action_row, text="Test Connection", width=130,
            fg_color=("gray60", "gray40"), hover_color=["#36719F", "#144870"],
            command=self._test_remote_connection,
        )
        self._test_conn_btn.pack(side="left", padx=(0, 8))
        self._test_conn_tooltip = Tooltip(self._test_conn_btn, "Test your connection to the configured server.")
        self._remote_conn_status = ctk.CTkLabel(action_row, text="", font=ctk.CTkFont(size=11),
                                                 text_color=("gray40", "gray60"))
        self._remote_conn_status.pack(side="left")
        self._save_remote_btn = ctk.CTkButton(action_row, text="Save", width=70, command=self._save_remote_settings)
        self._save_remote_btn.pack(side="right")
        self._remote_test_status = ctk.CTkLabel(action_row, text="", font=ctk.CTkFont(size=11),
                                                 text_color=("gray40", "gray60"))
        self._remote_test_status.pack(side="right", padx=(0, 8))


        # ── SOURCES ────────────────────────────────────────────────
        card = _card(left, "SOURCES")
        src_fields = ctk.CTkFrame(card, fg_color="transparent")
        src_fields.pack(fill="x", padx=12, pady=(10, 0))

        ctk.CTkLabel(src_fields, text="Fetch timeout (s):", width=140, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6))
        self._fetch_timeout_entry = ctk.CTkEntry(src_fields, width=70)
        self._fetch_timeout_entry.insert(0, self._db.get_setting("fetch_timeout", "30"))
        self._fetch_timeout_entry.grid(row=0, column=1, sticky="w")
        Tooltip(self._fetch_timeout_entry, "Seconds to wait for each source URL before giving up.")

        ctk.CTkLabel(src_fields, text="Max source size (MB):", width=140, anchor="w").grid(
            row=1, column=0, sticky="w", padx=(0, 6))
        self._max_fetch_mb_entry = ctk.CTkEntry(src_fields, width=70)
        self._max_fetch_mb_entry.insert(0, self._db.get_setting("max_fetch_mb", "50"))
        self._max_fetch_mb_entry.grid(row=1, column=1, sticky="w")
        Tooltip(self._max_fetch_mb_entry,
                "Maximum size (MB) accepted from a single source URL. "
                "Sources larger than this are skipped during combine.")

        src_action = ctk.CTkFrame(card, fg_color="transparent")
        src_action.pack(fill="x", padx=12, pady=(8, 12))
        self._src_status = ctk.CTkLabel(src_action, text="", font=ctk.CTkFont(size=11),
                                        text_color=("gray40", "gray60"))
        self._src_status.pack(side="left")
        ctk.CTkButton(src_action, text="Apply", width=70,
                      command=self._apply_source_settings).pack(side="right")

        # ── Right column ───────────────────────────────────────────
        right = ctk.CTkFrame(cols, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # ── LIBRARY STATS ──────────────────────────────────────────
        card = _card(right, "LIBRARY")
        self._stats_labels: dict[str, ctk.CTkLabel] = {}
        stats_row = ctk.CTkFrame(card, fg_color="transparent")
        stats_row.pack(fill="x", padx=12, pady=(6, 4))
        for key in ("domains", "db_size"):
            lbl = ctk.CTkLabel(stats_row, text="", anchor="w")
            lbl.pack(side="left", padx=(0, 20))
            self._stats_labels[key] = lbl
        self._refresh_stats()

        # ── DESKTOP INTEGRATION ────────────────────────────────────
        card = _card(right, "DESKTOP")
        desktop_row = ctk.CTkFrame(card, fg_color="transparent")
        desktop_row.pack(fill="x", padx=12, pady=10)
        _desktop_file = Path.home() / ".local/share/applications/phlist.desktop"
        _desktop_label = "Reinstall Shortcut" if _desktop_file.is_file() else "Install Desktop Shortcut"
        self._desktop_btn = ctk.CTkButton(
            desktop_row, text=_desktop_label, width=190,
            command=self._install_desktop,
        )
        self._desktop_btn.pack(side="left", padx=(0, 8))
        Tooltip(self._desktop_btn, "Create a .desktop launcher entry so the app appears in your GNOME/KDE app menu.")

        # ── DATA ───────────────────────────────────────────────────
        card = _card(right, "DATA")
        data_row = ctk.CTkFrame(card, fg_color="transparent")
        data_row.pack(fill="x", padx=12, pady=10)
        self._export_db_btn = ctk.CTkButton(data_row, text="Export DB", width=90, command=self._export_db)
        self._export_db_btn.pack(side="left", padx=(0, 8))
        Tooltip(self._export_db_btn, "Save a backup copy of your entire library database (phlist.db).")
        import_btn = ctk.CTkButton(data_row, text="Import DB", width=90, command=self._import_db)
        import_btn.pack(side="left", padx=(0, 8))
        Tooltip(import_btn, "Restore the library from a previously exported backup. Replaces all current data.")
        folder_btn = ctk.CTkButton(data_row, text="Open Folder", width=100, command=self._open_data_folder)
        folder_btn.pack(side="left")
        Tooltip(folder_btn, f"Open {_DATA_DIR} in the file manager.")

        data_row2 = ctk.CTkFrame(card, fg_color="transparent")
        data_row2.pack(fill="x", padx=12, pady=(0, 10))
        reset_lib_btn = ctk.CTkButton(data_row2, text="Reset Library", width=110,
                                      fg_color=["#C0392B", "#922B21"],
                                      hover_color=["#A93226", "#7B241C"],
                                      command=self._reset_db)
        reset_lib_btn.pack(side="left", padx=(0, 8))
        Tooltip(reset_lib_btn, "Delete all lists and folders. Settings (server URL, API key, etc.) are kept.")
        reset_cfg_btn = ctk.CTkButton(data_row2, text="Reset Config", width=110,
                                      fg_color=["#C0392B", "#922B21"],
                                      hover_color=["#A93226", "#7B241C"],
                                      command=self._reset_config)
        reset_cfg_btn.pack(side="left")
        Tooltip(reset_cfg_btn, "Clear all settings (server URL, API key, preferences). Library lists are kept.")
        self._refresh_credits_btn = ctk.CTkButton(
            data_row2, text="Refresh Credits", width=120,
            fg_color=("gray60", "gray40"), hover_color=["#36719F", "#144870"],
            command=self._refresh_credits,
        )
        self._refresh_credits_btn.pack(side="left", padx=(8, 0))
        Tooltip(self._refresh_credits_btn,
                "Legacy function — rarely needed.\n"
                "Re-extracts author credit headers from source URLs for library lists that are missing them.\n"
                "Only useful if you have older lists saved before credits were tracked automatically.")

        # ── LOG VIEWER ─────────────────────────────────────────────
        card = _card(scroll, "LOG")
        self._log_box = ctk.CTkTextbox(card, height=140, wrap="word", state="disabled",
                                        font=ctk.CTkFont(family="Courier New", size=11),
                                        text_color=("gray10", "gray90"))
        self._log_box.pack(fill="x", padx=12, pady=(8, 6))
        log_btn_row = ctk.CTkFrame(card, fg_color="transparent")
        log_btn_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(log_btn_row, text="Refresh", width=80, command=self._refresh_log).pack(side="left", padx=(0, 8))
        ctk.CTkButton(log_btn_row, text="Open Log File", width=110, command=self._open_log).pack(side="left")
        self._refresh_log()


        # Auto-hide scrollbar when content fits
        def _update_scroll_vis(canvas=get_canvas(scroll), sb=get_scrollbar(scroll)):
            bbox = canvas.bbox("all")
            if bbox and (bbox[3] - bbox[1]) > canvas.winfo_height():
                sb.grid()
            else:
                sb.grid_remove()
        get_canvas(scroll).bind("<Configure>", lambda _: self.after(0, _update_scroll_vis))

        self._polling_active: bool = False
        self._poll_generation: int = 0

    # ── Actions ─────────────────────────────────────────────────────

    def _install_desktop(self) -> None:
        from .._install_desktop import install as _install
        ok, msg = _install()
        if ok:
            _log.info("Desktop shortcut installed")
            self._desktop_btn.configure(state="disabled", text="Installed")
            self.after(2000, lambda: self._desktop_btn.configure(state="normal", text="Reinstall Shortcut"))
        else:
            _log.warning("Desktop shortcut install failed: %s", msg)
            messagebox.showerror("Install failed", msg)

    def _refresh_stats(self) -> None:
        stats = self._db.get_library_stats()
        self._stats_labels["domains"].configure(text=f"Domains: {_fmt_count(stats['total_domains'])}")
        self._stats_labels["db_size"].configure(text=f"DB: {_format_bytes(stats['db_bytes'])}")

    def _refresh_log(self) -> None:
        log_path = _DATA_DIR / "phlist.log"
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=15)
            # Newest entry first, separator between each for readability
            text = "\n─────────────────────────────────\n".join(
                l.rstrip("\n") for l in reversed(lines)
            )
        except FileNotFoundError:
            text = "(no log file found)"
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.insert("1.0", text)
        self._log_box.configure(state="disabled")

    def _open_log(self) -> None:
        log_path = _DATA_DIR / "phlist.log"
        if not log_path.exists():
            messagebox.showinfo("No log", "Log file does not exist yet.")
            return
        try:
            subprocess.Popen(["xdg-open", str(log_path)])
        except Exception as exc:
            messagebox.showerror("Could not open", f"Failed to open log file:\n{exc}")

    def _export_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export Library Database",
            initialfile="phlist-backup.db",
            defaultextension=".db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            shutil.copy2(self._db._path, path)
            _log.info("DB exported to: %s", path)
            self._export_db_btn.configure(state="disabled", text="Exported")
            self.after(2000, lambda: self._export_db_btn.configure(state="normal", text="Export DB"))
        except Exception as exc:
            _log.error("DB export failed: %s", exc)
            messagebox.showerror("Export failed", f"Could not export database:\n{exc}")

    def _import_db(self) -> None:
        if not messagebox.askyesno(
            "Import Library",
            "This will REPLACE your entire library with the backup.\n"
            "All current lists and folders will be lost.\n\nContinue?",
            icon="warning",
        ):
            return
        path = filedialog.askopenfilename(
            title="Import Library Database",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            src = sqlite3.connect(path)
            src.backup(self._db._conn)
            src.close()
        except Exception as exc:
            _log.error("DB import failed: %s", exc)
            messagebox.showerror("Import failed", f"Could not import database:\n{exc}")
            return
        _log.info("DB imported from: %s", path)
        if self._refresh_library_cb:
            self._refresh_library_cb()
        messagebox.showinfo("Imported", "Library imported successfully.")

    def _reset_db(self) -> None:
        if not messagebox.askyesno(
            "Reset Library",
            "This will permanently delete ALL lists and folders.\n"
            "Your settings (server URL, API key, etc.) will be kept.\n\n"
            "This cannot be undone. Continue?",
            icon="warning",
        ):
            return
        try:
            self._db.reset_library()
        except Exception as exc:
            _log.error("DB reset failed: %s", exc)
            messagebox.showerror("Reset failed", f"Could not reset library:\n{exc}")
            return
        _log.info("Library reset by user")
        if self._refresh_library_cb:
            self._refresh_library_cb()
        self._refresh_stats()

    def _reset_config(self) -> None:
        if not messagebox.askyesno(
            "Reset Config",
            "This will clear all settings — server URL, API key, and all preferences.\n"
            "Your library lists and folders will not be affected.\n\n"
            "This cannot be undone. Continue?",
            icon="warning",
        ):
            return
        try:
            self._db.reset_settings()
        except Exception as exc:
            _log.error("Config reset failed: %s", exc)
            messagebox.showerror("Reset failed", f"Could not reset config:\n{exc}")
            return
        _log.info("Config reset by user")
        self._polling_active = False
        self._poll_generation += 1
        # Clear the visible fields
        self._remote_url_entry.delete(0, "end")
        self._remote_key_entry.delete(0, "end")
        if self._notify_server_reachable_cb:
            self._notify_server_reachable_cb(False)
        if self._refresh_push_btn_cb:
            self._refresh_push_btn_cb()

    def _refresh_credits(self) -> None:
        if self._refresh_credits_cb:
            self._refresh_credits_cb()
            self._refresh_credits_btn.configure(state="disabled", text="Done")
            self.after(2000, lambda: self._refresh_credits_btn.configure(state="normal", text="Refresh Credits"))
        else:
            messagebox.showinfo("Refresh Credits", "Library not available.")

    def _apply_source_settings(self) -> None:
        for key, entry in [("fetch_timeout", self._fetch_timeout_entry),
                           ("max_fetch_mb", self._max_fetch_mb_entry)]:
            val = entry.get().strip()
            if val.isdigit() and int(val) > 0:
                self._db.set_setting(key, val)
        self._src_status.configure(text="Saved")
        self.after(2000, lambda: self._src_status.configure(text=""))

    def _open_data_folder(self) -> None:
        try:
            subprocess.Popen(["xdg-open", str(_DATA_DIR)])
        except Exception as exc:
            messagebox.showerror("Could not open", f"Failed to open data folder:\n{exc}")

    def _save_remote_settings(self) -> None:
        url = self._remote_url_entry.get().strip().rstrip("/")
        key = self._remote_key_entry.get().strip()
        self._db.set_setting("remote_server_url", url)
        self._db.set_setting("remote_server_key", key)
        val = self._push_timeout_entry.get().strip()
        if val.isdigit() and int(val) > 0:
            self._db.set_setting("push_timeout", val)
        _log.info("Remote settings saved: url=%s", url or "(cleared)")
        self._save_remote_btn.configure(state="disabled", text="Saved")
        self.after(2000, lambda: self._save_remote_btn.configure(state="normal", text="Save"))
        if url.startswith("http://"):
            self._remote_conn_status.configure(
                text="Note: API key sent in plaintext over http",
                text_color=("orange", "orange"),
            )
        # Reset test button to untested state since credentials changed
        self._polling_active = False
        self._poll_generation += 1
        self._test_conn_btn.configure(state="normal", text="Test Connection",
                                      fg_color=("gray60", "gray40"),
                                      hover_color=["#36719F", "#144870"])
        self._test_conn_tooltip.update("Test your connection to the configured server.")
        self._remote_conn_status.configure(text="")
        if self._notify_server_reachable_cb:
            self._notify_server_reachable_cb(False)
        if self._refresh_push_btn_cb:
            self._refresh_push_btn_cb()

    def auto_test_connection(self) -> None:
        """Re-run the connection test silently if a server URL is configured."""
        if self._remote_url_entry.get().strip():
            self._test_remote_connection()

    def _test_remote_connection(self) -> None:
        url = self._remote_url_entry.get().strip().rstrip("/")
        key = self._remote_key_entry.get().strip()
        if not url:
            self._remote_conn_status.configure(text="Enter a server URL first.",
                                                text_color=("#C0392B", "#E74C3C"))
            return

        # Stop any active polling cycle before running a manual test
        self._polling_active = False
        self._poll_generation += 1
        gen = self._poll_generation

        # Greyed-out "testing" state
        self._test_conn_btn.configure(state="disabled", text="Waiting...",
                                      fg_color=("gray60", "gray40"))
        self._remote_conn_status.configure(text="", text_color=("gray40", "gray60"))
        self.update_idletasks()

        def _worker():
            ok, msg = _check_connection(url, key)

            def _done():
                if gen != self._poll_generation:
                    return
                _log.info("Test connection: %s", "OK" if ok else f"failed — {msg}")
                if ok:
                    self._test_conn_btn.configure(
                        state="normal", text="Connected",
                        fg_color=("#27AE60", "#1E8449"),
                        hover_color=("#219A52", "#196F3D"),
                    )
                    self._test_conn_tooltip.update(f"Connected to {url}\nAPI key accepted.")
                else:
                    self._test_conn_btn.configure(
                        state="normal", text="Failed",
                        fg_color=("#C0392B", "#922B21"),
                        hover_color=("#A93226", "#7B241C"),
                    )
                    self._test_conn_tooltip.update(f"Failed: {msg}")
                self._remote_conn_status.configure(
                    text="" if ok else msg,
                    text_color=("#C0392B", "#E74C3C"),
                )
                if self._notify_server_reachable_cb:
                    self._notify_server_reachable_cb(ok)
                # Begin session polling now that user has manually tested once
                self._polling_active = True
                self.after(_POLL_INTERVAL_MS, self._poll_connection)

            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _poll_connection(self) -> None:
        """Silent background re-check; updates button + reachable state without user input."""
        if not self._polling_active:
            return
        url = self._remote_url_entry.get().strip().rstrip("/")
        key = self._remote_key_entry.get().strip()
        if not url:
            self._polling_active = False
            return
        gen = self._poll_generation

        def _worker():
            ok, msg = _check_connection(url, key)

            def _done():
                if gen != self._poll_generation:
                    return
                if ok:
                    self._test_conn_btn.configure(
                        state="normal", text="Connected",
                        fg_color=("#27AE60", "#1E8449"),
                        hover_color=("#219A52", "#196F3D"),
                    )
                    self._test_conn_tooltip.update(f"Connected to {url}\nAPI key accepted.")
                    self._remote_conn_status.configure(text="")
                else:
                    self._test_conn_btn.configure(
                        state="normal", text="Failed",
                        fg_color=("#C0392B", "#922B21"),
                        hover_color=("#A93226", "#7B241C"),
                    )
                    self._test_conn_tooltip.update(f"Failed: {msg}")
                    self._remote_conn_status.configure(
                        text=msg, text_color=("#C0392B", "#E74C3C"),
                    )
                if self._notify_server_reachable_cb:
                    self._notify_server_reachable_cb(ok)
                if self._polling_active:
                    self.after(_POLL_INTERVAL_MS, self._poll_connection)

            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

