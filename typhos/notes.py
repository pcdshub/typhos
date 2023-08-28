import getpass
import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Dict, Optional, Tuple

import ophyd
import platformdirs
import yaml
from qtpy import QtCore, QtWidgets

from . import utils, widgets

logger = logging.getLogger(__name__)
NOTES_VAR = "PCDS_DEVICE_NOTES"


class NotesSource(IntEnum):
    USER = 0
    ENV = 1
    # HAPPI = 2  # to be implemented later


def get_data_from_yaml(device_name: str, path: Path) -> Optional[Dict[str, str]]:
    """
    Returns the device data from the yaml file stored in ``path``.
    Returns `None` if reading the file fails or there is no information

    Parameters
    ----------
    device_name : str
        The name of the device to retrieve notes for.
    path : Path
        Path to the device information yaml

    Returns
    -------
    Optional[Dict[str, str]]
        The device information or None
    """
    try:
        with open(path) as f:
            device_notes = yaml.full_load(f)
    except Exception as ex:
        logger.warning(f'failed to load device notes: {ex}')
        return

    return device_notes.get(device_name, None)


def get_notes_data(device_name: str) -> Tuple[NotesSource, Dict[str, str]]:
    """
    get the notes data for a given device
    attempt to get the info from the following locations
    in order of priority (higher priority will shadow)
    1: device_notes in the user directory
    2: the path in NOTES_VAR environment variable
    3: TODO: happi ... eventually

    Parameters
    ----------
    device_name : str
        The device name.  Can also be a component. e.g. device_component_name

    Returns
    -------
    Tuple[NotesSource, dict]
        The source of the device notes, and
        a dictionary containing the device note information
    """
    data = {'note': '', 'timestamp': ''}
    source = NotesSource.USER

    # try env var
    env_notes_path = os.environ.get(NOTES_VAR)
    if env_notes_path and Path(env_notes_path).is_file():
        note_data = get_data_from_yaml(device_name, env_notes_path)
        if note_data:
            data = note_data
            source = NotesSource.ENV

    # try user directory
    user_data_path = platformdirs.user_data_path() / 'device_notes.yaml'
    if user_data_path.exists():
        note_data = get_data_from_yaml(device_name, user_data_path)
        if note_data:
            data = note_data
            source = NotesSource.USER

    return source, data


def insert_into_yaml(path: Path, device_name: str, data: dict[str, str]) -> None:
    try:
        with open(path, 'r') as f:
            device_notes = yaml.full_load(f)
    except FileNotFoundError:
        logger.info(f'No existing device notes found at {path}. '
                    'Creating new notes file.')
        device_notes = {}
    except Exception as ex:
        logger.warning(f'Unable to open existing device notes, aborting: {ex}')
        return

    device_notes[device_name] = data

    directory = os.path.dirname(path)
    temp_path = Path(directory) / (
        f".{getpass.getuser()}"
        f"_{int(time.time())}"
        f"_{str(uuid.uuid4())[:8]}"
        f"_{os.path.basename(path)}"
    )
    try:
        with open(temp_path, 'w') as f:
            yaml.dump(device_notes, f)
    except Exception as ex:
        logger.warning(f'unable to write device info: {ex}')
        return

    if os.path.exists(path):
        shutil.copymode(path, temp_path)
    shutil.move(temp_path, path)


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
        insert_into_yaml(user_data_path, device_name, data)
    elif source == NotesSource.ENV:
        env_data_path = Path(os.environ.get(NOTES_VAR))
        insert_into_yaml(env_data_path, device_name, data)


class TyphosNotesEdit(
    utils.TyphosBase,
    QtWidgets.QLineEdit,
    widgets.TyphosDesignerMixin,
):
    """
    A QLineEdit for storing notes for a device.
    """
    def __init__(self, *args, refresh_time: float = 5.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.editingFinished.connect(self.save_note)
        self.setPlaceholderText('no notes...')
        self.edit_filter = utils.FrameOnEditFilter(parent=self)
        self.setFrame(False)
        self.setStyleSheet("QLineEdit { background: transparent }")
        self.setReadOnly(True)
        self.installEventFilter(self.edit_filter)
        self._last_updated: float = None
        self._refresh_time: float = refresh_time
        # to be initialized later
        self.device_name: str = None
        self.notes_source: Optional[NotesSource] = None
        self.data = {'note': '', 'timestamp': ''}

    def update_tooltip(self) -> None:
        if self.data['note']:
            self.setToolTip(f"({self.data['timestamp']}, {self.notes_source.name}):\n"
                            f"{self.data['note']}")
        else:
            self.setToolTip('click to edit note')

    def add_device(self, device: ophyd.Device) -> None:
        super().add_device(device)
        if device is None:
            return
        self.setup_data(device.name)

    def setup_data(self, device_name: Optional[str] = None) -> None:
        """
        Set up the device data.  Saves the device name and initializes the notes
        line edit.  Will refresh the data if the time since the last refresh is
        longer than `self._refresh_time`

        Once initialized, this widget will not change its targeted device_name.
        Subsequent attempts to set a new device_name will be ignored, and simply
        refresh this widget's note

        The setup is split up here due to how Typhos Display initialize themselves
        first, then add the device later

        Parameters
        ----------
        device_name : Optional[str]
            The device name.  Can also be a component. e.g. device_component_name
        """
        # if not initialized
        if self.device_name is None:
            self.device_name = device_name

        # if no-arg called without device being initialized
        if self.device_name is None:
            return

        if not self._last_updated:
            self._last_updated = time.time()
        elif (time.time() - self._last_updated) < self._refresh_time:
            return

        self._last_updated = time.time()
        self.notes_source, self.data = get_notes_data(self.device_name)

        self.setText(self.data.get('note', ''))
        self.update_tooltip()

    def save_note(self) -> None:
        note_text = self.text()
        curr_time = datetime.now().ctime()
        self.data['note'] = note_text
        self.data['timestamp'] = curr_time
        self.update_tooltip()
        write_notes_data(self.notes_source, self.device_name, self.data)

    def event(self, event: QtCore.QEvent) -> bool:
        """ Overload event method to update data on tooltip-request """
        # Catch relevant events to update status tooltip
        if event.type() in (QtCore.QEvent.ToolTip, QtCore.QEvent.Paint,
                            QtCore.QEvent.FocusAboutToChange):
            self.setup_data()

        return super().event(event)
