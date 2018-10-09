import hashlib
import logging
import os
import tempfile
from time import localtime

from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.manager import QtKernelManager

from ..utils import TyphonBase, make_identifier

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

    def sizeHint(self):
        default = super().sizeHint()
        default.setWidth(600)
        return default

    def shutdown(self):
        logger.debug("Stopping Jupyter Client")
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


try:
    import happi

    def add_device(obj, device):
        # Needs metadata
        if not hasattr(device, 'md'):
            logger.error("Device %r has no stored metadata. "
                         "Unable to load in TyphonConsole",
                         device)
            return
        # Create a temporary file
        name = hashlib.md5(str(localtime()).encode('utf-8')).hexdigest()
        name = os.path.join(tempfile.gettempdir(), name)
        try:
            # Dump the device in the tempfile
            client = happi.Client(path=name, initialize=True)
            client.add_device(device.md)
            # Create a valid Python identifier
            python_name = make_identifier(device.md.name)
            # Create the script to load the device
            load_script = (
                       f'import happi; '
                       f'from happi.loader import from_container; '
                       f'client = happi.Client(path="{name}"); '
                       f'md = client.find_device(name="{device.md.name}"); '
                       f'{python_name} = from_container(md)')
            # Execute the script
            obj.kernel_client.execute(load_script, silent=True)
        except Exception as exc:
            logger.exception("Unable to add device %r to TyphonConsole.",
                             device.md.name)
            # Cleanup after ourselves
            if os.path.exists(name):
                os.remove(name)

    # Set the TyphonConsole up to load devices
    TyphonConsole.add_device = add_device

except ImportError:
    logger.info("Unable to import ``happi``. Devices will not be added "
                "to the ``TyphonConsole`` unless ``TyphoConsole.add_device`` "
                "is implemented.")

    # Dummy pass-through function
    def add_device(obj, x):
        pass

    TyphonConsole.add_device = add_device
