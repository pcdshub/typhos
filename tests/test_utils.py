import os
import pathlib
import subprocess
import tempfile

from qtpy.QtCore import QRect
from qtpy.QtGui import QPaintEvent
from qtpy.QtWidgets import QWidget, QMessageBox
from ophyd import Device, Component as Cpt, Kind
import pytest
import simplejson as json

import typhon
from typhon.utils import (use_stylesheet, clean_name, grab_kind,
                          TyphonBase, raise_to_operator, load_suite,
                          saved_template)

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


# Check to see that we were installed via CONDA. If not, we can not expect the
# PYQTDESIGNERPATH variable to have been configured correctly
try:
    channel = json.loads(subprocess.check_output(['conda',
                                                  'list',
                                                  'typhon',
                                                  '--json']))[0]['channel']
    is_conda_installed = channel != 'pypi'
except Exception:
    is_conda_installed = False


@pytest.mark.skipif(not is_conda_installed,
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


def test_load_suite(qtbot, happi_cfg):
    # Setup new saved file
    module = saved_template.format(devices=['test_motor'])
    module_file = str(pathlib.Path(tempfile.gettempdir()) / 'my_suite.py')
    with open(module_file, 'w+') as handle:
        handle.write(module)

    suite = load_suite(module_file, happi_cfg)
    qtbot.addWidget(suite)
    assert isinstance(suite, typhon.TyphonSuite)
    assert len(suite.devices) == 1
    assert suite.devices[0].name == 'test_motor'
    os.remove(module_file)


def test_load_suite_with_bad_py_file():
    with pytest.raises(AttributeError):
        suite = load_suite(typhon.utils.__file__)
