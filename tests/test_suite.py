############
# Standard #
############

############
# External #
############
import pytest
from pyqtgraph.parametertree import ParameterTree, parameterTypes as ptypes
from qtpy.QtWidgets import QDockWidget

###########
# Package #
###########
from typhon.utils import clean_name
from typhon.suite import TyphonSuite, DeviceParameter
from .conftest import show_widget


@pytest.fixture(scope='function')
def suite(qtbot, device):
    suite = TyphonSuite.from_device(device)
    qtbot.addWidget(suite)
    return suite


@show_widget
def test_suite_with_child_devices(suite, device):
    assert device in suite.devices
    device_group = suite.top_level_groups[0]
    assert len(device_group.childs) == 1
    child_displays = device_group.childs[0].childs
    assert len(child_displays) == len(device._sub_devices)
    return suite

def test_suite_without_children(device, qtbot):
    childless = TyphonSuite.from_device(device, children=False)
    qtbot.addWidget(childless)
    device_group = childless.top_level_groups[0]
    childless_displays = device_group.childs[0].childs
    assert len(childless_displays) == 0


def test_suite_tools(suite):
    assert len(suite.tools) == 3
    assert len(suite.tools[0].devices) == 1


def test_suite_subdisplay(qtbot, suite):
    device = suite.devices[0]
    x_display = suite.get_subdisplay(device.x)
    assert device.x in x_display.devices
    suite.show_subdisplay(device.x)
    assert isinstance(x_display.parent(), QDockWidget)
    # Set display by name
    y_display = suite.get_subdisplay(device.y)
    qtbot.addWidget(y_display)
    assert device.y in y_display.devices
    suite.show_subdisplay(clean_name(device.y))
    assert isinstance(y_display.parent(), QDockWidget)
    with qtbot.waitSignal(y_display.parent().closing):
        # Hide all our subdisplays
        suite.hide_subdisplays()
    return suite


@show_widget
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
    return tree
