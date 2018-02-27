############
# Standard #
############
import sys
import logging
import importlib

###############
# Third Party #
###############
from pydm.data_plugins.plugin import PyDMConnection

##########
# Module #
##########

logger = logging.getLogger(__name__)


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

        conn = ClassConnection(cls://ophyd.EpicsMotor|'Tst:Mtr:07'|name=Test,
                               ophyd.EpicsMotor|'Tst:Mtr:07'|name=Test)

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
            # NOTE: This was taken entirely from happi/loader.py. The reason it
            # was not directly imported was to avoid an unneeded dependency

            # Parse the classname, arguments and keywords from the address
            # First assume the form {class}|{args}|{kwargs}
            try:
                cls, args, kwargs = address.split('|', 2)
            # Keyword arguments are optional i.e {class}|{args}
            except ValueError:
                cls, args = address.split('|', 1)
                kwargs = None
            # Import the class
            mod, cls = cls.rsplit('.', 1)
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
            # Create our object
            logger.debug("Instantiating %s ...", cls.__name__)
            self.obj = cls(*args, **kwargs)

    @classmethod
    def from_object(cls, obj):
        """
        Create a Connection object with an already instantiated object

        Parameters
        ----------
        obj : object
        """
        return cls(None, None, preassembled=obj)
