############
# Standard #
############

############
# External #
############
from ophyd.signal import EpicsSignal, EpicsSignalRO
from ophyd.tests.conftest import using_fake_epics_pv
from pydm.widgets import PyDMEnumComboBox

###########
# Package #
###########
from typhon.signal import SignalPanel
from .conftest import show_widget


@show_widget
@using_fake_epics_pv
def test_panel_creation():
    panel = SignalPanel("Test Signals", signals={
                    # Signal is its own write
                    'Standard': EpicsSignal('Tst:Pv'),
                    # Signal has separate write/read
                    'Read and Write': EpicsSignal('Tst:Read',
                                                  write_pv='Tst:Write'),
                    # Signal is read-only
                    'Read Only': EpicsSignalRO('Tst:Pv:RO')})
    assert len(panel.pvs) == 3
    return panel


@show_widget
@using_fake_epics_pv
def test_panel_add_enum():
    panel = SignalPanel("Test Signals")
    # Create an enum pv
    sig = EpicsSignal("Tst:Enum")
    sig._write_pv.enum_strs = ('A', 'B')
    # Add our signal to the panel
    loc = panel.add_signal(sig, "Enum PV")
    # Check our signal was added a QCombobox
    # Assume it is the last item in the button layout
    but_layout = panel.layout().itemAtPosition(loc, 1)
    assert isinstance(but_layout.itemAt(but_layout.count()-1).widget(),
                      PyDMEnumComboBox)
    return panel
