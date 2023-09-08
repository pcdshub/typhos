"""
This is a caproto IOC used for benchmarking/profiling typhos.

It's used internally by the typhos test suite, but it may also be run
on its own.To run it outside of the test suite, use the following:

```
python -m typhos.benchmark.ioc "PV:PREFIX" (benchmark_name)
```

Where benchmark_name is one of the supported tests:
* cube_connect
* cube_noconnect
* cube_soft
* deep_connect
* deep_noconnect
* deep_soft
* flat_connect
* flat_noconnect
* flat_soft
* wide_connect
* wide_noconnect
* wide_soft
"""
from __future__ import annotations

import logging
import sys
from typing import Generator

import ophyd
from caproto.server import PVGroup, pvproperty, run

from .cases import make_tests

logger = logging.getLogger(__name__)


def yield_all_suffixes(device_class: ophyd.Device) -> Generator[str, None, None]:
    """
    Iterates through all full pvname suffixes defined by device_class.

    Assumes only basic :class:`ophyd.Component` instances in the class
    definition.
    """
    for walk in device_class.walk_components():
        if issubclass(walk.item.cls, ophyd.signal.EpicsSignalBase):
            suffix = get_suffix(walk)
            yield suffix


def get_suffix(walk: ophyd.device.ComponentWalk) -> str:
    """
    Returns the full pvname suffix from a ComponentWalk instance.

    This means everything after the top-level device's prefix.
    Assumes that walk is an :class:`ophyd.signal.EpicsSignalBase`
    subclass and that it was defined using only
    :class:`ophyd.Component` in the device ancestors tree.
    """
    suffix = ''
    for cls, attr in zip(walk.ancestors, walk.dotted_name.split('.')):
        suffix += getattr(cls, attr).suffix
    return suffix


def print_usage() -> None:
    """Print usage of the test IOC."""
    print(f"Usage: {sys.argv[0]} PV:PREFIX test_name")
    print("Where test_name is one of the following:")
    classes, _, _ = make_tests()
    for cls in sorted(classes):
        print(f"* {cls}")


def run_caproto_ioc(prefix: str, test_name: str) -> None:
    """
    Runs a dummy caproto IOC.

    Includes all the PVs that device_class will have if instantiated with
    prefix.

    Assumes only basic :class:`ophyd.Component` instances in the class
    definition.
    """
    classes, _, _ = make_tests()
    try:
        device_class = classes[test_name]
    except KeyError:
        print(f"Unsupported test name provided: {test_name}", file=sys.stderr)
        print_usage()
        sys.exit(1)

    pvprops = {}
    for suffix in yield_all_suffixes(device_class):
        pvprops[suffix] = pvproperty()

    print(
        f"Running caproto IOC for test: {test_name} "
        f"with prefix {prefix!r} "
        f"Total PVs: {len(pvprops)}",
    )

    try:
        DynIOC = type("DynIOC", (PVGroup,), pvprops)
        ioc = DynIOC(prefix)
        run(ioc.pvdb, module_name="caproto.asyncio.server", interfaces=["0.0.0.0"])
    finally:
        print(f"Benchmark test IOC exiting {test_name} ({prefix!r})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)
    run_caproto_ioc(prefix=sys.argv[1], test_name=sys.argv[2])
