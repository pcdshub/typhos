"""
A generator of test devices.

These are meant to be used for targetted benchmarking and typically are
"extreme" in both size and in composition in order to make specific
loading issues more obvious.

Note that this currently only supports devices with uniform signals.
In the future it can be expanded to have Kind information, different
data types to test different widget types, etc.
"""
from ophyd.device import (Component as Cpt,
                          create_device_from_components as create_device)
from ophyd.signal import Signal


def make_test_device_class(name='TestClass', signal_class=Signal,
                           include_prefix=False, num_signals=10,
                           subdevice_layers=0, subdevice_spread=0):
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
        The number of signals to use in the test class. Note that this is the
        number of signals per bottom-level subdevice. Therefore, the actual
        total number of signals can be some multiple of this number.
        Defaults to 10.

    subdevice_layers : int, optional
        The number of subdevices we need to traverse down before seeing
        signals. For example, putting this at 0 results in no subdevices and
        all signals at the top level, while putting this at 2 gives us only
        subdevices at the top level, only subdevices on each of these
        subdevices, and only signals on these bottom-most subdevices.
        Has no effect if subdevice_spread is 0.
        Defaults to 0.

    subdevice_spread : int, optional
        The number of subdevices to include in each layer.
        Has no effect if subdevice_layers is 0.
        Defaults to 0
    """
    signals = {}
    for nsig in range(num_signals):
        if include_prefix:
            sig_cpt = Cpt(signal_class, f'SIGPV{nsig}')
        else:
            sig_cpt = Cpt(signal_class)
        signals[f'signum{nsig}'] = sig_cpt

    SignalHolder = create_device('SignalHolder', **signals)

    if all((subdevice_layers > 0, subdevice_spread > 0)):
        PrevClass = SignalHolder
        while subdevice_layers > 0:
            subdevices = {}
            for ndev in range(subdevice_spread):
                subdevices[f'devnum{ndev}'] = Cpt(PrevClass, f'PREFIX{ndev}:')
            ThisClass = create_device(f'Layer{subdevice_layers}', **subdevices)
            PrevClass = ThisClass
            subdevice_layers -= 1
    else:
        ThisClass = SignalHolder

    return create_device(name, base_class=ThisClass)
