############
# Standard #
############
############
# External #
############
import numpy as np
from ophyd import Signal
from pydm.widgets import PyDMLineEdit
from pydm.utilities import close_widget_connections
import pytest

###########
# Package #
###########
from typhon.plugins.core import register_signal, signal_registry


@pytest.fixture(scope='function')
def widget_and_signal(qtbot):
    signal = Signal(name='my_signal', value=0)
    register_signal(signal)
    # This is a patch to get around some issues regarding the callbacks of
    # Signal. The software signal will never trigger connection callbacks,
    # and initializing the signal with a  value will not trigger a callback
    # either. It has been determined that changes need to be made to Ophyd to
    # make this not the case and it is not Typhon's responsibility. Therefore,
    # we patch our Signal as if it had sent out callbacks on connection and
    # first value update
    signal._args_cache['meta'] = ((), {'connected': True,
                                       'write_access': True})
    signal.put(1)
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://my_signal'
    yield widget, signal
    close_widget_connections(widget)
    # Pop the signal from the registry manually as the garbage collector for
    # some reason does not remove it between tests
    signal_registry.pop(signal.name)


@pytest.mark.parametrize('with_monitor', [False, True])
def test_signal_connection(qtbot, widget_and_signal, with_monitor):
    widget, signal = widget_and_signal
    # If we have seen a monitor update from the Signal the code does not need
    # to manually update. This option tests both the forced update and
    # subscription update routes
    if with_monitor:
        signal.put(2)
    qtbot.waitUntil(lambda: widget.value == signal.value, 2000)
    assert widget._write_access
    assert widget._connected


def test_repeated_connection(widget_and_signal, qtbot):
    widget, signal = widget_and_signal
    widget2 = PyDMLineEdit(init_channel=f'sig://{signal.name}')
    qtbot.addWidget(widget2)
    try:
        assert widget2._connected
        assert widget2._write_access
        assert widget2.value == signal.value
    finally:
        close_widget_connections(widget2)

def test_signal_disconnection(widget_and_signal):
    widget, signal = widget_and_signal
    close_widget_connections(widget)
    assert len(signal._callbacks['value']) == 0
    assert len(signal._callbacks['meta']) == 0


def test_signal_widget_write_to_signal(qtbot, widget_and_signal):
    widget, signal = widget_and_signal
    assert widget._write_access
    widget.write_to_channel(2)
    qtbot.waitUntil(lambda: signal.value == 2, 2000)


def test_signal_connection_metadata(qtbot, widget_and_signal):
    widget, signal = widget_and_signal
    signal._run_subs(sub_type=signal.SUB_META, connected=True,
                     write_acccess=False, enum_strs=('a', 'b', 'c'),
                     units='urad', precision=2, severity=1,
                     lower_ctrl_limit=-100, upper_ctrl_limit=100)
    qtbot.waitUntil(lambda: widget.enum_strings == ('a', 'b', 'c'), 2000)
    assert widget.enum_strings == ('a', 'b', 'c')
    assert widget._unit == 'urad'
    assert widget._prec == 2
    assert widget._alarm_state == 1
    assert widget._lower_ctrl_limit == -100
    assert widget._upper_ctrl_limit == 100


def test_nonexistant_widget(qtbot):
    signal = Signal(name='disconnected')
    register_signal(signal)
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = 'sig://disconnected'
    assert not widget._connected
    # We did not connect, but we subscribed so future connections will update
    # the user interface
    assert not widget._connected
    assert len(signal._callbacks['meta']) == 1


@pytest.mark.parametrize('value', ('True', 1, 3.14, np.ones(4)))
def test_signal_send_value_with_all_types(widget_and_signal, qtbot, value):
    widget, signal = widget_and_signal
    signal.put(value)
    if type(value) is np.ndarray:
        qtbot.waitUntil(lambda: all(widget.value == value), 3000)
    else:
        qtbot.waitUntil(lambda: widget.value == value, 3000)
