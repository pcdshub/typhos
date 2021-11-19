import os

import pydm
import pytest

import typhos
from typhos.app import QApplication
from typhos.cli import typhos_cli

from . import conftest


@pytest.fixture(scope='function')
def noapp(monkeypatch):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    monkeypatch.setattr(QApplication, 'exit', lambda x: 1)
    monkeypatch.setattr(
        pydm.exception, 'raise_to_operator', lambda *_, **__: None
    )


def test_cli_version(capsys):
    typhos_cli(['--version'])
    readout = capsys.readouterr()
    assert typhos.__version__ in readout.out


def test_cli_happi_cfg(noapp, qtbot, happi_cfg):
    window = typhos_cli(['test_motor', '--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert window.isVisible()
    assert 'test_motor' == window.centralWidget().devices[0].name


def test_cli_bad_entry(qtbot, happi_cfg):
    window = typhos_cli(['no_motor', '--happi-cfg', happi_cfg])
    assert window is None


def test_cli_no_entry(noapp, qtbot, happi_cfg):
    window = typhos_cli(['--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert window.isVisible()
    assert window.centralWidget().devices == []


def test_cli_stylesheet(noapp, qapp, qtbot, happi_cfg):
    with open('test.qss', 'w+') as handle:
        handle.write(
            "TyphosDeviceDisplay {qproperty-force_template: 'test.ui'}")
    style = qapp.styleSheet()
    window = typhos_cli(['test_motor', '--stylesheet', 'test.qss',
                         '--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    suite = window.centralWidget()
    dev_display = suite.get_subdisplay(suite.devices[0])
    assert dev_display.force_template == 'test.ui'
    qapp.setStyleSheet(style)
    os.remove('test.qss')


@pytest.mark.parametrize('klass, name', [
    ("ophyd.sim.SynAxis[]", "SynAxis"),
    ("ophyd.sim.SynAxis[{'name':'foo'}]", "foo")
])
def test_cli_class(noapp, qapp, qtbot, klass, name, happi_cfg):
    window = typhos_cli([klass])
    qtbot.addWidget(window)
    assert window.isVisible()

    suite = window.centralWidget()
    assert name == suite.devices[0].name

    for dev in suite.devices:
        conftest.clear_handlers(dev)


def test_cli_class_invalid(qtbot):
    window = typhos_cli(["non.Valid.ClassName[]"])
    assert window is None


def test_cli_profile_modules(noapp, capsys, qapp, qtbot):
    window = typhos_cli(['ophyd.sim.SynAxis[]', '--profile-modules',
                         'typhos.suite'])
    qtbot.addWidget(window)
    output = capsys.readouterr()
    assert 'add_device' in output.out


def test_cli_benchmark(noapp, capsys, qapp, qtbot):
    windows = typhos_cli(['ophyd.sim.SynAxis[]', '--benchmark',
                          'flat_soft'])
    qtbot.addWidget(windows[0])
    output = capsys.readouterr()
    assert 'add_device' in output.out


def test_cli_profile_output(noapp, capsys, qapp, qtbot):
    path_obj = conftest.MODULE_PATH / 'artifacts' / 'prof'
    if not path_obj.parent.exists():
        path_obj.parent.mkdir(parents=True)
    window = typhos_cli(['ophyd.sim.SynAxis[]', '--profile-output',
                         str(path_obj)])
    qtbot.addWidget(window)
    output = capsys.readouterr()
    assert 'add_device' not in output.out
    assert path_obj.exists()
