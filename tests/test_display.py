############
# Standard #
############

############
# External #
############
import numpy as np
from ophyd import Device, Component as C, FormattedComponent as FC
from ophyd.sim import SynAxis, Signal, SynPeriodicSignal, SignalRO
import pytest
from pydm.PyQt.QtGui import QWidget

###########
# Package #
###########
from typhon.utils import clean_attr, clean_name
from typhon.display import DeviceDisplay
from .conftest import show_widget


class ConfiguredSynAxis(SynAxis):
     velocity = C(Signal, value=100)
     acceleration = C(Signal, value=10)
     resolution = C(Signal, value=5)
     _default_configuration_attrs = ['velocity', 'acceleration']


class RandomSignal(SynPeriodicSignal):
    """
    Signal that randomly updates a random integer
    """
    def __init__(self,*args,  **kwargs):
        super().__init__(func=lambda: np.random.uniform(0, 100),
                         period=10, period_jitter=4, **kwargs)


class MockDevice(Device):
    # Device signals
    readback = C(RandomSignal)
    noise = C(RandomSignal)
    transmorgifier = C(SignalRO, value=4)
    setpoint = C(Signal, value=0)
    velocity = C(Signal, value=1)
    flux = C(RandomSignal)
    modified_flux = C(RandomSignal)
    capacitance = C(RandomSignal)
    acceleration = C(Signal, value=3)
    limit = C(Signal, value=4)
    inductance = C(RandomSignal)
    transformed_inductance = C(SignalRO, value=3)
    core_temperature = C(RandomSignal)
    resolution = C(Signal, value=5)
    duplicator = C(Signal, value=6)

    # Component Motors
    x = FC(ConfiguredSynAxis, name='X Axis')
    y = FC(ConfiguredSynAxis, name='Y Axis')
    z = FC(ConfiguredSynAxis, name='Z Axis')

    # Default Signal Sorting
    _default_read_attrs = ['readback', 'setpoint', 'transmorgifier',
                           'noise', 'inductance']
    _default_configuration_attrs = ['flux', 'modified_flux', 'capacitance',
                                    'velocity', 'acceleration']

    def insert(self, width: float=2.0, height: float=2.0,
               fast_mode: bool=False):
        """Fake insert function to display"""
        pass

    def remove(self, height: float,  fast_mode: bool=False):
        """Fake remove function to display"""
        pass

    @property
    def hints(self):
        return {'fields': [self.name+'_readback']}


@pytest.fixture(scope='function')
def device():
    return MockDevice('Tst:This', name='Simulated Device')


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
def test_display_with_images(device, test_images):
    (lenna, python) = test_images
    # Create a display with our image
    display = DeviceDisplay(device, image=lenna)
    assert display.image_widget.filename == lenna
    # Add our python image
    display.add_image(python)
    assert display.image_widget.filename == python
    # Add our component image
    display.add_image(lenna, subdevice=device.x)
    # Show our subdevice and image
    sub_display = display.get_subdisplay(device.x)
    assert sub_display.image_widget.filename == lenna
    # Bad input
    with pytest.raises(ValueError):
        display.add_image(lenna, subdevice=device)
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
