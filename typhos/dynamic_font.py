"""
Dynamic font size helper utilities:

Dynamically set widget font size based on its current size.
"""
from __future__ import annotations

import functools
import logging

from qtpy import QtGui, QtWidgets
from qtpy.QtCore import QRectF, Qt

logger = logging.getLogger(__name__)


def get_widget_maximum_font_size(
    widget: QtWidgets.QWidget,
    text: str,
    *,
    pad_width: float = 0.0,
    pad_height: float = 0.0,
    precision: float = 0.5,
) -> float:
    """
    Get the maximum font size for the given widget.

    Parameters
    ----------
    widget : QtWidgets.QWidget
        The widget to check.
    text : str
        The text for the widget to contain.
    pad_width : float, optional
        Padding to be used to reduce the size of the contents rectangle.
    pad_height : float, optional
        Padding to be used to reduce the size of the contents rectangle.
    precision : float
        Font size precision.

    Returns
    -------
    float
    """
    font = widget.font()
    widget_contents_rect = QRectF(widget.contentsRect())
    target_width = widget_contents_rect.width() - pad_width
    target_height = widget_contents_rect.height() - pad_height

    # QRectF new_rect
    current_size = font.pointSizeF()

    if not text or target_width <= 0 or target_height <= 0:
        return current_size

    step = current_size / 2.0

    # If too small, increase step
    if step <= precision:
        step = precision * 4.0

    last_tested_size = current_size
    curent_height = 0.0
    current_width = 0.0

    # Only stop when step is small enough and new size is smaller than QWidget
    while (
        step > precision
        or (curent_height > target_height)
        or (current_width > target_width)
    ):
        # Keep last tested value
        last_tested_size = current_size

        # Test label with its font
        font.setPointSizeF(current_size)
        # Use font metrics to test
        fm = QtGui.QFontMetricsF(font)

        # Check if widget is QLabel
        if isinstance(widget, QtWidgets.QLabel):
            if widget.wordWrap():
                flags = Qt.TextFlag.TextWordWrap | widget.alignment()
            else:
                flags = widget.alignment()
            new_rect = fm.boundingRect(widget_contents_rect, flags, text)
        else:
            new_rect = fm.boundingRect(widget_contents_rect, 0, text)

        curent_height = new_rect.height()
        current_width = new_rect.width()

        # If new font size is too big, decrease it
        if (curent_height > target_height) or (current_width > target_width):
            current_size -= step
            # if step is small enough, keep it constant, so it converges to
            # biggest font size
            if step > precision:
                step /= 2.0
            # Do not allow negative size
            if current_size <= 0:
                break
        else:
            # If new font size is smaller than maximum possible size, increase
            # it
            current_size += step

    return last_tested_size


def patch_widget(
    widget: QtWidgets.QWidget,
    *,
    pad_percent: float = 0.0,
    max_size: float | None = None,
    min_size: float | None = None,
) -> None:
    """
    Patch the widget to dynamically change its font.

    Parameters
    ----------
    widget : QtWidgets.QWidget
        The widget to patch.
    pad_percent : float, optional
        The normalized padding percentage (0.0 - 1.0) to use in determining the
        maximum font size. Content margin settings determine the content
        rectangle, and this padding is applied as a percentage on top of that.
    max_size : float or None, optional
        The maximum font point size we're allowed to apply to the widget.
    min_size : float or None, optional
        The minimum font point size we're allowed to apply to the widget.
    """
    if "font-size" in widget.styleSheet():
        logger.warning(
            f"Widget named {widget.objectName()} has a fixed size from its "
            "stylesheet, and cannot be resized dynamically."
        )

    def set_font_size() -> None:
        font = widget.font()
        font_size = get_max_font_size_cached(
            widget.text(),
            widget.width(),
            widget.height(),
        )
        # 0.1 = avoid meaningless resizes
        # 0.00001 = snap to min/max
        delta = 0.1
        if max_size is not None and font_size > max_size:
            font_size = max_size
            delta = 0.00001
        if min_size is not None and font_size < min_size:
            font_size = min_size
            delta = 0.00001
        if abs(font.pointSizeF() - font_size) > delta:
            font.setPointSizeF(font_size)
            widget.setFont(font)

    # Cache and reuse results per widget
    # Low effort and not exhaustive, but reduces the usage of the big loop
    @functools.lru_cache
    def get_max_font_size_cached(text: str, width: int, height: int) -> float:
        return get_widget_maximum_font_size(
            widget,
            text,
            pad_width=width * pad_percent,
            pad_height=height * pad_percent,
        )

    def resizeEvent(event: QtGui.QResizeEvent) -> None:
        set_font_size()
        return orig_resize_event(event)

    def setText(*args, **kwargs) -> None:
        # Re-evaluate the text size when the text changes too
        rval = orig_set_text(*args, **kwargs)
        set_font_size()
        return rval

    if hasattr(widget.resizeEvent, "_patched_methods_"):
        return

    orig_resize_event = widget.resizeEvent
    orig_set_text = widget.setText

    resizeEvent._patched_methods_ = (
        widget.resizeEvent,
        widget.setText
    )
    widget.resizeEvent = resizeEvent
    widget.setText = setText
    set_font_size()


def unpatch_widget(widget: QtWidgets.QWidget) -> None:
    """
    Remove dynamic font size patch from the widget, if previously applied.

    Parameters
    ----------
    widget : QtWidgets.QWidget
        The widget to unpatch.
    """
    if not hasattr(widget.resizeEvent, "_patched_methods_"):
        return

    (
        widget.resizeEvent,
        widget.setText,
    ) = widget.resizeEvent._patched_methods_


def is_patched(widget: QtWidgets.QWidget) -> bool:
    """
    Check if widget has been patched for dynamically-resizing fonts.

    Parameters
    ----------
    widget : QtWidgets.QWidget
        The widget to check.

    Returns
    -------
    bool
        True if the widget has been patched.
    """
    return hasattr(widget.resizeEvent, "_patched_methods_")
