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
from .device import TyphonPanel
from .utils import ui_dir, clean_name
from .widgets import TyphonSidebarItem
from .tools import TyphonTimePlot, TyphonLogDisplay, TyphonTool

logger = logging.getLogger(__name__)


class TyphonDisplay(TyphonTool):
    """
    Generalized Typhon display

    This widget lays out all of the architecture for a general Typhon display.
    The structure matches an ophyd Device, but for this specific instantation,
    one is not required to be given. There are four main panels available;
    :attr:`.read_panel`, :attr:`.config_panel`, :attr:`.method_panel`. These
    each provide a quick way to organize signals and methods by their
    importance to an operator. Because each panel can be hidden interactively,
    the screen works as both an expert and novice entry point for users. By
    default, widgets are hidden until contents are added. For instance, if you
    do not add any methods to the main panel it will not be visible.

    This device is the bare bones implementation in the event that someone
    might want to collect a random group of signals and devices together to
    create a screen. A more automated display generator is available  in the
    :class:`.DeviceDisplay`

    Parameters
    ----------
    name : str
        Title displayed on the widget

    image :str, optional
        Path to an image file to include in the display.

    parent : QWidget, optional
    """
    default_tools = {'Log': TyphonLogDisplay,
                     'StripTool': TyphonTimePlot}

    def __init__(self, parent=None):
        # Instantiate Widget
        super().__init__(parent=parent)
        # Instantiate UI
        self.ui = uic.loadUi(os.path.join(ui_dir, 'base.ui'), self)
        self.device_panel = TyphonPanel()
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

    def add_subdevice(self, device, **kwargs):
        """
        Add a subdevice to the `component_widget` stack

        Parameters
        ----------
        device : ophyd.Device

        kwargs:
            Passed to :class:`.TyphonPanel` constructor
        """
        logger.debug("Creating subdisplay for %s", device.name)
        # Remove parent from name for title
        if not name:
            name = clean_name(device)
        dd = TyphonPanel.from_device(device, name=name, **kwargs)
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


class DeviceDisplay(TyphonDisplay):
    """
    Display an Ophyd Device

    Using the panels created by the inherited :class:`.TyphonDisplay` the
    sub-devices and signals are added to the appropriate places in the widget.
    The display introspects the ``read_attrs``, ``configuration_attrs``,
    ``component_names`` and ``_sub_devices`` to find the signal names and
    heirarchy.

    Parameters
    ----------
    device : ophyd.Device
        Main ophyd device to display

    methods : list of callables, optional
        List of callables to pass to :meth:`.FunctionPanel.add_method`

    image : str, optional
        Path to image to add to display

    children: str, optional
        Choice to include child Device components

    parent : QWidget, optional
    """
    def __init__(self, device, methods=None, image=None,
                 children=True, parent=None):
        super().__init__(clean_name(device, strip_parent=False),
                         image=image, parent=parent)
        # Examine and store device for later reference
        self.device = device
        self.device_description = self.device.describe()
        # Handle child devices
        if children:
            for dev_name in self.device._sub_devices:
                self.add_subdevice(getattr(self.device, dev_name))

        # Create read and configuration panels
        for attr in self.device.read_attrs:
            signal = getattr(self.device, attr)
            if not isinstance(signal, Device):
                self.read_panel.add_signal(signal, clean_attr(attr))
        for attr in self.device.configuration_attrs:
            signal = getattr(self.device, attr)
            if not isinstance(signal, Device):
                self.config_panel.add_signal(signal, clean_attr(attr))
        # Catch the rest of the signals add to misc panel below misc_button
        for attr in self.device.component_names:
            if attr not in (self.device.read_attrs
                            + self.device.configuration_attrs
                            + self.device._sub_devices):
                signal = getattr(self.device, attr)
                if not isinstance(signal, Device):
                    self.misc_panel.add_signal(signal, clean_attr(attr))
        # Add our methods to the panel
        methods = methods or list()
        for method in methods:
                self.method_panel.add_method(method)
        # Add the plot tool
        self.add_tool('Plotting Tool', TyphonTimePlot.from_device(device))
        # Add a LogWidget to our toolset
        self.add_tool('Device Log', TyphonLogDisplay.from_device(device))
