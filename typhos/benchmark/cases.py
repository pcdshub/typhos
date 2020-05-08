"""
A collection of benchmarks to run for typhos.

These are included as standalone functions to make it easy to pass them into
arbitrary profiling modules.
"""
from collections import namedtuple
from contextlib import contextmanager
from functools import partial
from multiprocessing import Process
import signal
import os
import uuid

from caproto.server import pvproperty, PVGroup, run
from ophyd.signal import Signal, EpicsSignal, EpicsSignalBase

from .device import make_test_device_class as make_cls
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



def run_caproto_ioc(device_class, prefix):
    """
    Runs a dummy caproto IOC.

    Includes all the PVs that device_class will have if instantiated with
    prefix.

    Assumes only basic :class:`ophyd.Component` instances in the class
    definition.
    """
    pvprops = {}
    for suffix in yield_all_suffixes(device_class):
        pvprops[suffix] = pvproperty()

    DynIOC = type('DynIOC', (PVGroup,), pvprops)
    ioc = DynIOC(prefix)

    run(ioc.pvdb, module_name='caproto.asyncio.server',
        interfaces=['0.0.0.0'])


def yield_all_suffixes(device_class):
    """
    Iterates through all full pvname suffixes defined by device_class.

    Assumes only basic :class:`ophyd.Component` instances in the class
    definition.
    """
    for walk in device_class.walk_components():
        if issubclass(walk.item.cls, EpicsSignalBase):
            suffix = get_suffix(walk)
            yield suffix


def get_suffix(walk):
    """
    Returns the full pvname suffix from a ComponentWalk instance

    This means everything after the top-level device's prefix.
    Assumes that walk is an :class:`ophyd.signal.EpicsSignalBase`
    subclass and that it was defined using only
    :class:`ophyd.Component` in the device ancestors tree.
    """
    suffix = ''
    for cls, attr in zip(walk.ancestors, walk.dotted_name.split('.')):
        suffix += getattr(cls, attr).suffix
    return suffix


@contextmanager
def caproto_context(device_class, prefix):
    """
    Yields a caproto process with all elements of the input device.

    The caproto IOC will be run in a background process, making it suitable for
    testing devices in the main process.
    """
    proc = Process(target=run_caproto_ioc, args=(device_class, prefix))
    proc.start()
    yield
    if proc.is_alive():
        os.kill(proc.pid, signal.SIGKILL)


def random_prefix():
    """Returns a random prefix to avoid test cross-talk."""
    return str(uuid.uuid4())[:8] + ':'


@contextmanager
def nullcontext():
    """Stand-in for py3.7's contextlib.nullcontext"""
    yield


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
            test = benchmark_tests[benchmark]
            test()
