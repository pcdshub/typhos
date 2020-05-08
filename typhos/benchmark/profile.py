"""
Module using line_profiler to measure code performance and diagnose slowdowns.
"""
import importlib
import logging
import pkgutil
from contextlib import contextmanager
from inspect import isclass, isfunction

logger = logging.getLogger(__name__)

_optional_err = ('Optional dependency line_profiler missing from python '
                 'environment. Cannot run profiler.')
try:
    from line_profiler import LineProfiler
    has_line_profiler = True
except ImportError:
    has_line_profiler = False
    logger.debug(_optional_err)


# Global profiler instance
profiler = None


def get_profiler():
    """Returns the global profiler instance, creating it if necessary."""
    global profiler
    if not has_line_profiler:
        raise ImportError(_optional_err)
    elif profiler is None:
        profiler = LineProfiler()
    return profiler


@contextmanager
def profiler_context(module_names=[], filename=None):
    """Context manager for profiling the cli typhos application."""
    if not module_names:
        setup_profiler()
    else:
        setup_profiler(module_names)

    toggle_profiler(True)
    yield
    toggle_profiler(False)

    if filename is None:
        print_results()
    else:
        save_results(filename)


def setup_profiler(module_names=['typhos']):
    """
    Sets up the global profiler.

    Includes all functions and classes from all submodules of the given
    modules. This defaults to everything in the typhos module, but you can
    limit the scope by passing a particular submodule,
    e.g. module_names=['typhos.display']
    """
    profiler = get_profiler()

    functions = set()
    for module_name in module_names:
        modules = get_submodules(module_name)
        for module in modules:
            native_functions = get_native_functions(module)
            functions.update(native_functions)

    for function in functions:
        profiler.add_function(function)


def toggle_profiler(turn_on):
    """Turns the profiler off or on."""
    profiler = get_profiler()
    if turn_on:
        profiler.enable_by_count()
    else:
        profiler.disable_by_count()


def save_results(filename):
    """Saves the formatted profiling results to filename."""
    profiler = get_profiler()
    with open(filename, 'w') as fd:
        profiler.print_stats(fd, stripzeros=True, output_unit=1e-3)


def print_results():
    """Prints the formatted results directly to screen."""
    profiler = get_profiler()
    profiler.print_stats(stripzeros=True, output_unit=1e-3)


def is_native(obj, module):
    """Returns True if obj was defined in module."""
    return module.__name__ in obj.__module__


def get_native_functions(module):
    """Returns all functions and methods defined in module."""
    return get_native_methods(module, module)


def get_native_methods(cls, module):
    """Returns all methods defined in cls that belong to module."""
    native_methods = []
    for obj in cls.__dict__.values():
        if isclass(obj):
            inner_methods = get_native_methods(obj, module)
            native_methods.extend(inner_methods)
        elif isfunction(obj):
            if is_native(obj, module):
                native_methods.append(obj)
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

    for _, submodule_name, is_pkg in pkgutil.walk_packages(module_path):
        if submodule_name != '__main__':
            full_submodule_name = module_name + '.' + submodule_name
            submodule_names.append(full_submodule_name)
            if is_pkg:
                subsubmodule_names = get_submodule_names(full_submodule_name)
                submodule_names.extend(subsubmodule_names)
    return submodule_names


def import_modules(modules):
    """Utility function to import an iterator of module names as a list."""
    return [importlib.import_module(mod) for mod in modules]
