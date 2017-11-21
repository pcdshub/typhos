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
from pydm.PyQt.QtGui import QGroupBox, QWidget, QHBoxLayout, QPushButton

###########
# Package #
###########
from .func import FunctionPanel
from .panel import SignalPanel
from .utils import ui_dir, clean_attr, clean_source, channel_name

logger = logging.getLogger(__name__)


class DeviceDisplay(QWidget):
    """
    Display for an Ophyd Device

    The DeviceDisplay examines the supplied Ophyd Device and maps the contained
    signals into three separate panels; read, configuration, and miscellaneous.
    This allows the operator to quickly show and hide the information that is
    most pertinent to their current task. The supplied Device is also queried
    for the components which are not signals, but sub-devices. These are given
    their own DeviceDisplays and placed in a QStackedWidget that can optionally
    be shown and hidden based on the operators request.

    In order to accomodate an offline creation mode, each device is
    additionally checked for an ``enum_attrs`` property which contains which
    device signals should be passed to :class:`.Panel` in ``enum_sigs`. If
    the device you are creating a display for is avaiable through Channel
    Access, you do not have to worry about this step, as ``typhon`` will
    introspect the PV information to find which PVs are enums. However,
    offline, this information is not available and a user may want their screen
    to have certain EPICS variables displayed as QComboBoxes. In this case,
    devices and the sub-component devices should have the relevant attributes
    flagged under `enum_attrs`

    Parameters
    ----------
    device : ophyd.Device

    parent : QWidget, optional

    methods : list, optional
        List of callable functions to display in the interface

    dark : bool, optional
        Choice to use the `qdarkstyle` stylesheet

    read_attrs : list, optional
        Attributes to be used as read_attrs. This will also change the
        ``device.read_attrs``

    configuration_attrs : list, optional
        Attributes to be used as configuration_attrs. This will also change the
        ``device.configuration_attrs``

    Attributes
    ----------
    hint_plot:

    read_panel:

    config_panel:

    misc_panel:
    """
    default_curve_opts = {'lineStyle': Qt.SolidLine, 'symbol': 'o',
                          'lineWidth': 2, 'symbolSize': 4}
    def __init__(self, device, dark=True, methods=None, read_attrs=None,
                 configuration_attrs=None, parent=None):
        # Instantiate Widget
        super().__init__(parent=parent)
        # Change the stylesheet
        if dark:
            try:
                import qdarkstyle
            except ImportError:
                logger.error("Can not use dark theme, "
                             "qdarkstyle package not available")
            else:
                self.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
        # Instantiate UI
        self.ui = uic.loadUi(os.path.join(ui_dir, 'base.ui'), self)
        # Store device
        self.device = device
        self.device_description = self.device.describe()
        # Set Label Names
        self.ui.name_label.setText(self.device.name)
        self.ui.prefix_label.setText(self.device.prefix)

        # Handle Component Devices
        # Create buttons for subcomponents
        self.sub_device_group = None
        for dev_name in self.device._sub_devices:
            self.add_subdevice(getattr(self.device, dev_name))
        # Hide Subcomponents
        self.ui.component_widget.hide()

        # Create Panel Configurations
        # Create read and configuration panels
        self.read_panel = self.create_panel("Read", self.device.read_attrs)
        # Hide control of read_panel
        self.read_panel.hide_button.hide()
        self.config_panel = self.create_panel("Configuration",
                                              self.device.configuration_attrs)
        # Catch the rest of the signals add to misc panel below misc_button
        misc_sigs = [sig for sig in self.device.component_names
                     if sig not in (self.device.read_attrs
                                    + self.device.configuration_attrs
                                    + self.device._sub_devices)]
        self.misc_panel = self.create_panel("Miscellaneous", misc_sigs)
        # Create method panel
        self.method_panel = FunctionPanel(methods, parent=self)
        # Add all the panels
        self.ui.main_layout.addWidget(self.read_panel)
        self.ui.main_layout.addWidget(self.method_panel)
        self.ui.main_layout.addWidget(self.config_panel)
        self.ui.main_layout.addWidget(self.misc_panel)
        # Hide config/misc panels
        self.config_panel.show_contents(False)
        self.misc_panel.show_contents(False)
        # Hide if no methods are given
        if not self.methods:
            self.method_panel.hide()
        # Add our hints
        for field in getattr(self.device, 'hints', {}).get('fields', list()):
            try:
                # Get a description of the signal. Add the the PV name
                # to the hint_panel if it is a number and not a string
                sig_desc = self.device_description[field]
                if sig_desc['dtype'] == 'number':
                    self.add_plotted_signal(sig_desc['source'])
                else:
                    logger.debug("Not adding %s because it is not a number",
                                 field)
            except KeyError as exc:
                logger.error("Unable to find PV name of %s", field)
        # If we did not get any hints
        if not self.ui.hint_plot.curves:
            self.ui.hint_plot.hide()

    @property
    def all_devices(self):
        """
        List of devices contained in the screen
        """
        return [self.device] + [self.ui.component_stack.widget(i).device
                                for i in range(self.ui.component_stack.count())
                                if hasattr(self.ui.component_stack.widget(i),
                                           'device')]

    @property
    def methods(self):
        """
        Methods contained within :attr:`.method_panel`
        """
        return self.method_panel.methods

    def create_panel(self, title, signal_names, **kwargs):
        """
        Create a panel from a set of device signals

        Parameters
        ----------
        title :str
            Name of Panel

        signal_names : list
            Name of signals to add to panel. Must be a component of ``device``

        kwargs:
            All keywords are passed to the :class:`typhon.SignalPanel`. The
            signal dictionary is generated from the `signal_names` parameter.
            The device is also queried for :attr:`.enum_attrs`

        Returns
        -------
        panel : :class:`.typhon.Panel`
        """
        # Create dictionary mapping of alias -> EpicsSignal
        sig_dict = dict((clean_attr(sig), getattr(self.device, sig))
                        for sig in signal_names)
        # Search for fixed enum attrs
        enum_attrs = [clean_attr(sig)
                      for sig in getattr(self.device, 'enum_attrs', list())]
        enum_attrs.extend(kwargs.pop('enum_attrs', list()))
        # Create panel
        panel = SignalPanel(title, signals=sig_dict,
                            enum_sigs=enum_attrs, **kwargs)
        return panel

    def add_subdevice(self, device):
        """
        Add a subdevice to the `component_widget` stack

        This creates another DeviceDisplay for the subcomponent and a
        QPushButton that will bring the display to the forground

        Parameters
        ----------
        device : ophyd.Device
        """
        logger.debug("Adding device %s ...", device.name)
        # Add our button layout if not created
        if not self.sub_device_group:
            logger.debug("Creating button layout for subdevices ...")
            self.sub_device_group = QGroupBox("Component Devices")
            self.sub_device_group.setLayout(QHBoxLayout())
            self.ui.main_layout.insertWidget(1, self.sub_device_group)
        # Create device display
        sub_display = DeviceDisplay(device)
        idx = self.ui.component_stack.addWidget(sub_display)
        # Create button
        but = QPushButton()
        but.setText(clean_attr(device.name))
        self.sub_device_group.layout().addWidget(but)
        # Connect button
        but.clicked.connect(partial(self.show_subdevice, idx=idx))

    def add_plotted_signal(self, pv, **kwargs):
        """
        Add a signal to the PyDMTimePlot

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
        self.ui.component_stack.setCurrentIndex(idx)
