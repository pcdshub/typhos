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


class Panel(QWidget):
    """
    Base Panel Display for Signals

    Parameters
    ----------
    signals : OrderedDict, optional
        Signals to include in the panel

    enum_sigs : list, optional
        Force certain PV controls to be QComboxBoxes instead of LineEdits.
        Useful for PVs that are expecting a certain subset of strings for their
        input. Should match the keys provided in the :param:`.signals`
        dictionary

    parent : QWidget, optional
        Parent of panel
    """
    def __init__(self, signals=None, enum_sigs=None, parent=None):
        super().__init__(parent=parent)
        # Store signal information
        self.signals = dict()
        self.enum_sigs = enum_sigs or list()
        # Set QGridLayout to widget
        self._layout = QGridLayout()
        self.setLayout(self._layout)
        # Add supplied signals
        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

    def add_signal(self, signal, name, enum=False):
        """
        Parameters
        ----------
        signal : EpicsSignal, EpicsSignalRO
            Signal to create a widget

        name : str
            Name of signal to display

        enum : bool, optional
            Consider the PV to be an `Enum` and provide a QCombobox to control
            it rather than a LineEdit

        Returns
        -------
        loc : int
            Row number that the signal information was added to in the
            `Typhon.Panel.layout()``
        """
        logger.debug("Adding signal %s", name)
        # Add our signal to enum list
        if enum:
            self.enum_sigs.append(name)
        # Create label
        label = QLabel(self)
        label.setText(name)
        label_font = QFont()
        label_font.setBold(True)
        label.setFont(label_font)
        # Create signal display
        val_display = QHBoxLayout()
        # Add readback
        ro = TyphonLabel(init_channel=channel_name(signal._read_pv),
                         parent=self)
        val_display.addWidget(ro)
        # Add write
        if hasattr(signal, '_write_pv'):
            ch = channel_name(signal._write_pv)
            # Check whether our device is an enum or not
            if (name in self.enum_sigs or (signal.connected
                                           and signal._write_pv.enum_strs)):
                edit = TyphonComboBox(init_channel=ch, parent=self)
            else:
                logger.debug("Adding LineEdit for %s", name)
                edit = PyDMLineEdit(init_channel=ch, parent=self)
            # Add our control widget to layout
            val_display.addWidget(edit)
        # Add displays to panel
        loc = len(self.signals)
        self._layout.addWidget(label, loc, 0)
        self._layout.addLayout(val_display, loc, 1)

        # Store signal
        self.signals[name] = signal

        return loc
