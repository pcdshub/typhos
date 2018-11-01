############
# Standard #
############
from functools import partial
import logging
import warnings

############
# External #
############
from pyqtgraph.parametertree import ParameterTree, parameterTypes as ptypes
from ophyd import Device
from qtpy.QtCore import Signal, Slot, Qt
from qtpy.QtWidgets import QDockWidget, QListWidgetItem, QHBoxLayout, QWidget

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
        # Create device group
        self._device_group = ptypes.GroupParameter(name='Devices')
        self._tree.addParameters(self._device_group)
        # Create tool group
        self._tool_group = ptypes.GroupParameter(name='Tools')
        self._tree.addParameters(self._tool_group)
        # Setup layout
        self._layout = QHBoxLayout()
        self._layout.setSizeConstraint(QHBoxLayout.SetFixedSize)
        self._layout.addWidget(self._tree)
        self.setLayout(self._layout)

    def add_subdisplay(self, name, display, list_widget):
        """
        Add a widget to one of the button layouts

        This add a display for a subcomponent and a QPushButton that
        will bring the display to the foreground. Users can either specify
        their button or have one generate for them. Either way the button is
        connected to the `pyqSlot` :meth:`.show_subdevice`

        Parameters
        ----------
        name : str
            Name to place on QPushButton

        display : QWidget
            QWidget to associate with button

        button : QWidget, optional
            QWidget with the PyQtSignal ``clicked``. If None, is given a
            QPushButton is created
        """
        warnings.warn("This method is deprecated. Use TyphonSuite.add_device "
                      "or TyphonSuite.add_tool instead.")
        # Create QListViewItem to store the display information
        list_item = QListWidgetItem(name)
        list_item.setData(Qt.UserRole, display)
        list_widget.addItem(list_item)

    def _add_to_sidebar(self, param):
        """Add a SidebarParameter to the correct slots"""
        param.sigOpen.connect(partial(self.show_subdisplay,
                                      param))
        param.sigHide.connect(partial(self.hide_subdisplay,
                                      param))

    def add_subdevice(self, device, name=None, **kwargs):
        """
        Add a subdevice to the `component_widget` stack

        Parameters
        ----------
        device : ophyd.Device

        kwargs:
            Passed to :meth:`.TyphonSuite.add_device`
        """
        warnings.warn("This method is deprecated. "
                      "Use `TyphonSuite.add_device`")
        logger.debug("Creating subdisplay for %s", device.name)
        self.add_device(device, **kwargs)

    def add_tool(self, name, tool):
        """
        Add a widget to the toolbar

        Parameters
        ----------
        name :str
            Name of tool to be displayed in sidebar

        tool: QWidget
            Widget to be added to ``.ui.subdisplay``
        """
        tool_param = SidebarParameter(value=tool, name=name)
        self._tool_group.addChild(tool_param)
        self._add_to_sidebar(tool_param)
        return tool_param

    def get_subdisplay(self, display):
        """
        Get a subdisplay by name or device

        Parameters
        ----------
        display :str or Device
            Name of subdisplay. This will be the text shown on the sidebar. For
            devices screens you can pass in the device itself
            itself

        Returns
        -------
        widget : QWidget
            Widget that is a member of the :attr:`.ui.subdisplay`

        Example
        -------
        .. code:: python

            my_display.get_subdisplay(my_device.x)
            my_display.get_subdisplay('My Tool')
        """
        # Get the cleaned Device name if passed a Device
        if isinstance(display, Device):
            tree = flatten_tree(self._device_group)
            for param in tree:
                if display in getattr(param.value(), 'devices', []):
                    return param.value()
        # Otherwise we could be looking for either a tool or device
        else:
            tree = (flatten_tree(self._device_group)
                    + flatten_tree(self._tool_group))
            for param in tree:
                if param.name() == display:
                    return param.value()
        # If we got here we can't find the subdisplay
        raise ValueError("Unable to find subdisplay %r", display)

    @Slot(str)
    @Slot(object)
    def show_subdisplay(self, widget):
        """
        Show subdevice display of the QStackedWidget

        Parameters
        ----------
        name : str, Device or QModelIndex
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
            DockWidget we will close that, otherwise the widget is just hidden
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
        Hide the component widget and set all buttons unchecked
        """
        # Grab children from devices
        device_params = flatten_tree(self._device_group)
        for param in device_params[1:] + self._tool_group.childs:
            self.hide_subdisplay(param)

    @property
    def tools(self):
        """Tools loaded into the DeviceDisplay"""
        return [param.value() for param in self._tool_group.childs]

    def add_device(self, device, children=True, methods=None, image=None):
        """
        Add a device to the :attr:`.device_panel` and tools

        Parameters
        ----------
        device: ophyd.Device

        methods: list, optional
            Methods to add to the device
        """
        methods = methods or list()
        super().add_device(device)
        # Create DeviceParameter
        dev_param = DeviceParameter(device, subdevices=children)
        for method in methods:
            dev_param.value.add_method(method)
        if image:
            dev_param.value.add_image(image)
        # Attach signals
        all_params = [dev_param] + dev_param.childs
        for param in all_params:
            self._add_to_sidebar(param)
        # Add to tree
        self._device_group.addChild(dev_param)
        # Add a device to all the tool displays
        for tool in self.tools:
            try:
                tool.add_device(device)
            except Exception as exc:
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
