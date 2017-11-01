############
# Standard #
############
import logging

############
# External #
############
from pydm.PyQt.QtGui import QHBoxLayout, QFont, QLabel, QWidget, QGridLayout
from pydm.widgets.label import PyDMLabel
from pydm.widgets.line_edit import PyDMLineEdit

#############
#  Package  #
#############
from .utils import channel_name

logger = logging.getLogger(__name__)

class Panel(QWidget):
    """
    Base Panel Display for Signals

    Parameters
    ----------
    signals : OrderedDict, optional
        Signals to include in the panel

    max_cols : int, optional
        Number of columns of information to display

    parent : QWidget, optional
        Parent of panel
    """
    def __init__(self, signals=None, max_cols=8, parent=None):
        super().__init__(parent=parent)
        self.max_cols = max_cols
        self.signals  = dict()
        self.layout   = QGridLayout(self)
        #Add supplied signals
        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

    @property
    def current_column(self):
        """
        Current row of panel to add widgets
        """
        return 2*(len(self.signals)%self.max_cols)

    @property
    def current_row(self):
        """
        Current column of panels to add widgets
        """
        return len(self.signals) // self.max_cols

    def add_signal(self, signal, name):
        """
        Parameters
        ----------
        signal : EpicsSignal, EpicsSignalRO
            Signal to create a widget

        name : str
            Name of signal to display
        """
        logger.info("Adding signal %r with label %s", signal, name)
        #Create label
        label = QLabel(self)
        label.setText(name)
        label_font = QFont()
        label_font.setBold(True)
        label.setFont(label_font)
        #Create signal display
        val_display = QHBoxLayout(self)
        #Add readback
        val_display.addWidget(PyDMLabel(init_channel=channel_name(signal._read_pv),
                                        parent=self))
        #Add write
        if hasattr(signal, '_write_pv'):
            logger.debug("Adding PyDMLineEdit for %s", name)
            val_display.addWidget(PyDMLineEdit(init_channel=channel_name(signal._write_pv),
                                               parent=self))
        #Add displays to panel
        self.layout.addWidget(label, self.current_row, self.current_column)
        self.layout.addLayout(val_display, self.current_row, self.current_column+1)

        #Store signal
        self.signals[name] = signal

