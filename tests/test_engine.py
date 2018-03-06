############
# Standard #
############

############
# External #
############
import pytest
from bluesky.plan_stubs import pause, open_run, close_run, sleep

###########
# Package #
###########
from .conftest import show_widget
from typhon.engine import EngineWidget


def plan():
    yield from open_run()
    yield from sleep(1)
    yield from pause()
    yield from close_run()


def test_engine_state_changes():
    ew = EngineWidget()
    assert ew.label.text() == 'Idle'
    assert len(ew.control) == len(ew.control.available_commands['idle']) + 1
    ew.on_state_change('running', 'idle')
    assert ew.label.text() == 'Running'
    assert len(ew.control) == len(ew.control.available_commands['running']) + 1
    ew.on_state_change('paused', 'running')
    assert ew.label.text() == 'Paused'
    assert len(ew.control) == len(ew.control.available_commands['paused']) + 1


@show_widget
def test_engine_plan_execution():
    # Create a widget and load plans
    ew = EngineWidget()
    ew.plan = lambda: plan()
    ew.control.currentIndexChanged['QString'].emit('Start')
    assert ew.engine.state == 'paused'
    ew.control.currentIndexChanged['QString'].emit('Resume')
    assert ew.engine.state == 'idle'
    return ew
