import os
import pathlib

import pytest

import typhon
from typhon.cli import typhon_cli, QApplication


@pytest.fixture(scope='session')
def happi_cfg():
    path = pathlib.Path(__file__)
    return str(path.parent / 'happi.cfg')


def test_cli_version(capsys):
    typhon_cli(['--version'])
    readout = capsys.readouterr()
    assert typhon.__version__ in readout.out
    assert typhon.__file__ in readout.out


def test_cli_happi_cfg(monkeypatch, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    suite = typhon_cli(['test_motor', '--happi-cfg', happi_cfg])
    qtbot.addWidget(suite)
    assert 'test_motor' == suite.devices[0].name


def test_cli_stylesheet(monkeypatch, qapp, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    with open('test.qss', 'w+') as handle:
        handle.write("TyphonDisplay {qproperty-force_template: 'test.ui'}")
    style = qapp.styleSheet()
    suite = typhon_cli(['test_motor', '--stylesheet', 'test.qss',
                        '--happi-cfg', happi_cfg])
    qtbot.addWidget(suite)
    dev_display = suite.get_subdisplay(suite.devices[0])
    assert dev_display.force_template == 'test.ui'
    qapp.setStyleSheet(style)
    os.remove('test.qss')
