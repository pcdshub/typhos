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

    delay_draw : float, optional
        Do not draw anything until a certain amount of time has passed. This
        avoids rapid flashes for statuses that complete quickly. Units of
        seconds.

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

    def __init__(self, status, delay_draw=0., timeout=10.0, parent=None):
        super().__init__(parent=parent)
        self.status = status
        self.delay_draw = delay_draw
        self.timeout = timeout

    def run(self):
        """Start following a new motion"""
        # Don't do anything if we are handed a finished status
        if self.status.done:
            logger.debug("Status already completed.")
            return

        # Wait to emit to avoid too much flashing
        time.sleep(self.delay_draw)
        self.status_started.emit()
        try:
            if self.status.wait(timeout=self.timeout):
                logger.debug("Status completed!")
                self.status_finished.emit(self.status.success)
        except TimeoutError:
            logger.error("Status %r did not complete in %s seconds",
                         self.status, self.timeout)
        except RuntimeError:
            logger.exception('Status wait failed')
