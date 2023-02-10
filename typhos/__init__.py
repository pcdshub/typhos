from .version import __version__  # noqa: F401
from .display import TyphosDeviceDisplay
from .func import TyphosMethodButton
from .panel import TyphosCompositeSignalPanel, TyphosSignalPanel
from .plugins import register_signal
from .positioner import TyphosPositionerWidget
from .suite import TyphosSuite
from .utils import load_suite, patch_connect_slots, use_stylesheet

__all__ = [
    'use_stylesheet',
    'register_signal',
    'load_suite',
    'TyphosCompositeSignalPanel',
    'TyphosDeviceDisplay',
    'TyphosSuite',
    'TyphosSignalPanel',
    'TyphosPositionerWidget',
    'TyphosMethodButton',
]


# **NOTE** We patch QtCore.QMetaObject.connectSlotsByName to catch SystemError
# exceptions.
# We know this is not a good practice to do on import.  If you have a better
# solution, do let us know.
patch_connect_slots()

del patch_connect_slots
