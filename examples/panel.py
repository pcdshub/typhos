"""Example to create a Panel of Ophyd Signals from an object"""
import sys
import numpy as np
from ophyd import Device, Component as Cpt, Signal
try:
    from ophyd.sim import SignalRO
except ImportError:
    from ophyd.utils import ReadOnlyError

    class SignalRO(ophyd.sim.Signal):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._metadata.update(
                connected=True,
                write_access=False,
            )

        def put(self, value, *, timestamp=None, force=False):
            raise ReadOnlyError("The signal {} is readonly.".format(self.name))

        def set(self, value, *, timestamp=None, force=False):
            raise ReadOnlyError("The signal {} is readonly.".format(self.name))
from qtpy.QtWidgets import QApplication
import typhos


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
    typhos.use_stylesheet()
    # Create my panel
    panel = typhos.TyphonSignalPanel.from_device(sample)
    panel.sortBy = panel.byName
    # Execute
    panel.show()
    app.exec_()
