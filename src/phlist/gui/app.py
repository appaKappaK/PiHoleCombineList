"""Main application window."""

import base64
import importlib.resources as _ir
import logging
import re
import tkinter as _tk

import customtkinter as ctk

from .. import __version__
from ..database import Database
from ..logger import setup_logging
from .combine_tab import CombineTab
from .library_tab import LibraryTab
from .settings_tab import SettingsTab

_log = logging.getLogger(__name__)

ctk.set_default_color_theme("blue")

# ── Splash screen colours (easy to tweak) ─────────────────────────────
_SPLASH_BG = "#1a1a2e"       # dark navy background
_SPLASH_FG = "#e0e0e0"       # light text
_SPLASH_ACCENT = "#3B8ED0"   # accent / version text
_SPLASH_MS = 1500            # auto-dismiss after this many ms


class _SplashScreen(ctk.CTkToplevel):
    """Borderless splash shown while the main window initialises."""

    def __init__(self, parent, saved_geometry: str = "") -> None:
        super().__init__(parent)
        self.overrideredirect(True)  # borderless
        self.configure(fg_color=_SPLASH_BG)
        self.attributes("-topmost", True)

        # Size + center on last known main window position
        w, h = 380, 280
        sx, sy = self._calc_center(w, h, saved_geometry)
        self.geometry(f"{w}x{h}+{sx}+{sy}")
        self.update()  # Map the window before creating images (required on Wayland)

        # Load the larger splash logo — Canvas is more reliable than Label for
        # image rendering in overrideredirect windows on Wayland.
        # Composites RGBA images against the splash background so transparency works.
        try:
            from PIL import Image, ImageTk
            logo_path = _ir.files("phlist") / "assets" / "splash_logo.png"
            pil_img = Image.open(str(logo_path)).convert("RGBA").resize((128, 128), Image.LANCZOS)
            # Strip flat background with AA-preserving gradient:
            # pixels close to the corner colour fade to transparent smoothly.
            corner = pil_img.getpixel((0, 0))[:3]
            _HARD = 12   # below this distance → fully transparent
            _SOFT = 40   # above this distance → fully opaque
            new_data = []
            for r, g, b, a in pil_img.getdata():
                dist = max(abs(r - corner[0]), abs(g - corner[1]), abs(b - corner[2]))
                if dist < _HARD:
                    new_data.append((r, g, b, 0))
                elif dist < _SOFT:
                    new_a = int((dist - _HARD) / (_SOFT - _HARD) * 255)
                    new_data.append((r, g, b, new_a))
                else:
                    new_data.append((r, g, b, a))
            pil_img.putdata(new_data)
            bg_rgb = tuple(int(_SPLASH_BG.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            bg = Image.new("RGBA", pil_img.size, bg_rgb + (255,))
            composited = Image.alpha_composite(bg, pil_img)
            self._logo = ImageTk.PhotoImage(composited.convert("RGB"))
            canvas = _tk.Canvas(self, width=128, height=128, bg=_SPLASH_BG,
                                 highlightthickness=0, bd=0)
            canvas.pack(pady=(24, 8))
            canvas.create_image(64, 64, image=self._logo)
        except Exception as exc:
            _log.debug("Splash logo not loaded: %s", exc)  # Non-fatal — splash still shows text

        ctk.CTkLabel(
            self,
            text="Block/Allow List Combiner",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=_SPLASH_FG,
            fg_color=_SPLASH_BG,
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            self,
            text=f"for Pi-hole  v{__version__}",
            font=ctk.CTkFont(size=12),
            text_color=_SPLASH_ACCENT,
            fg_color=_SPLASH_BG,
        ).pack()

        ctk.CTkLabel(
            self,
            text="Loading...",
            font=ctk.CTkFont(size=11),
            text_color="gray50",
            fg_color=_SPLASH_BG,
        ).pack(pady=(12, 0))

        # Block interaction with busy cursor
        self.configure(cursor="watch")
        self.update_idletasks()
        self.grab_set()

    @staticmethod
    def _calc_center(w, h, saved_geometry):
        """Return (x, y) to center a w×h splash over the saved main window area.

        Falls back to (0, 0) on first launch — the WM will place it.
        """
        if saved_geometry:
            m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", saved_geometry)
            if m:
                mw, mh, mx, my = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                return mx + (mw - w) // 2, my + (mh - h) // 2
        return 0, 0


class App(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        setup_logging()

        # Init DB early so we can read saved settings before creating the window
        self._db = Database()
        saved_geo = self._db.get_setting("window_geometry", "")

        ctk.set_appearance_mode("Dark")

        super().__init__()
        _log.info("App started — v%s", __version__)

        # Hide main window during init
        self.withdraw()

        self.minsize(815, 585)

        # Set window/taskbar icon — reuse splash_logo with background stripped
        self._icon = None
        try:
            from PIL import Image, ImageTk
            _icon_path = _ir.files("phlist") / "assets" / "splash_logo.png"
            _icon_img = Image.open(str(_icon_path)).convert("RGBA").resize((64, 64), Image.LANCZOS)
            _corner = _icon_img.getpixel((0, 0))[:3]
            _HARD, _SOFT = 12, 40
            _icon_img.putdata([
                (r, g, b, 0) if (d := max(abs(r-_corner[0]), abs(g-_corner[1]), abs(b-_corner[2]))) < _HARD
                else (r, g, b, int((d - _HARD) / (_SOFT - _HARD) * 255)) if d < _SOFT
                else (r, g, b, a)
                for r, g, b, a in _icon_img.getdata()
            ])
            self._icon = ImageTk.PhotoImage(_icon_img)
            self.iconphoto(True, self._icon)
        except Exception as exc:
            _log.debug("Window icon not loaded: %s", exc)  # Non-fatal — icon is cosmetic

        # Apply saved geometry while hidden — no stutter on deiconify
        self.geometry(saved_geo if saved_geo else "1000x700")

        # Show splash centered on last known main window position
        splash = _SplashScreen(self, saved_geo)
        self.update()

        # Restore persisted list type; trace fires on every subsequent change
        list_type = self._db.get_setting("list_type", "Blocklist")
        self._list_type_var = ctk.StringVar(value=list_type)
        self._list_type_var.trace_add("write", self._on_list_type_change)

        # Title reflects the loaded list type immediately
        self.title(f"Pi-hole Combined {list_type} Combiner  v{__version__}")

        self._tabs = ctk.CTkTabview(
            self,
            command=self._on_tab_change,
            segmented_button_fg_color=("gray72", "gray22"),
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_selected_hover_color=("#36719F", "#144870"),
            segmented_button_unselected_color=("gray72", "gray22"),
            segmented_button_unselected_hover_color=("gray64", "gray28"),
            text_color=("gray10", "gray90"),
        )
        self._tabs.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self._tabs.add("Combine")
        self._tabs.add("Library")
        self._tabs.add("Settings")

        self._combine_tab = CombineTab(
            self._tabs.tab("Combine"),
            self._db,
            switch_to_library_cb=lambda: self._tabs.set("Library"),
            list_type_var=self._list_type_var,
        )
        self._combine_tab.pack(fill="both", expand=True)

        self._library_tab = LibraryTab(
            self._tabs.tab("Library"),
            self._db,
            get_combine_tab_cb=lambda: self._combine_tab,
            switch_to_combine_cb=lambda: self._tabs.set("Combine"),
            list_type_var=self._list_type_var,
        )
        self._library_tab.pack(fill="both", expand=True)

        self._settings_tab = SettingsTab(
            self._tabs.tab("Settings"),
            db=self._db,
            refresh_library_cb=lambda: self._library_tab.refresh(),
            refresh_push_btn_cb=lambda: self._combine_tab.refresh_push_btn_state(),
            notify_server_reachable_cb=lambda ok: (
                self._combine_tab.set_server_reachable(ok),
                self._library_tab.set_server_reachable(ok),
            ),
            refresh_credits_cb=lambda: self._library_tab.refresh_all_credits(),
        )
        self._settings_tab.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Dismiss splash and reveal main window
        def _dismiss_splash():
            splash.grab_release()
            splash.destroy()
            self.deiconify()

        self.after(_SPLASH_MS, _dismiss_splash)

    def _on_list_type_change(self, *_) -> None:
        list_type = self._list_type_var.get()
        self.title(f"Pi-hole Combined {list_type} Combiner  v{__version__}")
        self._db.set_setting("list_type", list_type)

    def _on_tab_change(self) -> None:
        tab = self._tabs.get()
        if tab == "Library":
            self._library_tab.refresh()
        elif tab == "Combine":
            self._combine_tab.after(50, self._combine_tab._refit_all_source_labels)
        elif tab == "Settings":
            self._settings_tab._refresh_stats()

    def _on_close(self) -> None:
        _log.info("App closed")
        self._db.set_setting("window_geometry", self.geometry())
        self._db.close()
        self.destroy()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
