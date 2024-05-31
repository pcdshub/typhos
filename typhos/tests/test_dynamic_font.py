from __future__ import annotations

import pytest
import pytestqt.qtbot
from qtpy import QtCore, QtGui, QtWidgets

from typhos.tests import conftest

from ..dynamic_font import (get_widget_maximum_font_size, is_patched,
                            patch_widget, unpatch_widget)


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

    old_size = widget.size()
    event = QtGui.QResizeEvent(
        QtCore.QSize(old_size.width() * 2, old_size.height() * 2),
        old_size,
    )

    assert not is_patched(widget)
    patch_widget(widget)
    assert is_patched(widget)

    widget.resizeEvent(event)
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


def test_wide_label(
    qapp: QtWidgets.QApplication,
    qtbot: pytestqt.qtbot.QtBot,
):
    """
    Replicate the wide label text in RIXS that clips
    """
    widget = QtWidgets.QLabel()
    qtbot.add_widget(widget)
    widget.setText("143252.468 urad")
    font = widget.font()
    font.setPointSizeF(16.0)
    widget.setFont(font)
    assert widget.font().pointSizeF() == 16.0

    patch_widget(widget)
    widget.setFixedSize(162.36, 34.65)
    for _ in range(3):
        qapp.processEvents()
    assert widget.font().pointSizeF() == get_widget_maximum_font_size(widget, widget.text())
