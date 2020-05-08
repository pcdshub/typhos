"""
A collection of benchmarks to run for typhos.

These are included as standalone functions to make it easy to pass them into
arbitrary profiling modules.
"""
from contextlib import contextmanager
from multiprocessing import Process
import uuid

from caproto.server import pvproperty, PVGroup, run
from ophyd.signal import Signal, EpicsSignal, EpicsSignalBase

from .device import make_test_device_class
from ..cli import launch_from_devices


# Create the test classes
FlatSoft = make_test_device_class(name='FlatSoft', signal_class=Signal,
                                  include_prefix=False, num_signals=1000)
                                  subdevice_layers=1, subdevice_spread=1)
FlatEpic = make_test_device_class(name='FlatEpic', signal_class=EpicsSignal,
                                  include_prefix=True, num_signals=1000)
                                  subdevice_layers=1, subdevice_spread=1)
WideSoft = make_test_device_class(name='WideSoft', signal_class=Signal,
                                  include_prefix=False, num_signals=1,
                                  subdevice_layers=1, subdevice_spread=1000)
WideEpic = make_test_device_class(name='WideEpics', signal_class=EpicsSignal,
                                  include_prefix=True, num_signals=1,
                                  subdevice_layers=1, subdevice_spread=1000)
DeepSoft = make_test_device_class(name='DeepSoft', signal_class=Signal,
                                  include_prefix=False, num_signals=1,
                                  subdevice_layers=1000, subdevice_spread=1)
DeepEpic = make_test_device_class(name='DeepEpic', signal_class=EpicsSignal,
                                  include_prefix=True, num_signals=1,
                                  subdevice_layers=1000, subdevice_spread=1)
CubeSoft = make_test_device_class(name='CubeSoft', signal_class=Signal,
                                  include_prefix=False, num_signals=10,
                                  subdevice_layers=10, subdevice_spread=10)
CubeEpic = make_test_device_class(name='CubeEpic', signal_class=EpicsSignal,
                                  include_prefix=True, num_signals=10,
                                  subdevice_layers=10, subdevice_spread=10)

benchmark_registry = {}


def run_benchmarks(benchmarks):
    if not benchmarks:
        for test in benchmark_registry.values():
            test()
    else:
        for benchmark in benchmarks:
            test = benchmark_registry[benchmark]
            test()


def register_benchmark(benchmark):
    global benchmark_registry
    benchmark_registry[benchmark.__name__] = benchmark
    return benchmark


def run_caproto_ioc(device_class, prefix):
    """
    Runs a dummy caproto IOC.

    Includes all the PVs that device_class will have if instantiate with
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
    proc.terminate()


def random_prefix():
    """Returns a random prefix to avoid test cross-talk."""
    return str(uuid.uuid4())[:8] + ':'


@register_benchmark
def test_flat_soft(auto_exit=True):
    """Launch typhos using a flat device with no EPICS connections."""
    launch_from_devices([FlatSoft('TEST:', name='test')],
                        auto_exit=auto_exit)


@register_benchmark
def test_flat_epics_no_connect(auto_exit=True):
    """Launch typhos using a flat device with failed EPICS connections."""
    launch_from_devices([FlatEpics('TEST:', name='test')],
                        auto_exit=auto_exit)


@register_benchmark
def test_flat_epics_caproto(auto_exit=True):
    """Launch typhos using a flat device backed by caproto."""
    prefix = random_prefix()
    with caproto_context(FlatEpics, prefix):
        launch_from_devices([FlatEpics(prefix, name='test')],
                            auto_exit=auto_exit)
