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
from pydm.PyQt.QtGui import QWidget, QPushButton, QButtonGroup

###########
# Package #
###########
from .func import FunctionPanel
from .panel import SignalPanel
from .utils import ui_dir, clean_attr, clean_source, channel_name
from .widgets import ComponentButton

logger = logging.getLogger(__name__)


class TyphonDisplay(QWidget):
    """
    Generalized Typhon display

    This widget lays out all of the architecture for a general Typhon display.
    The structure matches an ophyd Device, but for this specific instantation,
    one is not required to be given. There are four main panels are available;
    :attr:`.read_panel`. :attr:`.config_panel`, :attr:`.method_panel`. These
    give four separate panels provide a quick way to organize signals and
    methods by their importance to an operator. In addition, crucial signals
    can be added to a PyDMTimePlot under the attribute :attr:`.hint_plot`.
    Because each panel can be hidden interactively, the screen works as both an
    expert and novice entry point for users. By default, widgets are hidden
    until contents are added. For instance, if you do not add any methods to
    the main panel it will not be visible.

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
    default_curve_opts = {'lineStyle': Qt.SolidLine, 'symbol': 'o',
                          'lineWidth': 2, 'symbolSize': 4}

    def __init__(self, name, parent=None):
        # Instantiate Widget
        super().__init__(parent=parent)
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
        self.ui.main_layout.insertWidget(4, self.config_panel)
        self.ui.main_layout.insertWidget(5, self.misc_panel)
        # Hide control of read_panel
        self.read_panel.hide_button.hide()
        # Hide widgets until signals are added to them
        self.ui.buttons.hide()
        self.ui.component_widget.hide()
        self.config_panel.hide()
        self.misc_panel.hide()
        self.method_panel.hide()
        self.ui.hint_plot.hide()

    @property
    def methods(self):
        """
        Methods contained within :attr:`.method_panel`
        """
        return self.method_panel.methods

    def add_subdisplay(self, name, display, button=None):
        """

        This add adisplay for a subcomponent and a QPushButton that
        will bring the display to the foreground. Users can either specify
        their button or have one generate for them. Either way the button is
        connected to the the `pyqSlot` :meth:`.show_subdevice`

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
        # Connect button
        button.clicked.connect(partial(self.show_subdevice, idx=idx))
        # Show the widgets if hidden
        if self.ui.buttons.isHidden():
            self.ui.buttons.show()

    def add_subdevice(self, device, methods=None):
        """
        Add a subdevice to the `component_widget` stack

        Parameters
        ----------
        device : ophyd.Device

        methods : list of callables, optional
        """
        logger.debug("Creating button for %s", device.name)
        # Create ComponentButton adding the hints automatically
        button = ComponentButton(clean_attr(device.name), parent=self)
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

    def add_pv_to_plot(self, pv, **kwargs):
        """
        Add a PV to the PyDMTimePlot

        The default style of the curve is determined by
        :attr:`.default_curve_opts`. Though these can be overridden

        Parameters
        ----------
        pvname : str
            Name of PV

        kwargs:
            All keywords are passed directly to ``PyDMTimePlot.addYChannel``
        """
        # Show our plot if it was previously hidden
        if self.ui.hint_plot.isHidden():
            self.ui.hint_plot.show()
        # Combine user supplied options with defaults
        plot_opts = copy.copy(self.default_curve_opts)
        plot_opts.update(kwargs)
        self.ui.hint_plot.addYChannel(y_channel=channel_name(pv), **plot_opts)

    @pyqtSlot()
    def show_subdevice(self, idx):
        """
        Show subdevice display at index `idx` of the QStackedWidget

        Parameters
        ----------
        idx : int
            Index of subdevice widget
        """
        if self.ui.component_widget.isHidden():
            self.ui.component_widget.show()
        # Show the correct subdevice widget
        self.ui.component_widget.setCurrentIndex(idx)

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
    Display an ophyd Device

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
        super().__init__(device.name, parent=parent)
        # Examine and store device for later reference
        self.device = device
        self.device_description = self.device.describe()
        # Handle child devices
        for dev_name in self.device._sub_devices:
            self.add_subdevice(getattr(self.device, dev_name))

        # Create read and configuration panels
        for attr in self.device.read_attrs:
            self.read_panel.add_signal(getattr(self.device, attr),
                                       clean_attr(attr))

        for attr in self.device.configuration_attrs:
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

        # Add our hints
        for field in getattr(self.device, 'hints', {}).get('fields', list()):
            try:
                # Get a description of the signal. Add the the PV name
                # to the hint_panel if it is a number and not a string
                sig_desc = self.device_description[field]
                if sig_desc['dtype'] == 'number':
                    self.add_pv_to_plot(clean_source(sig_desc['source']))
                else:
                    logger.debug("Not adding %s because it is not a number",
                                 field)
            except KeyError as exc:
                logger.error("Unable to find PV name of %s", field)
        # Hide the lesser needed panels
        self.config_panel.show_contents(False)
        self.misc_panel.show_contents(False)
