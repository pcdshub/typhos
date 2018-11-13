import logging
import os.path

from pydm import Display

from .utils import ui_dir, TyphonBase, clear_layout

logger = logging.getLogger(__name__)


class TyphonDisplay(Display, TyphonBase):
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
    def __init__(self,  parent=None, **kwargs):
        # Set this to None first so we don't render
        self.template = None
        self._macros = None
        super().__init__(parent=parent)

    def ui_filepath(self):
        """Path to template"""
        return self.template

    def load_template(self, template, macros=None, **kwargs):
        """
        Load a new template

        Parameters
        ----------
        template: str
            Absolute path to template location

        macros: dict, optional
            Macro substitutions to be made in the file

        kwargs:
            Treated as additional macro substitutions
        """
        # Clear anything that exists in the current layout
        if self.layout():
            clear_layout(self.layout())
        # Assemble our macros
        macros = macros or dict()
        macros.update(kwargs)
        self._macros = macros  # Store for later in case we need to reload
        # Set our template and load
        self.template = template
        self.load_ui(macros=macros)

    def add_device(self, device, methods=None):
        """
        Add a Device and signals to the TyphonDisplay

        Parameters
        ----------
        device: ophyd.Device

        methods: list, optional
            List of methods to add to the :attr:`.method_panel`
        """
        # We only allow one device at a time
        if self.devices:
            self.devices.clear()
            # We should reload the UI
            self.load_ui(self.template, macros=self._macros)
        # Add the device to the cache
        super().add_device(device)
        # Add device to all children widgets
        for widget in self.findChildren(TyphonBase):
            widget.add_device(device)

    @classmethod
    def from_device(cls, device, template=None, methods=None, **kwargs):
        """
        Create a new TyphonDisplay from a Device

        Loads the signals in to the appropriate positions and sets the title to
        a cleaned version of the device name

        Parameters
        ----------
        device: ophyd.Device

        methods: list
            List of methods to add to the :attr:`.method_panel`

        kwargs:
            Treated as macros
        """
        # Use the provided template or the provided macros
        template = template or os.path.join(ui_dir, 'device.ui')
        # Ensure we at least past in the device name
        if 'name' not in kwargs:
            kwargs['name'] = device.name
        display = cls()
        display.load_template(template, **kwargs)
        display.add_device(device, methods=methods)
        return display


DeviceDisplay = TyphonDisplay.from_device
