"""
Module Docstring
"""
import logging

import numpy as np
from qtpy.QtCore import Qt, Slot

from ophyd.utils.epics_pvs import _type_map
from pydm.data_plugins.plugin import PyDMConnection, PyDMPlugin

from ..utils import raise_to_operator

logger = logging.getLogger(__name__)

signal_registry = dict()


def register_signal(signal):
    """
    Add a new Signal to the registry.

    The Signal object is kept within ``signal_registry`` for reference by name
    in the :class:`.SignalConnection`. Signals can be added multiple times and
    overwritten but a warning will be emitted.
    """
    # Warn the user if they are adding twice
    if signal.name in signal_registry:
        logger.debug("A signal named %s is already registered!", signal.name)
        return
    signal_registry[signal.name] = signal


class SignalConnection(PyDMConnection):
    """
    Connection to monitor an Ophyd Signal.

    This is meant as a generalized connection to any type of Ophyd Signal. It
    handles reporting updates to listeners as well as pushing new values that
    users request in the PyDM interface back to the underlying signal.

    The signal `data_type` is used to inform PyDM on the Python type that the
    signal will expect and emit. It is expected that this type is static
    through the execution of the application.

    Attributes
    ----------
    signal : ophyd.Signal
        Stored signal object.
    """
    supported_types = [int, float, str, np.ndarray]

    def __init__(self, channel, address, protocol=None, parent=None):
        # Create base connection
        super().__init__(channel, address, protocol=protocol, parent=parent)
        self.signal_type = None
        # Collect our signal
        self.signal = signal_registry[address]
        # Subscribe to updates from Ophyd
        self._cid = self.signal.subscribe(self.send_new_value,
                                          event_type=self.signal.SUB_VALUE)
        # Add listener
        self.add_listener(channel)

    def cast(self, value):
        """
        Cast a value to the correct Python type based on ``signal_type``.

        If ``signal_type`` is not set, the result of ``ophyd.Signal.describe``
        is used to determine what the correct Python type for value is. We need
        to be aware of the correct Python type so that we can emit the value
        through the correct signal and convert values returned by the widget to
        the correct type before handing them to Ophyd Signal.
        """
        # If this is the first time we are receiving a new value note the type
        # We make the assumption that signals do not change types during a
        # connection
        if not self.signal_type:
            dtype = self.signal.describe()[self.signal.name]['dtype']
            # Only way this raises a KeyError is if ophyd is confused
            self.signal_type = _type_map[dtype][0]
            logger.debug("Found signal type %r for %r. Using Python type %r",
                         dtype, self.signal.name, self.signal_type)

        logger.debug("Casting %r to %r", value, self.signal_type)
        if self.signal_type is np.ndarray:
            value = np.asarray(value)
        else:
            value = self.signal_type(value)
        return value

    @Slot(int)
    @Slot(float)
    @Slot(str)
    @Slot(np.ndarray)
    def put_value(self, new_val):
        """
        Pass a value from the UI to Signal.

        We are not guaranteed that this signal is writeable so catch exceptions
        if they are created. We attempt to cast the received value into the
        reported type of the signal unless it is of type ``np.ndarray``.
        """
        try:
            new_val = self.cast(new_val)
            logger.debug("Putting value %r to %r", new_val, self.address)
            self.signal.put(new_val)
        except Exception as exc:
            logger.exception("Unable to put %r to %s", new_val, self.address)
            raise_to_operator(exc)

    def send_new_value(self, value=None, **kwargs):
        """
        Update the UI with a new value from the Signal.
        """
        try:
            value = self.cast(value)
            self.new_value_signal[self.signal_type].emit(value)
        except Exception:
            logger.exception("Unable to update %r with value %r.",
                             self.signal.name, value)

    def add_listener(self, channel):
        """
        Add a listener channel to this connection.

        This attaches values input by the user to the `send_new_value` function
        in order to update the Signal object in addition to the default setup
        performed in PyDMConnection.
        """
        # Perform the default connection setup
        logger.debug("Adding %r ...", channel)
        super().add_listener(channel)
        # Report as no-alarm state
        self.new_severity_signal.emit(0)
        try:
            # Gather the current value
            signal_val = self.signal.get()
            # Gather metadata
            signal_desc = self.signal.describe()[self.signal.name]
        except Exception:
            logger.exception("Failed to gather proper information "
                             "from signal %r to initialize %r",
                             self.signal.name, channel)
            return
        # Report as connected
        self.write_access_signal.emit(True)
        self.connection_state_signal.emit(True)
        # Report metadata
        for (field, signal) in (
                    ('precision', self.prec_signal),
                    ('enum_strs', self.enum_strings_signal),
                    ('units', self.unit_signal)):
            # Check if we have metadata to send for field
            val = signal_desc.get(field)
            # If so emit it to our listeners
            if val:
                signal.emit(val)
        # Report new value
        self.send_new_value(signal_val)
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

    def remove_listener(self, channel, destroying=False, **kwargs):
        """
        Remove a listener channel from this connection.

        This removes the `send_new_value` connections from the channel in
        addition to the default disconnection performed in PyDMConnection.
        """
        logger.debug("Removing %r ...", channel)
        # Disconnect put_value from outgoing channel
        if channel.value_signal is not None and not destroying:
            for _typ in self.supported_types:
                try:
                    channel.value_signal[_typ].disconnect(self.put_value)
                except (KeyError, TypeError):
                    logger.debug("Unable to disconnect value_signal from %s "
                                 "for type %s", channel.address, _typ)
        # Disconnect any other signals
        super().remove_listener(channel, destroying=destroying, **kwargs)
        logger.debug("Successfully removed %r", channel)

    def close(self):
        """Unsubscribe from the Ophyd signal."""
        self.signal.unsubscribe(self._cid)


class SignalPlugin(PyDMPlugin):
    """Plugin registered with PyDM to handle SignalConnection."""
    protocol = 'sig'
    connection_class = SignalConnection

    def add_connection(self, channel):
        """Add a connection to a channel."""
        try:
            # Add a PyDMConnection for the channel
            super().add_connection(channel)
        # There is a chance that we raise an Exception on creation. If so,
        # don't add this to our list of good to go connections. The next
        # attempt we try again.
        except KeyError:
            logger.error("Unable to find signal for %r in signal registry."
                         "Use typhos.plugins.register_signal()",
                         channel)
        except Exception:
            logger.exception("Unable to create a connection to %r",
                             channel)
