import collections
import datetime
import logging

import qtawesome as qta
from pyqtgraph.parametertree import parameterTypes as ptypes
from qtpy import QtGui, QtWidgets
from qtpy.QtCore import Property, QObject, QSize, Qt, Signal, Slot
from qtpy.QtWidgets import (QAction, QDialog, QDockWidget, QPushButton,
                            QToolBar, QVBoxLayout, QWidget)

from pydm.widgets import (PyDMEnumComboBox, PyDMImageView, PyDMLabel,
                          PyDMLineEdit, PyDMWaveformPlot)
from pydm.widgets.base import PyDMWidget
from pydm.widgets.channel import PyDMChannel

logger = logging.getLogger(__name__)

EXPONENTIAL_UNITS = ['mtorr', 'torr', 'kpa', 'pa']


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


class TyphosComboBox(PyDMEnumComboBox):
    """
    Reimplementation of PyDMEnumComboBox to set some custom defaults
    """
    def sizeHint(self):
        return QSize(100, 30)


class TyphosLineEdit(PyDMLineEdit):
    """
    Reimplementation of PyDMLineEdit to set some custom defaults
    """
    def __init__(self, *args, **kwargs):
        self._setpoint_history_count = 5
        self._setpoint_history = collections.deque(
            [],  self._setpoint_history_count)

        super().__init__(*args, **kwargs)
        self.showUnits = True
        self.setMinimumHeight(30)
        self.setMaximumHeight(30)
        self.setMinimumWidth(60)

    def sizeHint(self):
        return QSize(100, 30)

    @property
    def setpoint_history(self):
        """
        History of setpoints, as a dictionary of {setpoint: timestamp}
        """
        return dict(self._setpoint_history)

    @Property(int, designable=True)
    def setpointHistoryCount(self):
        """
        Number of items to show in the context menu "setpoint history"
        """
        return self._setpoint_history_count

    @setpointHistoryCount.setter
    def setpointHistoryCount(self, value):
        self._setpoint_history_count = max((0, int(value)))
        self._setpoint_history = collections.deque(
            self._setpoint_history, self._setpoint_history_count)

    def _remove_history_item_by_value(self, remove_value):
        """
        Remove an item from the history buffer by value
        """
        new_history = [(value, ts) for value, ts in self._setpoint_history
                       if value != remove_value]
        self._setpoint_history = collections.deque(
            new_history, self._setpoint_history_count)

    def _add_history_item(self, value, *, timestamp=None):
        """
        Add an item to the history buffer
        """
        if value in dict(self._setpoint_history):
            # Push this value to the end of the list as most-recently used
            self._remove_history_item_by_value(value)

        self._setpoint_history.append(
            (value, timestamp or datetime.datetime.now())
        )

    def send_value(self):
        """
        Update channel value while recording setpoint history
        """
        value = self.text().strip()
        retval = super().send_value()
        self._add_history_item(value)
        return retval

    def _create_history_menu(self):
        if not self._setpoint_history:
            return None

        history_menu = QtWidgets.QMenu("&History")
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        history_menu.setFont(font)

        max_len = max(len(value)
                      for value, timestamp in self._setpoint_history)

        # Pad values such that timestamp lines up:
        # (Value)     @ (Timestamp)
        action_format = '{value:<%d} @ {timestamp}' % (max_len + 1)

        for value, timestamp in reversed(self._setpoint_history):
            timestamp = timestamp.strftime('%m/%d %H:%M')
            action = history_menu.addAction(
                action_format.format(value=value, timestamp=timestamp))

            def history_selected(*, value=value):
                self.setText(str(value))

            action.triggered.connect(history_selected)

        return history_menu

    def widget_ctx_menu(self):
        menu = super().widget_ctx_menu()
        if self._setpoint_history_count > 0:
            self._history_menu = self._create_history_menu()
            if self._history_menu is not None:
                menu.addSeparator()
                menu.addMenu(self._history_menu)

        return menu

    def unit_changed(self, new_unit):
        """
        Callback invoked when the Channel has new unit value.
        This callback also triggers an update_format_string call so the
        new unit value is considered if ```showUnits``` is set.

        Parameters
        ----------
        new_unit : str
            The new unit
        """
        if self._unit != new_unit:
            super().unit_changed(new_unit)
            if new_unit.lower() in EXPONENTIAL_UNITS \
                    and self.displayFormat == PyDMLabel.DisplayFormat.Default:
                self.displayFormat = PyDMLabel.DisplayFormat.Exponential


class TyphosLabel(PyDMLabel):
    """
    Reimplementation of PyDMLabel to set some custom defaults
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

    def unit_changed(self, new_unit):
        """
        Callback invoked when the Channel has new unit value.
        This callback also triggers an update_format_string call so the
        new unit value is considered if ```showUnits``` is set.

        Parameters
        ----------
        new_unit : str
            The new unit
        """
        if self._unit != new_unit:
            super().unit_changed(new_unit)
            if new_unit.lower() in EXPONENTIAL_UNITS \
                    and self.displayFormat == PyDMLabel.DisplayFormat.Default:
                self.displayFormat = PyDMLabel.DisplayFormat.Exponential


class TyphosSidebarItem(ptypes.ParameterItem):
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


class HappiChannel(PyDMChannel, QObject):
    """
    PyDMChannel to transport Device Information

    Parameters
    ----------
    tx_slot: callable
        Slot on widget to accept a dictionary of both the device and metadata
        information
    """
    def __init__(self, *, tx_slot, **kwargs):
        super().__init__(**kwargs)
        QObject.__init__(self)
        self._tx_slot = tx_slot
        self._last_md = None

    @Slot(dict)
    def tx_slot(self, value):
        """Transmission Slot"""
        # Do not fire twice for the same device
        if not self._last_md or self._last_md != value['md']:
            self._last_md = value['md']
            self._tx_slot(value)
        else:
            logger.debug("HappiChannel %r received same device. "
                         "Ignoring for now ...", self)


class TyphosDesignerMixin(PyDMWidget):
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
