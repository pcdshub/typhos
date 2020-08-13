from unittest.mock import Mock

import pytest
from ophyd.status import Status
from qtpy.QtWidgets import QWidget

from typhos.status import TyphosStatusThread


class Listener(QWidget):
    """Helper to catch signals"""

    def __init__(self):
        super().__init__()
        self.started = Mock()
        self.finished = Mock()


@pytest.fixture(scope='function')
def status(qtbot):
    status = Status()
    return status


@pytest.fixture(scope='function')
def listener(qtbot, status):
    listener = Listener()
    qtbot.addWidget(listener)
    return listener


@pytest.fixture(scope='function')
def thread(qtbot, status, listener):
    thread = TyphosStatusThread(status)
    thread.status_started.connect(listener.started)
    thread.status_finished.connect(listener.finished)
    yield thread
    if thread.isRunning():
        thread.quit()


def test_previously_done_status_in_thread(listener, status, thread):
    status.set_finished()
    status.wait()
    thread.run()
    assert not listener.started.called
    assert listener.finished.called


def test_status_thread_completed(qtbot, listener, status, thread):
    thread.start()
    qtbot.waitUntil(lambda: listener.started.called, timeout=2000)
    status.set_finished()
    qtbot.waitUntil(lambda: listener.finished.called, timeout=2000)


def test_status_thread_timeout(listener, thread, status):
    thread.timeout = 0.01
    thread.run()
    assert listener.started.called

    ex, = listener.finished.call_args[0]
    assert isinstance(ex, TimeoutError)
