"""
Widgets that open up typhos displays.
"""
import logging

from pydm.utilities import establish_widget_connections, is_qt_designer
from qtpy import QtCore, QtWidgets

from .suite import TyphosSuite
from .utils import (TyphosObject, no_device_lazy_load, raise_window,
                    use_stylesheet)

try:
    from happi.client import Client
    from happi.loader import load_devices
    happi_loaded = True
except ImportError:
    happi_loaded = False


logger = logging.getLogger(__name__)


def happi_check():
    if not happi_loaded:
        logger.warning(
            'The happi module is not in your Python environment, '
            'happi TyphosRelatedSuiteButton features will not work.'
        )
    return happi_loaded


class TyphosRelatedSuiteButton(TyphosObject, QtWidgets.QPushButton):
    """
    Button to open a typhos suite with happi-loaded devices.
    """

    _qt_designer_ = {
        "group": "Typhos Widgets",
        "is_container": False,
    }

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
        happi_check()
        self._happi_names = happi_names

    @QtCore.Property(str)
    def happi_cfg(self):
        """
        Happi config to use, or empty string to use environment variable.
        """
        return self._happi_cfg

    @happi_cfg.setter
    def happi_cfg(self, happi_cfg):
        happi_check()
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
        if self._preload and self._suite is None and not is_qt_designer():
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
        parent = self.parent()
        if parent is None:
            global_pos = self.pos()
        else:
            global_pos = self.parent().mapToGlobal(self.pos())
        self._suite.move(global_pos)
        raise_window(self._suite)

    def create_suite(self):
        """
        Create and cache the typhos suite.
        """
        devices = self.devices + self.get_happi_devices()
        if not devices:
            raise ValueError('There are no devices assigned to this button.')
        self._suite = TyphosSuite.from_devices(devices)
        use_stylesheet(widget=self._suite)
        establish_widget_connections(self._suite)
        return self._suite

    def get_happi_devices(self):
        """
        Request devices from happi based on our designer attributes.

        This relied on the happi_cfg and happi_names properties being
        set appropriately.
        """
        if self.happi_names and happi_check():
            happi_client = Client.from_config(cfg=self.happi_cfg or None)
            items = []
            for name in self.happi_names:
                try:
                    search_result = happi_client.search(name=name)[0]
                except IndexError:
                    raise ValueError(
                        f'Did not find device with name {name} in happi. '
                        'Please check your spelling and your database.'
                    ) from None
                items.append(search_result.item)

            with no_device_lazy_load():
                device_namespace = load_devices(*items, threaded=True)

            return [getattr(device_namespace, name)
                    for name in self.happi_names]
        return []
