import time

import ophyd
import ophyd.sim
from typhos.tools import TyphosConsole


def test_base_console(qtbot):
    tc = TyphosConsole()
    qtbot.addWidget(tc)
    assert tc.jupyter_widget.kernel_manager.is_alive()
    tc.shutdown()
    with qtbot.waitSignal(tc.kernel_shut_down, timeout=1000):
        ...
    assert not tc.jupyter_widget.kernel_manager.is_alive()
    tc.shutdown()


def test_add_happi_device(qapp, qtbot, happi_cfg, client):
    device = client['Syn:Motor'].get()

    tc = TyphosConsole.from_device(device)
    qtbot.addWidget(tc)

    with qtbot.waitSignal(tc.device_added, timeout=1000):
        ...

    tc.execute('print(test_motor.md["creation"])')

    creation = device.md['creation']
    while creation not in tc._plain_text:
        qapp.processEvents()
        print(tc._plain_text)
        time.sleep(0.5)


def test_add_importable_device(qapp, qtbot):
    device = ophyd.sim.SynAxis(name='device')
    tc = TyphosConsole.from_device(device)
    qtbot.addWidget(tc)

    with qtbot.waitSignal(tc.device_added, timeout=1000):
        ...

    tc.execute('print("velocity value is", device.velocity.get())')

    expected = 'velocity value is 1'
    while expected not in tc._plain_text:
        qapp.processEvents()
        print(tc._plain_text)
        time.sleep(0.5)

    tc.shutdown()


def test_add_fake_device(qapp, qtbot):
    EpicsMotor = ophyd.sim.make_fake_device(ophyd.EpicsMotor)
    device = EpicsMotor('sim:mtr1', name="sim_mtr1")

    tc = TyphosConsole.from_device(device)
    qtbot.addWidget(tc)

    with qtbot.waitSignal(tc.device_added, timeout=1000):
        ...

    tc.execute('print("my name is", sim_mtr1.name)')

    expected = 'my name is sim_mtr1'
    while expected not in tc._plain_text:
        qapp.processEvents()
        print(tc._plain_text)
        time.sleep(0.5)

    tc.shutdown()
