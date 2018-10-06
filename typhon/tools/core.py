import logging

from qtpy.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class TyphonTool(QWidget):
    """Mixin for all Typhon tool creation"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.devices = list()

    def add_device(self, device):
        """Add a new device to the tool"""
        logger.debug("Adding device %s ...", device.name)
        self.devices.append(device)

    @classmethod
    def from_device(cls, device, parent=None, **kwargs):
        """Create a new instance of the tool for a Device"""
        instance = cls(parent=parent, **kwargs)
        instance.add_device(device)
        return instance
