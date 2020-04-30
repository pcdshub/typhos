import collections
import functools
import logging
import sys
from functools import partial

from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Q_ENUMS, Property

import ophyd
from ophyd import Kind
from ophyd.signal import EpicsSignal, EpicsSignalBase, EpicsSignalRO
from pydm.widgets.display_format import DisplayFormat

from . import display, utils
from .plugins import register_signal
from .utils import (TyphosBase, TyphosLoading, channel_name, clean_attr,
                    clear_layout, is_signal_ro)
from .widgets import (ImageDialogButton, SignalDialogButton, TyphosComboBox,
                      TyphosDesignerMixin, TyphosLabel, TyphosLineEdit,
                      WaveformDialogButton)

logger = logging.getLogger(__name__)


SignalWidgetInfo = collections.namedtuple(
    'SignalWidgetInfo',
    'read_cls read_kwargs write_cls write_kwargs'
)


def widget_type_from_description(signal, desc, read_only=False):
    """
    Determine which widget class should be used for the given signal

    Parameters
    ----------
    signal : ophyd.Signal
        Signal object to determine widget class

    desc : dict
        Previously recorded description from the signal

    read_only: bool, optional
        Should the chosen widget class be read-only?

    Returns
    -------
    widget_class : class
        The class to use for the widget
    kwargs : dict
        Keyword arguments for the class
    """
    if isinstance(signal, EpicsSignalBase):
        # Still re-route EpicsSignal through the ca:// plugin
        pv = (signal._read_pv
              if read_only else signal._write_pv)
        init_channel = channel_name(pv.pvname)
    else:
        # Register signal with plugin
        register_signal(signal)
        init_channel = channel_name(signal.name, protocol='sig')

    kwargs = {
        'init_channel': init_channel,
    }

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
            widget_cls = TyphosLabel
        else:
            if 'enum_strs' in desc:
                # Create a QCombobox if the widget has enum_strs
                widget_cls = TyphosComboBox
            else:
                # Otherwise a LineEdit will suffice
                widget_cls = TyphosLineEdit
    elif dimensions == 1:
        # Waveform
        widget_cls = WaveformDialogButton
    elif dimensions == 2:
        # B/W image
        widget_cls = ImageDialogButton
    else:
        raise ValueError(f"Unable to create widget for widget of "
                         f"shape {len(desc.get('shape'))} from {signal.name}")

    if dtype == 'string' and widget_cls in (TyphosLabel, TyphosLineEdit):
        kwargs['display_format'] = DisplayFormat.String

    return widget_cls, kwargs


def determine_widget_type(signal, read_only=False):
    """
    Determine which widget class should be used for the given signal.

    Parameters
    ----------
    signal : ophyd.Signal
        Signal object to determine widget class

    read_only: bool, optional
        Should the chosen widget class be read-only?

    Returns
    -------
    widget_class : class
        The class to use for the widget
    kwargs : dict
        Keyword arguments for the class
    """
    try:
        desc = signal.describe()[signal.name]
    except Exception:
        logger.error("Unable to connect to %r during widget creation",
                     signal.name)
        desc = {}

    return widget_type_from_description(signal, desc)


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
    widget_cls, kwargs = determine_widget_type(signal, read_only=read_only)
    logger.debug("Creating %s for %s", widget_cls, signal.name)

    widget = widget_cls(**kwargs)
    widget.setObjectName(f'{signal.name}_{widget_cls.__name__}')
    if tooltip is not None:
        widget.setToolTip(tooltip)

    return widget


# Backward-compatibility (TODO deprecate)
signal_widget = create_signal_widget


class _GlobalDescribeCache(QtCore.QObject):
    """
    Cache of ophyd object descriptions

    ``obj.describe()`` is called in a thread from the global QThreadPool, and
    new results are marked by the Signal ``new_description``.

    To access a description, call :meth:`.get`. If available, it will be
    returned immediately.  Otherwise, wait for the ``new_description`` Signal.

    Attributes
    ----------
    connect_thread : :class:`ObjectConnectionMonitorThread`
        The thread which monitors connection status

    cache : dict
        The cache holding descriptions, keyed on ``obj``
    """

    new_description = QtCore.Signal(object, dict)

    def __init__(self):
        super().__init__()
        self.connect_thread = utils.ObjectConnectionMonitorThread(parent=self)
        self.connect_thread.connection_update.connect(self._connection_update)
        self.connect_thread.start()

        self._in_process = set()
        self.cache = {}

    def _describe(self, obj):
        """Retrieve the description of ``obj``."""
        try:
            return obj.describe()[obj.name]
        except Exception:
            logger.error("Unable to connect to %r during widget creation",
                         obj.name)
        return {}

    def _worker_describe(self, obj):
        """
        This is the worker thread method that gets run in the thread pool.

        It calls describe, updates the cache, and emits a signal when done.
        """
        try:
            self.cache[obj] = desc = self._describe(obj)
            self.new_description.emit(obj, desc)
        except Exception as ex:
            logger.exception('Worker describe failed: %s', ex)
        finally:
            self._in_process.remove(obj)

    @QtCore.Slot(object, bool, dict)
    def _connection_update(self, obj, connected, metadata):
        """
        A connection callback from the connection monitor thread.
        """
        if not connected:
            return
        elif self.cache.get(obj) or obj in self._in_process:
            return

        self._in_process.add(obj)
        func = functools.partial(self._worker_describe, obj)
        QtCore.QThreadPool.globalInstance().start(
            utils.ThreadPoolWorker(func)
        )

    def get(self, obj):
        """
        To access a description, call this method. If available, it will be
        returned immediately.  Otherwise, upon connection and successful
        ``describe()`` call, the ``new_description`` Signal will be emitted.

        Parameters
        ----------
        obj : :class:`ophyd.OphydObj`
            The object to get the description of

        Returns
        -------
        desc : dict or None
            If available in the cache, the description will be returned.
        """
        try:
            return self.cache[obj]
        except KeyError:
            # Add the object, waiting for a connection update to determine
            # widget types
            self.connect_thread.add_object(obj)


class _GlobalWidgetTypeCache(QtCore.QObject):
    """
    Cache of ophyd object Typhos widget types

    ``obj.describe()`` is called using :class:`_GlobalDescribeCache` and are
    therefore threaded and run in the background.  New results are marked by
    the Signal ``widgets_determined``.

    To access a set of widget types, call :meth:`.get`. If available, it will
    be returned immediately.  Otherwise, wait for the ``widgets_determined``
    Signal.

    Attributes
    ----------
    describe_cache : :class:`_GlobalDescribeCache`
        The describe cache, used for determining widget types

    cache : dict
        The cache holding widget type information.
        Keyed on ``obj``, the values are :class:`SignalWidgetInfo` tuples.
    """

    widgets_determined = QtCore.Signal(object, SignalWidgetInfo)

    def __init__(self):
        super().__init__()
        self.cache = {}
        self.describe_cache = get_global_describe_cache()
        self.describe_cache.new_description.connect(self._new_description)

    @QtCore.Slot(object, dict)
    def _new_description(self, obj, desc):
        """New description: determine widget types and update the cache."""
        if not desc:
            # Marks an error in retrieving the description
            # TODO: show error widget or some default widget?
            return

        read_cls, read_kwargs = widget_type_from_description(
            obj, desc, read_only=True)

        if is_signal_ro(obj) or issubclass(read_cls, SignalDialogButton):
            write_cls = None
            write_kwargs = {}
        else:
            write_cls, write_kwargs = widget_type_from_description(obj, desc)

        item = SignalWidgetInfo(read_cls, read_kwargs, write_cls,
                                write_kwargs)
        logger.debug('Determined widgets for %s: %s', obj.name, item)
        self.cache[obj] = item
        self.widgets_determined.emit(obj, item)

    def get(self, obj):
        """
        To access widget types, call this method. If available, it will be
        returned immediately.  Otherwise, upon connection and successful
        ``describe()`` call, the ``widgets_determined`` Signal will be emitted.

        Parameters
        ----------
        obj : :class:`ophyd.OphydObj`
            The object to get the widget types

        Returns
        -------
        desc : :class:`SignalWidgetInfo` or None
            If available in the cache, the information will be returned.
        """
        try:
            return self.cache[obj]
        except KeyError:
            # Add the signal, waiting for a connection update to determine
            # widget types
            desc = self.describe_cache.get(obj)
            if desc is not None:
                # In certain scenarios (such as testing) this might happen
                self._new_description(obj, desc)


_GLOBAL_WIDGET_TYPE_CACHE = None
_GLOBAL_DESCRIBE_CACHE = None


def get_global_describe_cache():
    """Get the _GlobalDescribeCache singleton."""
    global _GLOBAL_DESCRIBE_CACHE
    if _GLOBAL_DESCRIBE_CACHE is None:
        _GLOBAL_DESCRIBE_CACHE = _GlobalDescribeCache()
    return _GLOBAL_DESCRIBE_CACHE


def get_global_widget_type_cache():
    """Get the _GlobalWidgetTypeCache singleton."""
    global _GLOBAL_WIDGET_TYPE_CACHE
    if _GLOBAL_WIDGET_TYPE_CACHE is None:
        _GLOBAL_WIDGET_TYPE_CACHE = _GlobalWidgetTypeCache()
    return _GLOBAL_WIDGET_TYPE_CACHE


class SignalPanel(QtWidgets.QGridLayout):
    """
    Base panel display for EPICS signals

    Parameters
    ----------
    signals : OrderedDict, optional
        Signals to include in the panel
        Parent of panel
    """
    NUM_COLS = 3
    COL_LABEL = 0
    COL_READBACK = 1
    COL_SETPOINT = 2

    def __init__(self, signals=None):
        super().__init__()

        self.signal_name_to_info = {}
        self._row_count = 0
        self._devices = []

        # Make sure setpoint/readback share space evenly
        self.setColumnStretch(self.COL_READBACK, 1)
        self.setColumnStretch(self.COL_SETPOINT, 1)

        get_global_widget_type_cache().widgets_determined.connect(
            self._got_signal_widget_info)

        if signals:
            for name, sig in signals.items():
                self.add_signal(sig, name)

    @property
    def signals(self):
        """Return all instantiated signals, omitting components."""
        return {
            name: info['signal']
            for name, info in self.signal_name_to_info.items()
            if info['signal'] is not None
        }

    @property
    def visible_signals(self):
        """Return all visible signals, omitting components."""
        return {
            name: info['signal']
            for name, info in self.signal_name_to_info.items()
            if info['signal'] is not None and info['visible']
        }

    @property
    def row_count(self):
        """
        The number of filled-in rows
        """
        return self._row_count

    @property
    def active_row_count(self):
        """
        The number of visible filled-in rows
        """
        count = 0
        for row in range(self._row_count):
            # Skip col 0 as it is the title label
            active = False
            for col in range(1, self.NUM_COLS):
                item = self.itemAtPosition(row, col)
                if item and item.widget() and item.widget().isVisible():
                    active = True
                    break
            count += 1 if active else 0
        return count

    def _dump_layout(self, file=sys.stdout):
        """
        Utility to dump the current layout
        """
        return utils.dump_grid_layout(
            self, rows=self._row_count, cols=self.NUM_COLS, file=file)

    def _got_signal_widget_info(self, obj, info):
        try:
            sig_info = self.signal_name_to_info[obj.name]
        except KeyError:
            return

        sig_info['widget_info'] = info
        row = sig_info['row']

        read = info.read_cls(**info.read_kwargs)
        write = info.write_cls(**info.write_kwargs) if info.write_cls else None

        # Remove the 'loading...' animation if it's there
        item = self.itemAtPosition(row, self.COL_SETPOINT)
        if item:
            val_widget = item.widget()
            if isinstance(val_widget, TyphosLoading):
                self.removeItem(item)
                val_widget.deleteLater()

        # And add the new widgets to the layout:
        widgets = [None, read]
        if write is not None:
            widgets += [write]

        self._update_row(row, widgets)

        visible = sig_info['visible']
        for widget in widgets[1:]:
            widget.setVisible(visible)

    def add_signal(self, signal, name=None, *, tooltip=None):
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
        name = name or signal.name
        if signal.name in self.signal_name_to_info:
            return

        logger.debug("Adding signal %s (%s)", signal.name, name)

        label = QtWidgets.QLabel()
        label.setText(name)
        label.setObjectName(name + '_row_label')
        if tooltip is not None:
            label.setToolTip(tooltip)

        row = self.add_row(label, None)  # TyphosLoading())
        self.signal_name_to_info[signal.name] = dict(
            row=row,
            signal=signal,
            component=None,
            widget_info=None,
            label=label,
            create_signal=None,
            visible=True,
        )

        self._connect_signal(signal)
        return row

    def _connect_signal(self, signal):
        """
        Instantiate widgets for the given signal using `_GlobalWidgetTypeCache`
        """
        monitor = get_global_widget_type_cache()
        item = monitor.get(signal)
        if item is not None:
            self._got_signal_widget_info(signal, item)
        # else: - this will happen during a callback

    def _add_component(self, device, dotted_name, component):
        """Add a component which could be instantiated"""
        if dotted_name in self.signal_name_to_info:
            return

        logger.debug("Adding component %s", dotted_name)

        label = QtWidgets.QLabel()
        label.setText(dotted_name)
        label.setObjectName(dotted_name + '_row_label')
        label.setToolTip(component.doc or '')

        row = self.add_row(label, None)  # TyphosLoading())
        self.signal_name_to_info[dotted_name] = dict(
            row=row,
            signal=None,
            widget_info=None,
            label=label,
            component=component,
            create_signal=functools.partial(getattr, device, dotted_name),
            visible=False,
        )

        return row

    def add_row(self, *widgets, **kwargs):
        """
        Add ``widgets`` to the next row

        If fewer than ``NUM_COLS`` widgets are given, the last widget will be
        adjusted automatically to span the remaining columns.

        Parameters
        ----------
        *widgets
            List of :class:`QtWidgets.QWidget`

        Returns
        -------
        row : int
            The row number
        """
        row = self._row_count
        self._row_count += 1

        if widgets:
            self._update_row(row, widgets, **kwargs)

        return row

    def _update_row(self, row, widgets, **kwargs):
        """
        Update ``row`` to contain ``widgets``

        If fewer widgets than ``NUM_COLS`` are given, the last widget will be
        adjusted automatically to span the remaining columns.

        Parameters
        ----------
        row : int
            The row number
        widgets : list of :class:`QtWidgets.QWidget`
            If ``None`` is found, the cell will be skipped.
        **kwargs
            Passed into ``addWidget``
        """
        for col, item in enumerate(widgets[:-1]):
            if item is not None:
                self.addWidget(item, row, col, **kwargs)

        last_widget = widgets[-1]
        if last_widget is not None:
            # Column-span the last widget over the remaining columns:
            last_column = len(widgets) - 1
            colspan = self.NUM_COLS - last_column
            self.addWidget(last_widget, row, last_column, 1, colspan, **kwargs)

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

    @staticmethod
    def _apply_name_filter(filter_by, *items):
        """
        Apply the name filter
        """
        if not filter_by:
            return True

        return any(filter_by in item for item in items)

    def _should_show(self, kind, name, *, kinds, name_filter):
        """
        Based on the current filter settings, should ``signal`` be shown?
        """
        if kind not in kinds:
            return False
        return self._apply_name_filter(name_filter, name)

    def _set_visible(self, signal_name, visible):
        info = self.signal_name_to_info[signal_name]
        info['visible'] = bool(visible)
        row = info['row']
        for col in range(self.NUM_COLS):
            item = self.itemAtPosition(row, col)
            if item:
                widget = item.widget()
                if widget:
                    widget.setVisible(visible)

        if visible and info['signal'] is None:
            create_func = info['create_signal']
            info['signal'] = signal = create_func()
            logger.debug('Instantiating a not-yet-created signal from a '
                         'component: %s', signal.name)
            if signal.name != signal_name:
                # This is, for better or worse, possible; does not support the
                # case of changing the name after __init__
                self.signal_name_to_info[signal.name] = info
                del self.signal_name_to_info[signal_name]
            self._connect_signal(signal)

    def filter_signals(self, kinds, name_filter=None):
        """
        Filter signals based on the given kinds

        Parameters
        ----------
        kinds : list of :class:`ophyd.Kind`
            If given
        name_filter : str, optional
            Additionally filter signals by name
        """
        for name, info in self.signal_name_to_info.items():
            item = info['signal'] or info['component']
            visible = self._should_show(item.kind, name,
                                        kinds=kinds, name_filter=name_filter)
            self._set_visible(name, visible)

        self.update()
        # self._dump_layout()

    @property
    def _filter_settings(self):
        return self.parent().filter_settings

    def add_device(self, device):
        self.clear()
        self._devices.append(device)

        sorter = _get_component_sorter(self.parent().sortBy)
        non_devices = [
            walk
            for walk in sorted(device.walk_components(), key=sorter)
            if not issubclass(walk.item.cls, ophyd.Device)
        ]

        for walk in non_devices:
            self._maybe_add_signal(device, walk.item.attr, walk.dotted_name,
                                   walk.item)

        self.setSizeConstraint(self.SetMinimumSize)

    def _maybe_add_signal(self, device, attr, dotted_name, component):
        """
        Based on the current filter settings, add either the signal or a
        component stub.

        If the component does not match the current filter settings, a
        stub will be added that can be filled in later should the filter
        settings change.

        If the component matches the current filter settings, it will be
        instantiated and widgets will be added when the signal is connected.

        Parameters
        ----------
        device : ophyd.Device
            The device owner
        attr : str
            The signal's attribute name
        dotted_name : str
            The signal's dotted name
        component : ophyd.Component
            The component class used to generate the instance
        """
        if component.lazy:
            kind = component.kind
        else:
            try:
                signal = getattr(device, dotted_name)
            except Exception as ex:
                logger.warning('Failed to get signal %r from device %s: %s',
                               dotted_name, device.name, ex, exc_info=True)
                return

            kind = signal.kind

        if self._should_show(kind, dotted_name, **self._filter_settings):
            try:
                signal = getattr(device, dotted_name)
            except Exception as ex:
                logger.warning('Failed to get signal %r from device %s: %s',
                               dotted_name, device.name, ex, exc_info=True)
                return

            return self.add_signal(signal, name=attr, tooltip=component.doc)

        return self._add_component(device, attr, component)

    def clear(self):
        """Clear the SignalPanel"""
        logger.debug("Clearing layout %r ...", self)
        clear_layout(self)
        self._devices.clear()
        self.signal_name_to_info.clear()


class SignalOrder:
    """Option to sort signals"""
    byKind = 0
    byName = 1


DEFAULT_KIND_ORDER = (Kind.hinted, Kind.normal, Kind.config, Kind.omitted)


def _get_component_sorter(signal_order, *, kind_order=None):
    kind_order = kind_order or DEFAULT_KIND_ORDER

    def kind_sorter(walk):
        """Sort by kind."""
        return (kind_order.index(walk.item.kind), walk.dotted_name)

    def name_sorter(walk):
        """Sort by name."""
        return walk.dotted_name

    return {SignalOrder.byKind: kind_sorter,
            SignalOrder.byName: name_sorter
            }.get(signal_order, name_sorter)


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
        self._name_filter = ''
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

    @property
    def filter_settings(self):
        return dict(
            name_filter=self.nameFilter,
            kinds=self.show_kinds,
        )

    def _update_panel(self):
        self._panel_layout.filter_signals(**self.filter_settings)
        self.updated.emit()

    @property
    def show_kinds(self):
        return [kind for kind in Kind if self._kinds[kind.name]]

    # Kind Configuration pyqtProperty
    showHints = Property(bool,
                         partial(_get_kind, kind='hinted'),
                         partial(_set_kind, kind='hinted'),
                         doc='Show ophyd.Kind.hinted signals')
    showNormal = Property(bool,
                          partial(_get_kind, kind='normal'),
                          partial(_set_kind, kind='normal'),
                          doc='Show ophyd.Kind.normal signals')
    showConfig = Property(bool,
                          partial(_get_kind, kind='config'),
                          partial(_set_kind, kind='config'),
                          doc='Show ophyd.Kind.config signals')
    showOmitted = Property(bool,
                           partial(_get_kind, kind='omitted'),
                           partial(_set_kind, kind='omitted'),
                           doc='Show ophyd.Kind.omitted signals')

    @Property(str, doc='Filter signals by name')
    def nameFilter(self):
        return self._name_filter

    @nameFilter.setter
    def nameFilter(self, name_filter):
        if name_filter != self._name_filter:
            self._name_filter = name_filter.strip()
            self._update_panel()

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
        self.devices.clear()
        super().add_device(device)
        # Configure the layout for the new device
        self._panel_layout.add_device(device)
        self._update_panel()

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
        # TODO: note that this does not call super
        # super().add_device(device)
        self._devices.append(device)

        logger.debug('%s signals from device: %s', self.__class__.__name__,
                     device.name)

        for attr, component in utils._get_top_level_components(type(device)):
            dotted_name = f'{device.name}.{attr}'
            if issubclass(component.cls, ophyd.Device):
                sub_device = getattr(device, attr)
                self.add_sub_device(sub_device, name=dotted_name)
            else:
                self._maybe_add_signal(device, attr, attr, component)


class TyphosCompositeSignalPanel(TyphosSignalPanel):
    _panel_class = CompositeSignalPanel
