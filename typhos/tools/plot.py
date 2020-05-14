"""
Typhos Plotting Interface
"""
import logging

from qtpy import QtCore, QtGui
from qtpy.QtCore import Qt, Slot
from qtpy.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                            QVBoxLayout)
from timechart.displays.main_display import TimeChartDisplay
from timechart.utilities.utils import random_color

from .. import utils
from ..cache import get_global_describe_cache

logger = logging.getLogger(__name__)


class TyphosTimePlot(utils.TyphosBase):
    """
    Generalized widget for plotting Ophyd signals.

    This widget is a ``TimeChartDisplay`` wrapped with some convenient
    functions for adding signals by their attribute name.

    Parameters
    ----------
    parent : QWidget
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Setup layout
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(2, 2, 2, 2)

        self._model = QtGui.QStandardItemModel()
        self._proxy_model = QtCore.QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)

        self._available_signals = {}

        self.signal_combo = QComboBox()
        self.signal_combo.setModel(self._proxy_model)
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
        cache = get_global_describe_cache()
        cache.new_description.connect(self._new_description,
                                      Qt.QueuedConnection)

    @property
    def channel_to_curve(self):
        """
        A dictionary of channel_name to curve.
        """
        return dict(self.timechart.channel_map)

    def add_available_signal(self, signal, name):
        """
        Add an Ophyd signal to the list of available channels.

        If the Signal is not an EPICS Signal object you are responsible for
        registering this yourself, if not already done.

        Parameters
        ----------
        signal : ophyd.Signal

        name : str
            Alias for signal to display in QComboBox.

        Raises
        ------
        ValueError
            If a signal of the same name already is available.
        """
        if name in self._available_signals:
            raise ValueError('Signal already available')

        channel = utils.channel_from_signal(signal)
        self._available_signals[name] = (signal, channel)
        item = QtGui.QStandardItem(name)
        item.setData(channel, Qt.UserRole)
        self._model.appendRow(item)
        self._model.sort(0)

    def add_curve(self, channel, name=None, color=None, **kwargs):
        """
        Add a curve to the plot.

        Parameters
        ----------
        channel : str
            PyDMChannel address.

        name : str, optional
            Name of TimePlotCurveItem. If None is given, the ``channel`` is
            used.

        color : QColor, optional
            Color to display line in plot. If None is given, a QColor will be
            chosen randomly.

        **kwargs
            Passed to :meth:`timechart.add_y_channel`.
        """
        name = name or channel
        # Create a random color if None is supplied
        if not color:
            color = random_color()
        logger.debug("Adding %s to plot ...", channel)
        self.timechart.add_y_channel(pv_name=channel, curve_name=name,
                                     color=color, **kwargs)

    @Slot()
    def remove_curve(self, name):
        """
        Remove a curve from the plot.

        Parameters
        ----------
        name : str
            Name of the curve to remove. This should match the name given
            during the call of :meth:`.add_curve`.
        """
        logger.debug("Removing %s from TyphosTimePlot ...", name)
        self.timechart.remove_curve(name)

    @Slot()
    def creation_requested(self):
        """
        Reaction to ``create_button`` press.

        Observes the state of the selection widgets and makes the appropriate
        call to :meth:`.add_curve`.
        """
        # Find requested channel
        name = self.signal_combo.currentText()
        idx = self.signal_combo.currentIndex()
        channel = self.signal_combo.itemData(idx)
        # Add to the plot
        self.add_curve(channel, name=name)

    @Slot(object, dict)
    def _new_description(self, signal, desc):
        name = f'{signal.root.name}.{signal.dotted_name}'
        if 'dtype' not in desc:
            # Marks an error in retrieving the description
            logger.debug("Ignoring signal without description %s", name)
            return

        # Only include scalars
        if desc['dtype'] not in ('integer', 'number'):
            logger.debug("Ignoring non-scalar signal %s", name)
            return

        # Add to list of available signal
        try:
            self.add_available_signal(signal, name)
        except ValueError:
            # Signal already added
            return

    def add_device(self, device):
        """Add a device and it's component signals to the plot."""
        super().add_device(device)

        cache = get_global_describe_cache()
        for signal in utils.get_all_signals_from_device(device,
                                                        include_lazy=False):
            desc = cache.get(signal)
            if desc is not None:
                self._new_description(signal, desc)
