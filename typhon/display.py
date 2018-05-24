############
# Standard #
############
import copy
import os.path
import logging
from functools import partial

############
# External #
############
from pydm.PyQt import uic
from pydm.PyQt.QtCore import pyqtSlot, Qt
from pydm.PyQt.QtGui import QWidget, QPushButton, QButtonGroup, QVBoxLayout

###########
# Package #
###########
from .func import FunctionPanel
from .signal import SignalPanel
from .utils import ui_dir, clean_attr, clean_source, clean_name, channel_name
from .widgets import ComponentButton

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

    parent : QWidget, optional
    """
    def __init__(self, name, parent=None):
        # Instantiate Widget
        super().__init__(parent=parent)
        self.subdisplays = dict()
        # Instantiate UI
        self.ui = uic.loadUi(os.path.join(ui_dir, 'base.ui'), self)
        self.device_button_group = QButtonGroup()
        self.device_button_group.addButton(self.ui.hide_button)
        self.ui.hide_button.clicked.connect(self.hide_subdevices)
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
        # Hide widgets until signals are added to them
        self.ui.buttons.hide()
        self.ui.component_widget.hide()
        self.method_panel.hide()

    @property
    def methods(self):
        """
        Methods contained within :attr:`.method_panel`
        """
        return self.method_panel.methods

    def add_subdisplay(self, name, display, button=None):
        """
        Add a widget to the display

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
        # Create button
        if not button:
            button = QPushButton(self)
            button.setText(name)
        # Add the button to the group
        self.device_button_group.addButton(button)
        # Add our button to the layout last in the line of buttons
        # but above the spacer
        idx = self.ui.buttons.layout().count() - 1
        self.ui.buttons.layout().insertWidget(idx, button)
        # Add our display to the widget
        idx = self.ui.component_widget.addWidget(display)
        self.subdisplays[name] = idx
        # Connect button
        button.clicked.connect(partial(self.show_subdevice, name=name))
        # Show the widgets if hidden
        if self.ui.buttons.isHidden():
            self.ui.buttons.show()

    def add_subdevice(self, device, methods=None, image=None):
        """
        Add a subdevice to the `component_widget` stack

        Parameters
        ----------
        device : ophyd.Device

        methods : list of callables, optional
        """
        logger.debug("Creating button for %s", device.name)
        # Create ComponentButton adding the hints automatically
        button = ComponentButton(clean_name(device), parent=self)
        description = device.describe()
        for field in getattr(device, 'hints', {}).get('fields', list()):
            sig_source = description[field]['source']
            button.add_pv(clean_source(sig_source), clean_attr(field))
        # Create the actual subdisplay and add it to the component widget
        # along with the button
        logger.debug("Creating subdisplay for %s", device.name)
        self.add_subdisplay(device.name,
                            DeviceDisplay(device,
                                          methods=methods,
                                          parent=self),
                            button=button)

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

    def add_image(self, path):
        """
        Add an image to the display

        Parameters
        ----------
        path : str
            Absolute or relative path to image

        subdevice : ophyd.Device
            Device to associate the image with. If this is left as None, it is
            assumed that this image corresponds to the main device
        """
        # Make a name for the image to be referred to later
        if subdevice:
            name = subdevice.name
        else:
            name = None
        # Add the image to the widget. The show_subdevice slot will find this
        # automatically
        self.image_widget.add_image(path, name=name)
        # Show the widget if it is hidden
        if self.image_widget.isHidden():
            self.image_widget.show()

    @pyqtSlot()
    def show_subdevice(self, name):
        """
        Show subdevice display of the QStackedWidget

        Parameters
        ----------
        name : str
        """
        if self.ui.component_widget.isHidden():
            self.ui.component_widget.show()
        # Show the correct subdevice widget
        self.ui.component_widget.setCurrentIndex(self.subdisplays[name])

    @pyqtSlot()
    def hide_subdevices(self):
        """
        Hide the component widget and set all buttons unchecked
        """
        self.ui.component_widget.hide()
        # Toggle the button off, each button can use its own pyqtSlot
        for button in self.device_button_group.buttons():
            button.toggled.emit(False)


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

    parent : QWidget, optional
    """
    def __init__(self, device, methods=None, parent=None):
        super().__init__(clean_name(device, strip_parent=False),
                         parent=parent)
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
