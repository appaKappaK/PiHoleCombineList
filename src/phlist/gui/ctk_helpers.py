"""Thin wrappers around CustomTkinter private internals.

All private-attribute access (_parent_canvas, _scrollbar, _create_window_id,
_textbox) is isolated here.  If a CTk update changes internal names, only
this file needs adjustment.
"""

import customtkinter as ctk


def get_canvas(scrollable_frame: ctk.CTkScrollableFrame):
    """Return the underlying tk.Canvas for a CTkScrollableFrame."""
    return scrollable_frame._parent_canvas


def get_scrollbar(scrollable_frame: ctk.CTkScrollableFrame):
    """Return the scrollbar widget for a CTkScrollableFrame."""
    return scrollable_frame._scrollbar


def get_inner_window_id(scrollable_frame: ctk.CTkScrollableFrame):
    """Return the canvas window item ID for a CTkScrollableFrame's inner frame."""
    return scrollable_frame._create_window_id


def get_underlying_textbox(textbox: ctk.CTkTextbox):
    """Return the underlying tk.Text widget for a CTkTextbox."""
    return textbox._textbox


def get_label_inner(label: ctk.CTkLabel):
    """Return the underlying tk.Label for a CTkLabel (for font queries), or None."""
    return getattr(label, '_label', None) or getattr(label, '_text_label', None)
