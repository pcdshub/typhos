"""
Module Docstring
"""
############
# Standard #
############
import logging

###############
# Third Party #
###############
from ophyd import EpicsSignal, Signal
import pytest
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

##########
# Module #
##########
from typhon import register_signal
from typhon.plot import ChannelDisplay, TyphonTimePlot, DeviceTimePlot

@pytest.fixture(scope='session')
def sim_signal():
    sim_sig = Signal(name='tst_this_2')
    sim_sig.put(3.14)
    register_signal(sim_sig)
    return sim_sig


def test_channeldisplay():
    disp = ChannelDisplay('Test Channel', QColor(Qt.white))
    assert disp.ui.name.text() == 'Test Channel'
    assert disp.ui.color.brush.color() == QColor(Qt.white)


def test_add_signal(sim_signal):
    # Create Signals
    epics_sig = EpicsSignal('Tst:This')
    # Create empty plot
    ttp = TyphonTimePlot()
    # Add to list of available signals
    ttp.add_available_signal(epics_sig, 'Epics Signal')
    assert ttp.ui.signal_combo.itemText(0) == 'Epics Signal'
    assert ttp.ui.signal_combo.itemData(0) == 'ca://Tst:This'
    ttp.add_available_signal(sim_signal, 'Simulated Signal')
    assert ttp.ui.signal_combo.itemText(1) == 'Simulated Signal'
    assert ttp.ui.signal_combo.itemData(1) == 'sig://tst_this_2'


def test_curve_methods(sim_signal):
    ttp = TyphonTimePlot()
    orig_color = ttp.ui.color.brush
    ttp.add_curve('sig://' + sim_signal.name, name=sim_signal.name)
    # Check that our signal is stored in the mapping
    assert sim_signal.name in ttp.channel_map
    # Check that our next color is different
    assert ttp.ui.color.brush != orig_color
    # Check that our ChannelDisplay is live
    assert ttp.ui.live_channels.layout().count() == 2  # 1 is a spacer
    # Check that our curve is live
    assert len(ttp.ui.timeplot.curves) == 1
    # Try and add again
    ttp.add_curve('sig://' + sim_signal.name, name=sim_signal.name)
    # Check we didn't duplicate
    assert ttp.ui.live_channels.layout().count() == 2  # 1 is a spacer
    assert len(ttp.ui.timeplot.curves) == 1
    ttp.remove_curve(sim_signal.name)
    assert ttp.ui.live_channels.layout().count() == 1  # 1 is a spacer
    assert len(ttp.ui.timeplot.curves) == 0

def test_curve_creation_button(sim_signal):
    ttp = TyphonTimePlot()
    ttp.add_available_signal(sim_signal, 'Sim Signal')
    ttp.creation_requested()
    # Check that our signal is stored in the mapping
    assert 'Sim Signal' in ttp.channel_map
    assert len(ttp.ui.timeplot.curves) == 1

def test_device_plot(motor):
    dtp = DeviceTimePlot(motor)
    # Add the hint
    assert len(dtp.ui.timeplot.curves) == 1
    # Added all the signals
    assert dtp.ui.signal_combo.count() == len(motor.component_names)
