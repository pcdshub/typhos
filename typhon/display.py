from enum import Enum
import logging
import os.path
import warnings

from pydm import Display
from pydm.utilities.display_loading import load_py_file

from qtpy.QtCore import Property, Slot, Q_ENUMS, QSize
from qtpy.QtWidgets import QHBoxLayout, QWidget

from .utils import (ui_dir, TyphonBase, clear_layout,
                    reload_widget_stylesheet)
from .widgets import TyphonDesignerMixin


logger = logging.getLogger(__name__)


class DisplayTypes:
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


class TyphonDeviceDisplay(TyphonBase, TyphonDesignerMixin, DisplayTypes):
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
    Q_ENUMS(DisplayTypes)
    TemplateEnum = DisplayTypes.to_enum()  # For convenience

    def __init__(self,  parent=None, **kwargs):
        # Intialize background variable
        self._forced_template = ''
        self._last_macros = dict()
        self._main_widget = None
        self._embedded_size = QSize(300, 300)
        self._engineering_size = QSize(600, 600)
        self.templates = dict((_typ.name, os.path.join(ui_dir,
                                                       _typ.name + '.ui'))
                              for _typ in self.TemplateEnum)
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
        if self._forced_template:
            return self._forced_template
        # Search in the last macros, maybe our device told us what to do
        template_key = self.TemplateEnum(self.display_type).name
        return self.templates[template_key]

    @Property(DisplayTypes, designable=False)
    def display_type(self):
        """Current DisplayType based on the size of the widget"""
        return self._display_for_size(self.size())

    @display_type.setter
    def display_type(self, value):
        warnings.warn("display_type is no longer set explicitly. Instead it "
                      "is a funciton of the current size of the widget and "
                      "the ``embedded_size`` and ``engineering_size`` "
                      "properties")

    @Property(str, designable=False)
    def device_class(self):
        """Full class with module name of loaded device"""
        if getattr(self, 'devices', []):
            device_class = self.devices[0].__class__
            return '.'.join((device_class.__module__,
                             device_class.__name__))
        return ''

    @Property(str, designable=False)
    def device_name(self):
        "Name of loaded device"
        if getattr(self, 'devices', []):
            return self.devices[0].name
        return ''

    @Property(str)
    def embedded_template(self):
        """Embedded template"""
        return self.templates[self.TemplateEnum.embedded_screen.name]

    @embedded_template.setter
    def embedded_template(self, template):
        self._set_template(self.TemplateEnum.embedded_screen.name, template)

    @Property(str)
    def detailed_template(self):
        """Detailed template"""
        return self.templates[self.TemplateEnum.detailed_screen.name]

    @detailed_template.setter
    def detailed_template(self, template):
        self._set_template(self.TemplateEnum.detailed_screen.name, template)

    @Property(str)
    def engineering_template(self):
        """Engineering template"""
        return self.templates[self.TemplateEnum.engineering_screen.name]

    @engineering_template.setter
    def engineering_template(self, template):
        return self._set_template(self.TemplateEnum.engineering_screen.name,
                                  template)

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
        # If we are not fully initialized yet do not try and add anything to
        # the layout. This will happen if the QApplication has a stylesheet
        # that forces a template, prior to the creation of this display
        if self.layout() is None:
            logger.debug("Widget not initialized, do not load template")
            return
        # Clear anything that exists in the current layout
        if self._main_widget:
            logger.debug("Clearing existing layout ...")
            clear_layout(self.layout())
        # Assemble our macros
        self._last_macros = macros or self._last_macros
        for display_type in self.templates:
            value = self._last_macros.get(display_type)
            if value:
                logger.debug("Found new template %r for %r",
                             value, display_type)
                self.templates[display_type] = value
        try:
            logger.debug("Loading %s", self.current_template)
            ext = os.path.splitext(self.current_template)[1]
            # Support Python files
            if ext == '.py':
                logger.debug("Loading %r as a Python file ...",
                             self.current_template)
                self._main_widget = load_py_file(self.current_template,
                                                 macros=self._last_macros)
            # Otherwise assume you have given use a UI file
            else:
                logger.debug("Loading as a Qt Designer file ...")
                self._main_widget = Display(ui_filename=self.current_template,
                                            macros=self._last_macros)
            # Add device to all children widgets
            if self.devices:
                designer = (self._main_widget.findChildren(TyphonDesignerMixin)
                            or [])
                bases = (self._main_widget.findChildren(TyphonBase)
                         or [])
                for widget in set(bases + designer):
                    widget.add_device(self.devices[0])
        except Exception:
            logger.exception("Unable to load file %r", self.current_template)
            self._main_widget = QWidget()
        finally:
            self.layout().addWidget(self._main_widget)
            reload_widget_stylesheet(self)

    @Property(str)
    def force_template(self):
        """Force a specific template"""
        return self._forced_template

    @force_template.setter
    def force_template(self, value):
        if value != self._forced_template:
            self._forced_template = value
            self.load_template(macros=self._last_macros)

    def add_device(self, device, macros=None):
        """
        Add a Device and signals to the TyphonDeviceDisplay

        Parameters
        ----------
        device: ophyd.Device

        macros: dict, optional
            Set of macros to reload the template with. There are two fallback
            options attempted if no information is passed in. First, if the
            device has an ``md`` attribute after being loaded from a ``happi``
            database, that information will be passed in as macros. Finally, if
            no ``name`` field is passed in, we ensure the ``device.name`` and
            ``device.prefix`` are entered as well.
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
        # Ensure we at least pass in the device name and prefix
        if 'name' not in macros:
            macros['name'] = device.name
        if 'prefix' not in macros and hasattr(device, 'prefix'):
            macros['prefix'] = device.prefix
        # Reload template
        self.load_template(macros=macros)

    @Property(QSize)
    def engineering_size(self):
        """The minimum size to use the engineering template mode"""
        return self._engineering_size

    @engineering_size.setter
    def engineering_size(self, value):
        if self._engineering_size != value:
            display_type = self.display_type
            self._engineering_size = value
            if display_type != self.display_type:
                self.load_template()

    @Property(QSize)
    def embedded_size(self):
        """The maximum size to use the embedded template mode"""
        return self._embedded_size

    @embedded_size.setter
    def embedded_size(self, value):
        if self._embedded_size != value:
            display_type = self.display_type
            self._embedded_size = value
            if display_type != self.display_type:
                self.load_template()

    @classmethod
    def from_device(cls, device, template=None, macros=None):
        """
        Create a new TyphonDeviceDisplay from a Device

        Loads the signals in to the appropriate positions and sets the title to
        a cleaned version of the device name

        Parameters
        ----------
        device: ophyd.Device

        template :str, optional
            Set the ``display_template``
        macros: dict, optional
            Macro substitutions to be placed in template
        """
        display = cls()
        # Reset the template if provided
        if template:
            display.force_template = template
        # Add the device
        display.add_device(device, macros=macros)
        return display

    @Slot(object)
    def _tx(self, value):
        """Receive information from happi channel"""
        self.add_device(value['obj'], macros=value['md'])

    def _set_template(self, template_type, value):
        """Helper function for template type setters"""
        # Add our new template if valid and is different than the current
        if value and self.templates[template_type] != value:
            self.templates[template_type] = value
            # If we are currently using the old template we will need to
            # redraw with the new one
            if self.TemplateEnum(self.display_type).name == template_type:
                self.load_template()

    def _display_for_size(self, size):
        """Proper DisplayType for provided size"""
        # If we have no size information assume detailed
        if size.isEmpty():
            return DisplayTypes.detailed_screen
        # If the embedded size is larger than the current size
        # Arranged to be False for empty embedded_size
        elif (size - self._embedded_size).isEmpty():
            return DisplayTypes.embedded_screen
        # If we are larger than the engineering size
        # Arranged to be False for empty engineering_size
        elif (self._engineering_size - size).isEmpty():
            return DisplayTypes.engineering_screen
        else:
            return DisplayTypes.detailed_screen

    def resizeEvent(self, event):
        """If our resizeEvent crosses a barrier of screen type, redraw"""
        super().resizeEvent(event)
        # Add some hysteresis based on the direction of the resizing. This is
        # to prevent flashing screen approach the boundaries
        hysteresis = 50
        current_size = event.size()
        # If our old size is larger in either direction we are shrinking
        if (current_size - event.oldSize()).isValid():
            current_size += QSize(hysteresis, hysteresis)
        else:
            current_size += QSize(-hysteresis, -hysteresis)
        if (self._display_for_size(current_size) !=
            self._display_for_size(event.oldSize())
           ):
            self.load_template()
