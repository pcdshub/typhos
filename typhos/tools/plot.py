"""
Typhos Plotting Interface
"""
import logging

from qtpy.QtCore import Slot
from qtpy.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                            QVBoxLayout)
from timechart.displays.main_display import TimeChartDisplay
from timechart.utilities.utils import random_color

from .. import utils

logger = logging.getLogger(__name__)


class TyphosTimePlot(utils.TyphosBase):
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
        self._device_threads = {}

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
        self.signal_combo.addItem(name, utils.channel_from_signal(signal))

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

    @Slot(object, bool, dict)
    def _connection_update(self, signal, connected, metadata):
        if not connected:
            return

        name = f'{signal.root.name}.{signal.dotted_name}'

        try:
            desc = signal.describe()[signal.name]
        except Exception:
            logger.exception("Unable to add %s to plot-able signals", name)
            return

        # Only include scalars
        if desc['dtype'] not in ('integer', 'number'):
            logger.debug("Ignoring non-scalar signal %s", name)
            return

        # Add to list of available signal
        self.add_available_signal(signal, name)
        if signal.name in signal.root.hints.get('fields', []):
            self.add_curve(utils.channel_from_signal(signal), name=name)

    def add_device(self, device):
        """Add a device and it's component signals to the plot"""
        super().add_device(device)

        if device not in self._device_threads:
            thread = utils.DeviceConnectionMonitorThread(
                device, include_lazy=False)
            thread.connection_update.connect(self._connection_update)
            self._device_threads[device] = thread
            thread.start()
