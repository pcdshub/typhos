############
# Standard #
############
import logging

############
# External #
############
from ophyd.signal import EpicsSignalBase
from ophyd.sim import SignalRO
from pydm.PyQt.QtGui import QHBoxLayout, QLabel, QWidget, QGridLayout

#############
#  Package  #
#############
from .utils import channel_name
from .widgets import TyphonLineEdit, TyphonComboBox, TyphonLabel
from .plugins import register_signal

logger = logging.getLogger(__name__)


class SignalPanel(QWidget):
    """
    Base panel display for EPICS signals

    Parameters
    ----------
    title : str
        Title for hide button

    signals : OrderedDict, optional
        Signals to include in the panel

    parent : QWidget, optional
        Parent of panel
    """
    def __init__(self, title, signals=None, parent=None):
        super().__init__(parent=parent)
        # Store signal information
        self.pvs = dict()
        # Create panel layout
        self.setLayout(QGridLayout())
        self.layout().setContentsMargins(20, 20, 20, 20)
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
        # Reroute EpicsSignals to use PyDM EPICS Plugins
        if isinstance(signal, EpicsSignalBase):
            return self.add_pv(signal._read_pv, name,
                               write_pv=getattr(signal,
                                                '_write_pv',
                                                None))
        # Otherwise use SignalPlugin
        else:
            # Register signal with plugin
            register_signal(signal)
            # Check read-only
            if isinstance(signal, SignalRO):
                write = None
            else:
                write = channel_name(signal.name, protocol='sig')
            # Add signal row
            return self._add_row(channel_name(signal.name,
                                              protocol='sig'),
                                 name, write=write)

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
            is_enum = write_pv.enum_strs
            write_pv = channel_name(write_pv.pvname)
        else:
            is_enum = False
        # Add readback and discovered write PV to grid
        return self._add_row(channel_name(read_pv.pvname), name,
                             write=write_pv, is_enum=is_enum)

    def _add_row(self, read, name, write=None, is_enum=False):
        # Create label
        label = QLabel(self)
        label.setText(name)
        # Create signal display
        val_display = QHBoxLayout()
        # Add readback
        ro = TyphonLabel(init_channel=read, parent=self)
        val_display.addWidget(ro)
        # Add our write_pv if available
        if write:
            # Check whether our device is an enum or not
            if is_enum:
                edit = TyphonComboBox(init_channel=write, parent=self)
            else:
                logger.debug("Adding LineEdit for %s", name)
                edit = TyphonLineEdit(init_channel=write, parent=self)
            # Add our control widget to layout
            val_display.addWidget(edit)
            # Make sure they share space evenly
            val_display.setStretch(0, 1)
            val_display.setStretch(1, 1)
        # Add displays to panel
        loc = len(self.pvs)
        self.layout().addWidget(label, loc, 0)
        self.layout().addLayout(val_display, loc, 1)
        # Store signal
        self.pvs[name] = (read, write)
        return loc
