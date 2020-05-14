import logging
import threading

from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy import QtCore, QtWidgets

from .. import utils

logger = logging.getLogger(__name__)


def _make_jupyter_widget_with_kernel(kernel_name):
    """
    Start a kernel, connect to it, and create a RichJupyterWidget to use it.

    Parameters
    ----------
    kernel_name : str
        Kernel name to use.
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
    IPython Widget for Typhos Display.

    This widget handles starting a ``JupyterKernel`` and connecting an IPython
    console in which the user can type Python commands. It is important to note
    that the kernel in which commands are executed is a completely separate
    process. This protects the user against locking themselves out of the GUI,
    but makes it difficult to pass the Device..

    To get around this caveat, this widget uses ``happi`` to pass the Device
    between the processes. This is not a strict requirement, but if ``happi``
    is not installed, users will need to create a custom ``add_device`` method
    if they want their devices loaded in both the GUI and console.
    """

    device_added = QtCore.Signal(object)
    kernel_ready = QtCore.Signal()
    kernel_shut_down = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._shutting_down = False

        # Setup widget
        self.jupyter_widget = _make_jupyter_widget_with_kernel('python3')
        self.jupyter_widget.syntax_style = 'monokai'
        self.jupyter_widget.set_default_style(colors='Linux')
        self.jupyter_widget.kernel_manager.kernel_restarted.connect(
            self._handle_kernel_restart
        )

        # Setup kernel readiness checks
        self._ready_lock = threading.Lock()
        self._kernel_is_ready = False
        self._pending_devices = []
        self._pending_commands = []

        self._device_history = set()

        self._check_readiness_timer = QtCore.QTimer()
        self._check_readiness_timer.setInterval(100)
        self._check_readiness_timer.timeout.connect(self._wait_for_readiness)
        self._check_readiness_timer.start()
        self.kernel_ready.connect(self._add_pending_devices)

        # Set the layout
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.jupyter_widget)

        # Ensure we shutdown the kernel
        app = QtWidgets.QApplication.instance()
        app.aboutToQuit.connect(lambda: self.shutdown(block=True))

        self.device_added.connect(self._add_device_history)

    @property
    def kernel_is_ready(self):
        """Is the Jupyter kernel ready?"""
        return self.kernel_is_alive and self._kernel_is_read

    @property
    def kernel_is_alive(self):
        """Is the Jupyter kernel alive and not shutting down?"""
        return (self.jupyter_widget.kernel_manager.is_alive() and
                not self._shutting_down)

    def _add_pending_devices(self):
        """Add devices that were requested prior to the kernel being ready."""
        with self._ready_lock:
            self._kernel_is_ready = True

        for command in self._pending_commands:
            self.execute(command)

        for device in self._pending_devices:
            self._add_device(device)

        self._pending_commands = []
        self._pending_devices = []

    def _wait_for_readiness(self):
        """Wait for the kernel to show the prompt."""

        def looks_ready(text):
            return any(line.startswith('In ') for line in text.splitlines())

        if looks_ready(self._plain_text):
            self.kernel_ready.emit()
            self._check_readiness_timer.stop()

    def sizeHint(self):
        default = super().sizeHint()
        default.setWidth(600)
        return default

    def shutdown(self, *, block=False):
        """Shutdown the Jupyter Kernel."""
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
        if block:
            cleanup()
        else:
            QtCore.QTimer.singleShot(0, cleanup)

    def add_device(self, device):
        # Add the device after a short delay to allow the console widget time
        # to get initialized
        with self._ready_lock:
            if not self._kernel_is_ready:
                self._pending_devices.append(device)
                return

        self._add_device(device)

    @property
    def _plain_text(self):
        """
        Text in the console.
        """
        return self.jupyter_widget._control.toPlainText()

    def execute(self, script, *, echo=True, check_readiness=True):
        """
        Execute some code in the console.
        """
        if echo:
            # Can't seem to get `interactive` or `hidden=False` working:
            script = '\n'.join((f"print({repr(script)})", script))

        if check_readiness:
            with self._ready_lock:
                if not self._kernel_is_ready:
                    self._pending_commands.append(script)
                    return

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

    def _handle_kernel_restart(self):
        logger.debug('Kernel was restarted.')
        for dev in self._device_history:
            self.add_device(dev)

    def _add_device_history(self, device):
        self._device_history.add(device)
