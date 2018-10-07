############
# Standard #
############

############
# External #
############
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QWidget

###########
# Package #
###########
from typhon.utils import clean_attr, clean_name
from typhon.display import DeviceDisplay
from .conftest import show_widget


@show_widget
def test_display(device):
    device.name = 'test'
    display = DeviceDisplay(device)
    assert display.device_panel.title == device.name
    assert device in display.device_panel.devices
    # Grab all component displays 
    child_displays = [display.component_list.item(i).data(Qt.UserRole)
                      for i in range(display.component_list.count())]
    assert len(child_displays) == len(device._sub_devices)
    # Default tools are loaded
    assert len(display.tools) == 2
    assert len(display.tools[0].devices) == 1
    # No children
    childless = DeviceDisplay(device, children=False)
    # Grab all component displays 
    child_displays = [childless.component_list.item(i).data(Qt.UserRole)
                      for i in range(childless.component_list.count())]
    assert len(child_displays) == 0
    return display


@show_widget
def test_subdisplay(qapp, device):
    # Set display by Device component
    display = DeviceDisplay(device)
    display.show_subdisplay(device.x)
    assert not display.ui.subwindow.isHidden()
    assert device.x in display.ui.subdisplay.currentWidget().devices
    # Set display by name
    display.show_subdisplay(clean_name(device.y))
    assert device.y in display.ui.subdisplay.currentWidget().devices
    # Add a tool
    w = QWidget()
    # Clear other tools
    display.ui.tool_list.clear()
    display.add_tool('My Tool', w)
    # Release a model press event
    tool_item = display.ui.tool_list.item(0)
    tool_model = display.ui.tool_list.indexFromItem(tool_item)
    display.show_subdisplay(tool_model)
    assert display.ui.subdisplay.currentWidget() == w
    # Hide all our subdisplays
    display.hide_subdisplays()
    assert display.ui.subwindow.isHidden()
    assert display.ui.tool_list.selectedIndexes() == []
    assert display.ui.tool_list.selectedIndexes() == []
    return display
