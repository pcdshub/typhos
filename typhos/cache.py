import fnmatch
import functools
import logging
import os
import pathlib
import re
import time

from qtpy import QtCore

from . import utils
from .widgets import SignalWidgetInfo

logger = logging.getLogger(__name__)


# Global cache state. Do not use these directly, but instead use
# `get_global_describe_cache()` and `get_global_widget_type_cache()` below.
_GLOBAL_WIDGET_TYPE_CACHE = None
_GLOBAL_DESCRIBE_CACHE = None
_GLOBAL_DISPLAY_PATH_CACHE = None


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


def get_global_display_path_cache():
    """Get the _GlobalDisplayPathCache singleton."""
    global _GLOBAL_DISPLAY_PATH_CACHE
    if _GLOBAL_DISPLAY_PATH_CACHE is None:
        _GLOBAL_DISPLAY_PATH_CACHE = _GlobalDisplayPathCache()
    return _GLOBAL_DISPLAY_PATH_CACHE


class _GlobalDescribeCache(QtCore.QObject):
    """
    Cache of ophyd object descriptions.

    ``obj.describe()`` is called in a thread from the global QThreadPool, and
    new results are marked by the Signal ``new_description``.

    To access a description, call :meth:`.get`. If available, it will be
    returned immediately.  Otherwise, wait for the ``new_description`` Signal.

    Attributes
    ----------
    connect_thread : :class:`ObjectConnectionMonitorThread`
        The thread which monitors connection status.

    cache : dict
        The cache holding descriptions, keyed on ``obj``.
    """

    new_description = QtCore.Signal(object, dict)

    def __init__(self):
        super().__init__()
        self._in_process = set()
        self.cache = {}

        self.connect_thread = utils.ObjectConnectionMonitorThread(parent=self)
        self.connect_thread.connection_update.connect(
            self._connection_update, QtCore.Qt.QueuedConnection)
        self.connect_thread.start()

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
            The object to get the description of.

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
    Cache of ophyd object Typhos widget types.

    ``obj.describe()`` is called using :class:`_GlobalDescribeCache` and are
    therefore threaded and run in the background.  New results are marked by
    the Signal ``widgets_determined``.

    To access a set of widget types, call :meth:`.get`. If available, it will
    be returned immediately.  Otherwise, wait for the ``widgets_determined``
    Signal.

    Attributes
    ----------
    describe_cache : :class:`_GlobalDescribeCache`
        The describe cache, used for determining widget types.

    cache : dict
        The cache holding widget type information.
        Keyed on ``obj``, the values are :class:`SignalWidgetInfo` tuples.
    """

    widgets_determined = QtCore.Signal(object, SignalWidgetInfo)

    def __init__(self):
        super().__init__()
        self.cache = {}
        self.describe_cache = get_global_describe_cache()
        self.describe_cache.new_description.connect(self._new_description,
                                                    QtCore.Qt.QueuedConnection)

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
            The object to get the widget types.

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


# The default stale cached_path threshold time, in seconds:
TYPHOS_DISPLAY_PATH_CACHE_TIME = int(
    os.environ.get('TYPHOS_DISPLAY_PATH_CACHE_TIME', '600')
)


class _CachedPath:
    """
    A wrapper around pathlib.Path to support repeated globbing.

    Parameters
    ----------
    path : pathlib.Path
        The path to cache.

    Attributes
    ----------
    path : pathlib.Path
        The underlying path.
    cache : list
        The cache of filenames.
    _update_time : float
        The last time the cache was updated.
    stale_threshold : float, optional
        The time (in seconds) after which to update the path cache.  This
        happens on the next glob, and not on a timer-basis.
    """

    def __init__(self, path, *,
                 stale_threshold=TYPHOS_DISPLAY_PATH_CACHE_TIME):
        self.path = pathlib.Path(path)
        self.cache = None
        self._update_time = None
        self.stale_threshold = stale_threshold

    @classmethod
    def from_path(cls, path, **kwargs):
        """
        Get a cached path, if not already cached.

        Parameters
        ----------
        path : :class:`pathlib.Path` or :class:`_CachedPath`
            The paths to cache, if not already cached.
        """
        if isinstance(path, (cls, _GlobalDisplayPathCache)):
            # Already a _CachedPath
            return path
        return cls(path, **kwargs)

    def __hash__(self):
        # Keep the hash the same as the internal path for set()/dict() usage
        return hash(self.path)

    @property
    def time_since_last_update(self):
        """Time (in seconds) since the last update."""
        if self._update_time is None:
            return 0
        return time.monotonic() - self._update_time

    def update(self):
        """Update the file list."""
        self.cache = os.listdir(self.path)
        self._update_time = time.monotonic()

    def glob(self, pattern):
        """Glob a pattern."""
        if self.cache is None:
            self.update()
        elif self.time_since_last_update > self.stale_threshold:
            self.update()

        if any(c in pattern for c in '*?['):
            # Convert from glob syntax -> regular expression
            # And compile it for repeated usage.
            regex = re.compile(fnmatch.translate(pattern))
            for path in self.cache:
                if regex.match(path):
                    yield self.path / path
        else:
            # No globbing syntax: only check if file is in the list
            if pattern in self.cache:
                yield self.path / pattern


class _GlobalDisplayPathCache:
    """
    A cache for all configured display paths.

    All paths from `utils.DISPLAY_PATHS` will be included:
        1. Environment variable ``PYDM_DISPLAYS_PATH``.
        2. Typhos package built-in paths.
    """

    def __init__(self):
        self.paths = []
        for path in utils.DISPLAY_PATHS:
            self.add_path(path)

    def update(self):
        """Force a reload of all paths in the cache."""
        logger.debug('Clearing global path cache.')
        for path in self.paths:
            path.cache = None

    def add_path(self, path):
        """
        Add a path to be searched during ``glob``.

        Parameters
        ----------
        path : pathlib.Path or str
            The path to add.
        """
        logger.debug('Path added to _GlobalDisplayPathCache: %s', path)
        path = pathlib.Path(path).expanduser().resolve()
        path = _CachedPath(
            path, stale_threshold=TYPHOS_DISPLAY_PATH_CACHE_TIME)
        if path not in self.paths:
            self.paths.append(path)
