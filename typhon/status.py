import time
import logging

from qtpy.QtCore import QThread, Signal

from ophyd.status import wait as status_wait


logger = logging.getLogger(__name__)


class TyphonStatusThread(QThread):
    """
    Parameters
    ----------
    delay_draw: float, optional
        Do not draw anything until a certain amount of time has passed. This
        avoids rapid flashes for statuses that complete quickly. Units of
        seconds.


    Example
    ------

    .. code:: python

       status_manager = QtStatusManager()
       status = motor.set(...)
       status_manager(status)

    """
    status_started = Signal()
    status_finished = Signal(bool)

    def __init__(self, status, lag=0., timeout=10.0, parent=None):
        super().__init__(parent=parent)
        self.status = status
        self.lag = lag
        self.timeout = timeout

    def run(self):
        """Start following a new motion"""
        # Don't do anything if we are handed a finished status
        if self.status.done:
            logger.debug("Status already completed...")
            return
        # Wait to draw to avoid too much flashing
        logger.debug("Waiting for process to last for %r before emitting...",
                     self.lag)
        time.sleep(self.lag)
        if self.status.done:
            logger.debug("Process was too short to update user interface...")
            return
        # Draw
        self.status_started.emit()
        try:
            status_wait(self.status, timeout=self.timeout)
            logger.debug("Status completed!")
            self.status_finished.emit(self.status.success)
        except TimeoutError:
            logger.error("Status %r did not complete in %s seconds",
                         self.status, self.timeout)
        except RuntimeError as err:
            logger.error(err.args[0])
