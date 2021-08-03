import random
import threading
import time

from ophyd import Component as Cpt
from ophyd import Device, Signal, StatusBase

from .app import get_qapp, launch_suite
from .suite import TyphosSuite
from .utils import use_stylesheet


def example_positioner_suite():
    get_qapp()
    devices = [
        ExamplePositioner(name='example_motor'),
        ExampleComboPositioner(name='example_combo'),
        ]
    suite = TyphosSuite.from_devices(devices)
    use_stylesheet()
    launch_suite(suite)


class PositionerBase:
    """
    Trick Typhos into giving us the positioner template.
    """
    pass


class ExamplePositioner(Device, PositionerBase):
    user_readback = Cpt(Signal, value=0.0, kind='hinted',
                        metadata={'precision': 3})
    user_setpoint = Cpt(Signal, value=0.0)
    low_limit_switch = Cpt(Signal, value=False)
    high_limit_switch = Cpt(Signal, value=False)
    low_limit_travel = Cpt(Signal, value=-10.0)
    high_limit_travel = Cpt(Signal, value=10.0)
    velocity = Cpt(Signal, value=1.0)
    acceleration = Cpt(Signal, value=1.0)
    motor_is_moving = Cpt(Signal, value=False)
    error_message = Cpt(Signal, value='')
    cause_error = Cpt(Signal, value='')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._status = None
        self._status_ready_event = threading.Event()

    def set(self, position):
        self._status_ready_event.clear()
        self.user_setpoint.put(position)
        self._status_ready_event.wait()
        return self._status

    @user_setpoint.sub_value
    def _start_motion_thread(self, value, **kwargs):
        self.stop(success=True)
        self._status = StatusBase()
        self._status_ready_event.set()
        td = threading.Thread(target=self._motion_thread)
        td.start()

    def _motion_thread(self):
        self.motor_is_moving.put(True)
        while not self._status.done:
            self._step_position()
        self.motor_is_moving.put(False)

    def _step_position(self):
        time_step = 0.1
        noise_factor = 0.1
        noise = noise_factor * random.uniform(-1, 1)
        dist = self.user_setpoint.get() - self.user_readback.get()
        velo = self.velocity.get() * (1 + noise)
        step = velo * time_step
        if abs(dist) < step:
            self.user_readback.put(self.user_setpoint.get() + noise/10)
            self._status.set_finished()
        elif dist > 0:
            self.user_readback.put(self.user_readback.get() + step)
        elif dist < 0:
            self.user_readback.put(self.user_readback.get() - step)
        time.sleep(time_step)

    def stop(self, success=False):
        if self._status is not None and not self._status.done:
            if success:
                self._status.set_finished()
            else:
                self._status.set_exception(
                    RuntimeError('Move Interrupted')
                    )

    @user_readback.sub_value
    def _update_position(self, value, **kwargs):
        if self.low_limit_travel.get() or self.high_limit_travel.get():
            bot_hit = value <= self.low_limit_travel.get()
            top_hit = value >= self.high_limit_travel.get()
            self.low_limit_switch.put(bot_hit)
            self.high_limit_switch.put(top_hit)

    @low_limit_switch.sub_value
    @high_limit_switch.sub_value
    def _limit_hit(self, value, **kwargs):
        if value:
            self.stop(success=True)

    def clear_error(self):
        self.error_message.put('')

    @cause_error.sub_value
    def _cause_error(self, value, **kwargs):
        self.error_message.put(value)


class ExampleComboPositioner(Device, PositionerBase):
    user_readback = Cpt(Signal, value='OUT', kind='hinted')
    user_setpoint = Cpt(Signal, value='Unknown')
    motor_is_moving = Cpt(Signal, value=False)
    stop = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._status = None
        self._status_ready_event = threading.Event()
        enums = ('Unknown', 'OUT', 'TARGET1', 'TARGET2')
        self.user_readback.enum_strs = enums
        self.user_setpoint.enum_strs = enums

    def set(self, position):
        self._status_ready_event = threading.Event()
        self.user_setpoint.put(position)
        self._status_ready_event.wait()
        return self._status

    @user_setpoint.sub_value
    def _start_motion_thread(self, value, **kwargs):
        self._status = StatusBase()
        self._status_ready_event.set()
        if value == 'Unknown':
            self._status.set_exception(
                RuntimeError('Unknown not a valid target state')
                )
        else:
            td = threading.Thread(target=self._motion_thread)
            td.start()

    def _motion_thread(self):
        self.motor_is_moving.put(True)
        self.user_readback.put('Unknown')
        time.sleep(3)
        self.user_readback.put(self.user_setpoint.get())
        self.motor_is_moving.put(False)
        self._status.set_finished()
