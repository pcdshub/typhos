from __future__ import annotations

import pytest
import pytestqt.qtbot
from ophyd.sim import SynAxis
from pydm.widgets.label import PyDMLabel
from qtpy import QtCore, QtGui, QtWidgets

from typhos.positioner import TyphosPositionerRowWidget
from typhos.tests import conftest

from ..dynamic_font import (get_widget_maximum_font_size, is_patched,
                            patch_widget, unpatch_widget)


@pytest.mark.parametrize(
    "cls",
    [
        QtWidgets.QLabel,
        QtWidgets.QPushButton,
        PyDMLabel,
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
    widget.setFixedSize(162, 34)
    event = QtGui.QResizeEvent(
        QtCore.QSize(162, 34),
        widget.size(),
    )
    widget.resizeEvent(event)
    assert widget.font().pointSizeF() == get_widget_maximum_font_size(widget, widget.text())


def test_positioner_label(
    qapp: QtWidgets.QApplication,
    qtbot: pytestqt.qtbot.QtBot,
    motor: SynAxis,
):
    """
    Literally try the positioner label that causes issues
    """
    pos = 143252
    units = "urad"

    widget = TyphosPositionerRowWidget()
    qtbot.add_widget(widget)
    widget.readback_attribute = "readback"
    widget.add_device(motor)
    qapp.processEvents()

    motor.readback._metadata["units"] = units
    motor.readback._metadata["precision"] = 3
    motor.readback._run_metadata_callbacks()
    motor.velocity.put(10000000)
    motor.set(pos).wait(timeout=1.0)
    qapp.processEvents()

    expected_text = f"{pos:.3f} {units}"
    expected_size = get_widget_maximum_font_size(widget.user_readback, expected_text)
    actual_text = widget.user_readback.text()
    actual_size = widget.user_readback.font().pointSizeF()
    assert expected_text == actual_text
    assert expected_size == actual_size
