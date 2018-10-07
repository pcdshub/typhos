import logging

from pydm.widgets.logdisplay import PyDMLogDisplay
from qtpy.QtWidgets import QVBoxLayout

from ..utils import TyphonBase


class TyphonLogDisplay(TyphonBase):
    """Typhon Logging Display"""
    def __init__(self, level=logging.INFO, parent=None):
        super().__init__(parent=parent)
        self.logdisplay = PyDMLogDisplay(level=level)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.logdisplay)

    def add_device(self, device):
        """Add a device to the logging display"""
        super().add_device(device)
        # If this is the first device
        if len(self.devices) == 1:
            self.logdisplay.logName = device.log.name
        # If we have already attached a device, just set it to NOTSET to let
        # the existing handler do all the filtering
        else:
            device.log.setLevel(logging.NOTSET)
            device.log.addHandler(self.logdisplay.handler)
