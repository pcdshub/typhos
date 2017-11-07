############
# Standard #
############
import os.path
import logging
from functools import partial

############
# External #
############
from pydm.PyQt import uic
from pydm.PyQt.QtCore import pyqtSlot
from pydm.PyQt.QtGui import QPushButton
from pydm.PyQt.QtGui import QWidget, QHBoxLayout

###########
# Package #
###########
from .panel import Panel
from .utils import ui_dir, clean_attr

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

    dark : bool, optional
        Choice to use the `qdarkstyle` stylesheet

    read_attrs : list, optional
        Attributes to be used as read_attrs. This will also change the
        ``device.read_attrs``

    configuration_attrs : list, optional
        Attributes to be used as configuration_attrs. This will also change the
        ``device.configuration_attrs``
    """
    def __init__(self, device, dark=True, read_attrs=None,
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
        # Set Label Names
        self.ui.name_label.setText(self.device.name)
        self.ui.prefix_label.setText(self.device.prefix)
        # Hide Subcomponents
        self.ui.component_widget.hide()
        # Create Read and Configuration Panels
        self.read_panel = self.create_panel(self.device.read_attrs)
        self.config_panel = self.create_panel(self.device.configuration_attrs,
                                              button=self.ui.config_button)
        # Add read panel above config button
        rd_idx = self.ui.main_layout.indexOf(self.ui.config_button)
        self.ui.main_layout.insertWidget(rd_idx, self.read_panel)
        # Add config panel below config button
        cfg_idx = self.ui.main_layout.indexOf(self.ui.config_button)+1
        self.ui.main_layout.insertWidget(cfg_idx, self.config_panel)
        # Catch the rest of the signals add to misc panel below misc_button
        misc_sigs = [sig for sig in self.device.component_names
                     if sig not in (self.device.read_attrs
                                    + self.device.configuration_attrs
                                    + self.device._sub_devices)]
        self.misc_panel = self.create_panel(misc_sigs,
                                            button=self.ui.misc_button)
        misc_idx = self.ui.main_layout.indexOf(self.ui.misc_button)+1
        self.ui.main_layout.insertWidget(misc_idx, self.misc_panel)
        # Hide config/misc panels
        self.config_panel.hide()
        self.misc_panel.hide()
        # Create buttons for subcomponents
        self.sub_button_layout = None
        for dev_name in self.device._sub_devices:
            self.add_subdevice(getattr(self.device, dev_name))

    @property
    def all_devices(self):
        """
        List of devices contained in the screen
        """
        return [self.device] + [self.ui.component_stack.widget(i).device
                                for i in range(self.ui.component_stack.count())
                                if hasattr(self.ui.component_stack.widget(i),
                                           'device')]

    def create_panel(self, signal_names, button=None):
        """
        Create a panel from a set of device signals

        Parameters
        ----------
        signal_names : list
            Name of signals to add to panel. Must be a component of ``device``

        button: QAbstractButton, optional
            Existing button to hide or show the panel. This is connected to the
            created :class:`.typhon.Panel` using the function
            :func:`.toggle_panel`

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

        # Create panel
        panel = Panel(signals=sig_dict, enum_sigs=enum_attrs, parent=self)
        # Allow button to hide and show panel
        if button:
            button.toggled.connect(partial(self.toggle_panel, panel=panel))
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
        logger.info("Adding device %s ...", device.name)
        # Add our button layout if not created
        if not self.sub_button_layout:
            logger.debug("Creating button layout for subdevices ...")
            self.sub_button_layout = QHBoxLayout()
            self.ui.main_layout.insertLayout(1, self.sub_button_layout)
        # Create device display
        sub_display = DeviceDisplay(device)
        idx = self.ui.component_stack.addWidget(sub_display)
        # Create button
        but = QPushButton()
        but.setText(clean_attr(device.name))
        self.sub_button_layout.addWidget(but)
        # Connect button
        but.clicked.connect(partial(self.show_subdevice, idx=idx))

    @pyqtSlot(bool)
    def toggle_panel(self, checked, panel):
        """
        Toggle the visibility of a panel

        Parameters
        ----------
        checked : bool
            Whether to hide or show

        panel : QWidget
            Widget to hide or show
        """
        if checked:
            panel.show()
        else:
            panel.hide()

    @pyqtSlot()
    def show_subdevice(self, idx):
        """
        Show subdevice display at index `idx` of the QStackedWidget

        Parameters
        ----------
        idx : int
            Index of subdevice widget
        """
        # Show the component widget if hidden
        if self.ui.component_widget.isHidden():
            self.ui.component_widget.show()
        # Show the correct subdevice widget
        self.ui.component_stack.setCurrentIndex(idx)
