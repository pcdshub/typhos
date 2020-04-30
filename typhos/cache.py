import functools
import logging

from qtpy import QtCore

from . import utils
from .widgets import SignalWidgetInfo

logger = logging.getLogger(__name__)


# Global cache state. Do not use these directly, but instead use
# `get_global_describe_cache()` and `get_global_widget_type_cache()` below.
_GLOBAL_WIDGET_TYPE_CACHE = None
_GLOBAL_DESCRIBE_CACHE = None


def get_global_describe_cache():
    """Get the _GlobalDescribeCache singleton."""
    global _GLOBAL_DESCRIBE_CACHE
    if _GLOBAL_DESCRIBE_CACHE is None:
        _GLOBAL_DESCRIBE_CACHE = _GlobalDescribeCache()
    return _GLOBAL_DESCRIBE_CACHE


def get_global_widget_type_cache():
    """Get the _GlobalWidgetTypeCache singleton."""
    global _GLOBAL_WIDGET_TYPE_CACHE
    if _GLOBAL_WIDGET_TYPE_CACHE is None:
        _GLOBAL_WIDGET_TYPE_CACHE = _GlobalWidgetTypeCache()
    return _GLOBAL_WIDGET_TYPE_CACHE


class _GlobalDescribeCache(QtCore.QObject):
    """
    Cache of ophyd object descriptions

    ``obj.describe()`` is called in a thread from the global QThreadPool, and
    new results are marked by the Signal ``new_description``.

    To access a description, call :meth:`.get`. If available, it will be
    returned immediately.  Otherwise, wait for the ``new_description`` Signal.

    Attributes
    ----------
    connect_thread : :class:`ObjectConnectionMonitorThread`
        The thread which monitors connection status

    cache : dict
        The cache holding descriptions, keyed on ``obj``
    """

    new_description = QtCore.Signal(object, dict)

    def __init__(self):
        super().__init__()
        self.connect_thread = utils.ObjectConnectionMonitorThread(parent=self)
        self.connect_thread.connection_update.connect(self._connection_update)
        self.connect_thread.start()

        self._in_process = set()
        self.cache = {}

    def clear(self):
        """Clear the cache."""
        self.connect_thread.clear()
        self.cache.clear()
        self._in_process.clear()

    def _describe(self, obj):
        """Retrieve the description of ``obj``."""
        try:
            return obj.describe()[obj.name]
        except Exception:
            logger.error("Unable to connect to %r during widget creation",
                         obj.name)
        return {}

    def _worker_describe(self, obj):
        """
        This is the worker thread method that gets run in the thread pool.

        It calls describe, updates the cache, and emits a signal when done.
        """
        try:
            self.cache[obj] = desc = self._describe(obj)
            self.new_description.emit(obj, desc)
        except Exception as ex:
            logger.exception('Worker describe failed: %s', ex)
        finally:
            self._in_process.remove(obj)

    @QtCore.Slot(object, bool, dict)
    def _connection_update(self, obj, connected, metadata):
        """
        A connection callback from the connection monitor thread.
        """
        if not connected:
            return
        elif self.cache.get(obj) or obj in self._in_process:
            return

        self._in_process.add(obj)
        func = functools.partial(self._worker_describe, obj)
        QtCore.QThreadPool.globalInstance().start(
            utils.ThreadPoolWorker(func)
        )

    def get(self, obj):
        """
        To access a description, call this method. If available, it will be
        returned immediately.  Otherwise, upon connection and successful
        ``describe()`` call, the ``new_description`` Signal will be emitted.

        Parameters
        ----------
        obj : :class:`ophyd.OphydObj`
            The object to get the description of

        Returns
        -------
        desc : dict or None
            If available in the cache, the description will be returned.
        """
        try:
            return self.cache[obj]
        except KeyError:
            # Add the object, waiting for a connection update to determine
            # widget types
            self.connect_thread.add_object(obj)


class _GlobalWidgetTypeCache(QtCore.QObject):
    """
    Cache of ophyd object Typhos widget types

    ``obj.describe()`` is called using :class:`_GlobalDescribeCache` and are
    therefore threaded and run in the background.  New results are marked by
    the Signal ``widgets_determined``.

    To access a set of widget types, call :meth:`.get`. If available, it will
    be returned immediately.  Otherwise, wait for the ``widgets_determined``
    Signal.

    Attributes
    ----------
    describe_cache : :class:`_GlobalDescribeCache`
        The describe cache, used for determining widget types

    cache : dict
        The cache holding widget type information.
        Keyed on ``obj``, the values are :class:`SignalWidgetInfo` tuples.
    """

    widgets_determined = QtCore.Signal(object, SignalWidgetInfo)

    def __init__(self):
        super().__init__()
        self.cache = {}
        self.describe_cache = get_global_describe_cache()
        self.describe_cache.new_description.connect(self._new_description)

    def clear(self):
        """Clear the cache."""
        self.cache.clear()

    @QtCore.Slot(object, dict)
    def _new_description(self, obj, desc):
        """New description: determine widget types and update the cache."""
        if not desc:
            # Marks an error in retrieving the description
            # TODO: show error widget or some default widget?
            return

        item = SignalWidgetInfo.from_signal(obj, desc)
        logger.debug('Determined widgets for %s: %s', obj.name, item)
        self.cache[obj] = item
        self.widgets_determined.emit(obj, item)

    def get(self, obj):
        """
        To access widget types, call this method. If available, it will be
        returned immediately.  Otherwise, upon connection and successful
        ``describe()`` call, the ``widgets_determined`` Signal will be emitted.

        Parameters
        ----------
        obj : :class:`ophyd.OphydObj`
            The object to get the widget types

        Returns
        -------
        desc : :class:`SignalWidgetInfo` or None
            If available in the cache, the information will be returned.
        """
        try:
            return self.cache[obj]
        except KeyError:
            # Add the signal, waiting for a connection update to determine
            # widget types
            desc = self.describe_cache.get(obj)
            if desc is not None:
                # In certain scenarios (such as testing) this might happen
                self._new_description(obj, desc)
