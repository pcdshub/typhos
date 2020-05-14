"""
Module using line_profiler to measure code performance and diagnose slowdowns.
"""
import logging
from contextlib import contextmanager

from .utils import get_native_functions, get_submodules

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
def profiler_context(module_names=None, filename=None):
    """Context manager for profiling the cli typhos application."""
    setup_profiler(module_names=module_names)

    toggle_profiler(True)
    yield
    toggle_profiler(False)

    if filename is None:
        print_results()
    else:
        save_results(filename)


def setup_profiler(module_names=None):
    """
    Sets up the global profiler.

    Includes all functions and classes from all submodules of the given
    modules. This defaults to everything in the typhos module, but you can
    limit the scope by passing a particular submodule,
    e.g. module_names=['typhos.display'].
    """
    if module_names is None:
        module_names = ['typhos']

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
