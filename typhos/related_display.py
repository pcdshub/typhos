"""
Widgets intended to be used in other applications.
"""
from happi.client import Client
from happi.loader import load_devices
from pydm.utilities import establish_widget_connections
from qtpy import QtCore, QtWidgets

from .suite import TyphosSuite
from .utils import no_device_lazy_load, use_stylesheet


class TyphosRelatedSuiteButton(QtWidgets.QPushButton):
    """
    Button to open a typhos suite related to an open pydm ui.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._devices = []
        self._happi_cfg = ''
        self.clicked.connect(self.create_suite)

    @QtCore.Property('QStringList', designable=True)
    def devices(self):
        """
        List of devices to include in the suite.
        """
        return self._devices

    @devices.setter
    def devices(self, devices):
        self._devices = devices

    @QtCore.Property('QString', designable=True)
    def happi_cfg(self):
        """
        Happi config to use, or empty string to use environment variable.
        """
        return self._happi_cfg

    @happi_cfg.setter
    def happi_cfg(self, happi_cfg):
        self._happi_cfg = happi_cfg

    @QtCore.Slot()
    def create_suite(self):
        """
        Open a new window and put the suite into it.
        """
        device_names = list(map(str, self.devices))
        happi_cfg = str(self.happi_cfg)

        if not happi_cfg:
            happi_cfg = None

        happi_client = Client.from_config(cfg=happi_cfg)
        items = []
        for name in device_names:
            search_result = happi_client.search(name=name)[0]
            items.append(search_result.item)

        with no_device_lazy_load():
            device_namespace = load_devices(*items, threaded=True)

        devices = [getattr(device_namespace, name) for name in device_names]
        suite = TyphosSuite.from_devices(devices)
        use_stylesheet(widget=suite)
        establish_widget_connections(suite)
        suite.show()

        return suite
