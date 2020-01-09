import warnings

from typhos import *

__all__ = ['use_stylesheet', 'register_signal', 'load_suite',
           'TyphonDeviceDisplay',
           'TyphonSuite',
           'TyphonSignalPanel',
           'TyphonPositionerWidget',
           'TyphonMethodButton'
           ]

from .display import TyphonDeviceDisplay
from .func import TyphonMethodButton
from .suite import TyphonSuite
from .signal import TyphonSignalPanel
from .positioner import TyphonPositionerWidget
from .utils import use_stylesheet, load_suite

deprecation_message = "WARNING: typhon was renamed to typhos along with all " \
                      "classes and methods that started with typhon or Typhon."

warnings.warn(deprecation_message, DeprecationWarning, stacklevel=2)
