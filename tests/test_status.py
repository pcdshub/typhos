from unittest.mock import Mock

from ophyd.status import Status
import pytest
from qtpy.QtWidgets import QWidget

from typhon.status import TyphonStatusThread


class Listener(QWidget):
    """Helper to catch signals"""
    def __init__(self):
        super().__init__()
        self.started = Mock()
        self.finished = Mock()


@pytest.fixture(scope='function')
def threaded_status(qtbot):
    status = Status()
    listener = Listener()
    thread = TyphonStatusThread(status)
    qtbot.addWidget(listener)
    thread.status_started.connect(listener.started)
    thread.status_finished.connect(listener.finished)
    return listener, thread, status


def test_previously_done_status_in_thread(threaded_status):
    listener, thread, status = threaded_status
    status._finished()
    thread.run()
    assert not listener.started.called
    assert not listener.finished.called


def test_status_finished_during_lag(threaded_status):
    listener, thread, status = threaded_status
    thread.lag = 3
    thread.start()
    status._finished()
    thread.wait()
    assert not listener.started.called
    assert not listener.finished.called


def test_status_thread_completed(qtbot, threaded_status):
    listener, thread, status = threaded_status
    with qtbot.waitSignal(thread.status_started, timeout=1000):
        thread.start()
    assert listener.started.called
    with qtbot.waitSignal(thread.status_finished, timeout=2000):
        status._finished()
    assert listener.finished.called_with(True)


def test_status_thread_timeout(threaded_status):
    listener, thread, status = threaded_status
    thread.timeout = 0.01
    thread.run()
    assert listener.started.called
    assert not listener.finished.called
