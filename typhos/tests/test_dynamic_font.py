from __future__ import annotations

import logging

import pytest
import pytestqt.qtbot
from pydm.widgets.label import PyDMLabel
from qtpy import QtCore, QtGui, QtWidgets

from typhos.tests import conftest

from ..dynamic_font import (is_patched, patch_style_font_size, patch_widget,
                            unpatch_style_font_size, unpatch_widget)

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "cls",
    [
        QtWidgets.QLabel,
        QtWidgets.QPushButton,
        QtWidgets.QComboBox,
        PyDMLabel,
    ]
)
def test_patching(
    request: pytest.FixtureRequest,
    cls: type[QtWidgets.QWidget],
    qtbot: pytestqt.qtbot.QtBot,
) -> None:
    widget = cls()
    if isinstance(widget, QtWidgets.QComboBox):
        widget.addItems(["test", "text"])
    else:
        widget.setText("Test\ntext")
    widget.setFixedSize(500, 500)
    qtbot.add_widget(widget)

    original_font_size = widget.font().pointSizeF()
    conftest.save_image(
        widget,
        f"{request.node.name}_{cls.__name__}_default_font_size",
    )
    print("Starting font size", original_font_size)

    old_size = widget.size()
    event = QtGui.QResizeEvent(
        QtCore.QSize(old_size.width() * 2, old_size.height() * 2),
        old_size,
    )

    assert not is_patched(widget)
    patch_widget(widget)
    assert is_patched(widget)

    # Font size case 1: widget is resized
    widget.resizeEvent(event)
    resized_font_size = widget.font().pointSizeF()
    logger.debug(f"ResizeEvent patched font size is {resized_font_size}")
    assert original_font_size != resized_font_size

    # Font size case 2: text is updated (not supported in combobox yet)
    if not isinstance(widget, QtWidgets.QComboBox):
        widget.setText(widget.text()*100)
        new_text_font_size = widget.font().pointSizeF()
        logger.debug(f"setText patched font size is {new_text_font_size}")
        assert resized_font_size != new_text_font_size

    assert is_patched(widget)
    unpatch_widget(widget)
    assert not is_patched(widget)

    conftest.save_image(
        widget,
        f"{request.node.name}_{cls.__name__}_dynamic_font_size",
    )


@pytest.mark.parametrize(
    "stylesheet",
    [
        "",
        "background: red",
        "QLabel { background: blue }",
        "QWidget { font-size: 12 pt }",
    ]
)
def test_style_patching(stylesheet: str, qtbot: pytestqt.qtbot.QtBot):
    widget = QtWidgets.QWidget()
    qtbot.add_widget(widget)
    widget.setStyleSheet(stylesheet)

    expected_text = "font-size: 16 pt"
    assert expected_text not in widget.styleSheet()
    patch_style_font_size(widget=widget, font_size=16)
    assert expected_text in widget.styleSheet()
    unpatch_style_font_size(widget=widget)
    assert expected_text not in widget.styleSheet()

    assert widget.styleSheet() == stylesheet
