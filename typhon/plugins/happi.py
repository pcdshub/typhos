import logging

from happi import Client
from happi.loader import from_container
from happi.errors import SearchError
from pydm.data_plugins.plugin import PyDMPlugin, PyDMConnection
from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import Signal, Slot, QObject

_client = None
logger = logging.getLogger(__name__)


def register_client(client):
    """Register a Happi Client to be used with the DataPlugin"""
    global _client
    _client = client


class HappiChannel(PyDMChannel, QObject):
    """
    PyDMChannel to transport Device Information

    Parameters
    ----------
    tx_slot: callable
        Slot on widget to accept a dictionary of both the device and metadata
        information
    """
    def __init__(self, *, tx_slot, **kwargs):
        super().__init__(**kwargs)
        QObject.__init__(self)
        self._tx_slot = tx_slot
        self._last_md = None

    @Slot(dict)
    def tx_slot(self, value):
        """Transmission Slot"""
        # Do not fire twice for the same device
        if not self._last_md or self._last_md != value['md']:
            self._last_md = value['md']
            self._tx_slot(value)
        else:
            logger.debug("HappiChannel %r received same device. "
                         "Ignoring for now ...", self)


class HappiConnection(PyDMConnection):
    """A PyDMConnection to the Happi Database"""
    tx = Signal(dict)

    def __init__(self, channel, address, protocol=None, parent=None):
        super().__init__(channel, address, protocol=protocol, parent=parent)
        self.add_listener(channel)

    def add_listener(self, channel):
        """Add a new channel to the existing connection"""
        super().add_listener(channel)
        # Connect our channel to the signal
        self.tx.connect(channel.tx_slot)
        # Load the device from the Client
        md = _client.find_device(name=self.address)
        obj = from_container(md)
        # Send the device and metdata to all of our subscribers
        self.tx.emit({'obj': obj, 'md': md})

    def remove_listener(self, channel):
        """Remove a channel from the database connection"""
        super().remove_listener(channel)
        self.tx.disconnect(channel.tx_slot)


class HappiPlugin(PyDMPlugin):
    protocol = 'happi'
    connection_class = HappiConnection

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If we haven't made a Client by the time we register the Plugin. Try
        # and load one from configuration file
        if not _client:
            register_client(Client.from_config())

    def add_connection(self, channel):
        try:
            super().add_connection(channel)
        except SearchError:
            logger.error("Unable to find device for %r in happi database.",
                         channel)
        except Exception as exc:
            logger.exception("Unable to load %r from happi", channel.address)
