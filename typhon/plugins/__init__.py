__all__ = ['SignalPlugin', 'SignalConnection', 'register_signal',
           'HappiPlugin', 'HappiConnection', 'HappiChannel']

from pydm.data_plugins import add_plugin

from .core import SignalPlugin, SignalConnection, register_signal
from .happi import HappiPlugin, HappiConnection, HappiChannel

# Register custom plugins PyDMApplication
add_plugin(SignalPlugin)
add_plugin(HappiPlugin)
