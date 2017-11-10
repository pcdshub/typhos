############
# Standard #
############

############
# External #
############
from ophyd.signal import EpicsSignal, EpicsSignalRO
from pydm.widgets import PyDMEnumComboBox

###########
# Package #
###########
from typhon.panel import SignalPanel
from .conftest import show_widget


@show_widget
def test_panel_creation():
    panel = SignalPanel("Test Signals", signals={
                    # Signal is its own write
                    'Standard': EpicsSignal('Tst:Pv'),
                    # Signal has separate write/read
                    'Read and Write': EpicsSignal('Tst:Read',
                                                  write_pv='Tst:Write'),
                    # Signal is read-only
                    'Read Only': EpicsSignalRO('Tst:Pv:RO')})
    assert len(panel.signals) == 3
    return panel


def test_panel_hide():
    # Create basic panel
    panel = SignalPanel("Test Signals",
                        signals={'Standard': EpicsSignal("Tst:Pv")})
    # Toggle the button
    panel.show_contents(False)
    assert panel.contents.isHidden()


@show_widget
def test_panel_add_enum():
    panel = SignalPanel("Test Signals")
    loc = panel.add_signal(EpicsSignal("Tst:Enum"), "Enum PV", enum=True)
    # Check our signal was added in the `enum_attrs` list
    assert "Enum PV" in panel.enum_sigs
    # Check our signal was added a QCombobox
    # Assume it is the last item in the button layout
    but_layout = panel.contents.layout().itemAtPosition(loc, 1)
    assert isinstance(but_layout.itemAt(but_layout.count()-1).widget(),
                      PyDMEnumComboBox)
    return panel
