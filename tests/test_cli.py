import os

import pytest

import typhon
from typhon.cli import typhon_cli, QApplication


def test_cli_version(capsys):
    typhon_cli(['--version'])
    readout = capsys.readouterr()
    assert typhon.__version__ in readout.out
    assert typhon.__file__ in readout.out


def test_cli_happi_cfg(monkeypatch, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    window = typhon_cli(['test_motor', '--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert window.isVisible()
    assert 'test_motor' == window.centralWidget().devices[0].name

def test_cli_bad_entry(qtbot, happi_cfg):
    window = typhon_cli(['no_motor', '--happi-cfg', happi_cfg])
    assert window is None

def test_cli_no_entry(monkeypatch, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    window = typhon_cli(['--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert window.isVisible()
    assert window.centralWidget().devices == []

def test_cli_stylesheet(monkeypatch, qapp, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    with open('test.qss', 'w+') as handle:
        handle.write("TyphonDeviceDisplay {qproperty-force_template: 'test.ui'}")
    style = qapp.styleSheet()
    window = typhon_cli(['test_motor', '--stylesheet', 'test.qss',
                        '--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    suite = window.centralWidget()
    dev_display = suite.get_subdisplay(suite.devices[0])
    assert dev_display.force_template == 'test.ui'
    qapp.setStyleSheet(style)
    os.remove('test.qss')
