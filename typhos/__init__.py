__all__ = ['use_stylesheet', 'register_signal', 'load_suite',
           'TyphosCompositeSignalPanel',
           'TyphosDeviceDisplay',
           'TyphosSuite',
           'TyphosSignalPanel',
           'TyphosPositionerWidget',
           'TyphosMethodButton', '__version__'
           ]

from ._version import get_versions
from .display import TyphosDeviceDisplay
from .func import TyphosMethodButton
from .panel import TyphosCompositeSignalPanel, TyphosSignalPanel
from .plugins import register_signal
from .positioner import TyphosPositionerWidget
from .suite import TyphosSuite
from .utils import load_suite, patch_connect_slots, use_stylesheet

# **NOTE** We patch QtCore.QMetaObject.connectSlotsByName to catch SystemError
# exceptions.
# We know this is not a good practice to do on import.  If you have a better
# solution, do let us know.
patch_connect_slots()

__version__ = get_versions()['version']
del get_versions
del patch_connect_slots
