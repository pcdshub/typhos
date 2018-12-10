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
from qtpy.QtWidgets import QDockWidget, QHBoxLayout, QWidget

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
        # Create our parameter
        parameter = SidebarParameter(value=display, name=name)
        return self._add_to_sidebar(parameter, category)

    @property
    def top_level_groups(self):
        """All top-level groups expressed as ``QGroupParameterItem`` objects"""
        root = self._tree.invisibleRootItem()
        return [root.child(idx).param
                for idx in range(root.childCount())]

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
        return self.add_subdisplay(name, tool, 'Tools')

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
        for group in self.top_level_groups:
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
        dock.setWidget(widget)
        # Add to layout
        self.layout().addWidget(dock)

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
        if isinstance(widget.parent(), QDockWidget):
            widget.parent().close()
        else:
            widget.hide()

    @Slot()
    def hide_subdisplays(self):
        """
        Hide all open displays
        """
        # Grab children from devices
        for group in self.top_level_groups:
            for param in flatten_tree(group)[1:]:
                self.hide_subdisplay(param)

    @property
    def tools(self):
        """Tools loaded into the DeviceDisplay"""
        for group in self.top_level_groups:
            if group.name() == 'Tools':
                return [param.value() for param in group.childs]
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
        return dev_param

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
        param = display.add_device(device, **kwargs)
        display.show_subdisplay(param)
        return display

    def _add_to_sidebar(self, parameter, category=None):
        """Add an item to the sidebar, connecting neccesary signals"""
        if category:
            # Create or grab our category
            group_dict = dict((param.name(), param)
                              for param in self.top_level_groups)
            if category in group_dict:
                group = group_dict[category]
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
