import logging
import threading

from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtWidgets import QApplication, QHBoxLayout

from .. import utils

logger = logging.getLogger(__name__)


class TyphosConsole(utils.TyphosBase):
    """
    IPython Widget for Typhos Display

    This widget handles starting a ``JupyterKernel`` and connecting an IPython
    console in which the user can type Python commands. It is important to note
    that the kernel in which commands are executed is a completely separate
    process. This protects the user against locking themselves out of the GUI,
    but makes it difficult to pass the Device.

    To get around this caveat, this widget uses ``happi`` to pass the Device
    between the processes. This is not a strict requirement, but if ``happi``
    is not installed, users will need to create a custom ``add_device`` method
    if they want their devices loaded in both the GUI and console.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Setup widget
        self.kernel = RichJupyterWidget()
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.kernel)
        # Create a Kernel
        logger.debug("Starting Jupyter Kernel ...")
        kernel_manager = QtKernelManager(kernel_name='python3')
        kernel_manager.start_kernel()
        kernel_client = kernel_manager.client()
        kernel_client.start_channels()
        self.kernel.kernel_manager = kernel_manager
        self.kernel.kernel_client = kernel_client
        # Ensure we shutdown the kernel
        app = QApplication.instance()
        app.aboutToQuit.connect(self.shutdown)
        # Styling
        self.kernel.syntax_style = 'monokai'
        self.kernel.set_default_style(colors='Linux')
        # Ensure cleanup
        app = QApplication.instance()
        app.aboutToQuit.connect(self.shutdown)

    def sizeHint(self):
        default = super().sizeHint()
        default.setWidth(600)
        return default

    def shutdown(self):
        """Shutdown the Jupyter Kernel"""
        client = self.kernel.kernel_client
        if client.channels_running:
            logger.debug("Stopping Jupyter Client")
            # Stop channels in the background
            t = threading.Thread(target=client.stop_channels)
            t.start()
            self.kernel.kernel_manager.shutdown_kernel()
        else:
            logger.debug("Kernel is already shutdown.")

    def add_device(self, device):
        try:
            load_script = utils.code_from_device(device)
            self.kernel.kernel_client.execute(load_script, silent=False)
        except Exception:
            logger.exception("Unable to add device %r to TyphosConsole.",
                             device.name)
