import logging
import sys
from functools import partial

from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Q_ENUMS, Property, QSize, QTimer

import ophyd
from ophyd import Kind
from ophyd.signal import EpicsSignal, EpicsSignalBase, EpicsSignalRO, Signal
from pydm.widgets.display_format import DisplayFormat

from . import display, utils
from .plugins import register_signal
from .utils import (TyphosBase, TyphosLoading, channel_name, clean_attr,
                    clear_layout, is_signal_ro)
from .widgets import (ImageDialogButton, SignalDialogButton, TyphosComboBox,
                      TyphosDesignerMixin, TyphosLabel, TyphosLineEdit,
                      WaveformDialogButton)

logger = logging.getLogger(__name__)


def create_signal_widget(signal, read_only=False, tooltip=None):
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
    dtype = desc.get('dtype', '')
    try:
        dimensions = len(shape)
    except TypeError:
        dimensions = 0
    if dimensions == 0:
        # Check for enum_strs, if so create a QCombobox
        if read_only:
            widget = TyphosLabel
            name = signal.name + '_label'
        else:
            # Create a QCombobox if the widget has enum_strs
            if 'enum_strs' in desc:
                widget = TyphosComboBox
                name = signal.name + '_combo'
            # Otherwise a LineEdit will suffice
            else:
                widget = TyphosLineEdit
                name = signal.name + '_edit'
    # Waveform
    elif len(desc.get('shape')) == 1:
        widget = WaveformDialogButton
        name = signal.name + '_waveform_button'
    # B/W image
    elif len(desc.get('shape')) == 2:
        widget = ImageDialogButton
        name = signal.name + '_image_button'
    else:
        raise ValueError(f"Unable to create widget for widget of "
                         f"shape {len(desc.get('shape'))} from {signal.name}")

    logger.debug("Creating %s for %s", widget.__name__, signal.name)
    widget_instance = widget(init_channel=chan)
    widget_instance.setObjectName(name)

    if tooltip is not None:
        widget_instance.setToolTip(tooltip)

    if dtype == 'string' and widget in (TyphosLabel, TyphosLineEdit):
        widget_instance.displayFormat = DisplayFormat.String
    return widget_instance


# Backward-compatibility (TODO deprecate)
signal_widget = create_signal_widget


class SignalPanel(QtWidgets.QGridLayout):
    """
    Base panel display for EPICS signals

    Parameters
    ----------
    signals : OrderedDict, optional
        Signals to include in the panel
        Parent of panel
    """
    _NUM_COLS = 2

    def __init__(self, signals=None):
        super().__init__()

        self.signals = {}
        self._row_count = 0
        self._devices = []

        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

    @property
    def row_count(self):
        """
        The number of filled-in rows
        """
        return self._row_count

    def _dump_layout(self, file=sys.stdout):
        """
        Utility to dump the current layout
        """
        print('-' * (64 * self._NUM_COLS), file=file)
        found_widgets = set()
        for row in range(self._row_count):
            print('|', end='', file=file)
            for col in range(self._NUM_COLS):
                item = self.itemAtPosition(row, col)
                if item:
                    entry = item.widget() or item.layout()
                    found_widgets.add(entry)
                    if isinstance(entry, QtWidgets.QLabel):
                        entry = f'<QLabel {entry.text()!r}>'
                else:
                    entry = ''

                print(' {:<60s}'.format(str(entry)), end=' |', file=file)
            print(file=file)
        print('-' * (64 * self._NUM_COLS), file=file)

    def _add_devices_cb(self, name, row, signal):
        # Create the read-only signal
        read = create_signal_widget(signal, read_only=True)
        # Create the write signal
        if is_signal_ro(signal) or isinstance(read, SignalDialogButton):
            write = None
        else:
            write = create_signal_widget(signal)

        # Add readback
        val_widget = self.itemAtPosition(row, 1).widget()
        val_layout = val_widget.layout()
        loading_widget = val_layout.itemAt(0).widget()
        if isinstance(loading_widget, TyphosLoading):
            val_layout.removeWidget(loading_widget)
            loading_widget.deleteLater()
        val_layout.addWidget(read)
        # Add our write_pv if available
        if write is not None:
            # Add our control widget to layout
            val_layout.addWidget(write)
            # Make sure they share space evenly
            val_layout.setStretch(0, 1)
            val_layout.setStretch(1, 1)

        self.signals[name].update(read=read, write=write)

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
        row : int
            Row number that the signal information was added to in the
            `SignalPanel.layout()``
        """
        def _device_meta_cb(*args, **kwargs):
            connected = kwargs.get('connected', False)
            if connected:
                cid = None
                for id, func in signal._callbacks[Signal.SUB_META].items():
                    if func.__name__ == '_device_meta_cb':
                        cid = id
                        break

                if cid is not None:
                    signal.unsubscribe(cid)

                # Maybe a HACK to get the _add_devices_cb to happen at the
                # main thread.
                method = partial(self._add_devices_cb, name, row, signal)
                QTimer.singleShot(0, method)

        logger.debug("Adding signal %s", name)

        # Add to the layout

        # Create label
        label = QtWidgets.QLabel()
        label.setText(name)
        if tooltip is not None:
            label.setToolTip(tooltip)

        val_display = QtWidgets.QWidget()
        val_layout = QtWidgets.QHBoxLayout()
        val_layout.setContentsMargins(0, 0, 0, 0)
        val_display.setLayout(val_layout)
        val_layout.addWidget(TyphosLoading())
        row = self.add_row(label, val_display)

        # Store signal
        self.signals[name] = dict(read=None, write=None, row=row,
                                  signal=signal)

        if signal.connected:
            self._add_devices_cb(name, row, signal)
        else:
            signal.subscribe(_device_meta_cb, Signal.SUB_META, run=True)

        return row

    def add_row(self, *widgets, **kwargs):
        """
        Add ``widgets`` to the next row

        If only one widget is given, it will be adjusted automatically to span
        all columns.

        Parameters
        ----------
        *widgets
            List of :class:`QtWidgets.QWidget` or :class:`QtWidgets.QLayout`.

        Returns
        -------
        row : int
            The row number
        """
        row = self._row_count
        self._row_count += 1

        if len(widgets) == 1:
            item, = widgets
            self.addWidget(item, row, 0, 1, self._NUM_COLS, **kwargs)
        else:
            for col, item in enumerate(widgets):
                self.addWidget(item, row, col, **kwargs)

        return row

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
        row : int
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

    def filter_signals(self, kinds, order):
        """
        Filter signals based on the given kinds

        Parameters
        ----------
        kinds : list of :class:`ophyd.Kind`
            If given
        order : :class:`SignalOrder`
            Order by kind, or by name, for example

        Note
        ----
        :class:`SignalPanel` recreates all widgets when this is called.
        """
        self.clear()
        signals = []

        for device in self._devices:
            for kind in kinds:
                for label, signal, cpt in _device_signals_by_kind(
                        device, kind):
                    # Check twice for Kind as signal might have multiple kinds

                    # TODO: I think this is incorrect; as a 'hinted and normal'
                    # signal will not show up if showHints=False and
                    # showNormal=True
                    if signal.kind in kinds:
                        signals.append((label, signal, cpt))

        sorter = _get_signal_sorter(order)
        for (label, signal, cpt) in sorted(set(signals), key=sorter):
            self.add_signal(signal, label, tooltip=cpt.doc)

    def add_device(self, device):
        self._devices.append(device)

    def clear(self):
        """Clear the SignalPanel"""
        logger.debug("Clearing layout %r ...", self)
        clear_layout(self)
        self.signals.clear()


class SignalOrder:
    """Option to sort signals"""
    byKind = 0
    byName = 1


DEFAULT_KIND_ORDER = (Kind.hinted, Kind.normal, Kind.config, Kind.omitted)


def _get_signal_sorter(signal_order, *, kind_order=None):
    kind_order = kind_order or DEFAULT_KIND_ORDER

    # Pick our sorting function
    if signal_order == SignalOrder.byKind:
        # Sort by kind
        def sorter(x):
            return (kind_order.index(x[1].kind), x[0])

    elif signal_order == SignalOrder.byName:
        # Sort by name
        def sorter(x):
            return x[0]
    else:
        logger.exception("Unknown sorting type %r", kind_order)
        return []

    return sorter


def _device_signals_by_kind(device, kind):
    """
    Get signals from a device by kind

    Parameters
    ----------
    device : ophyd.Device
        The device
    kind : ophyd.Kind
        The kind with which to filter

    Yields
    ------
    name : str
        Cleaned attribute name
    signal : ophyd.OphydObj
        The signal itself
    component : ophyd.Component
        The component from which the signal was created
    """
    try:
        for attr, item in utils.grab_kind(device, kind.name).items():
            yield clean_attr(attr), item.signal, item.component
    except Exception:
        logger.exception("Unable to add %s signals from %r", kind.name, device)


class TyphosSignalPanel(TyphosBase, TyphosDesignerMixin, SignalOrder):
    """
    Panel of Signals for Device
    """
    Q_ENUMS(SignalOrder)  # Necessary for display in Designer
    SignalOrder = SignalOrder  # For convenience
    # From top of page to bottom
    kind_order = (Kind.hinted, Kind.normal,
                  Kind.config, Kind.omitted)
    _panel_class = SignalPanel
    updated = QtCore.Signal()

    _kind_to_property = {
        'hinted': 'showHints',
        'normal': 'showNormal',
        'config': 'showConfig',
        'omitted': 'showOmitted',
    }

    def __init__(self, parent=None, init_channel=None):
        super().__init__(parent=parent)
        # Create a SignalPanel layout to be modified later
        self._panel_layout = self._panel_class()
        self.setLayout(self._panel_layout)
        # Add default Kind values
        self._kinds = dict.fromkeys([kind.name for kind in Kind], True)
        self._signal_order = SignalOrder.byKind

        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu

    def _get_kind(self, kind):
        return self._kinds[kind]

    def _set_kind(self, value, kind):
        # If we have a new value store it
        if value != self._kinds[kind]:
            # Store it internally
            self._kinds[kind] = value
            # Remodify the layout for the new Kind
            self._update_panel()

    def _update_panel(self):
        self._panel_layout.filter_signals(
            kinds=self.show_kinds,
            order=self._signal_order,
        )
        self.updated.emit()

    @property
    def show_kinds(self):
        return [kind for kind in Kind if self._kinds[kind.name]]

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
            self._update_panel()

    def add_device(self, device):
        """Add a device to the widget"""
        # Only allow a single device
        self.devices.clear()
        # Add the new device
        super().add_device(device)
        # Configure the layout for the new device
        self._panel_layout.add_device(device)
        self._update_panel()

    def sizeHint(self):
        """Default SizeHint"""
        return QSize(240, 140)

    def set_device_display(self, display):
        self.display = display

    def generate_context_menu(self):
        menu = QtWidgets.QMenu(parent=self)
        for kind, property_name in self._kind_to_property.items():
            def selected(new_value, *, name=property_name):
                setattr(self, name, new_value)

            action = menu.addAction('Show &' + kind)
            action.setCheckable(True)
            action.setChecked(getattr(self, property_name))
            action.triggered.connect(selected)
        return menu

    def open_context_menu(self, ev):
        """
        Handler for when the Default Context Menu is requested.

        Parameters
        ----------
        ev : QEvent
        """
        menu = self.generate_context_menu()
        menu.exec_(self.mapToGlobal(ev.pos()))


class CompositeSignalPanel(SignalPanel):
    def __init__(self):
        super().__init__(signals=None)
        self._containers = {}

    def filter_signals(self, kinds, order):
        """
        Filter signals based on the given kinds

        Parameters
        ----------
        kinds : list of :class:`ophyd.Kind`
            If given
        order : :class:`SignalOrder`
            Order by kind, or by name, for example

        Note
        ----
        :class:`CompositeSignalPanel` merely toggles visibility and does not
        destroy nor recreate widgets when this is called.
        """
        for name, info in self.signals.items():
            signal = info['signal']
            row = info['row']
            visible = signal.kind in kinds
            for col in range(self._NUM_COLS):
                item = self.itemAtPosition(row, col)
                if item:
                    widget = item.widget()
                    if widget:
                        widget.setVisible(visible)

        self.update()
        # self._dump_layout()

    def add_sub_device(self, device, name):
        """
        Add a sub-device to the next row

        Parameters
        ----------
        device : ophyd.Device
            The device to add
        name : str
            The name/label to go with the device
        """
        logger.debug('%s adding sub-device: %s (%s)', self.__class__.__name__,
                     device.name, device.__class__.__name__)
        container = display.TyphosDeviceDisplay(name=name, scrollable=False,
                                                composite_heuristics=True)
        self._containers[name] = container
        self.add_row(container)
        container.add_device(device)

    def add_device(self, device):
        """
        Hook for typhos to add a device
        """
        super().add_device(device)

        logger.debug('%s signals from device: %s', self.__class__.__name__,
                     device.name)
        for attr, component in utils._get_top_level_components(type(device)):
            dotted_name = f'{device.name}.{attr}'
            obj = getattr(device, attr)
            if issubclass(component.cls, ophyd.Device):
                self.add_sub_device(obj, name=dotted_name)
            else:
                self.add_signal(obj, name=dotted_name)


class TyphosCompositeSignalPanel(TyphosSignalPanel):
    _panel_class = CompositeSignalPanel
