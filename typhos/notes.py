import logging
import os
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Dict, Tuple

import platformdirs
import yaml
from qtpy import QtWidgets

from typhos import utils

logger = logging.getLogger(__name__)


class NotesSource(IntEnum):
    USER = 0
    ENV = 1
    HAPPI = 2


def get_notes_data(device_name: str) -> Tuple[NotesSource, Dict[str, str]]:
    """
    get the notes data for a given device
    attempt to get the info from the following locations
    in order of priority (higher priority will shadow)
    1: device_notes in the user directory
    2: the path in DEVICE_NOTES environment variable
    3: TODO: happi ... eventually

    Parameters
    ----------
    device_name : str
        The name of the device to retrieve notes for.

    Returns
    -------
    Tuple[NotesSource, dict]
        The source of the device notes
        a dictionary containing the device note information
    """
    data = {'note': '', 'timestamp': ''}
    source = NotesSource.USER
    # try user directory
    user_data_path = platformdirs.user_data_path() / 'device_notes.yaml'
    if user_data_path.exists():
        with open(user_data_path) as f:
            device_notes = yaml.full_load(f)

        if device_name in device_notes:
            source = NotesSource.USER
            data = device_notes.get(device_name)

    env_notes_path = os.environ.get('DEVICE_NOTES')
    if env_notes_path and Path(env_notes_path).is_file():
        with open(Path(env_notes_path)) as f:
            device_notes = yaml.full_load(f)

        if device_name in device_notes:
            source = NotesSource.ENV
            data = device_notes.get(device_name)

    return source, data


def insert_into_data(path: Path, device_name: str, data: dict[str, str]) -> None:
    with open(path, 'r') as f:
        device_notes = yaml.full_load(f)

    device_notes[device_name] = data

    with open(path, 'w') as f:
        yaml.dump(device_notes, f)


def write_notes_data(
    source: NotesSource,
    device_name: str,
    data: dict[str, str]
) -> None:
    """
    Write the notes ``data`` to the specified ``source`` under the key ``device_name``

    Parameters
    ----------
    source : NotesSource
        The source to write the data to
    device_name : str
        The device name.  Can also be a component. e.g. device_component_name
    data : dict[str, str]
        The notes data.  Expected to contain the 'note' and 'timestamp' keys
    """
    if source == NotesSource.USER:
        user_data_path = platformdirs.user_data_path() / 'device_notes.yaml'
        insert_into_data(user_data_path, device_name, data)
    elif source == NotesSource.ENV:
        env_data_path = Path(os.environ.get('DEVICE_NOTES'))
        insert_into_data(env_data_path, device_name, data)


class TyphosNotesEdit(QtWidgets.QLineEdit):
    """
    A QLineEdit for storing notes for a device.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.editingFinished.connect(self.save_note)
        self.setPlaceholderText('...')
        self.edit_filter = utils.FrameOnEditFilter(parent=self)
        self.setFrame(False)
        self.setStyleSheet("QLineEdit { background: transparent }")
        self.setReadOnly(True)
        self.installEventFilter(self.edit_filter)

        # to be initialized later
        self.device_name = None
        self.notes_source = None
        self.data = {'note': '', 'timestamp': ''}

    def update_tooltip(self) -> None:
        if self.data:
            self.setToolTip(f"({self.data['timestamp']}):\n{self.data['note']}")

    def setup_data(self, device_name: str) -> None:
        """
        Set up the device data.  Saves the device name and initializes the notes
        line edit.

        The setup is split up here due to how Typhos Display initialize themselves
        first, then add the device later

        Parameters
        ----------
        device_name : str
            The device name.  Can also be a component. e.g. device_component_name
        """
        if self.device_name:
            return

        self.device_name = device_name
        self.notes_source, self.data = get_notes_data(device_name)

        self.setText(self.data['note'])
        self.update_tooltip()

    def save_note(self) -> None:
        note_text = self.text()
        curr_time = datetime.now().ctime()
        self.data['note'] = note_text
        self.data['timestamp'] = curr_time
        self.update_tooltip()
        write_notes_data(self.notes_source, self.device_name, self.data)
