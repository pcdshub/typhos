import os

import pytest

import typhos
from typhos.cli import typhos_cli, QApplication


def test_cli_version(capsys):
    typhos_cli(['--version'])
    readout = capsys.readouterr()
    assert typhos.__version__ in readout.out


def test_cli_happi_cfg(monkeypatch, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    window = typhos_cli(['test_motor', '--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert window.isVisible()
    assert 'test_motor' == window.centralWidget().devices[0].name


def test_cli_bad_entry(qtbot, happi_cfg):
    window = typhos_cli(['no_motor', '--happi-cfg', happi_cfg])
    assert window is None


def test_cli_no_entry(monkeypatch, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    window = typhos_cli(['--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    assert window.isVisible()
    assert window.centralWidget().devices == []


def test_cli_stylesheet(monkeypatch, qapp, qtbot, happi_cfg):
    monkeypatch.setattr(QApplication, 'exec_', lambda x: 1)
    with open('test.qss', 'w+') as handle:
        handle.write("TyphosDeviceDisplay {qproperty-force_template: 'test.ui'}")
    style = qapp.styleSheet()
    window = typhos_cli(['test_motor', '--stylesheet', 'test.qss',
                        '--happi-cfg', happi_cfg])
    qtbot.addWidget(window)
    suite = window.centralWidget()
    dev_display = suite.get_subdisplay(suite.devices[0])
    assert dev_display.force_template == 'test.ui'
    qapp.setStyleSheet(style)
    os.remove('test.qss')
