"""
Dynamic font size helper utilities:

Dynamically set widget font size based on its current size.
"""

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QRectF, Qt


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
    """
    def resizeEvent(event: QtGui.QResizeEvent) -> None:
        font = widget.font()
        font_size = get_widget_maximum_font_size(
            widget, widget.text(),
            pad_width=widget.width() * pad_percent,
            pad_height=widget.height() * pad_percent,
        )
        if abs(font.pointSizeF() - font_size) > 0.1:
            font.setPointSizeF(font_size)
            widget.setFont(font)
        return orig_resize_event(event)

    def minimumSizeHint() -> QtCore.QSize:
        # Do not give any size hint as it it changes during resizeEvent
        return QtWidgets.QWidget.minimumSizeHint(widget)

    def sizeHint() -> QtCore.QSize:
        # Do not give any size hint as it it changes during resizeEvent
        return QtWidgets.QWidget.sizeHint(widget)

    if hasattr(widget.resizeEvent, "_patched_methods_"):
        return

    orig_resize_event = widget.resizeEvent

    resizeEvent._patched_methods_ = (
        widget.resizeEvent,
        widget.sizeHint,
        widget.minimumSizeHint,
    )
    widget.resizeEvent = resizeEvent
    widget.sizeHint = sizeHint
    widget.minimumSizeHint = minimumSizeHint


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
        widget.sizeHint,
        widget.minimumSizeHint,
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
