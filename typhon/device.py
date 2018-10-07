import logging
import os.path

from ophyd import Device

from pydm.widgets.drawing import PyDMDrawingImage
from qtpy import uic
from qtpy.QtCore import Qt

from .func import FunctionPanel
from .signal import SignalPanel
from .utils import ui_dir, clean_attr, clean_name, TyphonBase

logger = logging.getLogger(__name__)


class TyphonPanel(TyphonBase):
    """
    Main Panel display for a signal Ophyd Device

    This contains the widgets for all of the root devices signals, any methods
    you would like to display, and an optional image. As with ``typhon``
    convention, the base initialization sets up the widgets and the
    ``.from_device`` class method will automatically populate them.

    Parameters
    ----------
    name: str, optional
        Name to displayed at the top of the panel

    image: str, optional
        Path to image file to displayed at the header

    parent: QWidget, optional
    """
    def __init__(self, name=None, image=None, parent=None):
        super().__init__(parent=parent)
        # Instantiate UI
        self.ui = uic.loadUi(os.path.join(ui_dir, 'device.ui'), self)
        # Set Label Names
        if name:
            self.title = name
        # Create child panels
        self.method_panel = FunctionPanel()
        self.read_panel = SignalPanel()
        self.config_panel = SignalPanel()
        self.misc_panel = SignalPanel()
        # Add to layout
        self.read_widget.setLayout(self.read_panel)
        self.config_widget.setLayout(self.config_panel)
        self.misc_widget.setLayout(self.misc_panel)
        self.main_layout.insertWidget(3, self.method_panel,
                                      0, Qt.AlignHCenter)
        self.method_panel.hide()
        # Create PyDMDrawingImage
        self.image_widget = None
        if image:
            self.add_image(image)

    @property
    def title(self):
        """Title at the top of panel"""
        return self.name_label.text()

    @title.setter
    def title(self, text):
        self.name_label.setText(text)

    def add_image(self, path):
        """
        Set the image of the PyDMDrawingImage

        Setting this twice will overwrite the first image given.

        Parameters
        ----------
        path : str
            Absolute or relative path to image
        """
        # Set existing image file
        logger.debug("Adding an image file %s ...", path)
        if self.image_widget:
            self.image_widget.filename = path
        else:
            logger.debug("Creating a new PyDMDrawingImage")
            self.image_widget = PyDMDrawingImage(filename=path,
                                                 parent=self)
            self.image_widget.setMaximumSize(350, 350)
            self.ui.main_layout.insertWidget(2, self.image_widget,
                                             0, Qt.AlignCenter)

    def add_device(self, device, methods=None):
        """
        Add a Device and signals to the TyphonPanel

        Parameters
        ----------
        device: ophyd.Device

        methods: list, optional
            List of methods to add to the :attr:`.method_panel`
        """
        super().add_device(device)
        # Create read and configuration panels
        for attr in device.read_attrs:
            signal = getattr(device, attr)
            if not isinstance(signal, Device):
                self.read_panel.add_signal(signal, clean_attr(attr))
        for attr in device.configuration_attrs:
            signal = getattr(device, attr)
            if not isinstance(signal, Device):
                self.config_panel.add_signal(signal, clean_attr(attr))
        # Catch the rest of the signals add to misc panel below misc_button
        for attr in device.component_names:
            if attr not in (device.read_attrs
                            + device.configuration_attrs):
                signal = getattr(device, attr)
                if not isinstance(signal, Device):
                    self.misc_panel.add_signal(signal, clean_attr(attr))
        # Add our methods to the panel
        methods = methods or list()
        for method in methods:
                self.method_panel.add_method(method)

    @classmethod
    def from_device(cls, device, methods=None, name=None, **kwargs):
        """
        Create a new TyphonPanel from a Device

        Loads the signals in to the appropriate positions and sets the title to
        a cleaned version of the device name

        Parameters
        ----------
        device: ophyd.Device

        methods: list
            List of methods to add to the :attr:`.method_panel`

        kwargs:
            Passed TyphonPanel constructor
        """
        if not name:
            name = clean_name(device, strip_parent=False)
        panel = cls(name=name, **kwargs)
        panel.add_device(device, methods=methods)
        return panel
