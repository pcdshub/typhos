import logging

from qtpy.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class TyphonTool(QWidget):
    """Base widget for all Typhon Tool creation"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.devices = list()

    def add_device(self, device):
        """
        Add a new device to the tool

        Parameters
        ----------
        device : ophyd.Device
        """
        logger.debug("Adding device %s ...", device.name)
        self.devices.append(device)

    @classmethod
    def from_device(cls, device, parent=None, **kwargs):
        """
        Create a new instance of the tool for a Device

        Shortcut for:

        .. code::

            tool = TyphonTool()
            tool.add_device(device)

        Parameters
        ----------
        device: ophyd.Device

        parent: QWidget
        """
        instance = cls(parent=parent, **kwargs)
        instance.add_device(device)
        return instance
