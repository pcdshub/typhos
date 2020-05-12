import functools
import logging
from functools import partial

from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Q_ENUMS, Property

import ophyd
from ophyd import Kind
from ophyd.signal import EpicsSignal, EpicsSignalRO

from . import display, utils
from .cache import get_global_widget_type_cache
from .utils import TyphosBase
from .widgets import SignalWidgetInfo, TyphosDesignerMixin

logger = logging.getLogger(__name__)


class SignalOrder:
    """Option to sort signals"""
    byKind = 0
    byName = 1


DEFAULT_KIND_ORDER = (Kind.hinted, Kind.normal, Kind.config, Kind.omitted)


def _get_component_sorter(signal_order, *, kind_order=None):
    """
    Get a sorting function for :class:`ophyd.device.ComponentWalk` entries.

    Parameters
    ----------
    signal_order : SignalOrder
        Order for signals
    kind_order : list, optional
        Order for Kinds, defaulting to ``DEFAULT_KIND_ORDER``.
    """
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


class SignalPanelRowLabel(QtWidgets.QLabel):
    """
    A row label for a signal panel.

    This subclass does not contain any special functionality currently, but
    remains a special class for ease of stylesheet configuration and label
    disambiguation.
    """


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

    loading_complete = QtCore.Signal(list)

    def __init__(self, signals=None):
        super().__init__()

        self.signal_name_to_info = {}
        self._row_count = 0
        self._devices = []

        # Make sure setpoint/readback share space evenly
        self.setColumnStretch(self.COL_READBACK, 1)
        self.setColumnStretch(self.COL_SETPOINT, 1)

        get_global_widget_type_cache().widgets_determined.connect(
            self._got_signal_widget_info, QtCore.Qt.QueuedConnection)

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
    def visible_elements(self):
        """Return all visible signals and components"""
        return self.visible_signals

    @property
    def row_count(self):
        """
        The number of filled-in rows
        """
        return self._row_count

    @QtCore.Slot(object, SignalWidgetInfo)
    def _got_signal_widget_info(self, obj, info):
        """Received information on how to make widgets for ``obj``"""
        try:
            sig_info = self.signal_name_to_info[obj.name]
        except KeyError:
            return

        if sig_info['widget_info'] is not None:
            # Only add widgets on the first callback
            # TODO: debug why multiple calls happen
            return

        sig_info['widget_info'] = info
        row = sig_info['row']

        read = info.read_cls(**info.read_kwargs)
        write = info.write_cls(**info.write_kwargs) if info.write_cls else None

        # Remove the 'loading...' animation if it's there
        item = self.itemAtPosition(row, self.COL_SETPOINT)
        if item:
            val_widget = item.widget()
            if isinstance(val_widget, utils.TyphosLoading):
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

        if all(sig_info['widget_info'] is not None
               for name, sig_info in self.signal_name_to_info.items()):
            self.loading_complete.emit(list(self.signal_name_to_info))

    def _create_row_label(self, attr, dotted_name, tooltip):
        """Create a row label (i.e., the one in column 0)."""
        label_text = self.label_text_from_attribute(attr, dotted_name)
        label = SignalPanelRowLabel(label_text)
        label.setObjectName(dotted_name + '_row_label')
        if tooltip is not None:
            label.setToolTip(tooltip)
        return label

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

        label = self._create_row_label(name, name, tooltip)
        row = self.add_row(label, utils.TyphosLoading())
        self.signal_name_to_info[signal.name] = dict(
            row=row,
            signal=signal,
            component=None,
            widget_info=None,
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

    def _add_component(self, device, attr, dotted_name, component):
        """Add a component which could be instantiated"""
        if dotted_name in self.signal_name_to_info:
            return

        logger.debug("Adding component %s", dotted_name)

        label = self._create_row_label(
            attr, dotted_name, tooltip=component.doc or '')
        row = self.add_row(label, None)  # utils.TyphosLoading())
        self.signal_name_to_info[dotted_name] = dict(
            row=row,
            signal=None,
            widget_info=None,
            component=component,
            create_signal=functools.partial(getattr, device, dotted_name),
            visible=False,
        )

        return row

    def label_text_from_attribute(self, attr, dotted_name):
        """Get label text for a given attribute."""
        # For a basic signal panel, use the full dotted name.
        return dotted_name

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
        read_pv : str
            The readback PV name
        name : str
            Name of signal to display
        write_pv : str, optional
            The setpoint PV name

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
        """Change the visibility of ``signal_name`` to ``visible``."""
        info = self.signal_name_to_info[signal_name]
        info['visible'] = bool(visible)
        row = info['row']
        for col in range(self.NUM_COLS):
            item = self.itemAtPosition(row, col)
            if item:
                widget = item.widget()
                if widget:
                    widget.setVisible(visible)

        if not visible or info['signal'] is not None:
            return

        # Create the signal if we're displaying it for the first time.
        create_func = info['create_signal']
        if create_func is None:
            # A signal we shouldn't try to create again
            return

        try:
            info['signal'] = signal = create_func()
        except Exception as ex:
            logger.exception('Failed to create signal %s: %s', signal_name, ex)
            # Stop it from another attempt
            info['create_signal'] = None
            return

        logger.debug('Instantiating a not-yet-created signal from a '
                     'component: %s', signal.name)
        if signal.name != signal_name:
            # This is, for better or worse, possible; does not support the case
            # of changing the name after __init__
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
        # utils.dump_grid_layout(self)

    @property
    def _filter_settings(self):
        """Current filter settings from the owner widget."""
        return self.parent().filter_settings

    def add_device(self, device):
        """Typhos hook for adding a new device."""
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

        return self._add_component(device, attr, dotted_name, component)

    def clear(self):
        """Clear the SignalPanel"""
        logger.debug("Clearing layout %r ...", self)
        utils.clear_layout(self)
        self._devices.clear()
        self.signal_name_to_info.clear()


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
        """Property getter for show[kind]."""
        return self._kinds[kind]

    def _set_kind(self, value, kind):
        """Property setter for show[kind] = value."""
        # If we have a new value store it
        if value != self._kinds[kind]:
            # Store it internally
            self._kinds[kind] = value
            # Remodify the layout for the new Kind
            self._update_panel()

    @property
    def filter_settings(self):
        """Get the filter settings dictionary."""
        return dict(
            name_filter=self.nameFilter,
            kinds=self.show_kinds,
        )

    def _update_panel(self):
        """Apply filters and emit the update signal."""
        self._panel_layout.filter_signals(**self.filter_settings)
        self.updated.emit()

    @property
    def show_kinds(self):
        """A list of the :class:`ophyd.Kind` that should be shown."""
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
        """Typhos hook for adding a new device."""
        self.devices.clear()
        super().add_device(device)
        # Configure the layout for the new device
        self._panel_layout.add_device(device)
        self._update_panel()

    def set_device_display(self, display):
        """Typhos hook for when the TyphosDeviceDisplay is associated."""
        self.display = display

    def generate_context_menu(self):
        """Generate a context menu for this TyphosSignalPanel."""
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

    def label_text_from_attribute(self, attr, dotted_name):
        """Get label text for a given attribute."""
        # For a hierarchical signal panel, use only the attribute name.
        return attr

    def add_sub_device(self, device, name):
        """
        Add a sub-device to the next row.

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
                                                composite_heuristics=True,
                                                nested=True)
        self._containers[name] = container
        self.add_row(container)
        container.add_device(device)

    def add_device(self, device):
        """Typhos hook for adding a new device."""
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

    @property
    def visible_elements(self):
        """Return all visible signals and components"""
        sigs = self.visible_signals
        containers = {
            name: cont
            for name, cont in self._containers.items() if cont.isVisible()
        }
        sigs.update(containers)
        return sigs


class TyphosCompositeSignalPanel(TyphosSignalPanel):
    _panel_class = CompositeSignalPanel
