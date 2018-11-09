"""
Typhon Plotting Interface
"""
############
# Standard #
############
import os.path
import logging
from functools import partial
from warnings import warn

###############
# Third Party #
###############
from ophyd import Device

from qtpy import uic
from qtpy.QtCore import Qt, Slot
from qtpy.QtGui import QBrush
from qtpy.QtWidgets import QApplication, QWidget

##########
# Module #
##########
from ..utils import (ui_dir, channel_from_signal, clean_attr, random_color,
                     clean_name, TyphonBase)

logger = logging.getLogger(__name__)


class ChannelDisplay(QWidget):
    """
    Display for a PyDM PlotCurveItem

    Parameters
    ----------
    name : str
        Alias of channel

    color: QColor
        Color of curve in plot
    """
    def __init__(self, name, color, parent=None):
        super().__init__(parent=parent)
        self.ui = uic.loadUi(os.path.join(ui_dir, 'plotitem.ui'), self)
        self.ui.name.setText(name)
        self.ui.color.brush = QBrush(color, Qt.SolidPattern)


class TyphonTimePlot(TyphonBase):
    """
    Generalized widget for plotting Ophyd signals

    This widget initializes a blank ``PyDMTimePlot`` with a small interface to
    configure the plotted signals. The list of signals available to the
    operator can be controlled via :meth:`.add_available_signal`. Shortcuts can
    be added to the plot itself via :meth:`.add_curve` or the
    :meth:`.creation_requested` ``Slot`` which takes the current status of
    the requested combinations

    Parameters
    ----------
    parent: QWidget
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Load generated user interface file
        self.ui = uic.loadUi(os.path.join(ui_dir, 'plot.ui'), self)
        # Connect create button
        self.create_button.clicked.connect(self.creation_requested)
        # Data structure for name / ChannelDisplay mapping
        self.channel_map = dict()

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
        self.ui.signal_combo.addItem(name, channel_from_signal(signal))

    def add_curve(self, channel, name=None, color=None):
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
        """
        name = name or channel
        # Do not allow duplicate channels
        if name in self.channel_map:
            logger.error("%r already has been added to the plot", name)
            return
        logger.debug("Adding %s to plot ...", channel)
        # Create a random color if None is supplied
        if not color:
            color = random_color()
        # Add to plot
        self.ui.timeplot.addYChannel(y_channel=channel, color=color,
                                     name=name, lineStyle=Qt.SolidLine,
                                     lineWidth=2, symbol=None)
        # Add a display to the LiveChannel display
        ch_display = ChannelDisplay(name, color)
        self.ui.live_channels.layout().insertWidget(0, ch_display)
        self.channel_map[name] = ch_display
        # Connect the removal button to the slot
        ch_display.remove_button.clicked.connect(partial(self.remove_curve,
                                                         name))
        # Establish connections for new instance
        pydm_app = QApplication.instance()
        pydm_app.establish_widget_connections(self)
        # Select new random color
        self.ui.color.brush = QBrush(random_color(), Qt.SolidPattern)

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
        if name in self.channel_map:
            logger.debug("Removing %s from DeviceTimePlot ...", name)
            self.ui.timeplot.removeCurveWithName(name)
            # Remove ChannelDisplay
            ch_display = self.channel_map.pop(name)
            self.ui.live_channels.layout().removeWidget(ch_display)
            # Destroy ChannelDisplay
            ch_display.deleteLater()
        else:
            logger.error("Curve %r was not found in DeviceTimePlot", name)

    @Slot()
    def creation_requested(self):
        """
        Reaction to ``create_button`` press

        Observes the state of the selection widgets and makes the appropriate
        call to :meth:`.add_curve`
        """
        # Find requested channel
        name = self.ui.signal_combo.currentText()
        idx = self.ui.signal_combo.currentIndex()
        channel = self.ui.signal_combo.itemData(idx)
        # Add to the plot
        self.add_curve(channel, name=name, color=self.ui.color.brush.color())

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


def DeviceTimePlot(device, parent=None):
    warn("DeviceTimePlot has been deprecated. "
         "Use TyphonTimePlot.from_device instead.")
    return TyphonTimePlot.from_device(device, parent=parent)
