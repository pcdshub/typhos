"""
Module to define alarm summary frameworks and widgets.
"""
from functools import partial

from ophyd.device import Kind
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.drawing import PyDMDrawing, PyDMDrawingCircle
from qtpy import QtCore

from .utils import channel_from_signal, get_all_signals_from_device, TyphosBase


class KindLevel:
    hinted = 0
    normal = 1
    config = 2
    omitted = 3


class AlarmLevel:
    no_alarm = 0
    minor = 1
    major = 2
    invalid = 3
    disconnected = 4


class TyphosAlarmBase(TyphosBase):
    # Qt macros for enum handling
    QtCore.Q_ENUMS(KindLevel)
    QtCore.Q_ENUMS(AlarmLevel)

    # Constants
    pydm_shape = None

    def __init__(self, *args, **kwargs):
        self._kind_level = KindLevel.hinted
        self.addr_connected = {}
        self.addr_severity = {}
        self.addr_channels = {}
        self.device_channels = {}
        self.alarm_summary = AlarmLevel.disconnected

        super().__init__(*args, **kwargs)

        self.alarm_changed.connect(self.update_alarm_color)
        self.alarm_changed.emit(self.alarm_summary)

    # Settings handling
    @QtCore.Property(KindLevel)
    def kindLevel(self):
        """
        Determines which signals to include in the alarm summary.

        If this is "hinted", only include hinted signals.
        If this is "normal", include normal and hinted signals.
        If this is "config", include everything except for omitted signals
        If this is "omitted", include all signals
        """
        return self._kind_level

    @kindLevel.setter
    def kindLevel(self, kind_level):
        self._kind_level = kind_level
        self.update_alarm_config()

    # Other properties
    @property
    def channels(self):
        """
        Let pydm know about our pydm channels
        """
        ch = []
        for lst in self.device_channels.values():
            ch.extend(lst)
        return ch

    # Signals
    alarm_changed = QtCore.Signal(AlarmLevel)

    # Slots
    def update_alarm_color(self, alarm):
        for cls in self.__class__.mro():
            if issubclass(cls, PyDMDrawing):
                style = indicator_stylesheet(cls.__name__, alarm=alarm)
                self.setStyleSheet(style)
                break

    # Methods
    def add_device(self, device):
        super().add_device(device)
        self.setup_alarm_config(device)

    def clear_all_alarm_configs(self):
        channels = self.addr_channels.values()
        for ch in channels:
            ch.disconnect()
        self.addr_channels = {}
        self.addr_connected = {}
        self.addr_severity = {}
        self.device_channels = {}


    def setup_alarm_config(self, device):
        sigs = get_all_signals_from_device(
            device,
            filter_by=kind_filters[self._kind_level]
            )
        channel_addrs = [channel_from_signal(sig) for sig in sigs]
        channels = [
            PyDMChannel(
                address=addr,
                connection_slot=partial(self.update_connection, addr=addr)
                severity_slot=partial(self.update_severity, addr=addr)
                )
            for addr in channel_addrs]

        self.device_channels[device.name] = channels
        for ch in channels:
            self.addr_channels[ch.address] = ch
            self.addr_connected[ch.address] = False
            self.addr_severity[ch.address] = AlarmLevel.invalid
            ch.connect()


    def update_alarm_config(self):
        self.clear_all_alarm_configs()
        for dev in self.devices:
            self.setup_alarms(device)


    def update_connection(self, connected, addr):
        self.addr_connected[addr] = connected
        self.update_current_alarm()


    def update_severity(self, severity, addr):
        self.addr_severity[addr] = severity
        self.update_current_alarm()


    def update_current_alarm(self):
        if not all(self.addr_connected.values()):
            new_alarm = AlarmLevel.disconnected
        else:
            new_alarm = max(self.addr_severity.values())
        if new_alarm != self.alarm_summary:
            self.alarm_changed.emit(new_alarm)
        self.alarm_summary = new_alarm


class TyphosAlarmCircleIndicator(TyphosAlarmBase, PyDMDrawingCircle):
    """
    Circle indicator for device alarm state.
    """
    pass


class TyphosAlarmRectangleIndicator(TyphosAlarmBase, PyDMDrawingRectangle):
    """
    Rectangle indicator for device alarm state.
    """
    pass


kind_filters = {
    KindLevel.hinted:
        (lambda walk: walk.item.kind == Kind.hinted),
    KindLevel.normal:
        (lambda walk: walk.item.kind in (Kind.hinted, Kind.normal)),
    KindLevel.config:
        (lambda walk: walk.item.kind != Kind.omitted),
    KindLevel.omitted:
        (lambda walk: True),
    }


def indicator_stylesheet(cls, alarm=None)
    base = (
        f'{cls} '
        '{border: none; '
        ' background: transparent;'
        ' qproperty-penColor: black;'
        ' qproperty-penWidth: 2;'
        ' qproperty-penStyle: SolidLine;'
        ' qproperty-brush: rgba'
        )

    if alarm in (None, AlarmLevel.disconnected):
        return base + '(255,255,255,255);}'
    elif alarm is AlarmLevel.no_alarm:
        return base + '(0,255,0,255);}'
    elif alarm is AlarmLevel.minor:
        return base + '(255,255,0,255);}'
    elif alarm is AlarmLevel.major:
        return base + '(255,0,0,255);}'
    elif alarm is AlarmLevel.invalid:
        return base + '(255,0,255,255);}'
