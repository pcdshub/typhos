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

    This picks between patch_text_widget and patch_combo_widget as appropriate.

    Depending on which is chosen, different methods may be patched to ensure
    that the widget will always have the maximum size font that fits within
    the bounding box.

    Regardless of which method is chosen, the font will be dynamically
    resized for the first time before this function returns.

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
    if isinstance(widget, QtWidgets.QComboBox):
        return patch_combo_widget(
            widget=widget,
            pad_percent=pad_percent,
            max_size=max_size,
            min_size=min_size,
        )
    elif hasattr(widget, "setText") and hasattr(widget, "text"):
        return patch_text_widget(
            widget=widget,
            pad_percent=pad_percent,
            max_size=max_size,
            min_size=min_size,
        )
    else:
        raise TypeError(f"Dynamic font not supported for {widget}")


def set_font_common(
    widget: QtWidgets.QWidget,
    font_size: int,
    min_size: int,
    max_size: int,
) -> None:
    # 0.1 = avoid meaningless resizes
    # 0.00001 = snap to min/max
    delta = 0.1
    if max_size is not None and font_size > max_size:
        font_size = max_size
        delta = 0.00001
    if min_size is not None and font_size < min_size:
        font_size = min_size
        delta = 0.00001
    font = widget.font()
    if abs(font.pointSizeF() - font_size) > delta:
        font.setPointSizeF(font_size)
        # Set the font directly
        widget.setFont(font)
        # Also set the font in the stylesheet
        # In case some code resets the style
        patch_style_font_size(widget=widget, font_size=font_size)


def patch_text_widget(
    widget: QtWidgets.QLabel | QtWidgets.QLineEdit,
    *,
    pad_percent: float = 0.0,
    max_size: float | None = None,
    min_size: float | None = None,
):
    """
    Specific patching for widgets with text() and setText() methods.

    This replaces resizeEvent and setText methods with versions that will
    set the font size to the maximum fitting value when the widget is
    resized or the text is updated.

    The text is immediately resized for the first time during this function call.
    """
    def set_font_size() -> None:
        font_size = get_max_font_size_cached(
            widget.text(),
            widget.width(),
            widget.height(),
        )
        set_font_common(
            widget=widget,
            font_size=font_size,
            max_size=max_size,
            min_size=min_size,
        )

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
        widget.setText,
    )
    widget.resizeEvent = resizeEvent
    widget.setText = setText
    set_font_size()


def patch_combo_widget(
    widget: QtWidgets.QComboBox,
    *,
    pad_percent: float = 0.0,
    max_size: float | None = None,
    min_size: float | None = None,
):
    """
    Specific patching for combobox widgets.

    This replaces resizeEvent with a version that will
    set the font size to the maximum fitting value
    when the widget is resized.

    The text is immediately resized for the first time during this function call.
    """
    def set_font_size() -> None:
        combo_options = [
            widget.itemText(index) for index in range(widget.count())
        ]
        font_sizes = [
            get_max_font_size_cached(
                text,
                widget.width(),
                widget.height(),
            )
            for text in combo_options
        ]
        set_font_common(
            widget=widget,
            font_size=min(font_sizes),
            max_size=max_size,
            min_size=min_size,
        )

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

    # TODO: figure out best way to resize font when combo options change

    if hasattr(widget.resizeEvent, "_patched_methods_"):
        return

    orig_resize_event = widget.resizeEvent

    resizeEvent._patched_methods_ = (
        widget.resizeEvent,
    )
    widget.resizeEvent = resizeEvent
    set_font_size()


def unpatch_widget(widget: QtWidgets.QWidget) -> None:
    """
    Remove dynamic font size patch from the widget, if previously applied.

    Parameters
    ----------
    widget : QtWidgets.QWidget
        The widget to unpatch.
    """
    unpatch_style_font_size(widget=widget)
    if not hasattr(widget.resizeEvent, "_patched_methods_"):
        return
    if isinstance(widget, QtWidgets.QComboBox):
        return unpatch_combo_widget(widget)
    elif hasattr(widget, "setText") and hasattr(widget, "text"):
        return unpatch_text_widget(widget)
    else:
        raise TypeError("Somehow, we have a patched widget that is unpatchable.")


def unpatch_text_widget(widget: QtWidgets.QLabel | QtWidgets.QLineEdit):
    (
        widget.resizeEvent,
        widget.setText,
    ) = widget.resizeEvent._patched_methods_


def unpatch_combo_widget(widget: QtWidgets.QComboBox):
    (
        widget.resizeEvent,
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


standard_comment = "/* Auto patch from typhos.dynamic_font */"


def patch_style_font_size(widget: QtWidgets.QWidget, font_size: int) -> None:
    """
    Update a widget's stylesheet to force the font size.

    Requires the widget stylesheet to either be empty or filled with
    existing rules that have class specifiers, e.g. it's ok to have:

    QPushButton { padding: 2px; margin: 0px; background-color: red }

    But not to just have:

    padding: 2px; margin: 0px; background-color: red

    This will not be applied until next style reload, which can be
    done via unpolish and polish
    (see https://wiki.qt.io/Dynamic_Properties_and_Stylesheets)

    In this module, this is used to guard against stylesheet reloads
    undoing the dynamic font size. We will not call unpolish or polish
    ourselves, but some other code might.
    """
    starting_stylesheet = widget.styleSheet()
    if standard_comment in starting_stylesheet:
        unpatch_style_font_size(widget=widget)
    widget.setStyleSheet(
        f"{widget.styleSheet()}\n"
        f"{standard_comment}\n"
        f"{widget.__class__.__name__} {{ font-size: {font_size} pt }}"
    )


def unpatch_style_font_size(widget: QtWidgets.QWidget) -> None:
    """
    Undo the effects of patch_style_font_size.

    Assumes that the last two lines of the stylesheet are the comment
    and the rule that we added.
    """
    if standard_comment in widget.styleSheet():
        widget.setStyleSheet(
            "\n".join(widget.styleSheet().split("\n")[:-2])
        )
