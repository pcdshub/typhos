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
                                  include_prefix=False, num_signals=100)
FlatEpics = make_test_device_class(name='FlatEpics', signal_class=EpicsSignal,
                                   include_prefix=True, num_signals=100)


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

    Currently only works for flat devices, e.g. no subdevices
    """
    pvprops = {}
    for walk in device_class.walk_components():
        cpt = walk.item
        if issubclass(cpt.cls, EpicsSignalBase):
            pvprops[cpt.suffix] = pvproperty()

    DynIOC = type('DynIOC', (PVGroup,), pvprops)
    ioc = DynIOC(prefix)

    run(ioc.pvdb, module_name='caproto.asyncio.server',
        interfaces=['0.0.0.0'])


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
