"""
Tests for the plot tool.
"""
import pytest
from ophyd import EpicsSignal, Signal

from typhos import register_signal
from typhos.tools.plot import TyphosTimePlot
from typhos.utils import channel_from_signal


@pytest.fixture(scope='session')
def sim_signal():
    sim_sig = Signal(name='tst_this_2')
    sim_sig.put(3.14)
    register_signal(sim_sig)
    return sim_sig


def test_add_signal(qtbot, sim_signal):
    # Create Signals
    epics_sig = EpicsSignal('Tst:This')
    # Create empty plot
    ttp = TyphosTimePlot()
    qtbot.addWidget(ttp)
    # Add to list of available signals
    ttp.add_available_signal(epics_sig, 'Epics Signal')
    assert ttp.signal_combo.itemText(0) == 'Epics Signal'
    assert ttp.signal_combo.itemData(0) == 'ca://Tst:This'
    ttp.add_available_signal(sim_signal, 'Simulated Signal')
    assert ttp.signal_combo.itemText(1) == 'Simulated Signal'
    assert ttp.signal_combo.itemData(1) == 'sig://tst_this_2'


def test_curve_methods(qtbot, sim_signal):
    ttp = TyphosTimePlot()
    qtbot.addWidget(ttp)
    ttp.add_curve('sig://' + sim_signal.name, name=sim_signal.name)
    # Check that our signal is stored in the mapping
    assert 'sig://' + sim_signal.name in ttp.channel_to_curve
    # Check that our curve is live
    assert len(ttp.timechart.chart.curves) == 1
    # Try and add again
    ttp.add_curve('sig://' + sim_signal.name, name=sim_signal.name)
    # Check we didn't duplicate
    assert len(ttp.timechart.chart.curves) == 1
    ttp.remove_curve(channel_from_signal(sim_signal))
    assert len(ttp.timechart.chart.curves) == 0


def test_curve_creation_button(qtbot, sim_signal):
    ttp = TyphosTimePlot()
    qtbot.addWidget(ttp)
    ttp.add_available_signal(sim_signal, 'Sim Signal')
    ttp.creation_requested()
    # Check that our signal is stored in the mapping
    assert channel_from_signal(sim_signal) in ttp.channel_to_curve
    assert len(ttp.timechart.chart.curves) == 1


def test_device_plot(motor, qapp, qtbot):
    dtp = TyphosTimePlot.from_device(motor)
    qtbot.addWidget(dtp)

    def all_signals_listed():
        assert dtp.signal_combo.count() == len(motor.component_names)

    qtbot.wait_until(all_signals_listed)
