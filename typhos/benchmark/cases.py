"""
A collection of benchmarks to run for typhos.

These are included as standalone functions to make it easy to pass them into
arbitrary profiling modules.
"""
from collections import namedtuple
from functools import partial

from ophyd.signal import EpicsSignal, Signal

from ..app import launch_from_devices
from ..suite import TyphosSuite
from ..utils import nullcontext
from .device import make_test_device_class as make_cls
from .utils import caproto_context, random_prefix

# Define matrix of testing parameters
Shape = namedtuple('Shape', ['num_signals', 'subdevice_layers',
                             'subdevice_spread'])
# total_signals == num_signals * (subdevice_spread ** subdevice_layers)
SHAPES = dict(flat=Shape(100, 1, 1),
              deep=Shape(100, 25, 1),
              wide=Shape(1, 1, 100),
              cube=Shape(4, 2, 5))

Test = namedtuple('Test', ['signal_class', 'include_prefix', 'start_ioc'])
TESTS = dict(soft=Test(Signal, False, False),
             connect=Test(EpicsSignal, True, True),
             noconnect=Test(EpicsSignal, True, False))


def profiler_benchmark(cls, start_ioc, auto_exit=True):
    """
    Catch-all for simple profiler benchmarks.

    This handles the case where we want to do interactive diagnosis with the
    profiler and launch a screen.
    """
    prefix = random_prefix()
    with benchmark_context(start_ioc, cls, prefix):
        return launch_from_devices([cls(prefix, name='test')],
                                   auto_exit=auto_exit)


def unittest_benchmark(cls, start_ioc):
    """
    Catch-all for simple pytest benchmarking.

    This handles the case where we want to put our faith in qtbot to execute
    the launching of the screen. Therefore, we return the tools to the unit
    test instead of launching the screen ourselves.
    """
    prefix = random_prefix()
    context = benchmark_context(start_ioc, cls, prefix)
    suite = TyphosSuite.from_device(cls(prefix, name='test'))
    return suite, context


def benchmark_context(start_ioc, cls, prefix):
    """Context manager that starts an ioc, or not."""
    if start_ioc:
        context = caproto_context(cls, prefix)
    else:
        context = nullcontext()
    return context


def make_tests():
    """Returns all test classes and their associated tests."""
    classes = {}
    profiler_tests = {}
    unit_tests = {}
    for shape_name, shape in SHAPES.items():
        for test_name, test in TESTS.items():
            cls_name = shape_name.title() + test_name.title()
            cls = make_cls(name=cls_name,
                           signal_class=test.signal_class,
                           include_prefix=test.include_prefix,
                           num_signals=shape.num_signals,
                           subdevice_layers=shape.subdevice_layers,
                           subdevice_spread=shape.subdevice_spread)
            classes[cls_name] = cls

            full_test_name = shape_name + '_' + test_name
            profiler_test = partial(profiler_benchmark, cls, test.start_ioc)
            profiler_tests[full_test_name] = profiler_test
            unit_test = partial(unittest_benchmark, cls, test.start_ioc)
            unit_tests[full_test_name] = unit_test

    return classes, profiler_tests, unit_tests


benchmark_classes, profiler_tests, unit_tests = make_tests()


def run_benchmarks(benchmarks):
    windows = []
    if not benchmarks:
        for test in profiler_tests.values():
            windows.append(test(auto_exit=True))
    else:
        for benchmark in benchmarks:
            test = get_profiler_test(benchmark)
            windows.append(test(auto_exit=True))
    return windows


def interactive_benchmark(benchmark):
    test = get_profiler_test(benchmark)
    return test(auto_exit=False)


def get_profiler_test(benchmark):
    try:
        return profiler_tests[benchmark]
    except KeyError:
        raise RuntimeError(f'{benchmark} is not a valid benchmark. '
                           'The full list of valid benchmarks is '
                           f'{list(profiler_tests.keys())}')
