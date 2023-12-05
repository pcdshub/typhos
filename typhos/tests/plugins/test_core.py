from __future__ import annotations

import numpy as np
import pydm.utilities
import pytest
from ophyd import Component as Cpt
from ophyd import Device, Signal
from pydm import PyDMApplication
from pydm.widgets import PyDMLineEdit
from pytestqt.qtbot import QtBot

from typhos.plugins.core import (SignalConnection, register_signal,
                                 signal_registry)

from ..conftest import DeadSignal, RichSignal


def test_signal_connection(qapp, qtbot):
    # Create a signal and attach our listener
    sig = Signal(name='my_signal', value=1)
    register_signal(sig)
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://my_signal'
    listener = widget.channels()[0]
    # If PyDMChannel can not connect, we need to connect it ourselves
    # In PyDM > 1.5.0 this will not be neccesary as the widget will be
    # connected after we set the channel name
    if not hasattr(listener, 'connect'):
        pydm.utilities.establish_widget_connections(widget)
    # Check that our widget receives the initial value
    qapp.processEvents()
    assert widget._write_access
    assert widget._connected
    assert widget.value == 1
    # Check that we can push values back to the signal which in turn causes the
    # internal value at the widget to update
    widget.send_value_signal[int].emit(2)
    qapp.processEvents()
    qapp.processEvents()  # Must be called twice. Multiple rounds of signals
    assert sig.get() == 2
    assert widget.value == 2
    # Try changing types
    qapp.processEvents()
    qapp.processEvents()  # Must be called twice. Multiple rounds of signals
    # In PyDM > 1.5.0 we will not need the application to disconnect the
    # widget, but until then we have to check for the attribute
    if hasattr(listener, 'disconnect'):
        listener.disconnect()
    else:
        qapp.close_widget_connections(widget)
    # Check that our signal is disconnected completely and maintains the same
    # value as the signal updates in the background
    sig.put(3)
    qapp.processEvents()
    assert widget.value == 2
    widget.send_value_signal.emit(1)
    qapp.processEvents()
    assert sig.get() == 3


def test_dotted_name():
    class TestDevice(Device):
        test = Cpt(Signal)

    device = TestDevice(name='test')
    register_signal(device.test)

    assert 'test.test' in signal_registry


def test_metadata(qapp, qtbot):
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://md_signal'
    listener = widget.channels()[0]
    # Create a signal and attach our listener
    sig = RichSignal(name='md_signal', value=1)
    register_signal(sig)
    _ = SignalConnection(listener, 'md_signal')
    qapp.processEvents()
    # Check that metadata the metadata got there
    assert widget.enum_strings == ('a', 'b', 'c')
    assert widget._unit == 'urad'
    assert widget._prec == 2


def test_metadata_with_explicit_signal(qapp, qtbot):
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://md_signal'
    listener = widget.channels()[0]
    # Create a signal and attach our listener
    sig = RichSignal(name='md_signal', value=1)
    _ = SignalConnection(listener, 'md_signal', signal=sig)
    qapp.processEvents()
    # Check that metadata the metadata got there
    assert widget.enum_strings == ('a', 'b', 'c')
    assert widget._unit == 'urad'
    assert widget._prec == 2
    

MISSING = object()


@pytest.mark.parametrize(
    "sig_name,value,prec,expected",
    [
        # float: None -> 3
        ("none_prec_signal_float", 1.5, None, 3),
        # float: Missing -> 3
        ("missing_prec_signal_float", 1.5, MISSING, 3),
        # float: 4 -> 4
        ("prec_signal_float", 2.718, 4, 4),
        # np float: 5 -> 5
        ("prec_signal_np_float", np.float32(3.14), 5, 5),
        # int: None -> 0
        ("no_prec_signal_int", 1, None, 0),
        # int: 2 -> 2
        ("prec_signal_int", 2, 2, 2),
        # float: 0 -> 3
        ("zero_prec_float", 1.618, 0, 3),
        # float: -2 -> 3
        ("neg_prec_float", 4.5, -2, 3),
        # int: -30 -> 0
        ("neg_prec_int", 5, -30, 0),
    ],
)
def test_precision_defaults(
    sig_name: str,
    value: int | float | np.floating,
    prec: int | None,
    expected: int,
    qapp: PyDMApplication,
    qtbot: QtBot,
):
    """
    Expected behavior:

    - If a precision is zero, negative, or missing, use the
      default precision of 3 for floats, 0 for ints.
    - If a precision is valid and given, use the given precision.
    """
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = f"sig://{sig_name}"
    listener = widget.channels()[0]
    # Create a signal and attach our listener
    if prec is None:
        # Use normal signal defaults, incl precision=None
        sig = Signal(name=sig_name, value=value)
    elif prec is MISSING:
        # Force a fully empty metadata dict
        sig = RichSignal(
            name=sig_name,
            value=value,
            metadata={},
        )
    else:
        # Specify the precision precisely
        sig = RichSignal(
            name=sig_name,
            value=value,
            metadata={"precision": prec},
        )
    register_signal(sig)
    _ = SignalConnection(listener, sig_name)
    qapp.processEvents()
    assert widget._prec == expected


def test_disconnection(qtbot):
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://invalid'
    listener = widget.channels()[0]
    # Non-existant signal doesn't raise an error
    listener.connect()
    # Create a signal that will raise a TimeoutError
    sig = DeadSignal(name='broken_signal', value=1)
    register_signal(sig)
    listener.address = 'sig://broken_signal'
    # This should fail on the subscribe
    listener.connect()
    # This should fail on the get
    sig.subscribable = True
    _ = SignalConnection(listener, 'broken_signal')


def test_array_signal_send_value(qapp, qtbot):
    sig = Signal(name='my_array', value=np.ones(4))
    register_signal(sig)
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://my_array'
    qapp.processEvents()
    assert all(widget.value == np.ones(4))


def test_array_signal_put_value(qapp, qtbot):
    sig = Signal(name='my_array_write', value=np.ones(4))
    register_signal(sig)
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://my_array_write'
    widget.send_value_signal[np.ndarray].emit(np.zeros(4))
    qapp.processEvents()
    assert all(sig.get() == np.zeros(4))
