############
# Standard #
############
import logging

############
# External #
############
from pydm.PyQt.QtGui import QHBoxLayout, QFont, QLabel, QWidget, QGridLayout
from pydm.widgets.line_edit import PyDMLineEdit

#############
#  Package  #
#############
from .utils import channel_name
from .widgets import TyphonLabel

logger = logging.getLogger(__name__)


class Panel(QWidget):
    """
    Base Panel Display for Signals

    Parameters
    ----------
    signals : OrderedDict, optional
        Signals to include in the panel

    parent : QWidget, optional
        Parent of panel
    """
    def __init__(self, signals=None, parent=None):
        super().__init__(parent=parent)
        self.signals = dict()
        # Set QGridLayout to widget
        self._layout = QGridLayout()
        self.setLayout(self._layout)
        # Add supplied signals
        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

    def add_signal(self, signal, name):
        """
        Parameters
        ----------
        signal : EpicsSignal, EpicsSignalRO
            Signal to create a widget

        name : str
            Name of signal to display
        """
        logger.debug("Adding signal %s", name)
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
            logger.debug("Adding LineEdit for %s", name)
            edit = PyDMLineEdit(init_channel=channel_name(signal._write_pv),
                                parent=self)
            val_display.addWidget(edit)
        # Add displays to panel
        self._layout.addWidget(label, len(self.signals), 0)
        self._layout.addLayout(val_display, len(self.signals), 1)

        # Store signal
        self.signals[name] = signal
