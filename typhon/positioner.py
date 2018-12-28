import os.path
import logging

from ophyd import Device
from qtpy import uic
from qtpy.QtCore import Slot

from .plugins import register_signal
from .utils import (TyphonBase, ui_dir, channel_from_signal, grab_kind,
                    raise_to_operator)
from .widgets import TyphonDesignerMixin


logger = logging.getLogger(__name__)


class TyphonPositionerWidget(TyphonBase, TyphonDesignerMixin):
    """
    Widget to interact with an ``ophyd.Positioner``

    Standard positioner motion requires a large amount of context for operator.
    For most motors, in may not be enough to simply have a text field where
    method can be punched in. Instead, information like soft limits and
    hardware limit switches are crucial for a full understanding of the
    position and behavior of a motor. This widget can supply a standard display
    for all of these, but at a bare minimum the provided ``Device`` needs a
    valid ``set`` function. The rest of the signals are searched for assuming
    that the interface matches the ``EpicsMotor`` example supplied in
    ``ophyd``.
    """
    ui_template = os.path.join(ui_dir, 'positioner.ui')

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Instantiate UI
        self.ui = uic.loadUi(self.ui_template, self)
        self.ui.progress_bar.hide()  # Hide until we are ready to move
        # Connect signals to slots
        self.ui.set_value.returnPressed.connect(self.set)
        self.ui.tweak_positive.clicked.connect(self.positive_tweak)
        self.ui.tweak_negative.clicked.connect(self.negative_tweak)
        self.ui.stop_button.clicked.connect(self.stop)
        self._readback = None

    @Slot()
    def set(self):
        """Set the device to the value configured by ``ui.set_value``"""
        self._set(float(self.ui.set_value.text()))

    @Slot()
    def positive_tweak(self):
        """Tweak positive by the amount listed in ``ui.tweak_value``"""
        setpoint = self._get_position() + float(self.tweak_value.text())
        self._set(setpoint)

    @Slot()
    def negative_tweak(self):
        """Tweak negative by the amount listed in ``ui.tweak_value``"""
        setpoint = self._get_position() - float(self.tweak_value.text())
        self._set(setpoint)

    @Slot()
    def stop(self):
        """Stop device"""
        for device in self.devices:
            device.stop()

    def _get_position(self):
        if not self._readback:
            raise Exception("No Device configured for widget!")
        return self._readback.get()

    def _set(self, value):
        try:
            if not self.devices:
                raise Exception("No Device configured for widget!")
            self.devices[0].set(value)
        except Exception as exc:
            logger.exception("Error setting %r to %r",
                             self.devices[0], value)
            raise_to_operator(exc)

    def add_device(self, device):
        """Add a device to the widget"""
        # Add device to cache
        self.devices.clear()  # only one device allowed
        super().add_device(device)
        # Limit switches
        for limit_switch in ('low_limit_switch',
                             'high_limit_switch'):
            # If our device has a limit switch attach it
            if getattr(device, limit_switch, False):
                widget = getattr(self.ui, limit_switch)
                limit = getattr(device, limit_switch)
                limit_chan = channel_from_signal(limit)
                register_signal(limit)
                widget.channel = limit_chan
            # Otherwise, hide it the widget
            else:
                getattr(self.ui, limit_switch).hide()
        # User Readback
        if hasattr(device, 'user_readback'):
            self._readback = device.user_readback
        else:
            # Let us assume it is the first hint
            self._readback = grab_kind(device, 'hinted')[0][1]
        register_signal(self._readback)
        self.ui.user_readback.channel = channel_from_signal(self._readback)
        # Limit values
        # Look for limit signals first
        if isinstance(device, Device):
            limit_signals = ('low_limit' in device.component_names
                             and 'high_limit' in device.component_names)
            # Use raw signals to keep widget updated
            if limit_signals:
                register_signal(device.low_limit)
                low_lim_chan = channel_from_signal(device.low_limit)
                self.ui.low_limit.channel = low_lim_chan
                register_signal(device.high_limit)
                high_lim_chan = channel_from_signal(device.high_limit)
                self.ui.high_limit.channel = high_lim_chan
                return
        # Check that we have limits at all, or if they are implemented
        if hasattr(device, 'limits') and device.limits[0] != device.limits[1]:
            self.ui.low_limit.setText(str(device.limits[0]))
            self.ui.high_limit.setText(str(device.limits[1]))
        # Look for limit value components
        else:
            self.ui.low_limit.hide()
            self.ui.high_limit.hide()
