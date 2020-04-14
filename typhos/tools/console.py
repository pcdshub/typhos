import logging

from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy import QtCore, QtWidgets

from .. import utils

logger = logging.getLogger(__name__)


def _make_jupyter_widget_with_kernel(kernel_name):
    """
    Start a kernel, connect to it, and create a RichJupyterWidget to use it

    Parameters
    ----------
    kernel_name : str
        Kernel name to use
    """
    kernel_manager = QtKernelManager(kernel_name=kernel_name)
    kernel_manager.start_kernel()

    kernel_client = kernel_manager.client()
    kernel_client.start_channels()

    jupyter_widget = RichJupyterWidget()
    jupyter_widget.kernel_manager = kernel_manager
    jupyter_widget.kernel_client = kernel_client
    return jupyter_widget


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

    device_added = QtCore.Signal(object)
    kernel_shut_down = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._shutting_down = False

        # Setup widget
        self.jupyter_widget = _make_jupyter_widget_with_kernel('python3')
        self.jupyter_widget.syntax_style = 'monokai'
        self.jupyter_widget.set_default_style(colors='Linux')

        # Set the layout
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.jupyter_widget)

        # Ensure we shutdown the kernel
        app = QtWidgets.QApplication.instance()
        app.aboutToQuit.connect(self.shutdown)

    def sizeHint(self):
        default = super().sizeHint()
        default.setWidth(600)
        return default

    def shutdown(self):
        """Shutdown the Jupyter Kernel"""
        client = self.jupyter_widget.kernel_client
        if self._shutting_down:
            logger.debug("Kernel is already shutting down")
            return

        self._shutting_down = True
        logger.debug("Stopping Jupyter Client")

        def cleanup():
            self.jupyter_widget.kernel_manager.shutdown_kernel()
            self.kernel_shut_down.emit()

        client.stop_channels()
        QtCore.QTimer.singleShot(0, cleanup)

    def add_device(self, device):
        # Add the device after a short delay to allow the console widget time
        # to get initialized
        QtCore.QTimer.singleShot(
            100, lambda device=device: self._add_device(device)
        )

    @property
    def _plain_text(self):
        """
        Text in the console
        """
        return self.jupyter_widget._control.toPlainText()

    def execute(self, script, *, echo=True):
        """
        Execute some code in the console
        """
        if echo:
            # Can't seem to get `interactive` or `hidden=False` working:
            script = '\n'.join((f"print({repr(script)})", script))

        self.jupyter_widget.kernel_client.execute(script)

    def _add_device(self, device):
        try:
            script = utils.code_from_device(device)
            self.execute(script)
        except Exception:
            logger.exception("Unable to add device %r to TyphosConsole.",
                             device.name)
        else:
            self.device_added.emit(device)
