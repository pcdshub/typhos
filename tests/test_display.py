############
# Standard #
############

############
# External #
############
from ophyd.signal import EpicsSignal, EpicsSignalRO
from ophyd import Device, EpicsMotor, Component as C, FormattedComponent as FC

###########
# Package #
###########
from typhon.utils import clean_attr
from typhon.display import DeviceDisplay
from .conftest import show_widget


class MockDevice(Device):
    # Device signals
    read1 = C(EpicsSignalRO, ':READ1')
    read2 = C(EpicsSignalRO, ':READ2')
    read3 = C(EpicsSignalRO, ':READ3')
    read4 = C(EpicsSignal,   ':READ4')
    read5 = C(EpicsSignal,   ':READ5', write_pv=':WRITE5')
    config1 = C(EpicsSignalRO, ':CFG1')
    config2 = C(EpicsSignalRO, ':CFG2')
    config3 = C(EpicsSignalRO, ':CFG3')
    config4 = C(EpicsSignal,   ':CFG4')
    config5 = C(EpicsSignal,   ':CFG5', write_pv=':CFGWRITE5')
    misc1 = C(EpicsSignalRO, ':MISC1')
    misc2 = C(EpicsSignalRO, ':MISC2')
    misc3 = C(EpicsSignalRO, ':MISC3')
    misc4 = C(EpicsSignal,   ':MISC4')
    misc5 = C(EpicsSignal,   ':MISC5', write_pv=':MISCWRITE5')

    # Component Motors
    x = FC(EpicsMotor, 'Tst:MMS:X', name='X Axis')
    y = FC(EpicsMotor, 'Tst:MMS:Y', name='Y Axis')
    z = FC(EpicsMotor, 'Tst:MMS:Z', name='Z Axis')

    # Default Signal Sorting
    _default_read_attrs = ['read1', 'read2', 'read3', 'read4', 'read5']
    _default_configuration_attrs = ['config1', 'config2', 'config3',
                                    'config4', 'config5']


@show_widget
def test_display():
    d = MockDevice("Tst:Dev", name='MockDevice')
    display = DeviceDisplay(d)
    # We have all our signals
    assert all([getattr(d, sig) in list(display.read_panel.signals.values())
                for sig in d.read_attrs])
    assert all([getattr(d, sig) in list(display.config_panel.signals.values())
                for sig in d.configuration_attrs])
    # We have all our subdevices
    assert all([getattr(d, dev) in display.all_devices
                for dev in d._sub_devices])
    return display


def test_enum_attrs():
    d = MockDevice("Tst:Dev", name='MockDevice')
    d.enum_attrs = ['read1']
    d = DeviceDisplay(d)
    assert clean_attr('read1') in d.read_panel.enum_sigs
