import os.path
import logging

from ophyd import Device
from qtpy import uic
from qtpy.QtCore import Property, Slot

from .plugins import register_signal
from .utils import (TyphonBase, ui_dir, channel_from_signal, grab_kind,
                    raise_to_operator, reload_widget_stylesheet)
from .status import TyphonStatusThread
from .widgets import TyphonDesignerMixin


logger = logging.getLogger(__name__)


class TyphonPositionerWidget(TyphonBase, TyphonDesignerMixin):
    """
    Widget to interact with an ``ophyd.Positioner``

    Standard positioner motion requires a large amount of context for operators.
    For most motors, it may not be enough to simply have a text field where
    setpoints can be punched in. Instead, information like soft limits and
    hardware limit switches are crucial for a full understanding of the
    position and behavior of a motor. This widget can supply a standard display
    for all of these, but at a bare minimum the provided ``Device`` needs a
    valid ``set`` function. The rest of the signals are searched for assuming
    that the interface matches the ``EpicsMotor`` example supplied in
    ``ophyd``.
    """
    ui_template = os.path.join(ui_dir, 'positioner.ui')
    _min_visible_operation = 0.1

    def __init__(self, parent=None):
        self._moving = False
        self._last_move = None
        super().__init__(parent=parent)
        # Instantiate UI
        self.ui = uic.loadUi(self.ui_template, self)
        # Connect signals to slots
        self.ui.set_value.returnPressed.connect(self.set)
        self.ui.tweak_positive.clicked.connect(self.positive_tweak)
        self.ui.tweak_negative.clicked.connect(self.negative_tweak)
        self.ui.stop_button.clicked.connect(self.stop)
        self._readback = None
        self._status_thread = None

    @Slot()
    def set(self):
        """Set the device to the value configured by ``ui.set_value``"""
        value = self.ui.set_value.text()
        try:
            # Check that we have a device configured
            if not self.devices:
                raise Exception("No Device configured for widget!")
            # Clear any old statuses
            if self._status_thread and self._status_thread.isRunning():
                logger.debug("Clearing current active status")
                self._status_thread.terminate()
            self._status_thread = None
            self._last_move = None
            # Call the set
            logger.debug("Setting device %r to %r", self.devices[0], value)
            status = self.devices[0].set(float(value))
            logger.debug("Setting up new status thread ...")
            self._status_thread = TyphonStatusThread(
                                        status,
                                        lag=self._min_visible_operation)
            self._status_thread.status_started.connect(self.move_changed)
            self._status_thread.status_finished.connect(self.done_moving)
            self._status_thread.start()
        except Exception as exc:
            logger.exception("Error setting %r to %r",
                             self.devices, value)
            self._last_move = False
            reload_widget_stylesheet(self, cascade=True)
            raise_to_operator(exc)

    @Slot()
    def positive_tweak(self):
        """Tweak positive by the amount listed in ``ui.tweak_value``"""
        setpoint = self._get_position() + float(self.tweak_value.text())
        self.ui.set_value.setText(str(setpoint))
        self.set()

    @Slot()
    def negative_tweak(self):
        """Tweak negative by the amount listed in ``ui.tweak_value``"""
        setpoint = self._get_position() - float(self.tweak_value.text())
        self.ui.set_value.setText(str(setpoint))
        self.set()

    @Slot()
    def stop(self):
        """Stop device"""
        for device in self.devices:
            device.stop()

    def _get_position(self):
        if not self._readback:
            raise Exception("No Device configured for widget!")
        return self._readback.get()

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

    @Property(bool, designable=False)
    def moving(self):
        """
        Current state of widget

        This will lag behind the actual state of the positioner in order to
        prevent unneccesary rapid movements
        """
        return getattr(self, '_moving', False)

    @moving.setter
    def moving(self, value):
        if value != self._moving:
            self._moving = value
            reload_widget_stylesheet(self, cascade=True)

    @Property(bool, designable=False)
    def successful_move(self):
        """The last requested move was successful"""
        return self._last_move is True

    @Property(bool, designable=False)
    def failed_move(self):
        """The last requested move failed"""
        return self._last_move is False

    def move_changed(self):
        """Called when a move is begun"""
        logger.debug("Begin showing move in TyphonPositionerWidget")
        self.moving = True

    def done_moving(self, success):
        """Called when a move is complete"""
        logger.debug("Completed move in TyphonPositionerWidget (success=%s)",
                     success)
        self._last_move = success
        self.moving = False
