import warnings

from typhos import *

from .display import TyphonDeviceDisplay
from .func import TyphonMethodButton
from .positioner import TyphonPositionerWidget
from .signal import TyphonSignalPanel
from .suite import TyphonSuite
from .utils import load_suite, use_stylesheet

__all__ = ['use_stylesheet', 'register_signal', 'load_suite',
           'TyphonDeviceDisplay',
           'TyphonSuite',
           'TyphonSignalPanel',
           'TyphonPositionerWidget',
           'TyphonMethodButton'
           ]


deprecation_message = "WARNING: typhon was renamed to typhos along with all " \
                      "classes and methods that started with typhon or Typhon."

warnings.warn(deprecation_message, DeprecationWarning, stacklevel=2)
