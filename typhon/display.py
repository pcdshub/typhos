from enum import Enum
import logging
import os.path

from pydm import Display
from qtpy.QtCore import Property, Slot, Q_ENUMS
from qtpy.QtWidgets import QHBoxLayout

from .utils import ui_dir, TyphonBase, clear_layout
from .widgets import TyphonDesignerMixin


logger = logging.getLogger(__name__)


class TemplateTypes:
    """Types of Available Templates"""
    embedded_screen = 0
    detailed_screen = 1
    engineering_screen = 2

    @classmethod
    def to_enum(cls):
        # First let's remove the internals
        entries = [(k, v) for k, v in cls.__dict__.items()
                   if not k.startswith("__")
                   and not callable(v)
                   and not isinstance(v, staticmethod)]
        return Enum('TemplateEnum', entries)


class TyphonDisplay(TyphonBase, TyphonDesignerMixin, TemplateTypes):
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
    # Template types and defaults
    Q_ENUMS(TemplateTypes)
    TemplateEnum = TemplateTypes.to_enum()  # For convenience
    default_templates = dict((_typ.name, os.path.join(ui_dir,
                                                      _typ.name + '.ui'))
                             for _typ in TemplateEnum)

    def __init__(self,  parent=None, **kwargs):
        # Intialize background variable
        self._use_default = False
        self._last_macros = dict()
        self._main_widget = None
        self._template_type = TemplateTypes.detailed_screen
        # Set this to None first so we don't render
        super().__init__(parent=parent)
        # Initialize blank UI
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # Load template
        self.load_template()

    @property
    def current_template(self):
        """Current template being rendered"""
        # Search in the last macros, maybe our device told us what to do
        template_key = self.TemplateEnum(self._template_type).name
        if not self._use_default and self._last_macros.get(template_key, None):
            return self._last_macros[template_key]
        # Otherwise just use the default
        return self.default_templates[template_key]

    @Property(TemplateTypes)
    def template_type(self):
        return self._template_type

    @template_type.setter
    def template_type(self, value):
        # Store our new value
        if self._template_type != value:
            self._template_type = value
            self.load_template(macros=self._last_macros)

    @Property(bool)
    def use_default_templates(self):
        """Use the default Typhon template instead of a device specific"""
        return self._use_default

    @use_default_templates.setter
    def use_default_templates(self, value):
        if value != self._use_default:
            self._use_default = value
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
        self._main_widget = Display(ui_filename=self.current_template,
                                    macros=macros)
        self.layout().addWidget(self._main_widget)
        # Add device to all children widgets
        if self.devices:
            for widget in self._main_widget.findChildren(TyphonBase):
                widget.add_device(self.devices[0])

    def add_device(self, device, macros=None):
        """
        Add a Device and signals to the TyphonDisplay

        Parameters
        ----------
        device: ophyd.Device

        macros: dict, optional
            Set of macros to reload the template with. There are two fallback
            options attempted if no information is passed in. First, if the
            device has an ``md`` attribute after being loaded from a ``happi``
            database, that information will be passed in as macros. Finally, if
            no ``name`` field is passed in, we ensure the ``device.name`` is
            entered as well.
        """
        # We only allow one device at a time
        if self.devices:
            logger.debug("Removing devices %r", self.devices)
            self.devices.clear()
        # Add the device to the cache
        super().add_device(device)
        # Try and collect macros from device
        if not macros:
            if hasattr(device, 'md'):
                macros = device.md.post()
            else:
                macros = dict()
        # Ensure we at least pass in the device name
        if 'name' not in macros:
            macros['name'] = device.name
        # Reload template
        self.load_template(macros=macros)

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
        display = cls()
        # Reset the template if provided
        if template:
            display.use_template = template
        # Add the device
        display.add_device(device, macros=macros)
        return display

    @Slot(object)
    def _tx(self, value):
        """Receive information from happi channel"""
        self.add_device(value['obj'], macros=value['md'])


DeviceDisplay = TyphonDisplay.from_device
