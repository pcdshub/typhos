import logging
import time

from qtpy.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class GenericStatusFailure(Exception):
    """A stand-in for a status value of ``False`` with no detailed info."""


class TyphosStatusThread(QThread):
    """
    Thread which monitors an ophyd Status object and emits start/stop signals.

    The ``status_started`` signal may be emitted after ``start_delay`` seconds,
    unless the status has already completed.

    The ``status_finished`` signal is guaranteed to be emitted with a status
    boolean indicating success or failure, or timeout.

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
    status_finished = Signal(object)

    def __init__(self, status, start_delay=0., timeout=10.0, parent=None):
        super().__init__(parent=parent)
        self.status = status
        self.start_delay = start_delay
        self.timeout = timeout

    def run(self):
        """Monitor status object status and emit signals."""
        # Don't do anything if we are handed a finished status
        if self.status.done:
            logger.debug("Status already completed.")
            self.status_finished.emit(
                self.status.success or GenericStatusFailure())
            return

        # Wait to emit to avoid too much flashing
        time.sleep(self.start_delay)
        self.status_started.emit()
        try:
            self.status.wait(timeout=self.timeout)
        except TimeoutError as ex:
            # May be a WaitTimeoutError or a StatusTimeoutError
            logger.error("%s: Status %r did not complete in %s seconds",
                         type(ex).__name__, self.status, self.timeout)
            finished_value = ex
        except Exception as ex:
            logger.exception('Status wait failed')
            finished_value = ex
        else:
            finished_value = self.status.success or GenericStatusFailure()

        logger.debug("Emitting finished: %r", finished_value)
        self.status_finished.emit(finished_value)
