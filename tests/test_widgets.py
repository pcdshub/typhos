import pytest
import qtawesome as qta
from qtpy.QtWidgets import QWidget
from qtpy.QtGui import QIcon

from typhos.widgets import (TyphosSidebarItem, SignalDialogButton, QDialog,
                            ImageDialogButton, WaveformDialogButton)
from typhos.suite import SidebarParameter


class DialogButton(SignalDialogButton):
    icon = 'fa.play'
    text = 'Show Widget'

    def widget(self):
        return QWidget(parent=self)


@pytest.fixture(scope='function')
def widget_button(qtbot, monkeypatch):
    monkeypatch.setattr(QDialog, 'exec_', lambda x: 1)
    button = DialogButton('ca://Pv:1')
    qtbot.addWidget(button)
    return button


def test_sidebar_item(qtbot):
    param = SidebarParameter(name='test', embeddable=True)
    item = TyphosSidebarItem(param, 0)
    qtbot.addWidget(item)
    assert len(item.toolbar.actions()) == 3
    assert item.open_action.isEnabled()
    assert item.embed_action.isEnabled()
    assert not item.hide_action.isEnabled()
    item.open_requested(True)
    assert not item.open_action.isEnabled()
    assert not item.embed_action.isEnabled()
    assert item.hide_action.isEnabled()
    item.hide_requested(True)
    assert item.open_action.isEnabled()
    assert item.embed_action.isEnabled()
    assert not item.hide_action.isEnabled()
    item.embed_requested(True)
    assert not item.open_action.isEnabled()
    assert not item.embed_action.isEnabled()
    assert item.hide_action.isEnabled()


def test_signal_dialog_button_show(widget_button):
    widget_button.show_dialog()
    assert widget_button.dialog is not None
    assert widget_button.dialog.isVisible()
    assert len(widget_button.children()) == 1


def test_signal_dialog_button_repeated_show(widget_button):
    widget_button.show_dialog()
    dialog = widget_button.dialog
    widget_button.show_dialog()
    assert id(dialog) == id(widget_button.dialog)


@pytest.mark.parametrize('button_type', [WaveformDialogButton,
                                         ImageDialogButton],
                         ids=['Waveform', 'Image'])
def test_dialog_button_instances_smoke(qtbot, button_type):
    button = button_type(init_channel='ca://Pv:2')
    qtbot.addWidget(button)
    widget = button.widget()
    assert widget.parent() == button
