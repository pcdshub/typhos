############
# Standard #
############

############
# External #
############
from qtpy.QtWidgets import QWidget

###########
# Package #
###########
from typhon.utils import clean_attr, clean_name
from typhon.display import DeviceDisplay
from .conftest import show_widget


@show_widget
def test_display(device):
    display = DeviceDisplay(device)
    # We have all our signals
    shown_read_sigs = list(display.read_panel.signals.keys())
    assert all([clean_attr(sig) in shown_read_sigs
                for sig in device.read_attrs])
    shown_cfg_sigs = list(display.config_panel.signals.keys())
    assert all([clean_attr(sig) in shown_cfg_sigs
                for sig in device.configuration_attrs])
    # We have all our subdevices
    sub_devices = [getattr(disp, 'device', None)
                   for disp in display.ui.subdisplay.children()]
    assert all([getattr(device, dev) in sub_devices
                for dev in device._sub_devices])
    # No children
    childless = DeviceDisplay(device, children=False)
    sub_display = [disp
                   for disp in childless.ui.subdisplay.children()
                   if isinstance(disp, DeviceDisplay)]
    assert len(sub_display) == 0
    return display


@show_widget
def test_display_with_funcs(device):
    display = DeviceDisplay(device, methods=[device.insert,
                                             device.remove])
    # The method panel is visible
    assert not display.method_panel.isHidden()
    # Assert we have all our specified functions
    assert 'insert' in display.methods
    assert 'remove' in display.methods
    return display


@show_widget
def test_subdisplay(qapp, device):
    # Set display by Device component
    display = DeviceDisplay(device)
    display.show_subdisplay(device.x)
    assert not display.ui.subwindow.isHidden()
    assert display.ui.subdisplay.currentWidget().device == device.x
    # Set display by name
    display.show_subdisplay(clean_name(device.y))
    assert display.ui.subdisplay.currentWidget().device == device.y
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
