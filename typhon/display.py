############
# Standard #
############
import os.path
import logging
from ophyd import Device

############
# External #
############
from pydm.PyQt import uic
from pydm.PyQt.QtCore import pyqtSlot, Qt, QModelIndex
from pydm.PyQt.QtGui import QWidget, QVBoxLayout
from pydm.widgets.drawing import PyDMDrawingImage
from pydm.widgets.logdisplay import PyDMLogDisplay

###########
# Package #
###########
from .func import FunctionPanel
from .signal import SignalPanel
from .utils import ui_dir, clean_attr, clean_name
from .widgets import TyphonSidebarItem
from .plot import DeviceTimePlot


logger = logging.getLogger(__name__)


class TyphonDisplay(QWidget):
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
    def __init__(self, name, image=None, parent=None):
        # Instantiate Widget
        super().__init__(parent=parent)
        self.subdisplays = dict()
        # Instantiate UI
        self.ui = uic.loadUi(os.path.join(ui_dir, 'base.ui'), self)
        # Set Label Names
        self.ui.name_label.setText(name)
        # Create Panels
        self.method_panel = FunctionPanel(parent=self)
        self.read_panel = SignalPanel("Read", parent=self)
        self.config_panel = SignalPanel("Configuration", parent=self)
        self.misc_panel = SignalPanel("Miscellaneous", parent=self)
        # Add all the panels
        self.ui.main_layout.insertWidget(2, self.read_panel)
        self.ui.main_layout.insertWidget(3, self.method_panel)
        # Create tabs
        self.ui.signal_tab.clear()
        self.add_tab('Configuration', self.config_panel)
        self.add_tab('Miscellaneous', self.misc_panel)
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
        self.method_panel.hide()
        # Create PyDMDrawingImage
        self.image_widget = None
        if image:
            self.add_image(image)

    @property
    def methods(self):
        """
        Methods contained within :attr:`.method_panel`
        """
        return self.method_panel.methods

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

        methods : list of callables, optional

        image: str, optional
            Path to image to display for device
        """
        logger.debug("Creating subdisplay for %s", device.name)
        dd = DeviceDisplay(device, **kwargs)
        # Hide the toolbar from children
        dd.ui.sidebar.hide()
        # Do not duplicate the margins around the display
        dd.ui.widget_layout.setContentsMargins(0, 0, 0, 0)
        self.add_subdisplay(clean_name(device),
                            dd, self.ui.component_list)

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

    def add_tab(self, name, widget):
        """
        Add a widget to the main signal tab

        Use this rather than directly setting ``signal_tab.addTab`` to ensure
        that the tab has the proper stretch to avoid distorting the size of the
        widget you are adding.

        Parameters
        ----------
        name : str
            Name that will be displayed on tab

        widget : QWidget
            Widget to be contained within the new tab
        """
        qw = QWidget()
        qw.setLayout(QVBoxLayout())
        qw.layout().addWidget(widget)
        qw.layout().addStretch(1)
        self.ui.signal_tab.addTab(qw, name)

    def add_image(self, path, subdevice=None):
        """
        Set the image of the PyDMDrawingImage

        Setting this twice will overwrite the first image given.

        Parameters
        ----------
        path : str
            Absolute or relative path to image

        subdevice: ophyd.Device
            Ophyd object that has been previously added with
            :meth:`.add_subdevice`
        """
        # Find the nested widget for this specific device
        if subdevice:
            widget = self.get_subdisplay(subdevice)
            return widget.add_image(path, subdevice=None)
        # Set existing image file
        logger.debug("Adding an image file %s ...", path)
        if self.image_widget:
            self.image_widget.filename = path
        else:
            logger.debug("Creating a new PyDMDrawingImage")
            self.image_widget = PyDMDrawingImage(filename=path,
                                                 parent=self)
            self.image_widget.setMaximumSize(350, 350)
            self.ui.main_layout.insertWidget(2, self.image_widget,
                                             0, Qt.AlignCenter)

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

    @pyqtSlot(str)
    @pyqtSlot(QModelIndex)
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

    @pyqtSlot()
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

    parent : QWidget, optional
    """
    def __init__(self, device, methods=None, image=None, parent=None):
        super().__init__(clean_name(device, strip_parent=False),
                         image=image, parent=parent)
        # Examine and store device for later reference
        self.device = device
        self.device_description = self.device.describe()
        # Handle child devices
        for dev_name in self.device._sub_devices:
            self.add_subdevice(getattr(self.device, dev_name))

        # Create read and configuration panels
        for attr in self.device.read_attrs:
            if attr not in self.device._sub_devices:
                self.read_panel.add_signal(getattr(self.device, attr),
                                           clean_attr(attr))

        for attr in self.device.configuration_attrs:
            if attr not in self.device._sub_devices:
                self.config_panel.add_signal(getattr(self.device, attr),
                                             clean_attr(attr))
        # Catch the rest of the signals add to misc panel below misc_button
        for attr in self.device.component_names:
            if attr not in (self.device.read_attrs
                            + self.device.configuration_attrs
                            + self.device._sub_devices):
                self.misc_panel.add_signal(getattr(self.device, attr),
                                           clean_attr(attr))
        # Add our methods to the panel
        methods = methods or list()
        for method in methods:
                self.method_panel.add_method(method)
        # Add the plot tool
        self.add_tool('Plotting Tool', DeviceTimePlot(device))
        # Add a LogWidget to our toolset
        self.add_tool('Device Log', PyDMLogDisplay(logname=device.log.name,
                                                   level=logging.INFO))
