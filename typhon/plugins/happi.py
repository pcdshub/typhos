import logging

from happi import Client
from happi.loader import from_container
from happi.errors import SearchError
from pydm.data_plugins.plugin import PyDMPlugin, PyDMConnection

from pydm.data_store import DataKeys

_client = None
logger = logging.getLogger(__name__)


def register_client(client):
    """
    Register a Happi Client to be used with the DataPlugin

    This is not required to be called by the user, if your environment is setup
    such that ``happi.Client.from_config`` will return the desired client
    """
    global _client
    _client = client


class HappiConnection(PyDMConnection):
    """A PyDMConnection to the Happi Database"""

    def __init__(self, channel, address, protocol=None, parent=None):
        # Create base connection
        super().__init__(channel, address, protocol=protocol, parent=parent)
        logger.debug("Loading %r from happi Client", channel)
        # Default channel information
        self.data = {DataKeys.CONNECTION: False,
                     DataKeys.WRITE_ACCESS: False,
                     'metadata': dict(),
                     'object': None}
        try:
            # If we haven't made a Client by the time we need the Plugin. Try
            # and load one from configuration file
            if not _client:
                register_client(Client.from_config())
            if '.' in self.address:
                device, child = self.address.split('.', 1)
            else:
                device, child = self.address, None
            # Load the device from the Client
            md = _client.find_device(name=device)
            obj = from_container(md)
            md = md.post()
            # If we have a child grab it
            if child:
                logger.debug("Retrieving child %r from %r",
                             child, obj.name)
                obj = getattr(obj, child)
                md = {'name': obj.name}
        except SearchError:
            logger.error("Unable to find device for %r in happi database.",
                         channel)
        except AttributeError as exc:
            logger.exception("Invalid attribute %r for address %r",
                             exc, channel.address)
        except Exception:
            logger.exception("Unable to load %r from happi", channel.address)
        else:
            self.data['object'] = obj
            self.data['metadata'] = md
            self.data[DataKeys.CONNECTION] = True
        finally:
            self.send_to_channel()


class HappiPlugin(PyDMPlugin):
    protocol = 'happi'
    connection_class = HappiConnection
