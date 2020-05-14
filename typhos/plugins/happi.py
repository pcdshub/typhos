import logging

from qtpy import QtCore

from happi import Client
from happi.errors import SearchError
from happi.loader import from_container
from pydm.data_plugins.plugin import PyDMConnection, PyDMPlugin


class HappiClientState:
    client = None


logger = logging.getLogger(__name__)


def register_client(client):
    """
    Register a Happi Client to be used with the DataPlugin.

    This is not required to be called by the user, if your environment is setup
    such that :meth:`happi.Client.from_config` will return the desired client.
    """
    HappiClientState.client = client


class HappiConnection(PyDMConnection):
    """A PyDMConnection to the Happi Database."""
    tx = QtCore.Signal(dict)

    def __init__(self, channel, address, protocol=None, parent=None):
        super().__init__(channel, address, protocol=protocol, parent=parent)
        self.add_listener(channel)

    def add_listener(self, channel):
        """Add a new channel to the existing connection."""
        super().add_listener(channel)
        # Connect our channel to the signal
        self.tx.connect(channel.tx_slot, QtCore.Qt.QueuedConnection)
        logger.debug("Loading %r from happi Client", channel)
        if '.' in self.address:
            device, child = self.address.split('.', 1)
        else:
            device, child = self.address, None
        # Load the device from the Client
        md = HappiClientState.client.find_device(name=device)
        obj = from_container(md)
        md = md.post()
        # If we have a child grab it
        if child:
            logger.debug("Retrieving child %r from %r",
                         child, obj.name)
            obj = getattr(obj, child)
            md = {'name': obj.name}
        # Send the device and metdata to all of our subscribers
        self.tx.emit({'obj': obj, 'md': md})

    def remove_listener(self, channel, destroying=False, **kwargs):
        """Remove a channel from the database connection."""
        super().remove_listener(channel, destroying=destroying, **kwargs)
        if not destroying:
            self.tx.disconnect(channel.tx_slot)


class HappiPlugin(PyDMPlugin):
    protocol = 'happi'
    connection_class = HappiConnection

    def add_connection(self, channel):
        # If we haven't made a Client by the time we need the Plugin. Try
        # and load one from configuration file
        if not HappiClientState.client:
            register_client(Client.from_config())
        try:
            super().add_connection(channel)
        except SearchError:
            logger.error("Unable to find device for %r in happi database.",
                         channel)
        except AttributeError as exc:
            logger.exception("Invalid attribute %r for address %r",
                             exc, channel.address)
        except Exception:
            logger.exception("Unable to load %r from happi", channel.address)
