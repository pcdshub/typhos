############
# Standard #
############
import logging

############
# External #
############
import qtawesome as qta
from qtpy.QtCore import Property, QSize, Qt, Signal, Slot
from qtpy.QtWidgets import (QAction, QPushButton, QVBoxLayout, QWidget,
                            QToolBar, QDockWidget, QDialog)
from pydm.widgets import (PyDMLabel, PyDMEnumComboBox, PyDMLineEdit,
                          PyDMWaveformPlot, PyDMImageView)
from pydm.widgets.base import PyDMWidget
from pyqtgraph.parametertree import parameterTypes as ptypes

###########
# Package #
###########
from .plugins import HappiChannel

logger = logging.getLogger(__name__)


class TogglePanel(QWidget):
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

    @Slot(bool)
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


class TyphonComboBox(PyDMEnumComboBox):
    """
    Reimplementation of PyDMEnumComboBox to set some custom defaults
    """
    def sizeHint(self):
        return QSize(100, 30)


class TyphonLineEdit(PyDMLineEdit):
    """
    Reimplementation of PyDMLineEdit to set some custom defaults
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.showUnits = True
        self.setMinimumHeight(30)
        self.setMaximumHeight(30)
        self.setMinimumWidth(60)

    def sizeHint(self):
        return QSize(100, 30)


class TyphonLabel(PyDMLabel):
    """
    Reimplemtation of PyDMLabel to set some custom defaults
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignCenter)
        self.showUnits = True
        self.setMinimumHeight(30)
        self.setMaximumHeight(30)
        self.setMinimumWidth(60)

    def sizeHint(self):
        return QSize(100, 30)


class TyphonSidebarItem(ptypes.ParameterItem):
    """
    Class to display a Device or Tool in the sidebar
    """
    def __init__(self, param, depth):
        super().__init__(param, depth)
        # Configure a QToolbar
        self.toolbar = QToolBar()
        self.toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.toolbar.setIconSize(QSize(15, 15))
        # Setup the action to open the widget
        self.open_action = QAction(qta.icon('fa.square',
                                            color='green'),
                                   'Open', self.toolbar)
        self.open_action.triggered.connect(self.open_requested)
        # Setup the action to embed the widget
        self.embed_action = QAction(qta.icon('fa.th-large',
                                             color='yellow'),
                                    'Embed', self.toolbar)
        self.embed_action.triggered.connect(self.embed_requested)
        # Setup the action to hide the widget
        self.hide_action = QAction(qta.icon('fa.times-circle',
                                            color='red'),
                                   'Close', self.toolbar)
        self.hide_action.triggered.connect(self.hide_requested)
        self.hide_action.setEnabled(False)
        # Add actions to toolbars
        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.hide_action)
        if self.param.embeddable:
            self.toolbar.insertAction(self.hide_action,
                                      self.embed_action)

    def open_requested(self, triggered):
        """Request to open display for sidebar item"""
        self.param.sigOpen.emit(self)
        self._mark_shown()

    def embed_requested(self, triggered):
        """Request to open embedded display for sidebar item"""
        self.param.sigEmbed.emit(self)
        self._mark_shown()

    def hide_requested(self, triggered):
        """Request to hide display for sidebar item"""
        self.param.sigHide.emit(self)
        self._mark_hidden()

    def _mark_shown(self):
        self.open_action.setEnabled(False)
        self.embed_action.setEnabled(False)
        self.hide_action.setEnabled(True)

    def _mark_hidden(self):
        self.open_action.setEnabled(True)
        self.embed_action.setEnabled(True)
        self.hide_action.setEnabled(False)

    def treeWidgetChanged(self):
        """Update the widget when add to a QTreeWidget"""
        super().treeWidgetChanged()
        tree = self.treeWidget()
        if tree is None:
            return
        tree.setItemWidget(self, 1, self.toolbar)


class SubDisplay(QDockWidget):
    """QDockWidget modified to emit a signal when closed"""
    closing = Signal()

    def closeEvent(self, evt):
        self.closing.emit()
        super().closeEvent(evt)


class TyphonDesignerMixin(PyDMWidget):
    # Unused properties that we don't want visible in designer
    alarmSensitiveBorder = Property(bool, designable=False)
    alarmSensitiveContent = Property(bool, designable=False)
    precisionFromPV = Property(bool, designable=False)
    precision = Property(int, designable=False)
    showUnits = Property(bool, designable=False)

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

    @Slot(object)
    def _tx(self, value):
        """Receive information from happi channel"""
        self.add_device(value['obj'])


class SignalDialogButton(QPushButton):
    """QPushButton to launch a QDialog with a PyDMWidget"""
    text = NotImplemented
    icon = NotImplemented

    def __init__(self, init_channel, text=None, icon=None, parent=None):
        self.text = text or self.text
        self.icon = icon or self.icon
        super().__init__(qta.icon(self.icon), self.text, parent=parent)
        self.clicked.connect(self.show_dialog)
        self.dialog = None
        self.channel = init_channel
        self.setIconSize(QSize(15, 15))

    def widget(self, channel):
        """Return a widget created with channel"""
        raise NotImplementedError

    def show_dialog(self):
        """Show the channel in a QDialog"""
        # Dialog Creation
        if not self.dialog:
            logger.debug("Creating QDialog for %r", self.channel)
            # Set up the QDialog
            self.dialog = QDialog(self)
            self.dialog.setWindowTitle(self.channel)
            self.dialog.setLayout(QVBoxLayout())
            self.dialog.layout().setContentsMargins(2, 2, 2, 2)
            # Add the widget
            widget = self.widget()
            self.dialog.layout().addWidget(widget)
        # Handle a lost dialog
        else:
            logger.debug("Redisplaying QDialog for %r", self.channel)
            self.dialog.close()
        # Show the dialog
        logger.debug("Showing QDialog for %r", self.channel)
        self.dialog.show()


class ImageDialogButton(SignalDialogButton):
    """QPushButton to show a 2-d array"""
    text = 'Show Image'
    icon = 'fa.camera'

    def widget(self):
        """Create PyDMImageView"""
        return PyDMImageView(parent=self,
                             image_channel=self.channel)


class WaveformDialogButton(SignalDialogButton):
    """QPushButton to show a 1-d array"""
    text = 'Show Waveform'
    icon = 'fa5s.chart-line'

    def widget(self):
        """Create PyDMWaveformPlot"""
        return PyDMWaveformPlot(init_y_channels=[self.channel],
                                parent=self)
