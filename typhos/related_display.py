"""
Widgets that open up typhos displays.
"""
from happi.client import Client
from happi.loader import load_devices
from pydm.utilities import establish_widget_connections, is_qt_designer
from qtpy import QtCore, QtWidgets

from .suite import TyphosSuite
from .utils import TyphosObject, no_device_lazy_load, use_stylesheet


class TyphosRelatedSuiteButton(TyphosObject, QtWidgets.QPushButton):
    """
    Button to open a typhos suite with happi-loaded devices.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._happi_names = []
        self._happi_cfg = ''
        self._preload = False
        self._suite = None
        self.clicked.connect(self.show_suite)

    @QtCore.Property('QStringList')
    def happi_names(self):
        """
        List of devices to include in the suite.
        """
        return self._happi_names

    @happi_names.setter
    def happi_names(self, happi_names):
        self._happi_names = happi_names

    @QtCore.Property(str)
    def happi_cfg(self):
        """
        Happi config to use, or empty string to use environment variable.
        """
        return self._happi_cfg

    @happi_cfg.setter
    def happi_cfg(self, happi_cfg):
        self._happi_cfg = happi_cfg

    @QtCore.Property(bool)
    def preload(self):
        """
        If True, we'll create the suite ahead of time.
        """
        return self._preload

    @preload.setter
    def preload(self, exec_preload):
        self._preload = exec_preload
        if self._preload and not is_qt_designer():
            self.create_suite()

    def show_suite(self):
        """
        Show the cached suite, creating it if necessary.

        This opens the suite in a new window, if it is not already open.
        If the suite is already open, this moves the open suite back to
        the starting location, which is the location of this button.

        This also unminimizes the window if needed, raises it to the front
        of the window stack, and activates it.
        """
        if self._suite is None:
            self.create_suite()
        global_pos = self.parent().mapToGlobal(self.pos())
        # Different window managers respond differently to the various
        # methods called here, the chosen sequence was intended for
        # good behavior on as many systems as possible.
        self._suite.hide()
        self._suite.window().move(global_pos)
        self._suite.show()
        if self._suite.isMinimized():
            self._suite.showNormal()
        self._suite.raise_()
        self._suite.activateWindow()
        self._suite.setFocus()

    def create_suite(self):
        """
        Create and cache the typhos suite.
        """
        # Get the devices associated with our designer attributes
        happi_names = list(map(str, self.happi_names))
        if happi_names:
            happi_cfg = str(self.happi_cfg)

            if not happi_cfg:
                happi_cfg = None

            happi_client = Client.from_config(cfg=happi_cfg)
            items = []
            for name in happi_names:
                search_result = happi_client.search(name=name)[0]
                items.append(search_result.item)

            with no_device_lazy_load():
                device_namespace = load_devices(*items, threaded=True)

            devices = [getattr(device_namespace, name) for name in happi_names]
        else:
            devices = []

        # Extend with devices from calls to self.add_devices
        devices.extend(self.devices)

        self._suite = TyphosSuite.from_devices(devices)
        use_stylesheet(widget=self._suite)
        establish_widget_connections(self._suite)
        return self._suite
