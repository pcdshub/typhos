__all__ = ['SignalPlugin', 'SignalConnection', 'register_signal',
           'HappiPlugin', 'HappiConnection', 'register_client']
import logging

from pydm.data_plugins import add_plugin

from .core import SignalPlugin, SignalConnection, register_signal


logger = logging.getLogger(__name__)
add_plugin(SignalPlugin)

try:
    from .happi import HappiPlugin, HappiConnection, register_client
    add_plugin(HappiPlugin)
except ImportError:
    logger.warning("Unable to import HappiPlugin")
