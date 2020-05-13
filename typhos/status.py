import logging
import time

from qtpy.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class TyphosStatusThread(QThread):
    """
    Thread which monitors an ophyd Status object and emits start/stop signals.

    Parameters
    ----------
    status : ophyd.status.StatusBase
        The status object.

    start_delay : float, optional
        Delay emitting ``status_started``. This avoids rapid flashes for
        statuses that complete quickly. Units of seconds.

    timeout : float, optional
        Timeout for considering status complete.

    Example
    ------

    .. code:: python

       thread = TyphosStatusThread(motor.set(...))
       thread.start()

    """
    status_started = Signal()
    status_finished = Signal(bool)

    def __init__(self, status, start_delay=0., timeout=10.0, parent=None):
        super().__init__(parent=parent)
        self.status = status
        self.start_delay = start_delay
        self.timeout = timeout

    def run(self):
        """Start following a new motion"""
        # Don't do anything if we are handed a finished status
        if self.status.done:
            logger.debug("Status already completed.")
            self.status_finished.emit(self.status.success)
            return

        # Wait to emit to avoid too much flashing
        time.sleep(self.start_delay)
        self.status_started.emit()
        try:
            self.status.wait(timeout=self.timeout)
            logger.debug("Status completed!")
            self.status_finished.emit(self.status.success)
        except TimeoutError as ex:
            # May be a WaitTimeoutError or a StatusTimeoutError
            logger.error("%s: Status %r did not complete in %s seconds",
                         type(ex).__name__, self.status, self.timeout)
            self.status_finished.emit(False)
        except Exception:
            logger.exception('Status wait failed')
            self.status_finished.emit(False)
