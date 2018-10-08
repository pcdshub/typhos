import logging

from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.manager import QtKernelManager

from ..utils import TyphonBase

logger = logging.getLogger(__name__)


class TyphonConsole(RichJupyterWidget, TyphonBase):
    """IPython widget for Typhon Display"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Create a Kernel
        logger.debug("Starting Jupyter Kernel ...")
        kernel_manager = QtKernelManager(kernel_name='python3')
        kernel_manager.start_kernel()
        kernel_client = kernel_manager.client()
        kernel_client.start_channels()
        self.kernel_manager = kernel_manager
        self.kernel_client = kernel_client
        # Ensure we shutdown the kernel
        self.exit_requested.connect(self.shutdown)
        # Styling
        self.syntax_style = 'monokai'
        self.set_default_style(colors='Linux')

    def add_device(self, device):
        pass

    def sizeHint(self):
        default = super().sizeHint()
        default.setWidth(600)
        return default

    def shutdown(self):
        logger.debug("Stopping Jupyter Client")
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()
