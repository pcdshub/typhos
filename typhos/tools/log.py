import logging

from qtpy.QtWidgets import QVBoxLayout

from pydm.widgets.logdisplay import PyDMLogDisplay

from ..utils import TyphosBase


class TyphosLogDisplay(TyphosBase):
    """Typhos Logging Display."""
    def __init__(self, level=logging.INFO, parent=None):
        super().__init__(parent=parent)
        # Set the logname to be non-existant so that we do not attach to the
        # root logger. This causes issue if this widget is closed before the
        # end of the Python session. For the long term this issue will be
        # resolved with https://github.com/slaclab/pydm/issues/474
        self.logdisplay = PyDMLogDisplay(logname='not_set', level=level,
                                         parent=self)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.logdisplay)

    def add_device(self, device):
        """Add a device to the logging display."""
        super().add_device(device)
        # If this is the first device
        if len(self.devices) == 1:
            self.logdisplay.logName = device.log.name
        # If we have already attached a device, just set it to NOTSET to let
        # the existing handler do all the filtering
        else:
            device.log.setLevel(logging.NOTSET)
            logger = getattr(device.log, 'logger', device.log)
            logger.addHandler(self.logdisplay.handler)
