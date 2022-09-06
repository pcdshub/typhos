"""This module defines methods for launching full typhos applications."""
import logging
from typing import Optional

from qtpy.QtCore import QSize, QTimer
from qtpy.QtWidgets import QApplication, QMainWindow

from .suite import TyphosSuite

logger = logging.getLogger(__name__)
qapp = None


def get_qapp():
    """Returns the global QApplication, creating it if necessary."""
    global qapp
    if qapp is None:
        if QApplication.instance() is None:
            logger.debug("Creating QApplication ...")
            qapp = QApplication([])
        else:
            logger.debug("Using existing QApplication")
            qapp = QApplication.instance()
    return qapp


def launch_suite(
    suite: TyphosSuite,
    initial_size: Optional[QSize] = None
) -> QMainWindow:
    """
    Creates a main window and execs the application.

    Parameters
    ----------
    suite : TyphosSuite
        The suite that we'd like to launch.
    initial_size : QSize, optional
        If provided, the initial size for the full suite window.
        This can be useful when creating launcher scripts when
        the default window size isn't very good for that
        particular suite (e.g. flow layouts)

    Returns
    -------
    window : QMainWindow
        The window that we created. This will not be returned until
        after the application is done running. This is primarily
        useful for unit tests.
    """
    window = QMainWindow()
    window.setCentralWidget(suite)
    window.setWindowTitle(suite.windowTitle())
    window.setUnifiedTitleAndToolBarOnMac(True)
    if initial_size is not None:
        window.resize(initial_size)
    logger.info("Launching application ...")
    QTimer.singleShot(0, window.show)
    get_qapp().exec_()
    logger.info("Execution complete!")
    return window


def launch_from_devices(devices, auto_exit=False):
    """Alternate entry point for non-cli testing of loader."""
    app = get_qapp()
    suite = TyphosSuite.from_devices(devices)
    if auto_exit:
        QTimer.singleShot(0, app.exit)
    return launch_suite(suite)
