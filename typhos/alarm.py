"""
Module to define alarm summary frameworks and widgets.
"""
from functools import partial

from ophyd.device import Kind
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.drawing import (PyDMDrawing, PyDMDrawingCircle,
                                  PyDMDrawingRectangle)
from qtpy import QtCore, QtGui, QtWidgets

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

    # Signals
    alarm_changed = QtCore.Signal(AlarmLevel)

    # Methods
    def channels(self):
        """
        Let pydm know about our pydm channels
        """
        ch = []
        for lst in self.device_channels.values():
            ch.extend(lst)
        return ch

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
                connection_slot=partial(self.update_connection, addr=addr),
                severity_slot=partial(self.update_severity, addr=addr),
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


class TyphosAlarmShape(TyphosAlarmBase):
    def __init__(self, *args, **kwargs):
        self._pen = QtGui.QPen(QtCore.Qt.NoPen)
        self._alarm_color = 'rgba(255,255,255,255)'
        super().__init__(self, *args, **kwargs)
        self.alarm_changed.connect(self.update_alarm_color)

    def update_alarm_color(self, alarm):
        if alarm in (None, AlarmLevel.disconnected):
            self._alarm_color = 'rgba(255,255,255,255)'
        elif alarm is AlarmLevel.no_alarm:
            self._alarm_color = 'rgba(0,255,0,255)'
        elif alarm is AlarmLevel.minor:
            self._alarm_color = 'rgba(255,255,0,255)'
        elif alarm is AlarmLevel.major:
            self._alarm_color = 'rgba(255,0,0,255)'
        elif alarm is AlarmLevel.invalid:
            self._alarm_color = 'rgba(255,0,255,255)'
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_Widget,
                                   opt, painter, self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        painter.setBrush(self._alarm_color)
        painter.setPen(self._pen)

        self.draw_item(painter)

    def draw_item(painter):
        painter.translate(self.width()/2, self.height()/2)


class TyphosAlarmCircle(TyphosAlarmShape):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def draw_item(painter):
        super().draw_item(painter)
        radius = min(self.width(), self.height())/2
        painter.drawEllipse(QtCore.QPoint(0, 0), radius, radius)


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
