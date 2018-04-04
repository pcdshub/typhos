############
# Standard #
############
import time

############
# External #
############
import pytest
from bluesky.plan_stubs import pause, open_run, close_run, sleep
from bluesky.utils import RunEngineInterrupted
from pydm.PyQt.QtCore import pyqtSlot, QObject

###########
# Package #
###########
from .conftest import show_widget
from typhon.engine import QRunEngine, EngineWidget


def plan():
    yield from open_run()
    yield from sleep(1)
    yield from pause()
    yield from close_run()


class QRecorder(QObject):
    """Helper object to record state change signals"""
    def __init__(self):
        super().__init__()
        self.state_changes = list()

    @pyqtSlot('QString', 'QString')
    def on_state_change(self, new, old):
        """Record all state changes"""
        self.state_changes.append((new, old))


def test_qrunengine_signals(qapp):
    # Create our Engine and recorder and connect the signal
    QRE = QRunEngine()
    qrec = QRecorder()
    QRE.state_changed.connect(qrec.on_state_change)
    # Run the plan until it pauses automatically
    try:
        QRE(plan())
    except RunEngineInterrupted:
        pass
    # Process our first round of events
    qapp.processEvents()
    assert qrec.state_changes[0] == ('running', 'idle')
    assert qrec.state_changes[1] == ('paused', 'running')
    QRE.resume()
    # Process our second round of events
    qapp.processEvents()
    assert qrec.state_changes[2] == ('running', 'paused')
    assert qrec.state_changes[3] == ('idle', 'running')


def test_engine_readback_state_changes(qapp):
    ew = EngineWidget()
    ew.engine.on_state_change('idle', 'running')
    qapp.processEvents()
    assert ew.label.text() == 'Idle'
    assert ew.control.currentWidget().text() == 'Start'
    ew.engine.on_state_change('running', 'idle')
    qapp.processEvents()
    assert ew.control.currentWidget().text() == 'Pause'
    assert ew.label.text() == 'Running'
    ew.engine.on_state_change('paused', 'running')
    qapp.processEvents()
    assert ew.label.text() == 'Paused'
    assert len(ew.control.currentWidget()) == len(ew.control.pause_commands)


@show_widget
def test_engine_plan_execution(qapp):
    # Create a widget and load plans
    ew = EngineWidget()
    # Create a plan
    ew.engine.plan_creator = lambda: plan()
    assert ew.engine.state == 'idle'
    # Start the RunEngine
    ew.control.state_widgets['idle'].clicked.emit()
    qapp.processEvents()
    time.sleep(1.0)
    assert ew.engine.state == 'paused'
    # Resume after a pause
    ew.control.currentWidget().activated['QString'].emit('Resume')
    qapp.processEvents()
    time.sleep(0.5)
    assert ew.engine.state == 'idle'
    return ew
