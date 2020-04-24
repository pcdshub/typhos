import enum
import logging
import os.path
import pathlib

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Q_ENUMS, Property, Qt, Slot

import ophyd
import pcdsutils
import pcdsutils.qt
import pydm.display
import pydm.exception
import pydm.utilities

from . import signal, utils, widgets

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

DETAILED_TREE_TEMPLATE = (utils.ui_dir / f'detailed_tree.ui').resolve()
DEFAULT_TEMPLATES['detailed_screen'].append(DETAILED_TREE_TEMPLATE)


def normalize_display_type(display_type):
    try:
        return DisplayTypes(display_type)
    except Exception as ex:
        if display_type in DisplayTypes.names:
            return getattr(DisplayTypes, display_type)
        raise ValueError(f'Unrecognized display type: {display_type}') from ex


class TyphosToolButton(QtWidgets.QToolButton):
    DEFAULT_ICON = 'circle'

    def __init__(self, icon=None, *, parent=None):
        super().__init__(parent=parent)

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu
        self.clicked.connect(self._clicked)
        self.setIcon(self.get_icon(icon))
        self.setMinimumSize(24, 24)

    def _clicked(self):
        'Override in a subclass'
        menu = self.generate_context_menu()
        if menu:
            menu.exec_(QtGui.QCursor.pos())

    def generate_context_menu(self):
        'Override in subclasses'
        return None

    @classmethod
    def get_icon(cls, icon=None):
        """
        Get a QIcon, if specified, or fall back to the default

        Parameters
        ----------
        icon : str or QtGui.QIcon
            If a string, assume it is from fontawesome.
            Otherwise, use
        """
        icon = icon or cls.DEFAULT_ICON
        if isinstance(icon, str):
            return pydm.utilities.IconFont().icon(icon)
        return icon

    def open_context_menu(self, ev):
        menu = self.generate_context_menu()
        if menu:
            menu.exec_(self.mapToGlobal(ev.pos()))


class TyphosDisplayConfigButton(TyphosToolButton):
    DEFAULT_ICON = 'ellipsis-v'

    _kind_to_property = signal.TyphosSignalPanel._kind_to_property

    def __init__(self, icon=None, *, parent=None):
        super().__init__(icon=icon, parent=parent)
        self.setPopupMode(self.InstantPopup)
        self.setArrowType(Qt.NoArrow)
        self.templates = None
        self.device_display = None

    def set_device_display(self, device_display):
        self.device_display = device_display

    def create_kind_filter_menu(self, panels, base_menu, *, only):
        """
        Create the "Kind" filter menu

        Parameters
        ----------
        panels : list of TyphosSignalPanel
        base_menu : QMenu
            The menu to add actions to
        only : bool
            False - create "Show Kind" actions
            True - create "Show only Kind" actions
        """
        for kind, prop in self._kind_to_property.items():
            def selected(new_value, *, prop=prop):
                if only:
                    # Show *only* the specific kind for all panels
                    for kind, current_prop in self._kind_to_property.items():
                        visible = (current_prop == prop)
                        for panel in panels:
                            setattr(panel, current_prop, visible)
                else:
                    # Toggle visibility of the specific kind for all panels
                    for panel in panels:
                        setattr(panel, prop, new_value)

            title = f'Show only &{kind}' if only else f'Show &{kind}'
            action = base_menu.addAction(title)
            if not only:
                action.setCheckable(True)
                action.setChecked(all(getattr(panel, prop)
                                      for panel in panels))
            action.triggered.connect(selected)

    def create_name_filter_menu(self, panels, base_menu):
        """
        Create the name-based filtering menu

        Parameters
        ----------
        base_menu : QMenu
            The menu to add actions to
        """
        def text_filter_updated():
            text = line_edit.text().strip()
            for panel in panels:
                panel.nameFilter = text

        line_edit = QtWidgets.QLineEdit()

        filters = list(set(panel.nameFilter for panel in panels
                           if panel.nameFilter))
        if len(filters) == 1:
            line_edit.setText(filters[0])
        else:
            line_edit.setPlaceholderText('/ '.join(filters))

        line_edit.editingFinished.connect(text_filter_updated)
        line_edit.setObjectName('menu_action')

        action = base_menu.addAction('Filter by name:')
        action.setEnabled(False)

        action = QtWidgets.QWidgetAction(self)
        action.setDefaultWidget(line_edit)
        base_menu.addAction(action)

    def generate_context_menu(self):
        """
        Generates the custom context menu

        Embedded
        Detailed
        Engineering
        -------------
        Refresh templates
        -------------
        Kind filter > Show hinted
                      ...
                      Show only hinted
        Filter by name
        """
        base_menu = QtWidgets.QMenu(parent=self)

        display = self.device_display
        if not display:
            return base_menu

        panels = display.findChildren(signal.TyphosSignalPanel) or []
        if not panels:
            return base_menu

        display._generate_template_menu(base_menu)

        filter_menu = base_menu.addMenu("&Kind filter")
        self.create_kind_filter_menu(panels, filter_menu, only=False)
        filter_menu.addSeparator()
        self.create_kind_filter_menu(panels, filter_menu, only=True)

        base_menu.addSeparator()
        self.create_name_filter_menu(panels, base_menu)

        return base_menu


class TyphosDisplaySwitcherButton(TyphosToolButton):
    'A button in the TyphosDisplaySwitcher'
    template_selected = QtCore.Signal(pathlib.Path)

    icons = {'embedded_screen': 'compress',
             'detailed_screen': 'braille',
             'engineering_screen': 'cogs'
             }

    def __init__(self, display_type, *, parent=None):
        super().__init__(icon=self.icons[display_type], parent=parent)
        self.templates = None

    def _clicked(self):
        if self.templates is None:
            logger.warning('set_device_display not called on %s', self)
            return

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
        if menu:
            menu.exec_(self.mapToGlobal(ev.pos()))


class TyphosDisplaySwitcher(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """
    Display switcher button set for use with a Typhos Device Display
    """
    template_selected = QtCore.Signal(pathlib.Path)

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
        self.config_button = None

        for template_type in DisplayTypes.names:
            button = TyphosDisplaySwitcherButton(template_type)
            self.buttons[template_type] = button
            button.template_selected.connect(self._template_selected)
            layout.addWidget(button, 0, Qt.AlignRight)

            friendly_name = template_type.replace('_', ' ')
            button.setToolTip(f'Switch to {friendly_name}')

        self.config_button = TyphosDisplayConfigButton()
        layout.addWidget(self.config_button, 0, Qt.AlignRight)
        self.config_button.setToolTip('Display settings...')

    def _template_selected(self, template):
        self.template_selected.emit(template)
        if self.device_display is not None:
            self.device_display.force_template = template

    def set_device_display(self, display):
        self.device_display = display

        for template_type in self.buttons:
            templates = display.templates.get(template_type, [])
            self.buttons[template_type].templates = templates
        self.config_button.set_device_display(display)

    def add_device(self, device):
        ...


class TyphosTitleLabel(QtWidgets.QLabel):
    toggle_requested = QtCore.Signal()

    def __init__(self, text):
        super().__init__(text)

        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.TitleFont)
        font.setPointSizeF(14.0)
        font.setBold(True)
        self.setFont(font)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_requested.emit()

        super().mousePressEvent(event)


class TyphosDisplayTitle(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """
    Standardized Typhos Device Display title
    """
    toggle_requested = QtCore.Signal()

    def __init__(self, title='${name}', *, show_switcher=True,
                 show_underline=True, parent=None):
        self._show_underline = show_underline
        self._show_switcher = show_switcher
        super().__init__(parent=parent)

        self.label = TyphosTitleLabel(title)
        self.switcher = TyphosDisplaySwitcher()

        self.underline = QtWidgets.QFrame()
        self.underline.setFrameShape(self.underline.HLine)
        self.underline.setFrameShadow(self.underline.Plain)
        self.underline.setLineWidth(10)

        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.addWidget(self.label, 0, 0)
        self.grid_layout.addWidget(self.switcher, 0, 1, Qt.AlignRight)
        self.grid_layout.addWidget(self.underline, 1, 0, 1, 2)
        self.grid_layout.setSizeConstraint(self.grid_layout.SetMinimumSize)
        self.setLayout(self.grid_layout)

        # Set the property:
        self.show_switcher = show_switcher
        self.show_underline = show_underline

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

    @QtCore.Property(bool)
    def show_underline(self):
        return self._show_underline

    @show_underline.setter
    def show_underline(self, value):
        self._show_underline = bool(value)
        self.underline.setVisible(self._show_underline)

    def set_device_display(self, display):
        self.device_display = display

        def toggle_display():
            widget = display.display_widget
            panels = widget.findChildren(signal.TyphosSignalPanel) or []
            visible = all(panel.isVisible() for panel in panels)
            for panel in panels:
                panel.setVisible(not visible)

        self.label.toggle_requested.connect(toggle_display)

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

    device_count_threshold = 0
    signal_count_threshold = 30

    def __init__(self, parent=None, *, scrollable=True,
                 composite_heuristics=True, embedded_templates=None,
                 detailed_templates=None, engineering_templates=None,
                 display_type='detailed_screen', **kwargs):

        self._composite_heuristics = composite_heuristics
        self._current_template = None
        self._forced_template = ''
        self._macros = {}
        self._display_widget = None
        self._scrollable = False
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

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setAlignment(Qt.AlignTop)
        self._scroll_area.setObjectName('_scroll_area')
        self._scroll_area.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll_area.setWidgetResizable(True)

        super().__init__(parent=parent)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll_area)

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu
        self.scrollable = scrollable

    @Property(bool)
    def composite_heuristics(self):
        """Allow composite screen to be suggested first by heuristics?"""
        return self._composite_heuristics

    @composite_heuristics.setter
    def composite_heuristics(self, composite_heuristics):
        self._composite_heuristics = bool(composite_heuristics)

    @Property(bool)
    def scrollable(self):
        """Place the display in a scrollable area?"""
        return self._scrollable

    @scrollable.setter
    def scrollable(self, scrollable):
        # Switch between using the scroll area layout or
        if scrollable == self._scrollable:
            return

        self._scrollable = bool(scrollable)
        self._move_display_to_layout(self._display_widget)

    def _move_display_to_layout(self, widget):
        if not widget:
            return

        widget.setParent(None)
        if self._scrollable:
            self._scroll_area.setWidget(widget)
        else:
            self.layout().addWidget(widget)

        self._scroll_area.setVisible(self._scrollable)

    def _generate_template_menu(self, base_menu):
        """Generate the template switcher menu, adding it to ``base_menu``"""
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

    def generate_context_menu(self):
        """
        Generates the custom context menu, and populates it with any external
        tools that have been loaded.

        Returns
        -------
        QMenu
        """
        base_menu = QtWidgets.QMenu(parent=self)
        self._generate_template_menu(base_menu)
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

    def _remove_display(self):
        """
        Remove the display widget, readying for a new template
        """
        display_widget = self._display_widget
        if display_widget:
            if self._scroll_area.widget():
                self._scroll_area.takeWidget()
            self.layout().removeWidget(display_widget)
            display_widget.deleteLater()

        self._display_widget = None

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

        self._remove_display()

        template = (self._forced_template or
                    self.get_best_template(self._display_type, self.macros))

        if not template:
            widget = QtWidgets.QWidget()
            template = None
        else:
            try:
                widget = self._load_template(template)
            except Exception as ex:
                logger.exception("Unable to load file %r", template)
                # If we have a previously defined template
                if self._current_template is not None:
                    # Fallback to it so users have a choice
                    self._load_template(self._current_template)
                    pydm.exception.raise_to_operator(ex)
                else:
                    widget = QtWidgets.QWidget()
                    template = None

        if widget:
            widget.setObjectName('display_widget')

        self._display_widget = widget
        self._current_template = template
        self._update_children()
        self._move_display_to_layout(self._display_widget)

        utils.reload_widget_stylesheet(self)

    @property
    def display_widget(self):
        """
        The widget from the display itself
        """
        return self._display_widget

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
        """
        Load template from file and return the widget
        """
        loader = (pydm.display.load_py_file if filename.suffix == '.py'
                  else pydm.display.load_ui_file)

        logger.debug('Load template using %s: %r', loader.__name__, filename)
        return loader(str(filename), macros=self._macros)

    def _update_children(self):
        """
        Notify child widgets of this device display + the device
        """
        device = self.device
        display = self._display_widget
        designer = display.findChildren(widgets.TyphosDesignerMixin) or []
        bases = display.findChildren(utils.TyphosBase) or []

        for widget in set(bases + designer):
            if device and hasattr(widget, 'add_device'):
                widget.add_device(device)

            if hasattr(widget, 'set_device_display'):
                widget.set_device_display(self)

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

            # 2. Composite heuristics, if enabled
            if self._composite_heuristics and view == 'detailed':
                if self.suggest_composite_screen(cls):
                    template_list.append(DETAILED_TREE_TEMPLATE)

            # 3. Templates based on class hierarchy names
            filenames = utils.find_templates_for_class(
                cls, view, utils.DISPLAY_PATHS)
            for filename in filenames:
                if filename not in template_list:
                    template_list.append(filename)
                    logger.debug('Found new template %s: %s (total=%d)',
                                 display_type, filename, len(template_list))

            # 4. Default templates
            template_list.extend(
                [templ for templ in DEFAULT_TEMPLATES[display_type]
                 if templ not in template_list]
            )

    @classmethod
    def suggest_composite_screen(cls, device_cls):
        """
        Should the composite screen be suggested for the given class?

        Returns
        -------
        composite : bool
            If True, favor the composite screen
        """
        num_devices = 0
        num_signals = 0
        for attr, component in utils._get_top_level_components(device_cls):
            num_devices += issubclass(component.cls, ophyd.Device)
            num_signals += issubclass(component.cls, ophyd.Signal)

        specific_screens = cls._get_specific_screens(device_cls)
        if (len(specific_screens) or
                (num_devices <= cls.device_count_threshold and
                 num_signals >= cls.signal_count_threshold)):
            # 1. There's a custom screen - we probably should use them
            # 2. There aren't many devices, so the composite display isn't
            #    useful
            # 3. There are many signals, which should be broken up somehow
            composite = False
        else:
            # 1. No custom screen, or
            # 2. Many devices or a relatively small number of signals
            composite = True

        logger.debug(
            '%s screens=%s num_signals=%d num_devices=%d -> composite=%s',
            device_cls, specific_screens, num_signals, num_devices, composite
        )
        return composite

    @classmethod
    def from_device(cls, device, template=None, macros=None, **kwargs):
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
        **kwargs
            Passed to the class init
        """
        display = cls(**kwargs)
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
        **kwargs
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

    @classmethod
    def _get_specific_screens(cls, device_cls):
        """
        Get the list of specific screens for a given device class

        That is, screens that are not default Typhos-provided screens
        """
        return [
            template for template in utils.find_templates_for_class(
                device_cls, 'detailed', utils.DISPLAY_PATHS)
            if not utils.is_standard_template(template)
        ]

    @Slot(object)
    def _tx(self, value):
        """Receive information from happi channel"""
        self.add_device(value['obj'], macros=value['md'])
