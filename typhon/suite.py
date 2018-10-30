############
# Standard #
############
import logging
import os.path

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
        # Create QListViewItem to store the display information
        list_item = TyphonSidebarItem(name)
        list_item.setData(Qt.UserRole, display)
        list_widget.addItem(list_item)
        # Add our display to the component widget
        self.ui.subdisplay.addWidget(display)
        self.subdisplays[name] = list_item
        # Hide the parent widget if hidden
        sidebar = list_widget.parent()
        if sidebar.isHidden():
            sidebar.show()

    def add_subdevice(self, device, name=None, **kwargs):
        """
        Add a subdevice to the `component_widget` stack

        Parameters
        ----------
        device : ophyd.Device

        kwargs:
            Passed to :meth:`.TyphonDevice.from_device`
        """
        logger.debug("Creating subdisplay for %s", device.name)
        # Remove parent from name for title
        if not name:
            name = clean_name(device)
        dd = TyphonDisplay.from_device(device, name=name, **kwargs)
        self.add_subdisplay(name, dd, self.component_list)

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
        self.add_subdisplay(name, tool, self.ui.tool_list)

    def _item_from_sidebar(self, name):
        """
        Get a child display based on the name given

        Parameters
        ----------
        name: str
            Name of display
        """
        # Gather QListWidgetItem
        try:
            list_item = self.subdisplays[name]
        except KeyError as exc:
            raise ValueError("Display {} has not been added to the "
                             "DeviceDisplay yet".format(name)) from exc
        return list_item

    def get_subdisplay(self, display):
        """
        Get a subdisplay by name

        Parameters
        ----------
        display :str or Device
            Name of subdisplay. This will be the text shown on the sidebar. For
            component devices screens you can pass in the component device
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
    @Slot(QModelIndex)
    def show_subdisplay(self, item):
        """
        Show subdevice display of the QStackedWidget

        Parameters
        ----------
        name : str, Device or QModelIndex
        """
        # Grab the relevant display
        if isinstance(item, QModelIndex):
            display = item.data(Qt.UserRole)
        else:
            display = self.get_subdisplay(item)
        # Show our subdisplay if previously hidden
        if self.ui.subwindow.isHidden():
            self.ui.subwindow.show()
        # Set the current display
        self.ui.subdisplay.setCurrentWidget(display)
        self.ui.subdisplay.setFixedWidth(display.sizeHint().width())

    @Slot()
    def hide_subdisplays(self):
        """
        Hide the component widget and set all buttons unchecked
        """
        # Hide the main display
        self.ui.subwindow.hide()
        self.ui.component_list.clearSelection()
        self.ui.tool_list.clearSelection()

    @property
    def tools(self):
        """Tools loaded into the DeviceDisplay"""
        return [self.tool_list.item(i).data(Qt.UserRole)
                for i in range(self.tool_list.count())]

    def add_device(self, device, children=True, methods=None, image=None):
        """
        Add a device to the :attr:`.device_panel` and tools

        Parameters
        ----------
        device: ophyd.Device

        methods: list, optional
            Methods to add to the device
        """
        super().add_device(device)
        # Add the device to the main panel
        self.device_panel.add_device(device, methods=methods)
        if image:
            self.device_panel.add_image(image)
        # Add a device to all the tool displays
        for tool in self.tools:
            try:
                tool.add_device(device)
            except Exception as exc:
                logger.exception("Unable to add %s to tool %s",
                                 device.name, type(tool))
        # Handle child devices
        if children:
            for dev_name in device._sub_devices:
                self.add_subdevice(getattr(device, dev_name))

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
