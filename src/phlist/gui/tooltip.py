"""Lightweight hover tooltip for customtkinter widgets."""

import tkinter as tk


class Tooltip:
    """Show a tooltip when the mouse hovers over a widget."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 400) -> None:
        self._widget = widget
        self._text = text
        self._delay = delay
        self._tip_window: tk.Toplevel | None = None
        self._after_id: str | None = None
        try:
            widget.bind("<Enter>", self._schedule, add="+")
            widget.bind("<Leave>", self._cancel, add="+")
            widget.bind("<ButtonPress>", self._cancel, add="+")
        except (NotImplementedError, tk.TclError):
            pass  # some CTk widgets (e.g. CTkSegmentedButton) don't support bind

    def _schedule(self, _event: tk.Event) -> None:
        self._cancel()
        self._after_id = self._widget.after(self._delay, self._show)

    def _cancel(self, _event: tk.Event | None = None) -> None:
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self) -> None:
        if self._tip_window:
            return
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self._text, justify="left",
            background="#333333", foreground="#eeeeee",
            relief="solid", borderwidth=1,
            font=("TkDefaultFont", 10),
            padx=6, pady=4, wraplength=300,
        )
        label.pack()
        self._tip_window = tw

    def update(self, text: str) -> None:
        """Change the tooltip text; hides any currently visible tip."""
        self._text = text
        self._hide()

    def _hide(self) -> None:
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None
