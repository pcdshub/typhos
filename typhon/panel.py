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
                self.contents.show()
            else:
                self.contents.hide()


class SignalPanel(Panel):
    """
    Base panel display for EPICS signals

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
    def __init__(self, title, signals=None, enum_sigs=None, parent=None):
        super().__init__(title, parent=parent)
        # Store signal information
        self.signals = dict()
        self.enum_sigs = enum_sigs or list()
        # Create empty panel contents
        self.contents = QWidget()
        self.contents.setLayout(QGridLayout())
        self.layout().addWidget(self.contents)
        # Add supplied signals
        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

    def add_signal(self, signal, name, enum=False):
        """
        Add a signal to the panel

        The type of widget control that is drawn is dependent on
        :attr:`_read_pv`, and :attr:`_write_pv`. attributes given
        ``EpicsSignal``, as well as the :attr:`enum_attrs` property. Because it
        is not possible to tell from a disconnected signal whether the PV has
        corresponding ``enum_strs``, you can force the widget that controls the
        PV to be a ``PyDMEnumComboBox`` by setting ``enum=True``. If this is
        False, the default widget will be a ``PyDMLineEdit``.

        Parameters
        ----------
        signal : EpicsSignal, EpicsSignalRO
            Signal to create a widget

        name : str
            Name of signal to display

        enum : bool, optional
            Consider the PV to be an `Enum` and provide a QComboBox to control
            it rather than a LineEdit

        Returns
        -------
        loc : int
            Row number that the signal information was added to in the
            `SignalPanel.contents.layout()``
        """
        logger.debug("Adding signal %s", name)
        # Add our signal to enum list
        if enum:
            self.enum_sigs.append(name)
        # Create label
        label = QLabel(self)
        label.setText(name)
        label_font = QFont()
        label.setFont(label_font)
        # Create signal display
        val_display = QHBoxLayout()
        # Add readback
        ro = TyphonLabel(init_channel=channel_name(signal._read_pv.pvname),
                         parent=self)
        val_display.addWidget(ro)
        # Add write
        if hasattr(signal, '_write_pv'):
            ch = channel_name(signal._write_pv.pvname)
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
        self.contents.layout().addWidget(label, loc, 0)
        self.contents.layout().addLayout(val_display, loc, 1)

        # Store signal
        self.signals[name] = signal

        return loc
