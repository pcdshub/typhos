__all__ = ['TyphonDisplay', 'DeviceDisplay', 'use_stylesheet',
           'register_signal']
from .display import TyphonDisplay, DeviceDisplay
from .utils import use_stylesheet
from .plugins import register_signal
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
