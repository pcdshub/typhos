"""
Helpful functions that don't belong in a more specific submodule.
"""
import importlib
import inspect
import logging
import pkgutil
import uuid
from contextlib import contextmanager
from inspect import isclass, isfunction, ismethod
from typing import Type

import ophyd

logger = logging.getLogger(__name__)


_optional_err = ('Optional dependency caproto missing from python '
                 'environment. Cannot test server.')

try:
    from caproto.tests.conftest import run_example_ioc
    has_caproto = True
except ImportError:
    has_caproto = False
    logger.debug(_optional_err)


@contextmanager
def caproto_context(
    device_class: Type[ophyd.Device],
    prefix: str,
    full_test_name: str,
    request=None,
):
    """
    Yields a caproto process with all elements of the input device.

    The caproto IOC will be run in a background process, making it suitable for
    testing devices in the main process.
    """
    if not has_caproto:
        raise ImportError(_optional_err)

    run_example_ioc(
        "typhos.benchmark.ioc",
        args=[prefix, full_test_name],
        pv_to_check="",
        request=request,
    )
    yield


def random_prefix():
    """Returns a random prefix to avoid test cross-talk."""
    return str(uuid.uuid4())[:8] + ':'


def is_native(obj, module):
    """
    Determines if obj was defined in module.

    Returns True if obj was defined in this module.
    Returns False if obj was not defined in this module.
    Returns None if we can't figure it out, e.g. if this is a primitive type.
    """
    try:
        return module.__name__ in obj.__module__
    except (AttributeError, TypeError):
        return None


def get_native_functions(module):
    """Returns a set of all functions and methods defined in module."""
    return get_native_methods(module, module)


def get_native_methods(cls, module, *, native_methods=None, seen=None):
    """Returns a set of all methods defined in cls that belong to module."""
    if native_methods is None:
        native_methods = set()
    if seen is None:
        seen = set()
    for _, obj in inspect.getmembers(cls):
        try:
            if obj in seen:
                continue
            seen.add(obj)
        except TypeError:
            # Unhashable type, definitely not a class or function
            continue
        if not is_native(obj, module):
            continue
        elif isclass(obj):
            get_native_methods(obj, module, native_methods=native_methods,
                               seen=seen)
        elif isfunction(obj):
            native_methods.add(obj)
        elif ismethod(obj):
            native_methods.add(obj)
    return native_methods


def get_submodules(module_name):
    """Returns a list of the imported module plus all submodules."""
    submodule_names = get_submodule_names(module_name)
    return import_modules(submodule_names)


def get_submodule_names(module_name):
    """
    Returns a list of the module name plus all importable submodule names.
    """
    module = importlib.import_module(module_name)
    submodule_names = [module_name]

    try:
        module_path = module.__path__
    except AttributeError:
        # This attr is missing if there are no submodules
        return submodule_names

    for info, submodule_name, is_pkg in pkgutil.walk_packages(module_path):
        if submodule_name != '__main__' and info.path in module_path:
            full_submodule_name = module_name + '.' + submodule_name
            submodule_names.append(full_submodule_name)
            if is_pkg:
                subsubmodule_names = get_submodule_names(full_submodule_name)
                submodule_names.extend(subsubmodule_names)
    return submodule_names


def import_modules(modules):
    """
    Utility function to import an iterator of module names as a list.

    Skips over modules that are not importable.
    """
    module_objects = []
    for module_name in modules:
        try:
            module_objects.append(importlib.import_module(module_name))
        except ImportError:
            pass
    return module_objects
