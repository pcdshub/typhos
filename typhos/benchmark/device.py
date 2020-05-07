"""
A generator of test devices.

These are meant to be used for targetted benchmarking and typically are
"extreme" in both size and in composition in order to make specific
loading issues more obvious.

Note that this currently only supports simple, flat devices.
In the future it can be expanded to have complicated nesting devices,
Kind information, different data types to test different widget types, etc.
"""
from ophyd.device import Device, Component as Cpt
from ophyd.signal import Signal


def make_test_device_class(name='TestClass', signal_class=Signal,
                           include_prefix=False, num_signals=10):
    """
    Creates a test :class:`ophyd.Device` subclass.

    Parameters
    ----------
    name : str, optional
        The name of the class.
        Defaults to 'TestClass'.

    signal_class : type, optional
        Picks which type of signal to use in the Device.
        Defaults to :class:`ophyd.Signal`.

    include_prefix : bool, optional
        If True, passes a string as a position argument into the signal
        components. This should be True for something like an
        :class:`ophyd.EpicsSignal` and False for something like a base
        :class:`ophyd.Signal`, depending on the required arguments.
        Defaults to False.

    num_signals : int, optional
        The number of signals to use in the test class.
        Defaults to 10.
    """
    signals = {}
    for nsig in range(num_signals):
        if include_prefix:
            sig_cpt = Cpt(signal_class, f'SIGPV{nsig}')
        else:
            sig_cpt = Cpt(signal_class)
        signals[f'signum{nsig}'] = sig_cpt

    return type(name, (Device,), signals)
