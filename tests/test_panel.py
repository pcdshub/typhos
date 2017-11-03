############
# Standard #
############

############
# External #
############
import pytest
from ophyd.signal import EpicsSignal, EpicsSignalRO

###########
# Package #
###########
from typhon.panel import Panel
from .conftest import show_widget

@show_widget
def test_panel(qapp):
    panel = Panel(signals={
                    #Signal is its own write            
                    'Standard' : EpicsSignal('Tst:Pv'),
                    #Signal has separate write/read
                    'Read and Write' : EpicsSignal('Tst:Read',
                                                   write_pv='Tst:Write'),
                    #Signal is read-only
                    'Read Only' : EpicsSignalRO('Tst:Pv:RO')})
    assert len(panel.signals) == 3
    return panel
