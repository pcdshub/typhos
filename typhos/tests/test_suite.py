import io
import os
import tempfile
from pathlib import Path

import pytest
from pyqtgraph.parametertree import ParameterTree
from pyqtgraph.parametertree import parameterTypes as ptypes
from qtpy import QtWidgets

from ..display import DisplayTypes, TyphosDeviceDisplay
from ..suite import DeviceParameter, TyphosSuite
from ..utils import save_suite
from .conftest import MockDevice, show_widget


@pytest.fixture(scope='function')
def suite(qtbot, device):
    suite = TyphosSuite.from_device(device, tools=None)
    qtbot.addWidget(suite)
    return suite


@show_widget
def test_suite_with_child_devices(suite: TyphosSuite, device: MockDevice):
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
    assert len(suite.tools) == len(TyphosSuite.default_tools)
    assert len(suite.tools[0].devices) == 1


def test_suite_get_subdisplay_by_device(suite: TyphosSuite, device: MockDevice):
    display = suite.get_subdisplay(device)
    assert device in display.devices


def test_suite_subdisplay_parentage(suite: TyphosSuite, device: MockDevice):
    display = suite.get_subdisplay(device)
    assert display in suite.findChildren(TyphosDeviceDisplay)


def test_suite_get_subdisplay_by_name(suite: TyphosSuite, device: MockDevice):
    display = suite.get_subdisplay(device.name)
    assert device in display.devices


def test_suite_show_display_by_device(suite: TyphosSuite, device: MockDevice):
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


def test_suite_hide_subdisplay_by_device(suite: TyphosSuite, device, qtbot):
    display = suite.get_subdisplay(device)
    suite.show_subdisplay(device)
    with qtbot.waitSignal(display.parent().closing):
        suite.hide_subdisplay(device)
    assert display.parent().isHidden()


def test_suite_hide_subdisplay_by_parameter(suite: TyphosSuite, qtbot):
    device_param = suite.top_level_groups['Devices'].childs[0]
    suite.show_subdisplay(device_param)
    display = suite.get_subdisplay(device_param.device)
    suite.show_subdisplay(device_param)
    with qtbot.waitSignal(display.parent().closing):
        suite.hide_subdisplay(device_param)
    assert display.parent().isHidden()


def test_suite_hide_subdisplays(suite: TyphosSuite, device: MockDevice):
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


def test_suite_embed_device(suite: TyphosSuite, device: MockDevice):
    suite.embed_subdisplay(device.x)
    dock_layout = suite.embedded_dock.widget().layout()
    assert dock_layout.itemAt(0).widget().devices[0] == device.x


def test_suite_embed_device_by_name(suite: TyphosSuite, device: MockDevice):
    suite.embed_subdisplay(device.name)
    dock_layout = suite.embedded_dock.widget().layout()
    assert dock_layout.itemAt(0).widget().devices[0] == device


def test_hide_embedded_display(suite: TyphosSuite, device: MockDevice):
    print("Embedding", device.x)
    suite.embed_subdisplay(device.x)
    print("Hiding")
    suite.hide_subdisplay(device.x)
    print("Get subdisplay")
    display = suite.get_subdisplay(device.x)
    print("Got subdisplay", display)
    assert suite.embedded_dock is None
    assert display.isHidden()
    print("Done")


def test_suite_save_util(suite: TyphosSuite, device: MockDevice):
    handle = io.StringIO()
    save_suite(suite, handle)
    handle.seek(0)
    devices = [device.name for device in suite.devices]
    assert str(devices) in handle.read()


def test_suite_save_screenshot(suite: TyphosSuite, device: MockDevice):
    with tempfile.NamedTemporaryFile(mode="wb") as fp:
        assert suite.save_screenshot(fp.name)
        # We could check that the file isn't empty, but this may fail on CI
        # or headless setups, so let's just trust that qt does its best to
        # save as we request.


def test_suite_save_device_screenshots(suite: TyphosSuite, device: MockDevice):
    with tempfile.NamedTemporaryFile(mode="wb") as fp:
        # There's only one device, so we don't need to pass in a format here
        screenshots = suite.save_device_screenshots(fp.name)
        assert device.name in screenshots
        assert len(screenshots) == 1


def test_suite_save(suite: TyphosSuite, monkeypatch: pytest.MonkeyPatch):
    tfile = Path(tempfile.gettempdir()) / 'test.py'
    monkeypatch.setattr(QtWidgets.QFileDialog,
                        'getSaveFileName',
                        lambda *args: (str(tfile), str(tfile)))
    suite.save()
    assert tfile.exists()
    devices = [device.name for device in suite.devices]
    with open(str(tfile)) as f:
        assert str(devices) in f.read()
    os.remove(str(tfile))


def test_suite_save_cancel_smoke(suite: TyphosSuite, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(QtWidgets.QFileDialog,
                        'getSaveFileName',
                        lambda *args: None)
    suite.save()


def test_suite_resize(suite: TyphosSuite, monkeypatch: pytest.MonkeyPatch):
    display = suite.show_subdisplay(suite.devices[0].name)
    display_min_size = display.minimumSizeHint()
    print("Suite width:", suite.width())
    print("Display min size", display_min_size)
    assert suite.width() >= display_min_size.width()

    fixed_height = 100

    for display_type in DisplayTypes:
        suite.resize(10, fixed_height)
        print("\nSwitched to template", display_type)
        print("Suite shrunk to", suite.size())
        display.display_type = display_type
        display_min_size = display.minimumSizeHint()
        print("New display min size", display_min_size)
        assert suite.width() >= display.minimumSizeHint().width()
        print("-> Suite width", suite.width())
        assert suite.height() == fixed_height
