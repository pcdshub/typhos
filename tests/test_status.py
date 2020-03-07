from unittest.mock import Mock

import pytest
from qtpy.QtWidgets import QWidget

from ophyd.status import Status
from typhos.status import TyphosStatusThread


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
    thread = TyphosStatusThread(status)
    qtbot.addWidget(listener)
    thread.status_started.connect(listener.started)
    thread.status_finished.connect(listener.finished)
    yield listener, thread, status
    if thread.isRunning():
        thread.quit()

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
    thread.start()
    qtbot.waitUntil(lambda: listener.started.called, timeout=2000)
    status._finished()
    qtbot.waitUntil(lambda: listener.finished.called, timeout=2000)


def test_status_thread_timeout(threaded_status):
    listener, thread, status = threaded_status
    thread.timeout = 0.01
    thread.run()
    assert listener.started.called
    assert not listener.finished.called
