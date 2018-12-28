from unittest.mock import Mock

import pytest
from ophyd import Component as Cpt, Signal
from ophyd.sim import SynAxis, SignalRO

from typhon.positioner import TyphonPositionerWidget

from .conftest import show_widget


class SimMotor(SynAxis):
    low_limit_switch = Cpt(SignalRO, value=0)
    high_limit_switch = Cpt(SignalRO, value=0)
    low_limit = Cpt(Signal, value=-10)
    high_limit = Cpt(Signal, value=10)
    stop = Mock()


@pytest.fixture(scope='function')
def motor_widget(qtbot):
    motor = SimMotor(name='test')
    setwidget = TyphonPositionerWidget.from_device(motor)
    qtbot.addWidget(setwidget)
    return motor, setwidget


def test_positioner_widget_no_limits(qtbot, motor):
    setwidget = TyphonPositionerWidget.from_device(motor)
    qtbot.addWidget(setwidget)
    for widget in ('low_limit', 'low_limit_switch',
                   'high_limit', 'high_limit_switch'):
        assert getattr(setwidget.ui, widget).isHidden()


def test_positioner_widget_fixed_limits(qtbot, motor):
    motor.limits = (-10, 10)
    widget = TyphonPositionerWidget.from_device(motor)
    qtbot.addWidget(widget)
    assert widget.ui.low_limit.text() == '-10'
    assert widget.ui.high_limit.text() == '10'


@show_widget
def test_positioner_widget_with_signal_limits(motor_widget):
    motor, widget = motor_widget
    # Check limit switches
    low_limit_chan = widget.ui.low_limit_switch.channel
    assert motor.low_limit_switch.name in low_limit_chan
    low_limit_chan = widget.ui.low_limit_switch.channel
    assert motor.low_limit_switch.name in low_limit_chan
    return widget


def test_positioner_widget_readback(motor_widget):
    motor, widget = motor_widget
    assert motor.readback.name in widget.ui.user_readback.channel


def test_positioner_widget_stop(motor_widget):
    motor, widget = motor_widget
    widget.stop()
    assert motor.stop.called


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
    assert motor.position == 1


def test_positioner_widget_negative_tweak(motor_widget):
    motor, widget = motor_widget
    widget.ui.tweak_value.setText('1')
    widget.negative_tweak()
    assert motor.position == -1
