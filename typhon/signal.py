############
# Standard #
############
import logging
from warnings import warn

############
# External #
############
from ophyd.signal import EpicsSignal, EpicsSignalBase, EpicsSignalRO
from ophyd.sim import SignalRO
from qtpy.QtCore import QSize
from qtpy.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QWidget)

#############
#  Package  #
#############
from .utils import channel_name
from .widgets import TyphonLineEdit, TyphonComboBox, TyphonLabel
from .plugins import register_signal

logger = logging.getLogger(__name__)


def signal_widget(signal, read_only=False):
    """
    Factory for creating a PyDMWidget from a signal

    Parameters
    ----------
    signal : ophyd.Signal
        Signal object to create widget

    read_only: bool, optional
        Whether this widget should be able to write back to the signal you
        provided

    Returns
    -------
    widget : PyDMWidget
        PyDMLabel, PyDMLineEdit, or PyDMEnumComboBox based on whether we should
        be able to write back to the widget and if the signal has ``enum_strs``
    """
    # Grab our channel name
    # Still re-route EpicsSignal through the ca:// plugin
    if isinstance(signal, EpicsSignalBase):
        if read_only:
            pv = signal._read_pv
        else:
            pv = signal._write_pv
        chan = channel_name(pv.pvname)
    else:
        # Register signal with plugin
        register_signal(signal)
        chan = channel_name(signal.name, protocol='sig')
    # Check for enum_strs, if so create a QCombobox
    if read_only:
        logger.debug("Creating Label for %s", signal.name)
        widget = TyphonLabel
    else:
        # Grab a description of the widget to see the correct widget type
        try:
            desc = signal.describe()[signal.name]
        except Exception as exc:
            logger.error("Unable to connect to %r during widget creation",
                         signal)
            desc = {}
        # Create a QCombobox if the widget has enum_strs
        if 'enum_strs' in desc:
            logger.debug("Creating Combobox for %s", signal.name)
            widget = TyphonComboBox
        # Otherwise a LineEdit will suffice
        else:
            logger.debug("Creating LineEdit for %s", signal.name)
            widget = TyphonLineEdit
    return widget(init_channel=chan)


class SignalPanel(QWidget):
    """
    Base panel display for EPICS signals

    Parameters
    ----------
    signals : OrderedDict, optional
        Signals to include in the panel

    parent : QWidget, optional
        Parent of panel
    """
    def __init__(self, title=None, signals=None, parent=None):
        super().__init__(parent=parent)
        # Title is no longer supported
        if title:
            warn("The 'title' option for SignalPanel is deprecated. "
                 "It will be removed in future releases.")
        # Store signal information
        self.signals = dict()
        # Create panel layout
        lay = QGridLayout()
        lay.setSizeConstraint(QGridLayout.SetFixedSize)
        self.setLayout(lay)
        self.layout().setContentsMargins(5, 5, 5, 5)
        # Add supplied signals
        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

    def sizeHint(self):
        return QSize(375, 375)

    def add_signal(self, signal, name):
        """
        Add a signal to the panel

        The type of widget control that is drawn is dependent on
        :attr:`_read_pv`, and :attr:`_write_pv`. attributes.

        Parameters
        ----------
        signal : EpicsSignal, EpicsSignalRO
            Signal to create a widget

        name : str
            Name of signal to display

        Returns
        -------
        loc : int
            Row number that the signal information was added to in the
            `SignalPanel.layout()``
        """
        logger.debug("Adding signal %s", name)
        # Create the read-only signal
        read = signal_widget(signal, read_only=True)
        # Create the write signal
        if not isinstance(signal, (SignalRO, EpicsSignalRO)):
            write = signal_widget(signal)
        else:
            write = None
        # Add to the layout
        return self._add_row(read, name, write=write)

    def add_pv(self, read_pv, name, write_pv=None):
        """
        Add PVs to the SignalPanel

        Parameters
        ---------
        read_pv : pyepics.PV

        name : str
            Name of signal to display

        write_pv : pyepics.PV, optional

        Returns
        -------
        loc : int
            Row number that the signal information was added to in the
            `SignalPanel.layout()``
        """
        logger.debug("Adding PV %s", name)
        # Configure optional write PV settings
        if write_pv:
            sig = EpicsSignal(read_pv, name=name, write_pv=write_pv)
        else:
            sig = EpicsSignalRO(read_pv, name=name)
        return self.add_signal(sig, name)

    def _add_row(self, read, name, write=None):
        # Create label
        label = QLabel(self)
        label.setText(name)
        # Create signal display
        val_display = QHBoxLayout()
        # Add readback
        val_display.addWidget(read)
        # Add our write_pv if available
        if write is not None:
            # Add our control widget to layout
            val_display.addWidget(write)
            # Make sure they share space evenly
            val_display.setStretch(0, 1)
            val_display.setStretch(1, 1)
        # Add displays to panel
        loc = len(self.signals)
        self.layout().addWidget(label, loc, 0)
        self.layout().addLayout(val_display, loc, 1)
        # Store signal
        self.signals[name] = (read, write)
        return loc
