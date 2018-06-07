from ophyd import Signal
from pydm.widgets.base import PyDMWritableWidget
from pydm.PyQt.QtGui import QWidget

from typhon.plugins.core import (SignalPlugin, SignalConnection,
                                 register_signal)

class WritableWidget(QWidget, PyDMWritableWidget):
    """Simple Testing Widget"""
    pass


def test_signal_connection(qapp):
    # Create a signal and attach our listener
    sig = Signal(name='my_signal', value=1)
    register_signal(sig)
    widget = WritableWidget()
    listener = widget.channels()[0]
    sig_conn = SignalConnection(listener, 'my_signal')
    sig_conn.add_listener(listener)
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
    sig_conn.remove_listener(listener)
    # Check that our signal is disconnected completely and maintains the same
    # value as the signal updates in the background
    sig.put(3)
    qapp.processEvents()
    assert widget.value == 2
    widget.send_value_signal.emit(1)
    qapp.processEvents()
    assert sig.get() == 3

def test_invalid_signal():
    widget = WritableWidget()
    listener = widget.channels()[0]
    # Invalid Signal
    sig_conn = SignalConnection(listener, 'my_signal')
    assert not widget._connected
    assert not widget._write_access
