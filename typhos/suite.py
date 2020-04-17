import logging
import os
import textwrap
from functools import partial

from pyqtgraph.parametertree import ParameterTree
from pyqtgraph.parametertree import parameterTypes as ptypes
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import QWidget

import ophyd
import pcdsutils.qt

from . import widgets
from .display import TyphosDeviceDisplay
from .tools import TyphosConsole, TyphosLogDisplay, TyphosTimePlot
from .utils import (TyphosBase, clean_name, flatten_tree, raise_to_operator,
                    save_suite, saved_template)
from .widgets import SubDisplay, TyphosSidebarItem

logger = logging.getLogger(__name__)


class SidebarParameter(ptypes.Parameter):
    """
    Parameter to hold information for the sidebar
    """
    itemClass = TyphosSidebarItem
    sigOpen = Signal(object)
    sigHide = Signal(object)
    sigEmbed = Signal(object)

    def __init__(self, embeddable=None, **opts):
        super().__init__(**opts)
        self.embeddable = embeddable


class DeviceParameter(SidebarParameter):
    """Parameter to hold information Ophyd Device"""
    itemClass = TyphosSidebarItem

    def __init__(self, device, subdevices=True, **opts):
        # Set options for parameter
        opts['name'] = clean_name(device, strip_parent=device.root)
        self.device = device
        opts['expanded'] = False
        # Grab children from the given device
        children = list()
        if subdevices:
            for child in device._sub_devices:
                subdevice = getattr(device, child)
                # If that device has children, make sure they are also
                # displayed further in the tree
                if subdevice._sub_devices:
                    children.append(
                        DeviceParameter(subdevice, subdevices=False))
                # Otherwise just make a regular parameter out of it
                else:
                    child_name = clean_name(subdevice,
                                            strip_parent=subdevice.root)
                    child_display = TyphosDeviceDisplay.from_device(subdevice)
                    children.append(SidebarParameter(value=child_display,
                                                     name=child_name,
                                                     embeddable=True))
        opts['children'] = children
        super().__init__(value=TyphosDeviceDisplay.from_device(device),
                         embeddable=opts.pop('embeddable', True),
                         **opts)


class TyphosSuite(TyphosBase):
    """
    Complete Typhos Window

    This contains all the neccesities to load tools and devices into a Typhos
    window.

    Parameters
    ----------
    parent : QWidget, optional
    """
    default_tools = {'Log': TyphosLogDisplay,
                     'StripTool': TyphosTimePlot,
                     'Console': TyphosConsole}

    def __init__(self, parent=None, *, pin=False):
        super().__init__(parent=parent)

        self._tree = ParameterTree(parent=self, showHeader=False)
        self._tree.setAlternatingRowColors(False)
        self._save_action = ptypes.ActionParameter(name='Save Suite')
        self._tree.addParameters(self._save_action)
        self._save_action.sigActivated.connect(self.save)

        self._bar = pcdsutils.qt.QPopBar(title='Suite', parent=self,
                                         widget=self._tree, pin=pin)

        self._content_frame = QtWidgets.QFrame(self)
        self._content_frame.setObjectName("content")
        self._content_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self._content_frame.setLayout(QtWidgets.QHBoxLayout())

        # Horizontal box layout: [PopBar] [Content Frame]
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.setSpacing(1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._bar)
        layout.addWidget(self._content_frame)

        self.embedded_dock = None

    def add_subdisplay(self, name, display, category):
        """
        Add an arbitrary widget to the tree of available widgets and tools

        Parameters
        ----------
        name : str
            Name to be displayed in the tree

        display : QWidget
            QWidget to show in the dock when expanded.

        category : str
            The top level group to place the controls under in the tree. If the
            category does not exist, a new one will be made
        """
        logger.debug("Adding widget %r with %r to %r ...",
                     name, display, category)
        # Create our parameter
        parameter = SidebarParameter(value=display, name=name)
        self._add_to_sidebar(parameter, category)

    @property
    def top_level_groups(self):
        """All top-level groups as name, ``QGroupParameterItem`` pairs"""
        root = self._tree.invisibleRootItem()
        return dict((root.child(idx).param.name(),
                     root.child(idx).param)
                    for idx in range(root.childCount()))

    def add_tool(self, name, tool):
        """
        Add a widget to the toolbar

        Shortcut for:

        .. code:: python

           suite.add_subdisplay(name, tool, category='Tools')

        Parameters
        ----------
        name :str
            Name of tool to be displayed in sidebar

        tool: QWidget
            Widget to be added to ``.ui.subdisplay``
        """
        self.add_subdisplay(name, tool, 'Tools')

    def get_subdisplay(self, display):
        """
        Get a subdisplay by name or contained device

        Parameters
        ----------
        display :str or Device
            Name of screen or device

        Returns
        -------
        widget : QWidget
            Widget that is a member of the :attr:`.ui.subdisplay`

        Example
        -------
        .. code:: python

            suite.get_subdisplay(my_device.x)
            suite.get_subdisplay('My Tool')
        """
        if isinstance(display, SidebarParameter):
            return display.value()
        for group in self.top_level_groups.values():
            tree = flatten_tree(group)
            for param in tree:
                match = (display in getattr(param.value(), 'devices', [])
                         or param.name() == display)
                if match:
                    return param.value()
        # If we got here we can't find the subdisplay
        raise ValueError(f"Unable to find subdisplay {display}")

    @Slot(str)
    @Slot(object)
    def show_subdisplay(self, widget):
        """
        Open a display in the dock system

        Parameters
        ----------
        widget: QWidget, SidebarParameter or str
            If given a ``SidebarParameter`` from the tree, the widget will be
            shown and the sidebar item update. Otherwise, the information is
            passed to :meth:`.get_subdisplay`
        """
        # Grab true widget
        if not isinstance(widget, QWidget):
            widget = self.get_subdisplay(widget)
        # Setup the dock
        dock = SubDisplay(self)
        # Set sidebar properly
        self._show_sidebar(widget, dock)
        # Add the widget to the dock
        logger.debug("Showing widget %r ...", widget)
        if hasattr(widget, 'display_type'):
            widget.display_type = widget.detailed_screen
        widget.setVisible(True)
        dock.setWidget(widget)
        # Add to layout
        self._content_frame.layout().addWidget(dock)

    @Slot(str)
    @Slot(object)
    def embed_subdisplay(self, widget):
        """Embed a display in the dock system"""
        # Grab the relevant display
        if not self.embedded_dock:
            self.embedded_dock = SubDisplay()
            self.embedded_dock.setWidget(QWidget())
            self.embedded_dock.widget().setLayout(QtWidgets.QVBoxLayout())
            self.embedded_dock.widget().layout().addStretch(1)
            self._content_frame.layout().addWidget(self.embedded_dock)

        if not isinstance(widget, QWidget):
            widget = self.get_subdisplay(widget)
        # Set sidebar properly
        self._show_sidebar(widget, self.embedded_dock)
        # Set our widget to be embedded
        widget.setVisible(True)
        widget.display_type = widget.embedded_screen
        widget_count = self.embedded_dock.widget().layout().count()
        self.embedded_dock.widget().layout().insertWidget(widget_count - 1,
                                                          widget)

    @Slot()
    @Slot(object)
    def hide_subdisplay(self, widget):
        """
        Hide a visible subdisplay

        Parameters
        ----------
        widget: SidebarParameter or Subdisplay
            If you give a SidebarParameter, we will find the corresponding
            widget and hide it. If the widget provided to us is inside a
            DockWidget we will close that, otherwise the widget is just hidden.
        """
        if not isinstance(widget, QWidget):
            widget = self.get_subdisplay(widget)
        sidebar = self._get_sidebar(widget)
        if sidebar:
            for item in sidebar.items:
                item._mark_hidden()
        else:
            logger.warning("Unable to find sidebar item for %r", widget)
        # Make sure the actual widget is hidden
        logger.debug("Hiding widget %r ...", widget)
        if isinstance(widget.parent(), QtWidgets.QDockWidget):
            logger.debug("Closing dock ...")
            widget.parent().close()
        # Hide the full dock if this is the last widget
        elif (self.embedded_dock
              and widget.parent() == self.embedded_dock.widget()):
            logger.debug("Removing %r from embedded widget layout ...",
                         widget)
            self.embedded_dock.widget().layout().removeWidget(widget)
            widget.hide()
            if self.embedded_dock.widget().layout().count() == 1:
                logger.debug("Closing embedded layout ...")
                self.embedded_dock.close()
                self.embedded_dock = None
        else:
            widget.hide()

    @Slot()
    def hide_subdisplays(self):
        """
        Hide all open displays
        """
        # Grab children from devices
        for group in self.top_level_groups.values():
            for param in flatten_tree(group)[1:]:
                self.hide_subdisplay(param)

    @property
    def tools(self):
        """Tools loaded into the TyphosDeviceDisplay"""
        if 'Tools' in self.top_level_groups:
            return [param.value()
                    for param in self.top_level_groups['Tools'].childs]
        return []

    def add_device(self, device, children=True, category='Devices'):
        """
        Add a device to the ``TyphosSuite``

        Parameters
        ----------
        device: ophyd.Device

        children: bool, optional
            Also add any ``subdevices`` of this device to the suite as well.

        category: str, optional
            Category of device. By default, all devices will just be added to
            the "Devices" group
        """
        super().add_device(device)
        # Create DeviceParameter and add to top level category
        dev_param = DeviceParameter(device, subdevices=children)
        self._add_to_sidebar(dev_param, category)
        # Grab children
        for child in flatten_tree(dev_param)[1:]:
            self._add_to_sidebar(child)
        # Add a device to all the tool displays
        for tool in self.tools:
            try:
                tool.add_device(device)
            except Exception:
                logger.exception("Unable to add %s to tool %s",
                                 device.name, type(tool))

    @classmethod
    def from_device(cls, device, parent=None, tools=dict(), pin=False,
                    **kwargs):
        """
        Create a new TyphosDeviceDisplay from an ophyd.Device

        Parameters
        ----------
        device: ophyd.Device

        children: bool, optional
            Choice to include child Device components

        parent: QWidgets

        tools: dict, optional
            Tools to load for the object. ``dict`` should be name, class pairs.
            By default these will be ``.default_tools``, but ``None`` can be
            passed to avoid tool loading completely.

        kwargs:
            Passed to :meth:`TyphosSuite.add_device`
        """
        display = cls(parent=parent, pin=pin)
        if tools is not None:
            if not tools:
                logger.debug("Using default TyphosSuite tools ...")
                tools = cls.default_tools
                for name, tool in tools.items():
                    try:
                        display.add_tool(name, tool())
                    except Exception:
                        logger.exception("Unable to load %s", type(tool))
        display.add_device(device, **kwargs)
        display.show_subdisplay(device)
        return display

    def save(self):
        """
        Save the TyphosSuite to a file using :meth:`typhos.utils.save_suite`

        A ``QFileDialog`` will be used to query the user for the desired
        location of the created Python file

        The template will be of the form:

        .. code::
        """
        logger.debug("Requesting file location for saved TyphosSuite")
        root_dir = os.getcwd()
        filename = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save TyphosSuite', root_dir, "Python (*.py)")
        if filename:
            try:
                with open(filename[0], 'w+') as handle:
                    save_suite(self, handle)
            except Exception as exc:
                logger.exception("Failed to save TyphosSuite")
                raise_to_operator(exc)
        else:
            logger.debug("No filename chosen")

    # Add the template to the docstring
    save.__doc__ += textwrap.indent('\n' + saved_template, '\t\t')

    def _get_sidebar(self, widget):
        items = {}
        for group in self.top_level_groups.values():
            for item in flatten_tree(group):
                items[item.value()] = item
        return items.get(widget)

    def _show_sidebar(self, widget, dock):
        sidebar = self._get_sidebar(widget)
        if sidebar:
            for item in sidebar.items:
                item._mark_shown()
            # Make sure we react if the dock is closed outside of our menu
            dock.closing.connect(partial(self.hide_subdisplay, sidebar))
        else:
            logger.warning("Unable to find sidebar item for %r", widget)

    def _add_to_sidebar(self, parameter, category=None):
        """Add an item to the sidebar, connecting necessary signals"""
        if category:
            # Create or grab our category
            if category in self.top_level_groups:
                group = self.top_level_groups[category]
            else:
                logger.debug("Creating new category %r ...", category)
                group = ptypes.GroupParameter(name=category)
                self._tree.addParameters(group)
                self._tree.sortItems(0, Qt.AscendingOrder)
            logger.debug("Adding %r to category %r ...",
                         parameter.name(), group.name())
            group.addChild(parameter)
        # Setup window to have a parent
        parameter.value().setParent(self)
        parameter.value().setHidden(True)
        logger.debug("Connecting parameter signals ...")
        parameter.sigOpen.connect(partial(self.show_subdisplay,
                                          parameter))
        parameter.sigHide.connect(partial(self.hide_subdisplay,
                                          parameter))
        if parameter.embeddable:
            parameter.sigEmbed.connect(partial(self.embed_subdisplay,
                                               parameter))
        return parameter


class TyphosTitleFilter(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """
    Display switcher button set for use with a Typhos Device Display
    """
    template_selected = QtCore.Signal(object)

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

        from . import display
        for template_type in display.DisplayTypes.names:
            # icon = pydm.utilities.IconFont().icon(self.icons[template_type])
            button = QtWidgets.QPushButton()
            button.setFixedWidth(50)
            self.buttons[template_type] = button
            # button.template_selected.connect(self._template_selected)
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


class TyphosDeviceContainerTitle(QtWidgets.QFrame,
                                 widgets.TyphosDesignerMixin):
    """
    Standardized Typhos Device Display title
    """
    toggle_requested = QtCore.Signal()

    def __init__(self, title, *, show_filter=True, show_line=False,
                 parent=None):
        self._show_filter = show_filter
        super().__init__(parent=parent)

        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.TitleFont)
        font.setPointSizeF(14.0)
        font.setBold(True)

        self.label = QtWidgets.QLabel(title)
        self.label.setFont(font)

        self.filter = TyphosTitleFilter()

        self.underline = QtWidgets.QFrame()
        self.underline.setFrameShape(self.underline.HLine)
        self.underline.setFrameShadow(self.underline.Plain)
        self.underline.setLineWidth(10)

        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.addWidget(self.label, 0, 0)
        self.grid_layout.addWidget(self.filter, 0, 1, Qt.AlignRight)
        self.grid_layout.addWidget(self.underline, 1, 0, 1, 2)
        self.grid_layout.setContentsMargins(5, 0, 1, 0)
        self.setLayout(self.grid_layout)

        # Set the property:
        self.show_filter = show_filter
        self.show_line = show_line

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_requested.emit()

        super().mousePressEvent(event)

    @QtCore.Property(bool)
    def show_line(self):
        return self._show_line

    @show_line.setter
    def show_line(self, value):
        self._show_line = bool(value)
        self.underline.setVisible(self._show_line)

    @QtCore.Property(bool)
    def show_filter(self):
        return self._show_filter

    @show_filter.setter
    def show_filter(self, value):
        self._show_filter = bool(value)
        self.filter.setVisible(self._show_filter)

    def add_device(self, device):
        if not self.label.text():
            self.label.setText(device.name)


class TyphosDeviceContainer(QtWidgets.QFrame):
    threshold = 5

    def __init__(self, title='', parent=None):
        super().__init__(parent=parent)

        self._title = TyphosDeviceContainerTitle(title=title)
        self._title.toggle_requested.connect(self._toggle_view)
        self._content = QtWidgets.QFrame()

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._title)
        self.layout().addWidget(self._content)

        self._content.setLineWidth(1)
        self._content.setFrameShadow(QtWidgets.QFrame.Raised)
        self._content.setFrameShape(QtWidgets.QFrame.StyledPanel)

        self._content_layout = QtWidgets.QVBoxLayout()
        # self._content_layout.
        self._content.setLayout(self._content_layout)

        if title:
            self.setObjectName(title)

        self._content.setObjectName(self.objectName() + '_content')
        self._filter_visible = False
        self._line_visible = False
        # self.cls = cls
        # self.device_display = TyphosDeviceDisplay()

    def _toggle_view(self):
        visible = not self._content.isVisible()
        self._content.setVisible(visible)
        if visible:
            self._title.show_filter = self._filter_visible
            self._title.show_line = self._line_visible
        else:
            self._filter_visible = self._title.show_filter
            self._line_visible = self._title.show_line
            self._title.show_filter = False
            self._title.show_line = False

    @property
    def widgets(self):
        for idx in range(self._content_layout.count()):
            yield self._content_layout.itemAt(idx).widget()

    def add_widget(self, widget):
        self._content_layout.addWidget(widget, 0, Qt.AlignTop)

    def complete_layout(self):
        if len(list(self.widgets)) < self.threshold:
            self._title.show_line = False
            self._title.show_filter = False

            font = self._title.label.font()
            font.setPointSizeF(font.pointSizeF() * 0.8)
            self._title.label.setFont(font)


class TyphosCompositeDisplay(TyphosBase):
    """
    Complete Typhos Window

    This contains all the necessities to load tools and devices into a Typhos
    window.

    Parameters
    ----------
    parent : QWidget, optional
    """
    default_tools = {'Log': TyphosLogDisplay,
                     'StripTool': TyphosTimePlot,
                     'Console': TyphosConsole}

    def __init__(self, use_templates=True, parent=None):
        super().__init__(parent=parent)

        self._scroll_area = QtWidgets.QScrollArea()  # (self)
        self._scroll_area.setAlignment(Qt.AlignTop)
        self._scroll_area.setObjectName("content")
        self._scroll_area.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn)
        self._scroll_area.setObjectName(self.objectName() + '_scroll_area')

        self._main_frame = TyphosDeviceContainer(parent=self._scroll_area)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll_area)

        self.use_templates = use_templates
        self.embedded_dock = None

    def add_device(self, device, children=True, category='Devices'):
        """
        Add a device to the ``TyphosSuite``

        Parameters
        ----------
        device: ophyd.Device

        children: bool, optional
            Also add any ``subdevices`` of this device to the suite as well.

        category: str, optional
            Category of device. By default, all devices will just be added to
            the "Devices" group
        """
        super().add_device(device)

        containers = {'': self._main_frame}

        self._main_frame._title.label.setText(device.name)

        for walk in device.walk_components():
            container_name = '.'.join(walk.dotted_name.split('.')[:-1])
            try:
                container = containers[container_name]
            except KeyError:
                container = TyphosDeviceContainer(
                    title=f'{device.name}.{container_name}')
                containers[container_name] = container

                parent_name = '.'.join(container_name.split('.')[:-1])
                parent_container = containers[parent_name]
                parent_container.add_widget(container)

            if issubclass(walk.item.cls, ophyd.Device):
                continue

            if not self.use_templates:
                label = QtWidgets.QLabel(walk.dotted_name)
                label.setObjectName(walk.dotted_name)
                container.add_widget(label)

        if self.use_templates:
            for dotted_name, container in containers.items():
                if not dotted_name:
                    continue
                inst = getattr(device, dotted_name)
                disp = TyphosDeviceDisplay.from_device(inst)
                container.add_widget(disp)

        for container in containers.values():
            container.complete_layout()

        self._scroll_area.setWidget(self._main_frame)
        self._scroll_area.setWidgetResizable(True)

    @classmethod
    def from_device(cls, device, parent=None, **kwargs):
        """
        Create a new TyphosDeviceDisplay from an ophyd.Device

        Parameters
        ----------
        device: ophyd.Device

        children: bool, optional
            Choice to include child Device components

        parent: QWidgets

        tools: dict, optional
            Tools to load for the object. ``dict`` should be name, class pairs.
            By default these will be ``.default_tools``, but ``None`` can be
            passed to avoid tool loading completely.

        kwargs:
            Passed to :meth:`TyphosSuite.add_device`
        """
        display = cls(parent=parent)
        display.add_device(device, **kwargs)
        return display

    def save(self):
        ''
