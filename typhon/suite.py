############
# Standard #
############
import logging
import os.path

############
# External #
############
from ophyd import Device
from qtpy import uic
from qtpy.QtCore import Slot, Qt, QModelIndex

###########
# Package #
###########
from .display import TyphonDisplay
from .utils import ui_dir, clean_name, TyphonBase
from .widgets import TyphonSidebarItem
from .tools import TyphonTimePlot, TyphonLogDisplay

logger = logging.getLogger(__name__)


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
        # Instantiate Widget
        super().__init__(parent=parent)
        # Instantiate UI
        self.ui = uic.loadUi(os.path.join(ui_dir, 'base.ui'), self)
        self.device_panel = TyphonDisplay()
        self.widget_layout.insertWidget(1, self.device_panel)
        self.subdisplays = dict()
        # Connect signals to slots
        self.ui.hide_button.clicked.connect(self.hide_subdisplays)
        self.ui.tool_list.clicked.connect(self.show_subdisplay)
        self.ui.tool_list.clicked.connect(
                self.ui.component_list.clearSelection)
        self.ui.component_list.clicked.connect(self.show_subdisplay)
        self.ui.component_list.clicked.connect(
                self.ui.tool_list.clearSelection)
        # Hide widgets until objects are added to them
        self.ui.subwindow.hide()
        self.ui.tool_sidebar.hide()
        self.ui.component_sidebar.hide()

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
            my_displyay.get_subsdisplay('My Tool')
        """
        # Get the cleaned Device name if passed a Device
        if isinstance(display, Device):
            display = clean_name(display)
        return self._item_from_sidebar(display).data(Qt.UserRole)

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
                           'StripTool': TyphonTimePlot},
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
            Passed to :meth:`.add_device`
        """
        display = cls(parent=parent)
        for name, tool in tools.items():
            try:
                display.add_tool(name, tool())
            except Exception:
                logger.exception("Unable to load %s", type(tool))
        display.add_device(device, **kwargs)
        display.device_panel.title = clean_name(device, strip_parent=False)
        return display
