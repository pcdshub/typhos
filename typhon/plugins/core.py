"""
Module Docstring
"""
############
# Standard #
############
import logging

###############
# Third Party #
###############
import numpy as np
from pydm.data_plugins.plugin import PyDMPlugin, PyDMConnection
from pydm.PyQt.QtCore import pyqtSlot, Qt

##########
# Module #
##########

logger = logging.getLogger(__name__)

signal_registry = dict()


def register_signal(signal):
    """Add a new Signal to the registry"""
    # Warn the user if they are adding twice
    if signal.name in signal_registry:
        logger.error("A signal named %s is already registered!", signal.name)
        return
    signal_registry[signal.name] = signal


class SignalConnection(PyDMConnection):
    """
    Connection to monitor an Ophyd Signal

    This is meant as a generalized connection to any type of Ophyd Signal. It
    handles reporting updates to listeners as well as pushing new values that
    users request in the PyDM interface back to the underlying signal

    Attributes
    ----------
    signal : ophyd.Signal
        Stored signal object

    Example
    -------
    .. code:: python
        conn = ClassConnection('sig://ophyd.Signal|name=Test',)
                               'ophyd.Signal|name=Test')
    """
    supported_types = [int, float, str, np.ndarray]

    def __init__(self, channel, address, protocol=None, parent=None):
        # Create base connection
        super().__init__(channel, address, protocol=protocol, parent=parent)
        self.signal_type = None
        # Get Signal from registry
        try:
            self.signal = signal_registry[address]
        except KeyError as exc:
            logger.exception("Unable to find signal %s in signal registry."
                             "Use typhon.plugins.register_signal()",
                             address)
            # Report as disconnected
            self.signal = None
        else:
            # Subscribe to updates from Ophyd
            self.signal.subscribe(self.send_new_value,
                                  event_type=self.signal.SUB_VALUE)

    @pyqtSlot(int)
    @pyqtSlot(float)
    @pyqtSlot(str)
    @pyqtSlot(np.ndarray)
    def put_value(self, new_val):
        """
        Pass a value from the UI to Signal
        We are not guaranteed that this signal is writeable so catch exceptions
        if they are created
        """
        try:
            self.signal.put(new_val)
        except Exception as exc:
            logger.exception("Unable to put %r to %s", new_val, self.address)

    def send_new_value(self, value=None, **kwargs):
        """
        Update the UI with a new value from the Signal
        """
        # If this is the first time we are receiving a new value note the type
        # We make the assumption that signals do not change types during a
        # connection
        if not self.signal_type:
            self.signal_type = type(value)
        self.new_value_signal[self.signal_type].emit(value)

    def add_listener(self, channel):
        """
        Add a listener channel to this connection
        This attaches values input by the user to the `send_new_value` function
        in order to update the Signal object in addition to the default setup
        performed in PyDMConnection
        """
        # Perform the default connection setup
        super().add_listener(channel)
        # Send the most recent value to the channel
        if self.signal:
            # Report as connected
            self.write_access_signal.emit(True)
            self.connection_state_signal.emit(True)
            self.send_new_value(value=self.signal.get())
            # If the channel is used for writing to PVs, hook it up to the
            # 'put' methods.
            if channel.value_signal is not None:
                for _typ in self.supported_types:
                    try:
                        val_sig = channel.value_signal[_typ]
                        val_sig.connect(self.put_value, Qt.QueuedConnection)
                    except KeyError:
                        logger.debug("%s has no value_signal for type %s",
                                     channel.address, _typ)
        else:
            self.write_access_signal.emit(False)
            self.connection_state_signal.emit(False)

    def remove_listener(self, channel):
        """
        Remove a listener channel from this connection

        This removes the `send_new_value` connections from the channel in
        addition to the default disconnection performed in PyDMConnection
        """
        # Disconnect put_value from outgoing channel
        if channel.value_signal is not None:
            for _typ in self.supported_types:
                try:
                    channel.value_signal[_typ].disconnect(self.put_value)
                except KeyError:
                    logger.debug("Unable to disconnect value_signal from %s "
                                 "for type %s", channel.address, _typ)
        # Disconnect any other signals
        super().remove_listener(channel)


class SignalPlugin(PyDMPlugin):
    protocol = 'sig'
    connection_class = SignalConnection
