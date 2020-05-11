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
        logger.debug("Creating QApplication ...")
        qapp = QApplication([])
    return qapp


def launch_suite(suite):
    """Creates a main window and execs the application."""
    window = QMainWindow()
    window.setCentralWidget(suite)
    window.show()
    logger.info("Launching application ...")
    QApplication.instance().exec_()
    logger.info("Execution complete!")
    return window


def launch_from_devices(devices, auto_exit=False):
    """Alternate entry point for non-cli testing of loader."""
    app = get_qapp()
    suite = TyphosSuite.from_devices(devices)
    if auto_exit:
        timer = QTimer(suite)
        timer.singleShot(0, app.exit)
    return launch_suite(suite)
