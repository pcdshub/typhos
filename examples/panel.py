"""Example to create a Panel of Ophyd Signals from an object"""
import sys
import numpy as np
from ophyd import Device, Component as Cpt, Signal
from ophyd.sim import SignalRO
from qtpy.QtWidgets import QApplication
import typhon


class Sample(Device):
    """Simulated Device"""
    readback = Cpt(SignalRO, value=1)
    setpoint = Cpt(Signal, value=2)
    waveform = Cpt(SignalRO, value=np.random.randn(100, ))
    image = Cpt(SignalRO, value=np.abs(np.random.randn(100, 100)) * 455)


# Create my device without a prefix
sample = Sample('', name='sample')

if __name__ == '__main__':
    # Create my application
    app = QApplication(sys.argv)
    typhon.use_stylesheet()
    # Create my panel
    panel = typhon.TyphonSignalPanel.from_device(sample)
    panel.sortBy = panel.byName
    # Execute
    panel.show()
    app.exec_()
