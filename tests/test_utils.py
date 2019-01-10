import os

from qtpy.QtCore import QRect
from qtpy.QtGui import QPaintEvent
from qtpy.QtWidgets import QWidget, QMessageBox
from ophyd import Device, Component as Cpt, Kind
import pytest

import typhon
from typhon.utils import (use_stylesheet, clean_name, grab_hints, grab_kind,
                          TyphonBase, raise_to_operator)

class NestedDevice(Device):
    phi = Cpt(Device)


class LayeredDevice(Device):
    radial = Cpt(NestedDevice)


def test_clean_name():
    device = LayeredDevice(name='test')
    assert clean_name(device.radial, strip_parent=False) == 'test radial'
    assert clean_name(device.radial, strip_parent=True) == 'radial'
    assert clean_name(device.radial.phi,
                      strip_parent=False) == 'test radial phi'
    assert clean_name(device.radial.phi, strip_parent=True) == 'phi'
    assert clean_name(device.radial.phi, strip_parent=device) == 'radial phi'


def test_grab_hints(motor):
    hint_names = [cpt.name for cpt in grab_hints(motor)]
    assert all([field in hint_names
                for field in motor.hints['fields']])


def test_stylesheet(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    use_stylesheet(widget=widget)
    use_stylesheet(widget=widget, dark=True)


def test_grab_kind(motor):
    assert len(grab_kind(motor, 'hinted')) == len(motor.hints['fields'])
    assert len(grab_kind(motor, 'normal')) == len(motor.read_attrs)
    assert len(grab_kind(motor, Kind.config)) == len(motor.configuration_attrs)
    omitted = (len(motor.component_names)
               - len(motor.read_attrs)
               - len(motor.configuration_attrs))
    assert len(grab_kind(motor, 'omitted')) == omitted


conda_prefix = os.getenv("CONDA_PREFIX")


@pytest.mark.skipif(not (conda_prefix and
                         typhon.__file__.startswith(conda_prefix)),
                    reason='Package not installed via CONDA')
def test_qtdesigner_env():
    assert 'etc/typhon' in os.getenv('PYQTDESIGNERPATH', '')


def test_typhonbase_repaint_smoke(qtbot):
    tp = TyphonBase()
    qtbot.addWidget(tp)
    pe = QPaintEvent(QRect(1, 2, 3, 4))
    tp.paintEvent(pe)


def test_raise_to_operator_msg(monkeypatch, qtbot):

    monkeypatch.setattr(QMessageBox, 'exec_', lambda x: 1)
    exc_dialog = None
    try:
        1/0
    except ZeroDivisionError as exc:
        exc_dialog = raise_to_operator(exc)

    qtbot.addWidget(exc_dialog)
    assert exc_dialog is not None
    assert 'ZeroDivisionError' in exc_dialog.text()
