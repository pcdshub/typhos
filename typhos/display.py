import enum
import logging
import os.path
import pathlib

from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Q_ENUMS, Property, Slot, Qt

import pcdsutils
import pcdsutils.qt
import pydm.display
import pydm.exception
import pydm.utilities

from . import utils
from . import widgets

logger = logging.getLogger(__name__)


class DisplayTypes(enum.IntEnum):
    """Types of Available Templates"""
    embedded_screen = 0
    detailed_screen = 1
    engineering_screen = 2


_DisplayTypes = utils.pyqt_class_from_enum(DisplayTypes)
DisplayTypes.names = [view.name for view in DisplayTypes]

DEFAULT_TEMPLATES = {
    name: [(utils.ui_dir / f'{name}.ui').resolve()]
    for name in DisplayTypes.names
}

def normalize_display_type(display_type):
    try:
        return DisplayTypes(display_type)
    except Exception as ex:
        if display_type in DisplayTypes.names:
            return getattr(DisplayTypes, display_type)
        raise ValueError(f'Unrecognized display type: {display_type}') from ex


class TyphosDisplaySwitcherButton(QtWidgets.QPushButton):
    'A button in the TyphosDisplaySwitcher'
    template_selected = QtCore.Signal(pathlib.Path)

    def __init__(self, icon, parent=None):
        super().__init__(parent=parent)

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu
        self.templates = None
        self.clicked.connect(self._select_first_template)
        self.setIcon(icon)
        self.setMinimumSize(32, 32)

    def _select_first_template(self):
        try:
            template = self.templates[0]
        except IndexError:
            return

        self.template_selected.emit(template)

    def generate_context_menu(self):
        if not self.templates:
            return

        menu = QtWidgets.QMenu(parent=self)
        for template in self.templates:
            def selected(*, template=template):
                self.template_selected.emit(template)

            action = menu.addAction(template.name)
            action.triggered.connect(selected)
        return menu

    def open_context_menu(self, ev):
        menu = self.generate_context_menu()
        menu.exec_(self.mapToGlobal(ev.pos()))


class TyphosDisplaySwitcher(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """
    Display switcher button set for use with a Typhos Device Display
    """
    template_selected = QtCore.Signal(pathlib.Path)

    icons = {'embedded_screen': 'compress',
             'detailed_screen': 'braille',
             'engineering_screen': 'cogs'
             }

    def __init__(self, parent=None, **kwargs):
        # Intialize background variable
        super().__init__(parent=None)

        self.device_display = None
        self.buttons = {}
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu

        if parent:
            self.setParent(parent)

        self._create_ui()

    def _create_ui(self):
        layout = self.layout()
        self.buttons.clear()

        for template_type in DisplayTypes.names:
            icon = pydm.utilities.IconFont().icon(self.icons[template_type])
            button = TyphosDisplaySwitcherButton(icon)
            self.buttons[template_type] = button
            button.template_selected.connect(self._template_selected)
            layout.addWidget(button, 0, Qt.AlignRight)

            friendly_name = template_type.replace('_', ' ')
            button.setToolTip(f'Switch to {friendly_name}')

    def _template_selected(self, template):
        self.template_selected.emit(template)
        if self.device_display is not None:
            self.device_display.force_template = template

    def set_device_display(self, display):
        self.device_display = display

        for template_type in self.buttons:
            templates = display.templates.get(template_type, [])
            self.buttons[template_type].templates = templates

    def add_device(self, device):
        ...


class TyphosDisplayTitle(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """
    Standardized Typhos Device Display title
    """
    def __init__(self, title='${name}', *, show_switcher=True, parent=None):
        self._show_switcher = show_switcher
        super().__init__(parent=parent)

        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.TitleFont)
        font.setPointSizeF(14.0)
        font.setBold(True)

        self.label = QtWidgets.QLabel(title)
        self.label.setFont(font)

        self.switcher = TyphosDisplaySwitcher()

        self.underline = QtWidgets.QFrame()
        self.underline.setFrameShape(self.underline.HLine)
        self.underline.setFrameShadow(self.underline.Plain)
        self.underline.setLineWidth(10)

        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.addWidget(self.label, 0, 0)
        self.grid_layout.addWidget(self.switcher, 0, 1, Qt.AlignRight)
        self.grid_layout.addWidget(self.underline, 1, 0, 1, 2)
        self.setLayout(self.grid_layout)

        # Set the property:
        self.show_switcher = show_switcher

    @Property(bool)
    def show_switcher(self):
        return self._show_switcher

    @show_switcher.setter
    def show_switcher(self, value):
        self._show_switcher = bool(value)
        self.switcher.setVisible(self._show_switcher)

    def add_device(self, device):
        if not self.label.text():
            self.label.setText(device.name)

    # Make designable properties from the title label available here as well
    locals().update(**pcdsutils.qt.forward_properties(
        locals_dict=locals(),
        attr_name='label',
        cls=QtWidgets.QLabel,
        superclasses=[QtWidgets.QFrame],
        condition=('alignment', 'buddy', 'font', 'indent', 'margin',
                   'openExternalLinks', 'pixmap', 'spacing', 'text',
                   'textFormat', 'textInteractionFlags', 'wordWrap',
                   ),
    ))

    # Make designable properties from the grid_layout
    locals().update(**pcdsutils.qt.forward_properties(
        locals_dict=locals(),
        attr_name='grid_layout',
        cls=QtWidgets.QHBoxLayout,
        superclasses=[QtWidgets.QFrame],
        prefix='layout_',
        condition=('margin', 'spacing'),
        )
    )

    # Make designable properties from the underline
    locals().update(**pcdsutils.qt.forward_properties(
        locals_dict=locals(),
        attr_name='underline',
        cls=QtWidgets.QFrame,
        superclasses=[QtWidgets.QFrame],
        prefix='underline_',
        condition=('palette', 'styleSheet', 'lineWidth', 'midLineWidth'),
    ))


class TyphosDeviceDisplay(utils.TyphosBase, widgets.TyphosDesignerMixin,
                          _DisplayTypes):
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
    you would like to display, and an optional image. As with ``typhos``
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
    Q_ENUMS(_DisplayTypes)
    TemplateEnum = DisplayTypes  # For convenience

    def __init__(self, parent=None, *, embedded_templates=None,
                 detailed_templates=None, engineering_templates=None,
                 display_type='detailed_screen',
                 **kwargs):
        # Intialize background variable
        self._forced_template = ''
        self._macros = dict()
        self._main_widget = None
        self._searched = False

        self.templates = {name: [] for name in DisplayTypes.names}
        self._display_type = normalize_display_type(display_type)

        instance_templates = {
            'embedded_screen': embedded_templates or [],
            'detailed_screen': detailed_templates or [],
            'engineering_screen': engineering_templates or [],
        }
        for view, path_list in instance_templates.items():
            paths = [pathlib.Path(p).expanduser().resolve() for p in path_list]
            self.templates[view].extend(paths)

        # Set this to None first so we don't render
        super().__init__(parent=parent)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu

    def generate_context_menu(self):
        """
        Generates the custom context menu, and populates it with any external
        tools that have been loaded.  PyDMWidget subclasses should override
        this method (after calling superclass implementation) to add the menu.

        Returns
        -------
        QMenu
        """
        base_menu = QtWidgets.QMenu(parent=self)

        for view, filenames in self.templates.items():
            if view.endswith('_screen'):
                view = view.split('_screen')[0]
            menu = base_menu.addMenu(view.capitalize())

            for filename in filenames:
                def switch_template(*, filename=filename):
                    self.force_template = filename

                action = menu.addAction(os.path.split(filename)[-1])
                action.triggered.connect(switch_template)

        def refresh_templates():
            self.search_for_templates()
            self.load_best_template()

        base_menu.addSeparator()
        refresh_action = base_menu.addAction("Refresh Templates")
        refresh_action.triggered.connect(refresh_templates)

        return base_menu

    def open_context_menu(self, ev):
        """
        Handler for when the Default Context Menu is requested.

        Parameters
        ----------
        ev : QEvent
        """
        menu = self.generate_context_menu()
        menu.exec_(self.mapToGlobal(ev.pos()))

    @property
    def current_template(self):
        """Current template being rendered"""
        return self._current_template

    @Property(_DisplayTypes)
    def display_type(self):
        return self._display_type

    @display_type.setter
    def display_type(self, value):
        value = normalize_display_type(value)
        if self._display_type != value:
            self._display_type = value
            self.load_best_template()

    @property
    def macros(self):
        return dict(self._macros)

    @macros.setter
    def macros(self, macros):
        self._macros.clear()
        self._macros.update(**(macros or {}))

        # If any display macros are specified, re-search for templates:
        if any(view in self._macros for view in DisplayTypes.names):
            self.search_for_templates()

    @Property(str, designable=False)
    def device_class(self):
        """Full class with module name of loaded device"""
        device = self.device
        cls = self.device.__class__
        return f'{cls.__module__}.{cls.__name__}' if device else ''

    @Property(str, designable=False)
    def device_name(self):
        "Name of loaded device"
        device = self.device
        return device.name if device else ''

    @property
    def device(self):
        '''The device associated with this Device Display'''
        try:
            device, = self.devices
            return device
        except ValueError:
            ...

    def get_best_template(self, display_type, macros):
        display_type = normalize_display_type(display_type).name

        templates = self.templates[display_type]
        if templates:
            return templates[0]

        logger.warning("No templates available for display type: %s",
                       self._display_type)

    def load_best_template(self):
        """
        Load a new template
        """
        if self.layout() is None:
            # If we are not fully initialized yet do not try and add anything
            # to the layout. This will happen if the QApplication has a
            # stylesheet that forces a template prior to the creation of this
            # display
            return

        if not self._searched:
            self.search_for_templates()

        # Clear anything that exists in the current layout
        if self._main_widget:
            logger.debug("Clearing existing layout ...")
            utils.clear_layout(self.layout())

        template = (self._forced_template or
                    self.get_best_template(self._display_type, self.macros))

        if not template:
            self._main_widget = QtWidgets.QWidget()
            self._current_template = None
        else:
            try:
                self._load_template(template)
            except Exception as ex:
                logger.exception("Unable to load file %r", template)
                # If we have a previously defined template
                if self._current_template is not None:
                    # Fallback to it so users have a choice
                    self._load_template(self._current_template)
                    pydm.exception.raise_to_operator(ex)
                else:
                    self._main_widget = QtWidgets.QWidget()
                    self._current_template = None

        self.layout().addWidget(self._main_widget)
        utils.reload_widget_stylesheet(self)

    @staticmethod
    def _get_templates_from_macros(macros):
        ret = {}
        for display_type in DisplayTypes.names:
            ret[display_type] = None
            try:
                value = macros[display_type]
            except KeyError:
                ...
            else:
                if not value:
                    continue
                try:
                    value = pathlib.Path(value)
                except ValueError as ex:
                    logger.debug('Invalid path specified in macro: %s=%s',
                                 display_type, value, exc_info=ex)
                else:
                    ret[display_type] = list(utils.find_file_in_paths(value))

        return ret

    def _load_template(self, filename):
        loader = (pydm.display.load_py_file if filename.suffix == '.py'
                  else pydm.display.load_ui_file)

        logger.debug('Load template using %s: %r', loader.__name__, filename)
        self._main_widget = main = loader(str(filename), macros=self._macros)

        # Notify child widgets of: this device dispay + the device
        device = self.device
        designer = main.findChildren(widgets.TyphosDesignerMixin) or []
        bases = main.findChildren(utils.TyphosBase) or []

        for widget in set(bases + designer):
            if device and hasattr(widget, 'add_device'):
                widget.add_device(device)

            if hasattr(widget, 'set_device_display'):
                widget.set_device_display(self)

        self._current_template = filename

    @Property(str)
    def force_template(self):
        """Force a specific template"""
        return self._forced_template

    @force_template.setter
    def force_template(self, value):
        if value != self._forced_template:
            self._forced_template = value
            self.load_best_template()

    @staticmethod
    def _build_macros_from_device(device, macros=None):
        result = {}
        if hasattr(device, 'md'):
            if isinstance(device.md, dict):
                result = dict(device.md)
            else:
                result = dict(device.md.post())

        if 'name' not in result:
            result['name'] = device.name
        if 'prefix' not in result and hasattr(device, 'prefix'):
            result['prefix'] = device.prefix

        result.update(**(macros or {}))
        return result

    def add_device(self, device, macros=None):
        """
        Add a Device and signals to the TyphosDeviceDisplay

        The full dictionary of macros is built with the following order of
        precedence::

           1. Macros from the device metadata itself
           2. If available, `name`, and `prefix` will be added from the device
           3. The argument ``macros`` is then used to fill/update the final
              macro dictionary

        Parameters
        ----------
        device: ophyd.Device
            The device to add
        macros: dict, optional
            Additional macros to use/replace the defaults.
        """
        # We only allow one device at a time
        if self.devices:
            logger.debug("Removing devices %r", self.devices)
            self.devices.clear()
        # Add the device to the cache
        super().add_device(device)
        self._searched = False
        self.macros = self._build_macros_from_device(device, macros=macros)
        self.load_best_template()

    def search_for_templates(self):
        '''
        Search the filesystem for device-specific templates
        '''
        device = self.device
        if not device:
            logger.debug('Cannot search for templates without device')
            return

        self._searched = True
        cls = device.__class__

        logger.debug('Searching for templates for %s', cls.__name__)
        macro_templates = self._get_templates_from_macros(self._macros)

        for display_type in DisplayTypes.names:
            view = display_type
            if view.endswith('_screen'):
                view = view.split('_screen')[0]

            template_list = self.templates[display_type]
            template_list.clear()

            # 1. Highest priority: macros
            for template in set(macro_templates[display_type] or []):
                template_list.append(template)
                logger.debug('Adding macro template %s: %s (total=%d)',
                             display_type, template, len(template_list))

            # 2. Templates based on class hierarchy names
            filenames = utils.find_templates_for_class(
                cls, view, utils.DISPLAY_PATHS)
            for filename in filenames:
                if filename not in template_list:
                    template_list.append(filename)
                    logger.debug('Found new template %s: %s (total=%d)',
                                 display_type, filename, len(template_list))

            # 3. Default templates
            template_list.extend(
                [templ for templ in DEFAULT_TEMPLATES[display_type]
                 if templ not in template_list]
            )

    @classmethod
    def from_device(cls, device, template=None, macros=None):
        """
        Create a new TyphosDeviceDisplay from a Device

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

    @classmethod
    def from_class(cls, klass, *, template=None, macros=None, **kwargs):
        """
        Create a new TyphosDeviceDisplay from a Device class

        Loads the signals in to the appropriate positions and sets the title to
        a cleaned version of the device name

        Parameters
        ----------
        klass : str or class
        template :str, optional
            Set the ``display_template``
        macros: dict, optional
            Macro substitutions to be placed in template
        kwargs : dict
            Extra arguments are used at device instantiation

        Returns
        -------
        TyphosDeviceDisplay
        """
        try:
            obj = pcdsutils.utils.get_instance_by_name(klass, **kwargs)
        except Exception:
            logger.exception('Failed to generate TyphosDeviceDisplay from '
                             'device %s', obj)
            return None

        return cls.from_device(obj, template=template, macros=macros)

    @Slot(object)
    def _tx(self, value):
        """Receive information from happi channel"""
        self.add_device(value['obj'], macros=value['md'])
