############
# Standard #
############
from functools import partial
import logging

############
# External #
############
from pyqtgraph.parametertree import ParameterTree, parameterTypes as ptypes
from qtpy.QtCore import Signal, Slot, Qt
from qtpy.QtWidgets import QDockWidget, QHBoxLayout, QVBoxLayout, QWidget

###########
# Package #
###########
from .display import TyphonDisplay
from .utils import clean_name, TyphonBase, flatten_tree
from .widgets import TyphonSidebarItem, SubDisplay
from .tools import TyphonTimePlot, TyphonLogDisplay, TyphonConsole

logger = logging.getLogger(__name__)


class SidebarParameter(ptypes.Parameter):
    """
    Parameter to hold information for the sidebar
    """
    itemClass = TyphonSidebarItem
    sigOpen = Signal(object)
    sigHide = Signal(object)
    sigEmbed = Signal(object)

    def __init__(self, embeddable=None, **opts):
        super().__init__(**opts)
        self.embeddable = embeddable


class DeviceParameter(SidebarParameter):
    """Parameter to hold information Ophyd Device"""
    itemClass = TyphonSidebarItem

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
                    children.append(DeviceParameter(subdevice))
                # Otherwise just make a regular parameter out of it
                else:
                    child_name = clean_name(subdevice,
                                            strip_parent=subdevice.root)
                    child_display = TyphonDisplay.from_device(subdevice)
                    children.append(SidebarParameter(value=child_display,
                                                     name=child_name))
        opts['children'] = children
        super().__init__(value=TyphonDisplay.from_device(device), **opts)


class TyphonSuite(TyphonBase):
    """
    Complete Typhon Window

    This contains all the neccesities to load tools and devices into a Typhon
    window.

    Parameters
    ----------
    parent : QWidget, optional
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Setup parameter tree
        self._tree = ParameterTree(parent=self, showHeader=False)
        self._tree.setAlternatingRowColors(False)
        # Setup layout
        self._layout = QHBoxLayout()
        self._layout.setSizeConstraint(QHBoxLayout.SetFixedSize)
        self._layout.addWidget(self._tree)
        self.setLayout(self._layout)
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
        # Setup the dock
        dock = SubDisplay(self)
        # Grab the relevant display
        if isinstance(widget, SidebarParameter):
            for item in widget.items:
                item._mark_shown()
            # Make sure we react if the dock is closed outside of our menu
            dock.closing.connect(partial(self.hide_subdisplay,
                                         widget))
            widget = widget.value()
        elif not isinstance(widget, QWidget):
            widget = self.get_subdisplay(widget)
        # Add the widget to the dock
        logger.debug("Showing widget %r ...", widget)
        dock.setWidget(widget)
        # Add to layout
        self.layout().addWidget(dock)

    @Slot(str)
    @Slot(object)
    def embed_subdisplay(self, widget):
        """Embed a display in the dock system"""
        # Grab the relevant display
        if not self.embedded_dock:
            self.embedded_dock = SubDisplay()
            self.embedded_dock.setWidget(QWidget())
            self.embedded_dock.widget().setLayout(QVBoxLayout())
            self.embedded_dock.widget().layout().addStretch(1)
            self.layout().addWidget(self.embedded_dock)

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
        # If we have a parameter grab the widget
        if isinstance(widget, SidebarParameter):
            for item in widget.items:
                item._mark_hidden()
            widget = widget.value()
        elif not isinstance(widget, QWidget):
            widget = self.get_subdisplay(widget)
        # Make sure the actual widget is hidden
        logger.debug("Hiding widget %r ...", widget)
        if isinstance(widget.parent(), QDockWidget):
            logger.debug("Closing dock ...")
            widget.parent().close()
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
        """Tools loaded into the DeviceDisplay"""
        if 'Tools' in self.top_level_groups:
            return [param.value()
                    for param in self.top_level_groups['Tools'].childs]
        return []

    def add_device(self, device, children=True, category='Devices'):
        """
        Add a device to the ``TyphonSuite``

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
    def from_device(cls, device, parent=None,
                    tools={'Log': TyphonLogDisplay,
                           'StripTool': TyphonTimePlot,
                           'Console': TyphonConsole},
                    **kwargs):
        """
        Create a new TyphonDisplay from an ophyd.Device

        Parameters
        ----------
        device: ophyd.Device

        children: bool, optional
            Choice to include child Device components

        parent: QWidgets

        tools: dict, optional
            Tools to load for the object. ``dict`` should be name, class pairs

        kwargs:
            Passed to :meth:`TyphonSuite.add_device`
        """
        display = cls(parent=parent)
        for name, tool in tools.items():
            try:
                display.add_tool(name, tool())
            except Exception:
                logger.exception("Unable to load %s", type(tool))
        display.add_device(device, **kwargs)
        display.show_subdisplay(device)
        return display

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
        logger.debug("Connecting parameter signals ...")
        parameter.sigOpen.connect(partial(self.show_subdisplay,
                                          parameter))
        parameter.sigHide.connect(partial(self.hide_subdisplay,
                                          parameter))
        return parameter
