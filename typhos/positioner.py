import functools
import logging
import operator
import os.path

from qtpy import uic
from qtpy.QtCore import Property, Slot

from .plugins import register_signal
from .status import TyphosStatusThread
from .utils import (TyphosBase, channel_from_signal, raise_to_operator,
                    reload_widget_stylesheet, ui_dir)
from .widgets import TyphosDesignerMixin

logger = logging.getLogger(__name__)


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
                register_signal(signal)
                if widget is not None:
                    widget.channel = channel_from_signal(signal)

            logger.debug('device.%s => self.%s (signal: %s widget: %s)',
                         device_attr, widget_attr, signal, widget)
            return func(self, signal, widget)

        return wrapped
    return wrapper


class TyphosPositionerWidget(TyphosBase, TyphosDesignerMixin):
    """
    Widget to interact with an ``ophyd.Positioner``

    Standard positioner motion requires a large amount of context for
    operators. For most motors, it may not be enough to simply have a text
    field where setpoints can be punched in. Instead, information like soft
    limits and hardware limit switches are crucial for a full understanding of
    the position and behavior of a motor. The widget will work with any object
    that implements ``set``, however to get other relevant information, we also
    duck-type to see if we can find other useful signals.  Below is a table of
    attributes that the widget looks for to inform screen design:

    ============== ===========================================================
    Widget         Attribute Selection
    ============== ===========================================================
    User Readback  The ``readback_attribute`` property is used, which defaults
                   to ``user_readback``.

    Limit Switches The ``low_limit_switch_attribute`` and
                   ``high_limit_switch_attribute`` properties are used, which
                   default to ``low_limit_switch`` and ``high_limit_switch``,
                   respectively.

    Soft Limits    The ``low_limit_attribute`` and ``high_limit_attribute``
                   properties are used, which default to ``low_limit`` and
                   ``high_limit``, respectively.  As a fallback, the ``limit``
                   property on the device may be queried directly.

    Set and Tweak  Both of these methods simply use ``Device.set`` which is
                   expected to take a ``float`` and return a ``status`` object
                   that indicates the motion completeness. Must be implemented.

    Stop           Device.stop()
    ============== ===========================================================
    """
    ui_template = os.path.join(ui_dir, 'positioner.ui')
    _readback_attr = 'user_readback'
    _low_limit_switch_attr = 'low_limit_switch'
    _high_limit_switch_attr = 'high_limit_switch'
    _low_limit_attr = 'low_limit'
    _high_limit_attr = 'high_limit'
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
            self._status_thread = TyphosStatusThread(
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

    def tweak(self, offset):
        """Tweak by the given ``offset``."""
        try:
            setpoint = self._get_position() + float(offset)
        except Exception:
            logger.exception('Tweak failed')
            return

        self.ui.set_value.setText(str(setpoint))
        self.set()

    @Slot()
    def positive_tweak(self):
        """Tweak positive by the amount listed in ``ui.tweak_value``"""
        try:
            self.tweak(float(self.tweak_value.text()))
        except Exception:
            logger.exception('Tweak failed')

    @Slot()
    def negative_tweak(self):
        """Tweak negative by the amount listed in ``ui.tweak_value``"""
        try:
            self.tweak(-float(self.tweak_value.text()))
        except Exception:
            logger.exception('Tweak failed')

    @Slot()
    def stop(self):
        """Stop device"""
        for device in self.devices:
            device.stop()

    def _get_position(self):
        if not self._readback:
            raise Exception("No Device configured for widget!")
        return self._readback.get()

    @_linked_attribute('_readback_attr', 'ui.user_readback')
    def _link_readback(self, signal, widget):
        """Link the positioner readback with the ui element."""
        self._readback = signal

    @_linked_attribute('_low_limit_switch_attr', 'ui.low_limit_switch')
    def _link_low_limit_switch(self, signal, widget):
        """Link the positioner lower limit switch with the ui element."""
        if signal is None:
            widget.hide()

    @_linked_attribute('_high_limit_switch_attr', 'ui.high_limit_switch')
    def _link_high_limit_switch(self, signal, widget):
        """Link the positioner high limit switch with the ui element."""
        if signal is None:
            widget.hide()

    @_linked_attribute('_low_limit_attr', 'ui.low_limit')
    def _link_low_limit(self, signal, widget):
        """Link the positioner lower limit with the ui element."""
        return signal is not None

    @_linked_attribute('_high_limit_attr', 'ui.high_limit')
    def _link_high_limit(self, signal, widget):
        """Link the positioner high limit with the ui element."""
        return signal is not None

    def _link_limits_by_limits_attr(self):
        """Link limits by using ``device.limits``."""
        device = self.device
        try:
            low_limit, high_limit = device.limits
        except AttributeError:
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
        self._link_low_limit_switch()
        self._link_high_limit_switch()

        if not (self._link_low_limit() and self._link_high_limit()):
            self._link_limits_by_limits_attr()

    @Property(bool, designable=False)
    def moving(self):
        """
        Current state of widget

        This will lag behind the actual state of the positioner in order to
        prevent unnecessary rapid movements
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

    @Property(str, designable=True)
    def readback_attribute(self):
        """The attribute name for the readback signal."""
        return self._readback_attr

    @readback_attribute.setter
    def readback_attribute(self, value):
        self._readback_attr = value

    @Property(str, designable=True)
    def low_limit_switch_attribute(self):
        """The attribute name for the low limit switch signal."""
        return self._low_limit_switch_attr

    @low_limit_switch_attribute.setter
    def low_limit_switch_attribute(self, value):
        self._low_limit_switch_attr = value

    @Property(str, designable=True)
    def high_limit_switch_attribute(self):
        """The attribute name for the high limit switch signal."""
        return self._high_limit_switch_attr

    @high_limit_switch_attribute.setter
    def high_limit_switch_attribute(self, value):
        self._high_limit_switch_attr = value

    @Property(str, designable=True)
    def low_limit_attribute(self):
        """The attribute name for the low limit signal."""
        return self._low_limit_attr

    @low_limit_attribute.setter
    def low_limit_attribute(self, value):
        self._low_limit_attr = value

    @Property(str, designable=True)
    def high_limit_attribute(self):
        """The attribute name for the high limit signal."""
        return self._high_limit_attr

    @high_limit_attribute.setter
    def high_limit_attribute(self, value):
        self._high_limit_attr = value

    def move_changed(self):
        """Called when a move is begun"""
        logger.debug("Begin showing move in TyphosPositionerWidget")
        self.moving = True

    def done_moving(self, success):
        """Called when a move is complete"""
        logger.debug("Completed move in TyphosPositionerWidget (success=%s)",
                     success)
        self._last_move = success
        self.moving = False
