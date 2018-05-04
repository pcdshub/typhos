############
# Standard #
############
import sys
import logging
import importlib

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


def obj_from_string(clsname, args=None, kwargs=None):
    """
    Create an object from a string specification

    Provide a name of a class as well as optional arguments and keywords. This
    class handles importing the class and instantiating a new object.

    Parameters
    ----------
    clsname : str

    args: optional
        Passed directly to class constructor

    kwargs: optional
        Passed directly to class constructor

    Returns
    -------
    obj: object
        Object of type ``clsname``
    """
    # Import the class
    mod, cls = clsname.rsplit('.', 1)
    if mod in sys.modules:
        mod = sys.modules[mod]
    else:
        logger.debug("Importing %s", mod)
        mod = importlib.import_module(mod)
    # Grab our device
    cls = getattr(mod, cls)
    # Format arguments
    if args:
        args = args.split(',')
    else:
        args = list()
    # Format keywords
    if kwargs:
        kwargs = dict([pair.split('=', 1)
                       for pair in kwargs.split(',')])
    else:
        kwargs = dict()
    # Create object
    return cls(*args, **kwargs)


class ClassConnection(PyDMConnection):
    """
    Connection which spawns an object of specified class

    Attributes
    ----------
    obj: object
        The created object is stored on the connection for use by subclasses

    Example
    -------
    .. code:: python

        conn = ClassConnection("cls://ophyd.EpicsMotor|'Tst:Mtr:07'|name=Test",
                               "ophyd.EpicsMotor|'Tst:Mtr:07'|name=Test")

    Notes
    -----
    "preassembled" provides a shortcut instead of creating a new object. This
    is useful if channel connections are being scripted programatically as
    opposed to from the Designer. The channel and address arguments are
    completely ignored in this case.
    """
    def __init__(self, channel, address, protocol=None,
                 parent=None, preassembled=None):
        # Base initialization
        super().__init__(channel, address, protocol=protocol, parent=parent)
        # Just use the preassambled object if given to us
        # Otherwise, instantiate our own
        logger.debug("Creating connection to %s", address)
        if preassembled:
            logger.debug("Using an already instantiated object as reference")
            self.obj = preassembled
        else:
            # Parse the classname, arguments and keywords from the address
            # First assume the form {class}|{args}|{kwargs}
            try:
                cls, args, kwargs = address.split('|', 2)
            # Keyword arguments are optional i.e {class}|{args}
            except ValueError:
                cls, args = address.split('|', 1)
                kwargs = None
            # Create our object
            logger.debug("Instantiating %s ...", cls)
            self.obj = obj_from_string(cls, args, kwargs)
        # Report the object as accessible and connected
        self.write_access_signal.emit(True)
        self.connection_state_signal.emit(True)

    @classmethod
    def from_object(cls, obj):
        """
        Create a Connection object with an already instantiated object

        Parameters
        ----------
        obj : object
        """
        return cls(None, None, preassembled=obj)


class SignalConnection(ClassConnection):
    """
    Connection to monitor an Ophyd Signal

    This is meant as a generalized connection to any type of Ophyd Signal. It
    handles reporting new values to listeners as well as pushing new
    values that users update in the PyDM interface back to the underlying
    signal

    Attributes
    ----------
    obj : ophyd.Signal
        Stored signal object

    Example
    -------
    .. code:: python

        conn = ClassConnection('sig://ophyd.Signal|name=Test',)
                               'ophyd.Signal|name=Test')
    """
    supported_types = [int, float, str, np.ndarray]

    def __init__(self, *args, **kwargs):
        # Create Signal
        super().__init__(*args, **kwargs)
        # Subscribe to updates from Ophyd
        self.obj.subscribe(self.send_new_value, event_type=self.obj.SUB_VALUE)
        self.signal_type = None

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
            self.obj.put(new_val)
        except Exception as exc:
            logger.exception("Unable to put %r to %s", new_val, self.obj.name)

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
        self.send_new_value(value=self.obj.get())
        # If the channel is used for writing to PVs, hook it up to the 'put'
        # methods.
        if channel.value_signal is not None:
            for _typ in self.supported_types:
                try:
                    channel.value_signal[_typ].connect(self.put_value,
                                                       Qt.QueuedConnection)
                except KeyError:
                    logger.debug("%s has no value_signal for type %s",
                                 channel.address, _typ)

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


class ClassPlugin(PyDMPlugin):
    """Plugin for generic Python objects"""
    protocol = 'obj'
    connection_class = ClassConnection


class SignalPlugin(PyDMPlugin):
    """Plugin for Ophyd Signal objects"""
    protocol = 'sig'
    connection_class = SignalConnection

