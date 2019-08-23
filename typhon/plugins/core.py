from collections.abc import Iterable
import logging
import threading
from weakref import WeakValueDictionary
import numpy as np
from pydm.data_plugins.plugin import PyDMPlugin, PyDMConnection
from pydm.data_store import DataKeys

from ..utils import raise_to_operator

logger = logging.getLogger(__name__)

signal_registry = WeakValueDictionary()


def register_signal(signal):
    """
    Add a new Signal to the registry

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
    Connection to monitor an Ophyd Signal

    This is meant as a generalized connection to any type of Ophyd Signal. It
    handles reporting updates to listeners as well as pushing new values that
    users request in the PyDM interface back to the underlying signal

    The signal `data_type` is used to inform PyDM on the Python type that the
    signal will expect and emit. It is expected that this type is static
    through the execution of the application

    Attributes
    ----------
    signal : ophyd.Signal
        Stored signal object
    """
    def __init__(self, channel, address, protocol=None, parent=None):
        self._md_cid = None
        self._val_cid = None
        self._has_seen_value = threading.Event()
        # Collect our signal
        try:
            self.signal = signal_registry[address]
        except KeyError:
            logger.debug("Signal with name %r not found in signal registry!",
                         address)
            return
        # Create base connection
        super().__init__(channel, address, protocol=protocol, parent=parent)
        # Subscribe to the metadata state
        self._md_cid = self.signal.subscribe(self.send_new_metadata,
                                             event_type=self.signal.SUB_META,
                                             run=True)

    def receive_from_channel(self, payload):
        """
        Pass a value from the UI to Signal

        We are not guaranteed that this signal is writeable so catch exceptions
        if they are created. We attempt to cast the received value into the
        reported type of the signal unless it is of type ``np.ndarray``
        """
        logger.debug("Putting %r to %r", payload, self.address)
        if self.data.get(DataKeys.WRITE_ACCESS, False):
            try:
                new_val = payload[DataKeys.VALUE]
                self.signal.put(new_val)
            except Exception as exc:
                logger.exception("Unable to put %r to %s",
                                 payload,
                                 self.address)
                raise_to_operator(exc)
        else:
            logger.error("%r does not have write privileges",
                         self.signal.name)

    def send_new_value(self, value=None, **kwargs):
        """
        Update the UI with a new value from the Signal
        """
        # Here we make an effort to convert all arrays to be numpy arrays to
        # ease the burden on downstream widgets
        logger.debug("Sending value %r to %r", value, self.signal.name)
        if isinstance(value, Iterable) and not isinstance(value, str):
            value = np.asarray(value)
        # Send to widget
        self.data[DataKeys.VALUE] = value
        self.send_to_channel()
        self._has_seen_value.set()

    def send_new_metadata(self, connected=False, write_access=False,
                          severity=0, precision=0, enum_strs=None, units=None,
                          upper_ctrl_limit=None, lower_ctrl_limit=None,
                          **kw):
        """Send metadata from the Signal to the widget"""
        # We always need to send the connection and access states
        self.data[DataKeys.CONNECTION] = connected
        self.data[DataKeys.WRITE_ACCESS] = write_access
        # For other keys, only send them if we see them
        for md, key in ((severity, DataKeys.SEVERITY),
                        (precision, DataKeys.PRECISION),
                        (enum_strs, DataKeys.ENUM_STRINGS),
                        (units, DataKeys.UNIT),
                        (upper_ctrl_limit, DataKeys.UPPER_LIMIT),
                        (lower_ctrl_limit, DataKeys.LOWER_LIMIT)):
            # If we received a value, include in our packet
            if md:
                self.data[key] = md
        # If we just connected for the first time.
        if self._val_cid is None and connected:
            logger.debug("Initial connection of %r, subscribing to value",
                         self.address)
            self._val_cid = self.signal.subscribe(
                                            self.send_new_value,
                                            event_type=self.signal.SUB_VALUE,
                                            run=True)
            # If we did not fire the callback by subscribing we need to
            # manually ship out the information
            if not self._has_seen_value.is_set():
                self.send_to_channel()
        else:
            # Send our new metadata to the world
            logger.debug("Sending md %r", self.data)
            self.send_to_channel()

    def close(self):
        """Unsubscribe from the Ophyd signal"""
        logger.debug("Closing all subscriptions to %r for %r",
                     self.signal, self.address)
        # Knock off all of the subs
        if self._val_cid is not None:
            self.signal.unsubscribe(self._val_cid)
        if self._md_cid is not None:
            self.signal.unsubscribe(self._md_cid)
        # Perfrom basic PyDMConnection cleanup
        super().close()


class SignalPlugin(PyDMPlugin):
    """Plugin registered with PyDM to handle SignalConnection"""
    protocol = 'sig'
    connection_class = SignalConnection
