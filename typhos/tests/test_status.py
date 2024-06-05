from unittest.mock import Mock

import pytest
from ophyd.status import Status
from ophyd.utils import (StatusTimeoutError, UnknownStatusFailure,
                         WaitTimeoutError)
from qtpy.QtWidgets import QWidget

from typhos.status import TyphosStatusResult, TyphosStatusThread


class Listener(QWidget):
    """Helper to catch signals"""

    def __init__(self):
        super().__init__()
        self.started = Mock()
        self.timeout = Mock()
        self.finished = Mock()
        self.err_msg = Mock()
        self.exc = Mock()


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
    thread.status_timeout.connect(listener.timeout)
    thread.status_finished.connect(listener.finished)
    thread.error_message.connect(listener.err_msg)
    thread.status_exc.connect(listener.exc)
    yield thread
    if thread.isRunning():
        thread.quit()


def test_previously_done_status_in_thread(listener, status, thread):
    """
    Expected behavior: thread finishes without starting if already done
    """
    status.set_finished()
    status.wait()
    thread.run()
    assert not listener.started.called
    assert not listener.timeout.called
    assert listener.finished.called
    assert not listener.err_msg.called
    assert not listener.exc.called


def test_status_thread_completed(qtbot, listener, status, thread):
    """
    Expected behavior: thread doesn't finish until status does
    """
    thread.start()
    qtbot.waitUntil(lambda: listener.started.called, timeout=2000)
    status.set_finished()
    qtbot.waitUntil(lambda: listener.finished.called, timeout=2000)
    assert not listener.timeout.called
    assert not listener.err_msg.called
    assert not listener.exc.called
    res, = listener.finished.call_args[0]
    assert res == TyphosStatusResult.success


def test_status_thread_wait_timeout(qtbot, listener, thread, status):
    """
    Expected behavior: thread times out but doesn't outright fail
    """
    thread.timeout = 0.1
    thread.start()
    qtbot.waitUntil(lambda: listener.started.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.timeout.called, timeout=2000)
    msg, = listener.err_msg.call_args[0]
    exc, = listener.exc.call_args[0]
    assert "taking longer than expected" in msg.text
    assert isinstance(exc, WaitTimeoutError)
    assert not listener.finished.called
    # and now we should be able to finish
    status.set_finished()
    qtbot.waitUntil(lambda: listener.finished.called, timeout=2000)
    res, = listener.finished.call_args[0]
    assert res == TyphosStatusResult.success


def test_status_thread_status_timeout(qtbot, listener, thread):
    """
    Expected behavior: the status fails, so the thread does too
    """
    status = Status(timeout=0.1)
    thread.status = status
    thread.start()
    qtbot.waitUntil(lambda: listener.started.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.err_msg.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.exc.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.finished.called, timeout=2000)
    res, = listener.finished.call_args[0]
    msg, = listener.err_msg.call_args[0]
    exc, = listener.exc.call_args[0]
    assert res == TyphosStatusResult.failure
    assert "failed with timeout" in msg.text
    assert isinstance(exc, StatusTimeoutError)
    assert not listener.timeout.called


def test_status_thread_unk_failure(qtbot, listener, status, thread):
    """
    Expected behavior: the thread fails when the status does
    """
    thread.start()
    qtbot.waitUntil(lambda: listener.started.called, timeout=2000)
    status._finished(success=False)
    qtbot.waitUntil(lambda: listener.err_msg.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.exc.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.finished.called, timeout=2000)
    res, = listener.finished.call_args[0]
    msg, = listener.err_msg.call_args[0]
    exc, = listener.exc.call_args[0]
    assert res == TyphosStatusResult.failure
    assert "failed with no reason" in msg.text
    assert isinstance(exc, UnknownStatusFailure)
    assert not listener.timeout.called


def test_status_thread_specific_failure(qtbot, listener, status, thread):
    """
    Expected behavior: the thread fails when the status does
    """
    thread.start()
    qtbot.waitUntil(lambda: listener.started.called, timeout=2000)
    status.set_exception(Exception("test_error"))
    qtbot.waitUntil(lambda: listener.err_msg.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.exc.called, timeout=2000)
    qtbot.waitUntil(lambda: listener.finished.called, timeout=2000)
    res, = listener.finished.call_args[0]
    msg, = listener.err_msg.call_args[0]
    exc, = listener.exc.call_args[0]
    assert res == TyphosStatusResult.failure
    assert "test_error" in msg.text
    assert not isinstance(exc, WaitTimeoutError)
    assert not isinstance(exc, StatusTimeoutError)
    assert not isinstance(exc, UnknownStatusFailure)
    assert not listener.timeout.called
