__all__ = [
    "SignalPlugin",
    "SignalConnection",
    "register_signal",
    "HappiPlugin",
    "HappiConnection",
    "register_client",
]
import logging

from .core import SignalConnection, SignalPlugin, register_signal

logger = logging.getLogger(__name__)

try:
    from .happi import HappiConnection, HappiPlugin, register_client
except ImportError:
    logger.debug("Unable to import HappiPlugin")
