from __future__ import annotations

import pytest
import pytestqt.qtbot
from qtpy import QtCore, QtGui, QtWidgets

from typhos.tests import conftest

from ..dynamic_font import is_patched, patch_widget, unpatch_widget


@pytest.mark.parametrize(
    "cls",
    [
        QtWidgets.QLabel,
        QtWidgets.QPushButton,
    ]
)
def test_patching(
    request: pytest.FixtureRequest,
    cls: type[QtWidgets.QWidget],
    qtbot: pytestqt.qtbot.QtBot,
) -> None:
    widget = cls()
    widget.setText("Test\ntext")
    widget.setFixedSize(500, 500)
    qtbot.add_widget(widget)

    original_font_size = widget.font().pointSizeF()
    conftest.save_image(
        widget,
        f"{request.node.name}_{cls.__name__}_default_font_size",
    )
    print("Starting font size", original_font_size)

    event = QtGui.QPaintEvent(QtCore.QRect(0, 0, widget.width(), widget.height()))

    assert not is_patched(widget)
    patch_widget(widget)
    assert is_patched(widget)

    widget.paintEvent(event)
    new_font_size = widget.font().pointSizeF()
    print("Patched font size", new_font_size)
    assert original_font_size != new_font_size

    assert is_patched(widget)
    unpatch_widget(widget)
    assert not is_patched(widget)

    conftest.save_image(
        widget,
        f"{request.node.name}_{cls.__name__}_dynamic_font_size",
    )
