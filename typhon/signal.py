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
from qtpy.QtCore import Property, Q_ENUMS, QSize
from qtpy.QtWidgets import (QGridLayout, QHBoxLayout, QLabel)

#############
#  Package  #
#############
from .utils import (channel_name, clear_layout, clean_attr, grab_kind,
                    GrabKindItem, is_signal_ro, TyphonBase)
from .widgets import (TyphonLineEdit, TyphonComboBox, TyphonLabel,
                      TyphonDesignerMixin, ImageDialogButton,
                      WaveformDialogButton, SignalDialogButton)
from .plugins import register_signal


logger = logging.getLogger(__name__)


def signal_widget(signal, read_only=False, tooltip=None):
    """
    Factory for creating a PyDMWidget from a signal

    Parameters
    ----------
    signal : ophyd.Signal
        Signal object to create widget

    read_only: bool, optional
        Whether this widget should be able to write back to the signal you
        provided

    tooltip : str, optional
        Tooltip to use for the widget

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
    # Grab a description of the widget to see the correct widget type
    try:
        desc = signal.describe()[signal.name]
    except Exception:
        logger.error("Unable to connect to %r during widget creation",
                     signal.name)
        desc = {}
    # Unshaped data
    shape = desc.get('shape', [])
    try:
        dimensions = len(shape)
    except TypeError:
        dimensions = 0
    if dimensions == 0:
        # Check for enum_strs, if so create a QCombobox
        if read_only:
            logger.debug("Creating Label for %s", signal.name)
            widget = TyphonLabel
            name = signal.name + '_label'
        else:
            # Create a QCombobox if the widget has enum_strs
            if 'enum_strs' in desc:
                logger.debug("Creating Combobox for %s", signal.name)
                widget = TyphonComboBox
                name = signal.name + '_combo'
            # Otherwise a LineEdit will suffice
            else:
                logger.debug("Creating LineEdit for %s", signal.name)
                widget = TyphonLineEdit
                name = signal.name + '_edit'
    # Waveform
    elif len(desc.get('shape')) == 1:
        logger.debug("Creating WaveformDialogButton for %s", signal.name)
        widget = WaveformDialogButton
        name = signal.name + '_waveform_button'
    # B/W image
    elif len(desc.get('shape')) == 2:
        logger.debug("Creating ImageDialogButton for %s", signal.name)
        widget = ImageDialogButton
        name = signal.name + '_image_button'
    else:
        raise ValueError(f"Unable to create widget for widget of "
                         f"shape {len(desc.get('shape'))} from {signal.name}")
    widget_instance = widget(init_channel=chan)
    widget_instance.setObjectName(name)
    if tooltip is not None:
        widget_instance.setToolTip(tooltip)
    return widget_instance


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

    def add_signal(self, signal, name, *, tooltip=None):
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
        read = signal_widget(signal, read_only=True, tooltip=tooltip)
        # Create the write signal
        if (not is_signal_ro(signal) and not isinstance(read,
                                                        SignalDialogButton)):
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


class SignalOrder:
    """Option to sort signals"""
    byKind = 0
    byName = 1


class TyphonSignalPanel(TyphonBase, TyphonDesignerMixin, SignalOrder):
    """
    Panel of Signals for Device
    """
    Q_ENUMS(SignalOrder)  # Necessary for display in Designer
    SignalOrder = SignalOrder  # For convenience
    # From top of page to bottom
    kind_order = (Kind.hinted, Kind.normal,
                  Kind.config, Kind.omitted)

    def __init__(self, parent=None, init_channel=None):
        super().__init__(parent=parent)
        # Create a SignalPanel layout to be modified later
        self.setLayout(SignalPanel())
        # Add default Kind values
        self._kinds = dict.fromkeys([kind.name for kind in Kind], True)
        self._signal_order = SignalOrder.byKind

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

    @Property(SignalOrder)
    def sortBy(self):
        """Order signals will be placed in layout"""
        return self._signal_order

    @sortBy.setter
    def sortBy(self, value):
        if value != self._signal_order:
            self._signal_order = value
            self._set_layout()

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
        signals = list()
        device = self.devices[0]
        for kind in shown_kind:
            try:
                for attr, item in grab_kind(device, kind.name).items():
                    # Check twice for Kind as signal might have multiple kinds
                    if item.signal.kind in shown_kind:
                        label = clean_attr(attr)
                        signals.append((label, item.signal, item.component))
            except Exception:
                logger.exception("Unable to add %s signals from %r",
                                 kind.name, self.devices[0])
        # Pick our sorting function
        if self._signal_order == SignalOrder.byKind:

            # Sort by kind
            def sorter(x):
                return self.kind_order.index(x[1].kind)

        elif self._signal_order == SignalOrder.byName:

            # Sort by name
            def sorter(x):
                return x[0]
        else:
            logger.exception("Unknown sorting type %r", self.sortBy)
            return
        # Add to layout
        for (label, signal, cpt) in sorted(set(signals), key=sorter):
            self.layout().add_signal(signal, label, tooltip=cpt.doc)

    def sizeHint(self):
        """Default SizeHint"""
        return QSize(240, 140)
