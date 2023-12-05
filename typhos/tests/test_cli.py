import os

import pytest
from qtpy.QtWidgets import QLabel

import typhos
from typhos.cli import typhos_cli

from . import conftest


def test_cli_version(capsys):
    typhos_cli(['--version'])
    readout = capsys.readouterr()
    assert str(typhos.__version__) in readout.out


def test_cli_happi_cfg(qtbot, happi_cfg):
    window = typhos_cli(['test_motor', '--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert 'test_motor' == window.centralWidget().devices[0].name


def test_cli_bad_entry(qtbot, happi_cfg):
    window = typhos_cli(['no_motor', '--happi-cfg', happi_cfg])
    assert window is None


def test_cli_no_entry(qtbot, happi_cfg):
    window = typhos_cli(['--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert window.centralWidget().devices == []


def test_cli_stylesheet(qapp, qtbot, happi_cfg):
    with open('test.qss', 'w+') as handle:
        handle.write("QLabel {color: red}")
    try:
        style = qapp.styleSheet()
        window = typhos_cli(['test_motor', '--stylesheet', 'test.qss',
                             '--happi-cfg', happi_cfg])
        qtbot.addWidget(window)
        suite = window.centralWidget()
        qtbot.addWidget(suite)
        some_label = suite.findChild(QLabel)
        assert isinstance(some_label, QLabel)
        color = some_label.palette().color(some_label.foregroundRole())
        assert color.red() == 255
    finally:
        qapp.setStyleSheet(style)
        os.remove('test.qss')


@pytest.mark.parametrize('klass, name', [
    ("ophyd.sim.SynAxis[]", "SynAxis"),
    ("ophyd.sim.SynAxis[{'name':'foo'}]", "foo")
])
def test_cli_class(qtbot, klass, name, happi_cfg):
    window = typhos_cli([klass])
    qtbot.addWidget(window)

    suite = window.centralWidget()
    assert name == suite.devices[0].name

    for dev in suite.devices:
        conftest.clear_handlers(dev)


def test_cli_class_invalid(qtbot):
    window = typhos_cli(["non.Valid.ClassName[]"])
    assert window is None


def test_cli_profile_modules(capsys, qtbot):
    window = typhos_cli(['ophyd.sim.SynAxis[]', '--profile-modules',
                         'typhos.suite'])
    qtbot.addWidget(window)
    output = capsys.readouterr()
    assert 'add_device' in output.out


def test_cli_benchmark(capsys, qtbot):
    windows = typhos_cli(['ophyd.sim.SynAxis[]', '--benchmark',
                          'flat_soft'])
    qtbot.addWidget(windows[0])
    output = capsys.readouterr()
    assert 'add_device' in output.out


def test_cli_profile_output(capsys, qtbot):
    path_obj = conftest.MODULE_PATH / 'artifacts' / 'prof'
    if not path_obj.parent.exists():
        path_obj.parent.mkdir(parents=True)
    window = typhos_cli(['ophyd.sim.SynAxis[]', '--profile-output',
                         str(path_obj)])
    qtbot.addWidget(window)
    output = capsys.readouterr()
    assert 'add_device' not in output.out
    assert path_obj.exists()
