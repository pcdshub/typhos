"""
Typhos handling of "variety" metadata and related utilities.
"""

import inspect
import logging

logger = logging.getLogger(__name__)
_variety_to_widget_class = {}


def _warn_unhandled(instance, metadata_key, value):
    if value is None:
        return

    logger.warning(
        '%s: Not yet implemented variety handling: key=%s value=%s',
        instance.__class__.__name__, metadata_key, value
    )


def _warn_unhandled_kwargs(instance, kwargs):
    for key, value in kwargs.items():
        _warn_unhandled(instance, key, value)


def _set_variety_key_handler(key):
    """
    A method wrapper to mark a specific variety metadata key with the method.

    Parameters
    ----------
    key : str
        The variety key (e.g., 'delta')
    """

    def wrapper(method):
        assert callable(method)
        if not hasattr(method, '_variety_handler'):
            method._variety_handler_keys = set()
        method._variety_handler_keys.add(key)
        return method

    return wrapper


def _get_variety_handlers(members):
    handlers = {}
    for attr, method in members:
        for key in getattr(method, '_variety_handler_keys', []):
            if key not in handlers:
                handlers[key] = [method]
            handlers[key].append(method)

    return handlers


def uses_variety_handler(cls):
    """
    Class wrapper to finish variety handler configuration.

    Parameters
    ----------
    cls : class
        The class to wrap.
    """
    cls._variety_handlers = _get_variety_handlers(inspect.getmembers(cls))
    return cls


def for_variety(variety, *, read=True, write=True):
    """
    A class wrapper to associate a specific variety with the class.

    Defaults to registering for both read and write widgets.

    Parameters
    ----------
    variety : str
        The variety (e.g., 'command')

    read : bool, optional
        Use for readback widgets

    write : bool, optional
        Use for setpoint widgets
    """

    known_varieties = {
        'array-histogram',
        'array-image',
        'array-nd',
        'array-timeseries',
        'bitmask',
        'command',
        'command-enum',
        'command-proc',
        'command-setpoint-tracks-readback',
        'enum',
        'scalar',
        'scalar-range',
        'scalar-tweakable',
        'text',
        'text-enum',
        'text-multiline',
    }

    if variety not in known_varieties:
        # NOTE: not kept in sync with pcdsdevices; so this wrapper may need
        # updating.
        raise ValueError(f'Not a known variety: {variety}')

    def wrapper(cls):
        if variety not in _variety_to_widget_class:
            _variety_to_widget_class[variety] = {}

        if read:
            _variety_to_widget_class[variety]['read'] = cls

        if write:
            _variety_to_widget_class[variety]['write'] = cls

        if not read and not write:
            raise ValueError('`write` or `read` must be set.')

        return cls

    return wrapper


def for_variety_read(variety):
    """`for_variety` shorthand for setting the readback widget class."""
    return for_variety(variety, read=True, write=False)


def for_variety_write(variety):
    """`for_variety` shorthand for setting the setpoint widget class."""
    return for_variety(variety, read=False, write=True)


def _get_widget_class_from_variety(desc, variety_md, read_only):
    variety = variety_md['variety']  # a required key
    read_key = 'read' if read_only else 'write'
    try:
        widget_cls = _variety_to_widget_class[variety].get(read_key)
    except KeyError:
        logger.error('Unsupported variety: %s (%s / %s)',
                     variety_md['variety'], desc, variety_md)
    else:
        if widget_cls is None:
            # TODO: remove
            logger.error('TODO no widget?: %s (%s / %s)',
                         variety_md['variety'], desc, variety_md)
        return widget_cls
