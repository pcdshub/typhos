"""
Module using line_profiler to measure code performance and diagnose slowdowns.
"""
import importlib
import pkgutil

from line_profiler import LineProfiler


# Global profiler instance
PROFILER=None


def get_profiler():
    """Returns the global profiler instance, creating it if necessary."""
    global PROFILER
    if PROFILER is None:
        PROFILER = LineProfiler()
    return PROFILER


def setup_profiler(module_names=['typhos']):
    """
    Sets up the global profiler.

    Includes all functions and classes from all submodules of the given
    modules. This defaults to everything in the typhos module, but you can
    limit the scope by passing a particular submodule,
    e.g. module_names=['typhos.display']
    """
    modules = set()
    for module_name in module_names:
        submodule_names = get_submodule_names(module_name)
        modules.update(import_modules(submodule_names))

    profiler = get_profiler()
    for module in modules:
        profiler.add_module(module)


def save_results(filename):
    """Saves the formatted profiling results to filename."""
    profiler = get_profiler()
    with open(filename, 'w') as fd:
        profiler.print_stats(fd)


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
    """Utility function to import an interator of module names as a list."""
    return [importlib.import_module(mod) for mod in modules]
