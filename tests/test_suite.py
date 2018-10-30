############
# Standard #
############

############
# External #
############
from pyqtgraph.parametertree import ParameterTree, parameterTypes as ptypes
from qtpy.QtWidgets import QDockWidget

###########
# Package #
###########
from typhon.utils import clean_name
from typhon.suite import TyphonSuite, DeviceParameter
from .conftest import show_widget


@show_widget
def test_suite(device):
    device.name = 'test'
    suite = TyphonSuite.from_device(device)
    assert suite.device_panel.title == device.name
    assert device in suite.device_panel.devices
    # Grab all component displays 
    child_displays = [suite.component_list.item(i).data(Qt.UserRole)
                      for i in range(suite.component_list.count())]
    assert len(child_displays) == len(device._sub_devices)
    # Default tools are loaded
    assert len(suite.tools) == 3
    assert len(suite.tools[0].devices) == 1
    # No children
    childless = TyphonSuite.from_device(device, children=False)
    # Grab all component displays 
    child_displays = [childless.component_list.item(i).data(Qt.UserRole)
                      for i in range(childless.component_list.count())]
    assert len(child_displays) == 0
    return suite


@show_widget
def test_suite_subdisplay(device):
    # Set display by Device component
    suite = TyphonSuite.from_device(device)
    suite.show_subdisplay(device.x)
    assert not suite.ui.subwindow.isHidden()
    assert device.x in suite.ui.subdisplay.currentWidget().devices
    # Set display by name
    suite.show_subdisplay(clean_name(device.y))
    assert device.y in suite.ui.subdisplay.currentWidget().devices
    # Add a tool
    w = QWidget()
    # Clear other tools
    suite.ui.tool_list.clear()
    suite.add_tool('My Tool', w)
    # Release a model press event
    tool_item = suite.ui.tool_list.item(0)
    tool_model = suite.ui.tool_list.indexFromItem(tool_item)
    suite.show_subdisplay(tool_model)
    assert suite.ui.subdisplay.currentWidget() == w
    # Hide all our subdisplays
    suite.hide_subdisplays()
    assert suite.ui.subwindow.isHidden()
    assert suite.ui.tool_list.selectedIndexes() == []
    assert suite.ui.tool_list.selectedIndexes() == []
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
