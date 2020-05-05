import ast
import collections.abc
import fnmatch
import functools
import logging
import ophyd
import os
import pathlib
import re
import sqlite3
import time

from qtpy import QtCore

import ophyd

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
        # NOTE: it's possible to disable the cache by clearing the environment
        # variable `TYPHOS_DATABASE_PATH`.
        db_path = get_describe_database_path()
        persistent_cache = _DescribeDatabase() if db_path else None
        _GLOBAL_DESCRIBE_CACHE = _GlobalDescribeCache(persistent_cache)
        persistent_cache.describe_cache = _GLOBAL_DESCRIBE_CACHE

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


def get_describe_database_path():
    """Get the typhos describe database path."""
    # Highest priority: TYPHOS_DATABASE_PATH
    env_path = os.environ.get('TYPHOS_DATABASE_PATH')
    if env_path:
        return env_path

    # Fall back to config_path/typhos_describe.sqlite
    config_path = utils.get_config_path()
    if config_path is None:
        # But if not accessible, do not use the disk
        return ':memory:'

    config_path = config_path / 'typhos_describe.sqlite'
    return str(os.environ.get('TYPHOS_DATABASE_PATH', config_path))


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

    persistent_cache : dict or _DescribeDatabase
        Cache that may persist between runs of typhos. Must support a ``.get``
        method that takes an :class:`OphydObj` instance, and a ``.clear``
        method with no arguments.
    """

    new_description = QtCore.Signal(object, dict)

    def __init__(self, persistent_cache=None):
        super().__init__()
        self._in_process = set()
        self.cache = {}
        if persistent_cache is None:
            persistent_cache = {}

        self.persistent_cache = persistent_cache

        self.connect_thread = utils.ObjectConnectionMonitorThread(parent=self)
        self.connect_thread.connection_update.connect(self._connection_update)
        self.connect_thread.start()

    def clear(self):
        """Clear the cache."""
        self.connect_thread.clear()
        self.cache.clear()
        # self.persistent_cache.clear()  # ?
        self._in_process.clear()

    def _describe(self, obj):
        """Retrieve the description of ``obj``."""
        try:
            if isinstance(obj, ophyd.NDDerivedSignal):
                # Force initial value readout otherwise _readback was never
                # set and that causes issues with more complex describe
                # types such as DerivedSignal and NDDerivedSignal.
                # TODO: This is a temporary fix and must be removed once
                #       https://github.com/bluesky/ophyd/pull/858 is merged
                obj.get()
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
            # Add the object, waiting for a connection update to call describe
            self.connect_thread.add_object(obj)
            desc = self.persistent_cache.get(obj)

            if desc is not None:
                self.cache[obj] = desc
                self.new_description.emit(obj, desc)
                return desc


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

        if self.cache.get(obj) != item:
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


# The default stale cached_path threshold time, in seconds:
TYPHOS_DISPLAY_PATH_CACHE_TIME = int(
    os.environ.get('TYPHOS_DISPLAY_PATH_CACHE_TIME', '600')
)


class _CachedPath:
    """
    A wrapper around pathlib.Path to support repeated globbing

    Parameters
    ----------
    path : pathlib.Path
        The path to cache

    Attributes
    ----------
    path : pathlib.Path
        The underlying path
    cache : list
        The cache of filenames
    _update_time : float
        The last time the cache was updated
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
        """Update the file list"""
        self.cache = os.listdir(self.path)
        self._update_time = time.monotonic()

    def glob(self, pattern):
        """Glob a pattern"""
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
        1. Environment variable ``PYDM_DISPLAYS_PATH``
        2. Typhos package built-in paths
    """

    def __init__(self):
        self.paths = []
        for path in utils.DISPLAY_PATHS:
            self.add_path(path)

    def add_path(self, path):
        """
        Add a path to be searched during ``glob``.

        Parameters
        ----------
        path : pathlib.Path or str
            The path to add.
        """
        path = pathlib.Path(path).expanduser().resolve()
        path = _CachedPath(
            path, stale_threshold=TYPHOS_DISPLAY_PATH_CACHE_TIME)
        if path not in self.paths:
            self.paths.append(path)


class _DescribeDatabase(collections.abc.Mapping):
    """
    An Sqlite3 database-backed cache of ophyd object descriptions

    Works in conjunction with :class:`_GlobalDescribeCache` by marking itself
    as its persistent cache.

    Attributes
    ----------
    cache : dict
        The cache holding descriptions, keyed on ``obj``
    """

    _columns = {
        # Each object should translate to one unique set of the next 4:
        'name': None,  # handled separately
        'class': None,  # handled separately
        'pvname': None,  # handled separately
        'setpoint_pvname': None,  # handled separately

        # Stashed keys from descriptions:
        'derived_from': str,
        'dtype': str,
        'enum_strs': repr,
        'precision': int,
        'shape': repr,
        'source': str,
        'units': str,

        'lower_ctrl_limit': float,
        'upper_ctrl_limit': float,
    }

    _key_cols = [col for col, dtype in _columns.items() if dtype is None]

    _type_map = {
        int: 'numeric',
        float: 'numeric',
        repr: 'text',
        str: 'text',
    }

    # NOTE: If the above schema changes, the version encoded in the table name
    # should be bumped (or the db should be wiped entirely)
    _version = 0
    _table_name = f'describe_cache_v{_version}'

    def __init__(self, path=None):
        super().__init__()
        self.log = logging.getLogger(__name__ + '._DescribeDatabase')
        self._describe_cache = None
        self._preload_cache = {}
        self._init_queries()
        self._init_database(path or get_describe_database_path())

    @property
    def path(self):
        """The database file path (or ':memory:')."""
        return self._path

    @property
    def describe_cache(self):
        """The in-memory describe cache - _GlobalDescribeCache."""
        return self._describe_cache

    @describe_cache.setter
    def describe_cache(self, cache):
        if self._describe_cache is not None:
            raise ValueError('describe_cache already set')

        self._describe_cache = cache
        cache.new_description.connect(self._new_description)
        # NOTE: this does not set the describe cache's persistent cache.

    def _init_queries(self):
        """Pre-create all queries sent to the database connection."""
        cols = ', '.join(f'{key} {self._type_map[value]}'
                         for key, value in self._columns.items()
                         if value is not None)

        self._create_query = f'''
            CREATE TABLE IF NOT EXISTS "{self._table_name}" (
                name text primary key,
                class text not null,
                pvname text,
                setpoint_pvname text,
                {cols})
        '''

        col_names = ', '.join(self._columns)
        empty_names = ', '.join('?' * len(self._columns))
        self._insert_query = f'''
            REPLACE INTO "{self._table_name}"
            ({col_names})
            VALUES ({empty_names})
        '''

        self._select_query = f'''
            SELECT * FROM "{self._table_name}" WHERE
            name=? AND
            class=? AND
            pvname=? AND
            setpoint_pvname=?
        '''

        self._select_key_query = f'''
            SELECT name, class, pvname, setpoint_pvname
            FROM "{self._table_name}"
        '''

        self._select_count_query = f'SELECT COUNT(*) FROM {self._table_name}'

        self.log.debug('Create query: %s', self._create_query)
        self.log.debug('Insert query: %s', self._insert_query)
        self.log.debug('Select query: %s', self._select_query)

    def _init_database(self, path):
        self._path = path
        self._con = sqlite3.connect(path)
        # Support __getitem__ in row access:
        self._con.row_factory = sqlite3.Row

        self.log.info('Describe database path: %s', path)
        self._con.execute(self._create_query)

        t0 = time.time()
        self._preload()
        elapsed = time.time() - t0
        self.log.info('Took %d ms to preload the cache', int(elapsed * 1000))

    def _preload(self):
        """Pre-load all entries from the database."""
        self._preload_cache = dict(self)

    def _get_key_from_object(self, obj):
        """Return a database key for the given object."""
        return (
            obj.name,
            obj.__class__.__name__,   # perhaps '.'join(mro())?
            getattr(obj, 'pvname', '') or '',
            getattr(obj, 'setpoint_pvname', '') or '',
        )

    def _stash_description(self, obj, desc):
        """
        Store a new (or updated) description in the database.

        Parameters
        ----------
        obj : :class:`ophyd.OphydObj`
            The object that the description belongs to
        desc : dict
            The object's description
        """
        items = list(self._get_key_from_object(obj))

        for key, dtype in self._columns.items():
            if dtype is not None:
                try:
                    value = desc.get(key)
                    if value is not None:
                        value = dtype(value)
                except Exception:
                    value = None
                items.append(value)

        with self._con:
            self._con.execute(self._insert_query, items)

    def _new_description(self, obj, desc):
        """New description retrieved via the ``_GlobalDescribeCache``."""
        try:
            self.log.debug('Stashing description for %r: %s', obj.name, desc)
            self._stash_description(obj, desc)
        except Exception:
            self.log.exception('Failed to save object description: %s %s',
                               obj.name, desc)

    def clear(self):
        """Clear the cache."""
        self._preload_cache.clear()
        self._con.execute(f'drop table {self._table_name}')
        self._con.commit()
        self._con.close()

        self._init_database(self.path)

    def _row_to_key(self, row):
        """
        Convert an :class:`sqlite3.Row` to a key.

        Parameters
        ----------
        row : :class:`sqlite3.Row`

        Returns
        -------
        key : tuple
            The key tuple which can be used in :meth:`.__getitem__`.
        """
        if not row:
            return None

        return tuple(
            row[key]
            for key, dtype in self._columns.items()
            if dtype is None
        )

    def _row_to_desc(self, row):
        """
        Convert an :class:`sqlite3.Row` to a description dictionary.

        Parameters
        ----------
        row : :class:`sqlite3.Row`

        Returns
        -------
        desc : dict or None
            The object description
        """
        if not row:
            return None

        desc = {}
        for key, dtype in self._columns.items():
            if dtype is None:
                continue

            try:
                value = row[key]
                if value is not None:
                    if dtype is repr:
                        # Convert back from the repr
                        desc[key] = ast.literal_eval(value)
                    else:
                        # Take the value as-is from the database
                        desc[key] = value
            except Exception:
                ...

        return desc

    def get(self, obj):
        """
        To access a description, call this method.

        Parameters
        ----------
        obj : :class:`ophyd.OphydObj`
            The object to get the description of

        Returns
        -------
        desc : dict or None
            If available in the cache, the description will be returned.
        """
        return self._select(self._get_key_from_object(obj))

    def _select(self, key):
        """Perform a SELECT on the given ``key``."""
        try:
            return self._preload_cache[key]
        except KeyError:
            cur = self._con.execute(self._select_query, key)
            desc = self._row_to_desc(cur.fetchone())
            if desc is not None:
                self._preload_cache[key] = desc
            return desc

    def __getitem__(self, item):
        if hasattr(item, 'name'):
            return self.get(item)
        return self._select(item)

    def __iter__(self):
        for row in self._con.execute(self._select_key_query):
            yield self._row_to_key(row)

    def __len__(self):
        cur = self._con.execute(self._select_count_query)
        return cur.fetchone()[0]

    def __repr__(self):
        return f'{self.__class__.__name__}(path={self.path})'
