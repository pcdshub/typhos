"""
Helpful functions that don't belong in a more specific submodule
"""
import signal
import os
import uuid
from contextlib import contextmanager
from multiprocessing import Process

from caproto.server import pvproperty, PVGroup, run
from ophyd.signal import EpicsSignalBase


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


@contextmanager
def nullcontext():
    """Stand-in for py3.7's contextlib.nullcontext"""
    yield


def random_prefix():
    """Returns a random prefix to avoid test cross-talk."""
    return str(uuid.uuid4())[:8] + ':'
