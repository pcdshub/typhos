__all__ = ['TyphonDisplay', 'DeviceDisplay', 'ComponentButton']
from .plugins import SignalPlugin
from .display import TyphonDisplay, DeviceDisplay
from .widgets import ComponentButton
from pydm.data_plugins import add_plugin
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

add_plugin(SignalPlugin)
