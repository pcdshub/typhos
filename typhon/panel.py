############
# Standard #
############
import logging

############
# External #
############
from pydm.PyQt.QtCore import pyqtSlot
from pydm.PyQt.QtGui import QHBoxLayout, QFont, QLabel, QWidget, QGridLayout
from pydm.PyQt.QtGui import QPushButton, QVBoxLayout
from pydm.widgets import PyDMLineEdit

#############
#  Package  #
#############
from .utils import channel_name
from .widgets import TyphonComboBox, TyphonLabel

logger = logging.getLogger(__name__)


class Panel(QWidget):
    """
    Generic Panel Widget

    Displays a widget below QPushButton that hides and shows the contents. It
    is up to subclasses to re-point the attribute :attr:`.contents` to the
    widget whose visibility you would like to toggle.

    By default, it is assumed that the Panel is initialized with the
    :attr:`.contents` widget as visible, however the contents will be hidden
    and the button synced to the proper position if :meth:`.show_contents` is
    called after instance creation

    Parameters
    ----------
    title : str
        Title of Panel. This will be the text on the QPushButton

    parent : QWidget

    Attributes
    ----------
    contents : QWidget
        Widget whose visibility is controlled via the QPushButton
    """
    def __init__(self, title, parent=None):
        super().__init__(parent=parent)
        # Create Widget Infrastructure
        self.title = title
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(2, 2, 2, 2)
        self.layout().setSpacing(5)
        # Create button control
        # Assuming widget is visible, set the button as checked
        self.contents = None
        self.hide_button = QPushButton(self.title)
        self.hide_button.setCheckable(True)
        self.hide_button.setChecked(True)
        self.layout().addWidget(self.hide_button)
        self.hide_button.clicked.connect(self.show_contents)

    @pyqtSlot(bool)
    def show_contents(self, show):
        """
        Show the contents of the Widget

        Hides the :attr:`.contents` QWidget and sets the :attr:`.hide_button`
        to the proper status to indicate whether the widget is hidden or not

        Parameters
        ----------
        show : bool
        """
        # Configure our button in case this slot was called elsewhere
        self.hide_button.setChecked(show)
        # Show or hide the widget if the contents exist
        if self.contents:
            if show:
                self.show()
                self.contents.show()
            else:
                self.contents.hide()


class SignalPanel(Panel):
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
        super().__init__(title, parent=parent)
        # Store signal information
        self.pvs = dict()
        # Create empty panel contents
        self.contents = QWidget()
        self.contents.setLayout(QGridLayout())
        self.contents.layout().setContentsMargins(2, 2, 2, 2)
        self.layout().addWidget(self.contents)
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
            `SignalPanel.contents.layout()``
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
            `SignalPanel.contents.layout()``
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
        self.contents.layout().addWidget(label, loc, 0)
        self.contents.layout().addLayout(val_display, loc, 1)
        # Store signal
        self.pvs[name] = (read_pv, write_pv)
        # Check that our widget is not hidden
        self.show_contents(True)
        return loc
