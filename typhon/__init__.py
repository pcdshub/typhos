__all__ = ['TyphonDisplay', 'DeviceDisplay', 'use_stylesheet',
           'register_signal', 'TyphonSuite']
from .display import TyphonDisplay, DeviceDisplay
from .suite import TyphonSuite
from .utils import use_stylesheet
from .plugins import register_signal
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
