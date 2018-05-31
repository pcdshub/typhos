__all__ = ['SignalPlugin', 'SignalConnection', 'register_signal']

from pydm.data_plugins import add_plugin

from .core import SignalPlugin, SignalConnection, register_signal

# Register SignalPlugin with PyDMApplication
add_plugin(SignalPlugin)
