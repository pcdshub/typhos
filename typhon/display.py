import logging
import os.path

from pydm import Display
from qtpy.QtWidgets import QHBoxLayout

from .utils import ui_dir, TyphonBase, clear_layout

logger = logging.getLogger(__name__)


class TyphonDisplay(TyphonBase):
    """
    Main Panel display for a signal Ophyd Device

    This widget lays out all of the architecture for a single Ophyd display.
    The structure matches an ophyd Device, but for this specific instantation,
    one is not required to be given. There are four main panels available;
    :attr:`.read_panel`, :attr:`.config_panel`, :attr:`.method_panel`. These
    each provide a quick way to organize signals and methods by their
    importance to an operator. Because each panel can be hidden interactively,
    the screen works as both an expert and novice entry point for users. By
    default, widgets are hidden until contents are added. For instance, if you
    do not add any methods to the main panel it will not be visible.

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
    default_template = os.path.join(ui_dir, 'device.ui')

    def __init__(self,  parent=None, **kwargs):
        # Intialize background variable
        self._template = None
        self._last_macros = dict()
        self._main_widget = None
        # Set this to None first so we don't render
        super().__init__(parent=parent)
        # Initialize blank UI
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.template = self.default_template

    @Property(str)
    def template(self):
        """Absolute path to template"""
        return self._template

    @template.setter
    def template(self, value):
        if value != self._template:
            self._template = value
            # Reload template with last known set of macros
            self.load_template(macros=self._last_macros)

    def load_template(self, macros=None):
        """
        Load a new template

        Parameters
        ----------
        template: str
            Absolute path to template location

        macros: dict, optional
            Macro substitutions to be made in the file
        """
        # Clear anything that exists in the current layout
        if self._main_widget:
            logger.debug("Clearing existing layout ...")
            clear_layout(self.layout())
        # Assemble our macros
        macros = macros or dict()
        self._last_macros = macros
        self._main_widget = Display(ui_filename=self.template,
                                    macros=macros)
        self.layout().addWidget(self._main_widget)

    def add_device(self, device, macros=None):
        """
        Add a Device and signals to the TyphonDisplay

        Parameters
        ----------
        device: ophyd.Device

        macros: dict, optional
            Set of macros to reload the template with. If not entered this will
            just be the device name with key "name"
        """
        # We only allow one device at a time
        if self.devices:
            logger.debug("Removing devices %r", self.devices)
            self.devices.clear()
        # Ensure we at least pass in the device name
        macros = macros or dict()
        if 'name' not in macros:
            macros['name'] = device.name
        # Reload template
        self.load_template(macros=macros)
        # Add the device to the cache
        super().add_device(device)
        # Add device to all children widgets
        for widget in self._main_widget.findChildren(TyphonBase):
            widget.add_device(device)

    @classmethod
    def from_device(cls, device, template=None, macros=None):
        """
        Create a new TyphonDisplay from a Device

        Loads the signals in to the appropriate positions and sets the title to
        a cleaned version of the device name

        Parameters
        ----------
        device: ophyd.Device

        macros: dict, optional
            Macro substitutions to be placed in template
        """
        # Use the provided template or the provided macros
        template = template or os.path.join(ui_dir, 'device.ui')
        display = cls()
        # Reset the template if provided
        if template:
            display.template = template
        # Add the device
        display.add_device(device, macros=macros)
        return display


DeviceDisplay = TyphonDisplay.from_device
