############
# Standard #
############
import logging

############
# External #
############
from pydm.PyQt.QtGui import QHBoxLayout, QFont, QLabel, QWidget, QGridLayout
from pydm.widgets import PyDMLineEdit

#############
#  Package  #
#############
from .utils import channel_name
from .widgets import TyphonComboBox, TyphonLabel

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
        self.layout().setContentsMargins(2, 2, 2, 2)
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
        return self.add_pv(signal._read_pv, name,
                           write_pv=getattr(signal, '_write_pv', None))

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
        # Create label
        label = QLabel(self)
        label.setText(name)
        label_font = QFont()
        label.setFont(label_font)
        # Create signal display
        val_display = QHBoxLayout()
        # Add readback
        ro = TyphonLabel(init_channel=channel_name(read_pv.pvname),
                         parent=self)
        val_display.addWidget(ro)
        # Add our write_pv if available
        if write_pv:
            ch = channel_name(write_pv.pvname)
            # Check whether our device is an enum or not
            if write_pv.enum_strs:
                edit = TyphonComboBox(init_channel=ch, parent=self)
            else:
                logger.debug("Adding LineEdit for %s", name)
                edit = PyDMLineEdit(init_channel=ch, parent=self)
            # Add our control widget to layout
            val_display.addWidget(edit)
        # Add displays to panel
        loc = len(self.pvs)
        self.layout().addWidget(label, loc, 0)
        self.layout().addLayout(val_display, loc, 1)
        # Store signal
        self.pvs[name] = (read_pv, write_pv)
        return loc
