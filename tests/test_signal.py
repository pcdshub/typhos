############
# Standard #
############

############
# External #
############
from ophyd.signal import Signal, EpicsSignal, EpicsSignalRO
from ophyd.sim import SynSignal, SynSignalRO
from ophyd.tests.conftest import using_fake_epics_pv
from pydm.widgets import PyDMEnumComboBox

###########
# Package #
###########
from typhon.signal import SignalPanel
from .conftest import show_widget, RichSignal, DeadSignal

@show_widget
@using_fake_epics_pv
def test_panel_creation(qtbot):
    panel = SignalPanel(signals={
                    # Signal is its own write
                    'Standard': EpicsSignal('Tst:Pv'),
                    # Signal has separate write/read
                    'Read and Write': EpicsSignal('Tst:Read',
                                                  write_pv='Tst:Write'),
                    # Signal is read-only
                    'Read Only': EpicsSignalRO('Tst:Pv:RO'),
                    # Simulated Signal
                    'Simulated': SynSignal(name='simul'),
                    'SimulatedRO': SynSignalRO(name='simul_ro')})
    qtbot.addWidget(panel)
    assert len(panel.signals) == 5
    # Check read-only channels do not have write widgets
    panel.layout().itemAtPosition(2, 1).layout().count() == 1
    panel.layout().itemAtPosition(4, 1).layout().count() == 1
    # Check write widgets are present
    panel.layout().itemAtPosition(0, 1).layout().count() == 2
    panel.layout().itemAtPosition(1, 1).layout().count() == 2
    panel.layout().itemAtPosition(3, 1).layout().count() == 2
    return panel


@show_widget
@using_fake_epics_pv
def test_panel_add_enum(qtbot):
    panel = SignalPanel()
    qtbot.addWidget(panel)
    # Create an enum pv
    epics_sig = EpicsSignal("Tst:Enum")
    epics_sig._write_pv.enum_strs = ('A', 'B')
    # Create an enum signal
    syn_sig = RichSignal(name='Syn:Enum', value=1)
    # Add our signals to the panel
    loc1 = panel.add_signal(epics_sig, "EPICS Enum PV")
    loc2 = panel.add_signal(syn_sig, "Sim Enum PV")
    # Check our signal was added a QCombobox
    # Assume it is the last item in the button layout
    but_layout = panel.layout().itemAtPosition(loc1, 1)
    assert isinstance(but_layout.itemAt(but_layout.count()-1).widget(),
                      PyDMEnumComboBox)
    # Check our signal was added a QCombobox
    # Assume it is the last item in the button layout
    but_layout = panel.layout().itemAtPosition(loc2, 1)
    assert isinstance(but_layout.itemAt(but_layout.count()-1).widget(),
                      PyDMEnumComboBox)
    return panel


def test_add_dead_signal(qtbot):
    panel = SignalPanel()
    qtbot.addWidget(panel)
    dead_sig = DeadSignal(name='ded')
    panel.add_signal(dead_sig, 'Dead Signal')
    assert 'Dead Signal' in panel.signals


@using_fake_epics_pv
def test_add_pv(qtbot):
    panel = SignalPanel()
    qtbot.addWidget(panel)
    panel.add_pv('Tst:A', 'Read Only')
    assert 'Read Only' in panel.signals
    assert panel.layout().itemAtPosition(0, 1).count() == 1
    panel.add_pv('Tst:A', "Write", write_pv='Tst:B')
    assert panel.layout().itemAtPosition(1, 1).count() == 2
