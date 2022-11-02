from unittest.mock import Mock

import pytest
from ophyd import Component as Cpt
from ophyd import Signal
from ophyd.device import Device
from ophyd.positioner import SoftPositioner
from ophyd.sim import SynAxis
from ophyd.utils.errors import LimitError, UnknownStatusFailure

from typhos.positioner import TyphosPositionerWidget
from typhos.utils import SignalRO

from .conftest import RichSignal, show_widget


class SimMotor(SynAxis):
    low_limit_switch = Cpt(SignalRO, value=0)
    high_limit_switch = Cpt(SignalRO, value=0)
    low_limit = Cpt(Signal, value=-10)
    high_limit = Cpt(Signal, value=10)
    motor_is_moving = Cpt(RichSignal,
                          value=0,
                          metadata={
                            'enum_strs': ('not moving', 'moving')
                          })
    stop = Mock()
    clear_error = Mock()

    # TODO: fix upstream - Mock interferes with @required_for_connection
    stop._required_for_connection = False
    clear_error._required_for_connection = False

    # PositionerBase has a timeout arg, SynAxis does not
    def set(self, value, timeout=None):
        self.check_value(value)
        return super().set(value)

    def check_value(self, pos: float):
        if not self.low_limit.get() <= pos <= self.high_limit.get():
            raise LimitError('Sim limits error')


@pytest.fixture(scope='function')
def motor_widget(qtbot):
    motor = SimMotor(name='test')
    widget = TyphosPositionerWidget()
    widget.readback_attribute = 'readback'
    widget.add_device(motor)
    qtbot.addWidget(widget)
    yield motor, widget
    if widget._status_thread and widget._status_thread.isRunning():
        widget._status_thread.wait()


def test_positioner_widget_no_limits(qtbot, motor):
    setwidget = TyphosPositionerWidget.from_device(motor)
    qtbot.addWidget(setwidget)
    for widget in ('low_limit', 'low_limit_switch',
                   'high_limit', 'high_limit_switch'):
        assert getattr(setwidget.ui, widget).isHidden()


def test_positioner_widget_fixed_limits(qtbot, motor):
    motor.limits = (-10, 10)
    widget = TyphosPositionerWidget.from_device(motor)
    qtbot.addWidget(widget)
    assert widget.ui.low_limit.text() == '-10'
    assert widget.ui.high_limit.text() == '10'


@show_widget
def test_positioner_widget_with_signal_limits(motor_widget):
    motor, widget = motor_widget
    # Check limit switches
    low_limit_chan = widget.ui.low_limit_switch.channel
    assert motor.low_limit_switch.name in low_limit_chan
    high_limit_chan = widget.ui.high_limit_switch.channel
    assert motor.high_limit_switch.name in high_limit_chan
    motor.delay = 3.  # Just for visual testing purposes
    return widget


def test_positioner_widget_readback(motor_widget):
    motor, widget = motor_widget
    assert motor.readback.name in widget.ui.user_readback.channel


def test_positioner_widget_stop(motor_widget):
    motor, widget = motor_widget
    widget.stop()
    assert motor.stop.called_with(success=True)


class NoMoveSoftPos(SoftPositioner, Device):
    """
    SoftPositioner that does not move.

    This allows us to "stop" the move at any time.
    This must be a device for inclusion in the widget,
    as typhos calls "walk_signals".
    """
    def _setup_move(self, *args, **kwargs):
        ...


def test_positioner_widget_stop_no_error(motor_widget):
    _, widget = motor_widget
    motor = NoMoveSoftPos(name='motor')
    widget.add_device(motor)
    # Calling stop on the motor directly is an error status
    status = motor.move(1, wait=False)
    motor.stop()
    with pytest.raises(UnknownStatusFailure):
        # Raises if the outcome is an exception
        status.wait(timeout=1)
    # But the button should avoid this pitfall and have no error
    status = motor.move(2, wait=False)
    widget.stop()
    # Raises if the outcome is an exception
    status.wait(timeout=1)


def test_positioner_widget_set(motor_widget):
    motor, widget = motor_widget
    # Check motion
    widget.ui.set_value.setText('4')
    widget.ui.set()
    assert motor.position == 4


def test_positioner_widget_positive_tweak(motor_widget):
    motor, widget = motor_widget
    widget.ui.tweak_value.setText('1')
    widget.positive_tweak()
    assert widget.ui.set_value.text() == '1.0'
    assert motor.position == 1


def test_positioner_widget_negative_tweak(motor_widget):
    motor, widget = motor_widget
    widget.ui.tweak_value.setText('1')
    widget.negative_tweak()
    assert widget.ui.set_value.text() == '-1.0'
    assert motor.position == -1


def test_positioner_widget_moving_property(motor_widget, qtbot):
    motor, widget = motor_widget
    assert not widget.moving
    motor.delay = 1.
    widget.ui.set_value.setText('34')
    widget.set()
    qtbot.waitUntil(lambda: widget.moving, timeout=500)
    qtbot.waitUntil(lambda: not widget.moving, timeout=1000)


def test_positioner_widget_last_move(motor_widget):
    motor, widget = motor_widget
    assert not widget.successful_move
    assert not widget.failed_move
    widget._status_finished(True)
    assert widget.successful_move
    assert not widget.failed_move
    widget._status_finished(Exception())
    assert not widget.successful_move
    assert widget.failed_move


def test_positioner_widget_moving_text_changes(motor_widget, qtbot):
    motor, widget = motor_widget

    def get_moving_text():
        return widget.ui.moving_indicator_label.text()

    start_text = get_moving_text()
    motor.motor_is_moving.put(1)
    qtbot.waitUntil(lambda: widget.moving, timeout=500)
    move_text = get_moving_text()
    motor.motor_is_moving.put(0)
    qtbot.waitUntil(lambda: not widget.moving, timeout=500)
    end_text = get_moving_text()
    assert start_text != move_text
    assert move_text != end_text
    assert end_text == start_text


def test_positioner_widget_alarm_text_changes(motor_widget, qtbot):
    motor, widget = motor_widget
    alarm_texts = []

    def get_alarm_text():
        return widget.ui.alarm_label.text()

    def update_alarm(level, connected=True):
        with qtbot.waitSignal(
                widget.ui.alarm_circle.alarm_changed,
                timeout=500,
                ):
            motor.motor_is_moving.update_metadata(
                {
                    'severity': level,
                    'connected': connected,
                }
            )

    def check_alarm_text_at_level(level):
        update_alarm(level)
        alarm_texts.append(get_alarm_text())

    update_alarm(0, connected=False)

    for num in range(4):
        check_alarm_text_at_level(num)

    for text in alarm_texts:
        assert alarm_texts.count(text) == 1


def test_positioner_widget_clear_error(motor_widget, qtbot):
    motor, widget = motor_widget
    widget.clear_error()
    qtbot.waitUntil(lambda: motor.clear_error.called, timeout=500)


def test_positioner_widget_move_error(motor_widget, qtbot):
    motor, widget = motor_widget
    bad_position = motor.high_limit.get() + 1

    with pytest.raises(LimitError):
        motor.check_value(bad_position)

    assert widget.ui.status_label.text() == ''
    widget._set(bad_position)

    def has_limit_error():
        assert 'LimitError' in widget.ui.status_label.text()

    qtbot.waitUntil(has_limit_error, timeout=1000)
