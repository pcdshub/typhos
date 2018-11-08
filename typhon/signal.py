############
# Standard #
############
from functools import partial
import logging

############
# External #
############
from ophyd import Kind
from ophyd.signal import EpicsSignal, EpicsSignalBase, EpicsSignalRO
from qtpy.QtCore import Property, QSize
from qtpy.QtWidgets import (QGridLayout, QHBoxLayout, QLabel)
from pydm.widgets.base import PyDMWidget

#############
#  Package  #
#############
from .utils import (channel_name, clear_layout, clean_attr, grab_kind,
                    is_signal_ro, TyphonBase)
from .widgets import TyphonLineEdit, TyphonComboBox, TyphonLabel
from .plugins import register_signal, HappiChannel

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
        except Exception:
            logger.error("Unable to connect to %r during widget creation",
                         signal.name)
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


class SignalPanel(QGridLayout):
    """
    Base panel display for EPICS signals

    Parameters
    ----------
    signals : OrderedDict, optional
        Signals to include in the panel
        Parent of panel
    """
    def __init__(self, signals=None):
        super().__init__()
        # Store signal information
        self.signals = dict()
        # Add supplied signals
        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

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
        if not is_signal_ro(signal):
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

    def clear(self):
        """Clear the SignalPanel"""
        logger.debug("Clearing layout %r ...", self)
        clear_layout(self)
        self.signals.clear()

    def _add_row(self, read, name, write=None):
        # Create label
        label = QLabel()
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
        self.addWidget(label, loc, 0)
        self.addLayout(val_display, loc, 1)
        # Store signal
        self.signals[name] = (read, write)
        return loc


class TyphonPanel(TyphonBase, PyDMWidget):
    """
    Panel of Signals for Device
    """

    def __init__(self, parent=None, init_channel=None):
        super().__init__(parent=parent)
        # Create a SignalPanel layout to be modified later
        self.setLayout(SignalPanel())
        # Add default Kind values
        self._kinds = dict.fromkeys([kind.name for kind in Kind], True)

    def _get_kind(self, kind):
        return self._kinds[kind]

    def _set_kind(self, value, kind):
        # If we have a new value store it
        if value != self._kinds[kind]:
            # Store it internally
            self._kinds[kind] = value
            # Remodify the layout for the new Kind
            self._set_layout()

    # Kind Configuration pyqtProperty
    showHints = Property(bool,
                         partial(_get_kind, kind='hinted'),
                         partial(_set_kind, kind='hinted'))
    showNormal = Property(bool,
                          partial(_get_kind, kind='normal'),
                          partial(_set_kind, kind='normal'))
    showConfig = Property(bool,
                          partial(_get_kind, kind='config'),
                          partial(_set_kind, kind='config'))
    showOmitted = Property(bool,
                           partial(_get_kind, kind='omitted'),
                           partial(_set_kind, kind='omitted'))

    @Property(str)
    def channel(self):
        """The channel address to use for this widget"""
        if self._channel:
            return str(self._channel)
        return None

    @channel.setter
    def channel(self, value):
        if self._channel != value:
            # Remove old connection
            if self._channels:
                self._channels.clear()
                for channel in self._channels:
                    if hasattr(channel, 'disconnect'):
                        channel.disconnect()
            # Load new channel
            self._channel = str(value)
            channel = HappiChannel(address=self._channel,
                                   tx_slot=self._tx)
            self._channels = [channel]
            # Connect the channel to the HappiPlugin
            if hasattr(channel, 'connect'):
                channel.connect()

    def add_device(self, device):
        """Add a device to the widget"""
        # Only allow a single device
        self.devices.clear()
        # Add the new device
        super().add_device(device)
        # Configure the layout for the new device
        self._set_layout()

    def _set_layout(self):
        """Set the layout based on the current device and kind"""
        # We can't set a layout if we don't have any devices
        if not self.devices:
            return
        # Clear our layout
        self.layout().clear()
        shown_kind = [kind for kind in Kind if self._kinds[kind.name]]
        # Iterate through kinds
        for kind in (Kind.hinted, Kind.normal, Kind.config, Kind.omitted):
            if kind in shown_kind:
                try:
                    for (attr, signal) in grab_kind(self.devices[0],
                                                    kind.name):
                        label = clean_attr(attr)
                        in_layout = label in self.layout().signals
                        # Check twice for Kind as signal might have multiple
                        # kinds
                        if signal.kind in shown_kind and not in_layout:
                            self.layout().add_signal(signal, label)
                except Exception:
                    logger.exception("Unable to add %s signals from %r",
                                     kind.name, self.devices[0])

    def sizeHint(self):
        """Default SizeHint"""
        return QSize(240, 140)

    def _tx(self, value):
        """Receive new device information"""
        self.add_device(value['obj'])
