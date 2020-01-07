"""
Typhos Plotting Interface
"""
############
# Standard #
############
import logging

###############
# Third Party #
###############
from ophyd import Device
from timechart.displays.main_display import TimeChartDisplay
from timechart.utilities.utils import random_color
from qtpy.QtCore import Slot
from qtpy.QtWidgets import (QComboBox, QPushButton, QLabel, QVBoxLayout,
                            QHBoxLayout)
##########
# Module #
##########
from ..utils import (channel_from_signal, clean_attr, clean_name, TyphosBase,
                     warn_renamed)

logger = logging.getLogger(__name__)


class TyphosTimePlot(TyphosBase):
    """
    Generalized widget for plotting Ophyd signals

    This widget is a ``TimeChartDisplay`` wrapped with some convenient
    functions for adding signals by their attribute name.

    Parameters
    ----------
    parent: QWidget
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Setup layout
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(2, 2, 2, 2)
        # Make sure we can add signals
        self.signal_combo = QComboBox()
        self.signal_combo_label = QLabel('Available Signals: ')
        self.signal_create = QPushButton('Connect')
        self.signal_combo_layout = QHBoxLayout()
        self.signal_combo_layout.addWidget(self.signal_combo_label, 0)
        self.signal_combo_layout.addWidget(self.signal_combo, 1)
        self.signal_combo_layout.addWidget(self.signal_create, 0)
        self.signal_create.clicked.connect(self.creation_requested)
        self.layout().addLayout(self.signal_combo_layout)
        # Add timechart
        self.timechart = TimeChartDisplay(show_pv_add_panel=False)
        self.layout().addWidget(self.timechart)
        self.channel_map = self.timechart.channel_map

    def add_available_signal(self, signal, name):
        """
        Add an Ophyd signal to the list of available channels

        If the Signal is not an EPICS Signal object you are responsible for
        registering this yourself, if not already done.

        Parameters
        ----------
        signal: ophyd.Signal

        name: str
            Alias for signal to display in QComboBox
        """
        self.signal_combo.addItem(name, channel_from_signal(signal))

    def add_curve(self, channel, name=None, color=None, **kwargs):
        """
        Add a curve to the plot

        Parameters
        ----------
        channel : str
            PyDMChannel address

        name : str, optional
            Name of TimePlotCurveItem. If None is given, the ``channel`` is
            used.

        color: QColor, optional
            Color to display line in plot. If None is given, a QColor will be
            chosen randomly

        kwargs:
            Passed to ``timechart.add_y_channel``
        """
        name = name or channel
        # Create a random color if None is supplied
        if not color:
            color = random_color()
        logger.debug("Adding %s to plot ...", channel)
        # TODO: Until https://github.com/slaclab/timechart/pull/32 is in
        # a release, the pv_name and curve_name need to be the same
        self.timechart.add_y_channel(pv_name=channel, curve_name=channel,
                                     color=color, **kwargs)

    @Slot()
    def remove_curve(self, name):
        """
        Remove a curve from the plot

        Parameters
        ----------
        name: str
            Name of the curve to remove. This should match the name given
            during the call of :meth:`.add_curve`
        """
        logger.debug("Removing %s from TyphosTimePlot ...", name)
        self.timechart.remove_curve(name)

    @Slot()
    def creation_requested(self):
        """
        Reaction to ``create_button`` press

        Observes the state of the selection widgets and makes the appropriate
        call to :meth:`.add_curve`
        """
        # Find requested channel
        name = self.signal_combo.currentText()
        idx = self.signal_combo.currentIndex()
        channel = self.signal_combo.itemData(idx)
        # Add to the plot
        self.add_curve(channel, name=name)

    def add_device(self, device):
        """Add a device and it's component signals to the plot"""
        super().add_device(device)
        # Sort through components
        devices = [device] + [getattr(device, sub)
                              for sub in device._sub_devices]
        for subdevice in devices:
            logger.debug("Adding signals for %s to plot ...", subdevice.name)
            for component in subdevice.component_names:
                # Find all signals
                if not isinstance(component, Device):
                    try:
                        sig = getattr(subdevice, component)
                        # Only include scalars
                        if sig.describe()[sig.name]['dtype'] in ('integer',
                                                                 'number'):
                            # Make component name
                            name = clean_attr(component)
                            if subdevice != device:
                                name = ' '.join((clean_name(subdevice), name))
                            # Add to list of available signals
                            self.add_available_signal(sig, name)
                            # Automatically plot if in Device hints
                            if sig.name in subdevice.hints.get('fields', []):
                                self.add_curve(channel_from_signal(sig),
                                               name=name)
                    except Exception:
                        logger.exception("Unable to add %s to "
                                         "plot-able signals",
                                         component)

TyphonTimePlot = warn_renamed(TyphosTimePlot, 'TyphonTimePlot')