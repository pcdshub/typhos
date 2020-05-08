"""
A collection of benchmarks to run for typhos.

These are included as standalone functions to make it easy to pass them into
arbitrary profiling modules.
"""
from collections import namedtuple
from functools import partial

from ophyd.signal import Signal, EpicsSignal

from .device import make_test_device_class as make_cls
from .utils import caproto_context, nullcontext, random_prefix
from ..cli import launch_from_devices


# Define matrix of testing parameters
Shape = namedtuple('Shape', ['num_signals', 'subdevice_layers',
                             'subdevice_spread'])
SHAPES = dict(flat=Shape(1000, 1, 1),
              deep=Shape(1, 1000, 1),
              wide=Shape(1, 1, 1000),
              cube=Shape(10, 10, 10))

Test = namedtuple('Test', ['signal_class', 'include_prefix', 'start_ioc'])
TESTS = dict(soft=Test(Signal, False, False),
             connect=Test(EpicsSignal, True, True),
             noconnect=Test(EpicsSignal, True, False))


def generic_benchmark(cls, start_ioc, auto_exit=True):
    """Catch-all for simple benchmarks"""
    prefix = random_prefix()
    if start_ioc:
        context = caproto_context(cls, prefix)
    else:
        context = nullcontext()
    with context:
        launch_from_devices([cls(prefix, name='test')],
                            auto_exit=auto_exit)


def make_tests():
    """Returns all test classes and their associated tests."""
    classes = {}
    tests = {}
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
            test = partial(generic_benchmark, cls, test.start_ioc)
            tests[full_test_name] = test

    return classes, tests


benchmark_classes, benchmark_tests = make_tests()


def run_benchmarks(benchmarks):
    if not benchmarks:
        for test in benchmark_tests.values():
            test()
    else:
        for benchmark in benchmarks:
            try:
                test = benchmark_tests[benchmark]
            except KeyError:
                raise RuntimeError(f'{benchmark} is not a valid benchmark. '
                                   f'The full list of valid benchmarks is '
                                   f'{list(benchmark_tests.keys())}')
            test()
