import functools
import logging
import math
import operator
import os.path

from qtpy import QtCore, uic

from . import plugins, utils, widgets
from .status import TyphosStatusThread

logger = logging.getLogger(__name__)


def _link_signal_to_widget(signal, widget):
    """
    Registers the signal with PyDM, and sets the widget channel.

    Parameters
    ----------
    signal : ophyd.OphydObj
        The signal to use.

    widget : QtWidgets.QWidget
        The widget with which to connect the signal.
    """
    if signal is not None:
        plugins.register_signal(signal)
        if widget is not None:
            widget.channel = utils.channel_from_signal(signal)


def _linked_attribute(property_attr, widget_attr):
    """
    Decorator which connects a device signal with a widget.

    Retrieves the signal from the device, registers it with PyDM, and sets the
    widget channel.

    Parameters
    ----------
    property_attr : str
        This is one level of indirection, allowing for the component attribute
        to be configurable by way of designable properties.
        In short, this looks like:
            ``getattr(self.device, getattr(self, property_attr))``
        The component attribute name may include multiple levels (e.g.,
        ``'cpt1.cpt2.low_limit'``).

    widget_attr : str
        The attribute name of the widget, referenced from ``self``.
        The component attribute name may include multiple levels (e.g.,
        ``'ui.low_limit'``).
    """
    get_widget_attr = operator.attrgetter(widget_attr)

    def wrapper(func):
        @functools.wraps(func)
        def wrapped(self):
            widget = get_widget_attr(self)
            device_attr = getattr(self, property_attr)
            get_device_attr = operator.attrgetter(device_attr)

            try:
                signal = get_device_attr(self.device)
            except AttributeError:
                signal = None
            else:
                # Fall short of an `isinstance(signal, OphydObj) check here:
                try:
                    _link_signal_to_widget(signal, widget)
                except Exception:
                    logger.exception(
                        'device.%s => self.%s (signal: %s widget: %s)',
                        device_attr, widget_attr, signal, widget)
                    signal = None
                else:
                    logger.debug('device.%s => self.%s (signal=%s widget=%s)',
                                 device_attr, widget_attr, signal, widget)

            return func(self, signal, widget)

        return wrapped
    return wrapper


class TyphosPositionerWidget(utils.TyphosBase, widgets.TyphosDesignerMixin):
    """
    Widget to interact with a :class:`ophyd.Positioner`.

    Standard positioner motion requires a large amount of context for
    operators. For most motors, it may not be enough to simply have a text
    field where setpoints can be punched in. Instead, information like soft
    limits and hardware limit switches are crucial for a full understanding of
    the position and behavior of a motor. The widget will work with any object
    that implements the method ``set``, however to get other relevant
    information, we see if we can find other useful signals.  Below is a table
    of attributes that the widget looks for to inform screen design.

    ============== ===========================================================
    Widget         Attribute Selection
    ============== ===========================================================
    User Readback  The ``readback_attribute`` property is used, which defaults
                   to ``user_readback``. Linked to UI element
                   ``user_readback``.

    User Setpoint  The ``setpoint_attribute`` property is used, which defaults
                   to ``user_setpoint``. Linked to UI element
                   ``user_setpoint``.

    Limit Switches The ``low_limit_switch_attribute`` and
                   ``high_limit_switch_attribute`` properties are used, which
                   default to ``low_limit_switch`` and ``high_limit_switch``,
                   respectively.

    Soft Limits    The ``low_limit_travel_attribute`` and
                   ``high_limit_travel_attribute`` properties are used, which
                   default to ``low_limit_travel`` and ``high_limit_travel``,
                   respectively.  As a fallback, the ``limit`` property on the
                   device may be queried directly.

    Set and Tweak  Both of these methods simply use ``Device.set`` which is
                   expected to take a ``float`` and return a ``status`` object
                   that indicates the motion completeness. Must be implemented.

    Stop           Device.stop()
    ============== ===========================================================
    """

    ui_template = os.path.join(utils.ui_dir, 'positioner.ui')
    _readback_attr = 'user_readback'
    _setpoint_attr = 'user_setpoint'
    _low_limit_switch_attr = 'low_limit_switch'
    _high_limit_switch_attr = 'high_limit_switch'
    _low_limit_travel_attr = 'low_limit_travel'
    _high_limit_travel_attr = 'high_limit_travel'
    _velocity_attr = 'velocity'
    _acceleration_attr = 'acceleration'
    _min_visible_operation = 0.1

    def __init__(self, parent=None):
        self._moving = False
        self._last_move = None
        self._readback = None
        self._setpoint = None
        self._status_thread = None

        super().__init__(parent=parent)

        self.ui = uic.loadUi(self.ui_template, self)
        self.ui.set_value.returnPressed.connect(self.set)
        self.ui.tweak_positive.clicked.connect(self.positive_tweak)
        self.ui.tweak_negative.clicked.connect(self.negative_tweak)
        self.ui.stop_button.clicked.connect(self.stop)

    def _clear_status_thread(self):
        """Clear a previous status thread."""
        if self._status_thread is None:
            return

        logger.debug("Clearing current active status")
        self._status_thread.disconnect()
        self._status_thread = None

    def _start_status_thread(self, status, timeout):
        """Start the status monitoring thread for the given status object."""
        self._status_thread = thread = TyphosStatusThread(
            status, start_delay=self._min_visible_operation,
            timeout=timeout
        )
        thread.status_started.connect(self.move_changed)
        thread.status_finished.connect(self._status_finished)
        thread.start()

    def _get_timeout(self, set_position, settle_time):
        """Use positioner's configuration to select a timeout."""
        pos_sig = getattr(self.device, self._readback_attr, None)
        vel_sig = getattr(self.device, self._velocity_attr, None)
        acc_sig = getattr(self.device, self._acceleration_attr, None)
        # Not enough info == no timeout
        if pos_sig is None or vel_sig is None:
            return math.inf
        delta = pos_sig.get() - set_position
        speed = vel_sig.get()
        # Bad speed == no timeout
        if speed == 0:
            return math.inf
        # Bad acceleration == ignore acceleration
        if acc_sig is None:
            acc_time = 0
        else:
            acc_time = acc_sig.get()
        # This time is always greater than the kinematic calc
        return abs(delta/speed) + 2 * abs(acc_time) + abs(settle_time)

    def _set(self, value):
        """Inner `set` routine - call device.set() and monitor the status."""
        self._clear_status_thread()
        self._last_move = None
        set_position = float(value)

        try:
            timeout = self._get_timeout(set_position, 5)
        except Exception:
            # Something went wrong, just run without a timeout.
            logger.exception('Unable to estimate motor timeout.')
            timeout = math.inf
        logger.debug("Setting device %r to %r with timeout %r",
                     self.device, value, timeout)
        # Send timeout through thread because status timeout stops the move
        status = self.device.set(set_position)
        self._start_status_thread(status, timeout)

    @QtCore.Slot()
    def set(self):
        """Set the device to the value configured by ``ui.set_value``"""
        if not self.device:
            return

        try:
            value = self.ui.set_value.text()
            self._set(value)
        except Exception as exc:
            logger.exception("Error setting %r to %r", self.devices, value)
            self._last_move = False
            utils.reload_widget_stylesheet(self, cascade=True)
            utils.raise_to_operator(exc)

    def tweak(self, offset):
        """Tweak by the given ``offset``."""
        try:
            setpoint = self._get_position() + float(offset)
        except Exception:
            logger.exception('Tweak failed')
            return

        self.ui.set_value.setText(str(setpoint))
        self.set()

    @QtCore.Slot()
    def positive_tweak(self):
        """Tweak positive by the amount listed in ``ui.tweak_value``"""
        try:
            self.tweak(float(self.tweak_value.text()))
        except Exception:
            logger.exception('Tweak failed')

    @QtCore.Slot()
    def negative_tweak(self):
        """Tweak negative by the amount listed in ``ui.tweak_value``"""
        try:
            self.tweak(-float(self.tweak_value.text()))
        except Exception:
            logger.exception('Tweak failed')

    @QtCore.Slot()
    def stop(self):
        """Stop device"""
        for device in self.devices:
            device.stop()

    def _get_position(self):
        if not self._readback:
            raise Exception("No Device configured for widget!")
        return self._readback.get()

    @_linked_attribute('readback_attribute', 'ui.user_readback')
    def _link_readback(self, signal, widget):
        """Link the positioner readback with the ui element."""
        self._readback = signal

    @_linked_attribute('setpoint_attribute', 'ui.user_setpoint')
    def _link_setpoint(self, signal, widget):
        """Link the positioner setpoint with the ui element."""
        self._setpoint = signal
        if signal is not None:
            # Seed the set_value text with the user_setpoint channel value.
            if hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._user_setpoint_update)

    @_linked_attribute('low_limit_switch_attribute', 'ui.low_limit_switch')
    def _link_low_limit_switch(self, signal, widget):
        """Link the positioner lower limit switch with the ui element."""
        if signal is None:
            widget.hide()

    @_linked_attribute('high_limit_switch_attribute', 'ui.high_limit_switch')
    def _link_high_limit_switch(self, signal, widget):
        """Link the positioner high limit switch with the ui element."""
        if signal is None:
            widget.hide()

    @_linked_attribute('low_limit_travel_attribute', 'ui.low_limit')
    def _link_low_travel(self, signal, widget):
        """Link the positioner lower travel limit with the ui element."""
        return signal is not None

    @_linked_attribute('high_limit_travel_attribute', 'ui.high_limit')
    def _link_high_travel(self, signal, widget):
        """Link the positioner high travel limit with the ui element."""
        return signal is not None

    def _link_limits_by_limits_attr(self):
        """Link limits by using ``device.limits``."""
        device = self.device
        try:
            low_limit, high_limit = device.limits
        except Exception:
            ...
        else:
            if low_limit < high_limit:
                self.ui.low_limit.setText(str(low_limit))
                self.ui.high_limit.setText(str(high_limit))
                return

        # If not found or invalid, hide them:
        self.ui.low_limit.hide()
        self.ui.high_limit.hide()

    @property
    def device(self):
        """The associated device."""
        try:
            return self.devices[0]
        except Exception:
            ...

    def add_device(self, device):
        """Add a device to the widget"""
        # Add device to cache
        self.devices.clear()  # only one device allowed
        super().add_device(device)

        self._link_readback()
        self._link_setpoint()
        self._link_low_limit_switch()
        self._link_high_limit_switch()

        if not (self._link_low_travel() and self._link_high_travel()):
            self._link_limits_by_limits_attr()

    @QtCore.Property(bool, designable=False)
    def moving(self):
        """
        Current state of widget

        This will lag behind the actual state of the positioner in order to
        prevent unnecessary rapid movements
        """
        return self._moving

    @moving.setter
    def moving(self, value):
        if value != self._moving:
            self._moving = value
            utils.reload_widget_stylesheet(self, cascade=True)

    @QtCore.Property(bool, designable=False)
    def successful_move(self):
        """The last requested move was successful"""
        return self._last_move is True

    @QtCore.Property(bool, designable=False)
    def failed_move(self):
        """The last requested move failed"""
        return self._last_move is False

    @QtCore.Property(str, designable=True)
    def readback_attribute(self):
        """The attribute name for the readback signal."""
        return self._readback_attr

    @readback_attribute.setter
    def readback_attribute(self, value):
        self._readback_attr = value

    @QtCore.Property(str, designable=True)
    def setpoint_attribute(self):
        """The attribute name for the setpoint signal."""
        return self._setpoint_attr

    @setpoint_attribute.setter
    def setpoint_attribute(self, value):
        self._setpoint_attr = value

    @QtCore.Property(str, designable=True)
    def low_limit_switch_attribute(self):
        """The attribute name for the low limit switch signal."""
        return self._low_limit_switch_attr

    @low_limit_switch_attribute.setter
    def low_limit_switch_attribute(self, value):
        self._low_limit_switch_attr = value

    @QtCore.Property(str, designable=True)
    def high_limit_switch_attribute(self):
        """The attribute name for the high limit switch signal."""
        return self._high_limit_switch_attr

    @high_limit_switch_attribute.setter
    def high_limit_switch_attribute(self, value):
        self._high_limit_switch_attr = value

    @QtCore.Property(str, designable=True)
    def low_limit_travel_attribute(self):
        """The attribute name for the low limit signal."""
        return self._low_limit_travel_attr

    @low_limit_travel_attribute.setter
    def low_limit_travel_attribute(self, value):
        self._low_limit_travel_attr = value

    @QtCore.Property(str, designable=True)
    def high_limit_travel_attribute(self):
        """The attribute name for the high (soft) limit travel signal."""
        return self._high_limit_travel_attr

    @high_limit_travel_attribute.setter
    def high_limit_travel_attribute(self, value):
        self._high_limit_travel_attr = value

    @QtCore.Property(str, designable=True)
    def velocity_attribute(self):
        """The attribute name for the velocity signal."""
        return self._velocity_attr

    @velocity_attribute.setter
    def velocity_attribute(self, value):
        self._velocity_attr = value

    @QtCore.Property(str, designable=True)
    def acceleration_attribute(self):
        """The attribute name for the acceleration time signal."""
        return self._acceleration_attr

    @acceleration_attribute.setter
    def acceleration_attribute(self, value):
        self._acceleration_attr = value

    def move_changed(self):
        """Called when a move is begun"""
        logger.debug("Begin showing move in TyphosPositionerWidget")
        self.moving = True

    def _set_status_text(self, text, *, max_length=60):
        """Set the status text label to ``text``."""
        if len(text) >= max_length:
            self.ui.status_label.setToolTip(text)
            text = text[:max_length] + '...'
        else:
            self.ui.status_label.setToolTip('')

        self.ui.status_label.setText(text)

    def _status_finished(self, result):
        """Called when a move is complete."""
        if isinstance(result, Exception):
            text = f'<b>{result.__class__.__name__}</b> {result}'
        else:
            text = ''

        self._set_status_text(text)

        success = not isinstance(result, Exception)
        logger.debug("Completed move in TyphosPositionerWidget (result=%r)",
                     result)
        self._last_move = success
        self.moving = False

    @QtCore.Slot(str)
    def _user_setpoint_update(self, text):
        """Qt slot - indicating the ``user_setpoint`` widget text changed."""
        try:
            text = text.strip().split(' ')[0]
            text = text.strip()
        except Exception:
            return

        # Update set_value if it's not being edited.
        if not self.ui.set_value.hasFocus():
            self.ui.set_value.setText(text)
