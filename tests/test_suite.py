import io
import os
import tempfile
from pathlib import Path

import pytest
from pyqtgraph.parametertree import ParameterTree
from pyqtgraph.parametertree import parameterTypes as ptypes
from qtpy import QtWidgets

from typhos.display import TyphosDeviceDisplay
from typhos.suite import DeviceParameter, TyphosSuite
from typhos.utils import save_suite

from .conftest import show_widget


@pytest.fixture(scope='function')
def suite(qtbot, device):
    suite = TyphosSuite.from_device(device, tools=None)
    qtbot.addWidget(suite)
    return suite


@show_widget
def test_suite_with_child_devices(suite, device):
    assert device in suite.devices
    device_group = suite.top_level_groups['Devices']
    assert len(device_group.childs) == 1
    child_displays = device_group.childs[0].childs
    assert len(child_displays) == len(device._sub_devices)
    return suite


def test_suite_without_children(device, qtbot):
    childless = TyphosSuite.from_device(device, children=False)
    qtbot.addWidget(childless)
    device_group = childless.top_level_groups['Devices']
    childless_displays = device_group.childs[0].childs
    assert len(childless_displays) == 0


def test_suite_tools(device, qtbot):
    suite = TyphosSuite.from_device(device)
    qtbot.addWidget(suite)
    assert len(suite.tools) == 3
    assert len(suite.tools[0].devices) == 1


def test_suite_get_subdisplay_by_device(suite, device):
    display = suite.get_subdisplay(device)
    assert device in display.devices


def test_suite_subdisplay_parentage(suite, device):
    display = suite.get_subdisplay(device)
    assert display in suite.findChildren(TyphosDeviceDisplay)


def test_suite_get_subdisplay_by_name(suite, device):
    display = suite.get_subdisplay(device.name)
    assert device in display.devices


def test_suite_show_display_by_device(suite, device):
    suite.show_subdisplay(device.x)
    dock = suite._content_frame.layout().itemAt(
        suite.layout().count() - 1).widget()
    assert isinstance(dock, QtWidgets.QDockWidget)
    assert device.x in dock.widget().devices


def test_suite_show_display_by_parameter(suite):
    device_param = suite.top_level_groups['Devices'].childs[0]
    suite.show_subdisplay(device_param)
    dock = suite._content_frame.layout().itemAt(
        suite.layout().count() - 1).widget()
    assert isinstance(dock, QtWidgets.QDockWidget)
    assert device_param.device in dock.widget().devices
    assert dock.receivers(dock.closing) == 1


def test_suite_hide_subdisplay_by_device(suite, device, qtbot):
    display = suite.get_subdisplay(device)
    suite.show_subdisplay(device)
    with qtbot.waitSignal(display.parent().closing):
        suite.hide_subdisplay(device)
    assert display.parent().isHidden()


def test_suite_hide_subdisplay_by_parameter(suite, qtbot):
    device_param = suite.top_level_groups['Devices'].childs[0]
    suite.show_subdisplay(device_param)
    display = suite.get_subdisplay(device_param.device)
    suite.show_subdisplay(device_param)
    with qtbot.waitSignal(display.parent().closing):
        suite.hide_subdisplay(device_param)
    assert display.parent().isHidden()


def test_suite_hide_subdisplays(suite, device):
    suite.show_subdisplay(device)
    suite.show_subdisplay(device.x)
    suite.show_subdisplay(device.y)
    suite.hide_subdisplays()
    for dev in (device, device.x, device.y):
        display = suite.get_subdisplay(device)
        assert display.parent().isHidden()


def test_device_parameter_tree(qtbot, motor, device):
    tree = ParameterTree(showHeader=False)
    devices = ptypes.GroupParameter(name='Devices')
    tree.addParameters(devices)
    qtbot.addWidget(tree)
    # Device with no subdevices
    motor_param = DeviceParameter(motor, embeddable=False)
    assert len(motor_param.childs) == 0
    devices.addChild(motor_param)
    # Device with subdevices
    dev_param = DeviceParameter(device, emeddable=True)
    assert len(dev_param.childs) == len(device._sub_devices)
    devices.addChild(dev_param)


def test_suite_embed_device(suite, device):
    suite.embed_subdisplay(device.x)
    dock_layout = suite.embedded_dock.widget().layout()
    assert dock_layout.itemAt(0).widget().devices[0] == device.x


def test_suite_embed_device_by_name(suite, device):
    suite.embed_subdisplay(device.name)
    dock_layout = suite.embedded_dock.widget().layout()
    assert dock_layout.itemAt(0).widget().devices[0] == device


def test_hide_embedded_display(suite, device):
    suite.embed_subdisplay(device.x)
    suite.hide_subdisplay(device.x)
    display = suite.get_subdisplay(device.x)
    assert suite.embedded_dock is None
    assert display.isHidden()


def test_suite_save_util(suite, device):
    handle = io.StringIO()
    save_suite(suite, handle)
    handle.seek(0)
    devices = [device.name for device in suite.devices]
    assert str(devices) in handle.read()


def test_suite_save(suite, monkeypatch):
    tfile = Path(tempfile.gettempdir()) / 'test.py'
    monkeypatch.setattr(QtWidgets.QFileDialog,
                        'getSaveFileName',
                        lambda *args: (str(tfile), str(tfile)))
    suite.save()
    assert tfile.exists()
    devices = [device.name for device in suite.devices]
    with open(str(tfile), 'r') as f:
        assert str(devices) in f.read()
    os.remove(str(tfile))


def test_suite_save_cancel_smoke(suite, monkeypatch):
    monkeypatch.setattr(QtWidgets.QFileDialog,
                        'getSaveFileName',
                        lambda *args: None)
    suite.save()
