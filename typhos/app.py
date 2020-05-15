"""This module defines methods for launching full typhos applications."""
import logging

from qtpy.QtCore import QTimer
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


def launch_suite(suite):
    """Creates a main window and execs the application."""
    window = QMainWindow()
    window.setCentralWidget(suite)
    window.setWindowTitle(suite.windowTitle())
    window.setUnifiedTitleAndToolBarOnMac(True)
    window.show()
    logger.info("Launching application ...")
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
