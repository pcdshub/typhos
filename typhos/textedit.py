import logging

import numpy as np
from qtpy import QtWidgets

from pydm.widgets.base import PyDMWritableWidget

from .variety import use_for_variety_write

logger = logging.getLogger(__name__)


@use_for_variety_write('text-multiline')
class TyphosTextEdit(QtWidgets.QWidget, PyDMWritableWidget):
    """
    A writable, multiline text editor with support for PyDM Channels.

    Parameters
    ----------
    parent : QWidget
        The parent widget.

    init_channel : str, optional
        The channel to be used by the widget.
    """

    def __init__(self, parent=None, init_channel=None):
        QtWidgets.QWidget.__init__(self, parent)
        PyDMWritableWidget.__init__(self, init_channel=init_channel)
        # superclasses do *not* support cooperative init:
        # super().__init__(self, parent=parent, init_channel=init_channel)
        self._display = None
        self._scale = 1

        self._setup_ui()
        self._string_encoding = "utf_8"

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self._text_edit = QtWidgets.QTextEdit()
        self._send_button = QtWidgets.QPushButton('Send')
        self._send_button.clicked.connect(self._send_clicked)

        self._revert_button = QtWidgets.QPushButton('Revert')
        self._revert_button.clicked.connect(self._revert_clicked)

        self._button_layout = QtWidgets.QHBoxLayout()

        self._button_layout.addWidget(self._revert_button)
        self._button_layout.addWidget(self._send_button)

        layout.addWidget(self._text_edit)
        layout.addLayout(self._button_layout)

    def _revert_clicked(self):
        self._set_text(self._display)

    def _send_clicked(self):
        self.send_value()

    def value_changed(self, value):
        """Receive and update the TyphosTextEdit for a new channel value."""
        super().value_changed(self._from_wire(value))
        self.set_display()

    def _to_wire(self, text=None):
        """TextEdit text -> numpy array."""
        if text is None:
            # text-format: toMarkdown, toHtml
            text = self._text_edit.toPlainText()
        return np.array(list(text.encode(self._string_encoding)),
                        dtype=np.uint8)

    def _from_wire(self, value):
        """numpy array/string/bytes -> string."""
        if isinstance(value, (list, np.ndarray)):
            return bytes(value).decode(self._string_encoding)
        return value

    def _set_text(self, text):
        return self._text_edit.setText(text)

    def send_value(self):
        """Emit a :attr:`send_value_signal` to update channel value."""
        send_value = self._to_wire()

        try:
            self.send_value_signal[np.ndarray].emit(send_value)
        except ValueError:
            logger.exception(
                "send_value error %r with type %r and format %r (widget %r).",
                send_value, self.channeltype, self._display_format_type,
                self.objectName()
            )

        self._text_edit.document().setModified(False)

    def write_access_changed(self, new_write_access):
        """
        Change the TyphosTextEdit to read only if write access is denied
        """
        super().write_access_changed(new_write_access)
        self._text_edit.setReadOnly(not new_write_access)
        self._send_button.setVisible(new_write_access)
        self._revert_button.setVisible(new_write_access)

    def set_display(self):
        """Set the text display of the TyphosTextEdit."""
        if self.value is None or self._text_edit.document().isModified():
            return

        self._display = str(self.value)
        self._set_text(self._display)
