import os
import shutil
from pathlib import Path

import platformdirs
import pytest
import yaml
from pytestqt.qtbot import QtBot

from typhos.notes import NOTES_VAR, TyphosNotesEdit

from .conftest import MODULE_PATH


@pytest.fixture(scope='function')
def user_notes_path(monkeypatch, tmp_path: Path):
    # copy user device_notes.yaml to a temp file
    # monkeypatch platformdirs to look for device_notes.yaml
    # provide the new path for confirmation
    user_path = tmp_path / 'device_notes.yaml'
    notes_path = MODULE_PATH / 'utils' / 'user_device_notes.yaml'
    shutil.copy(notes_path, user_path)
    monkeypatch.setattr(platformdirs, 'user_data_path',
                        lambda: tmp_path)

    yield user_path


@pytest.fixture(scope='function')
def env_notes_path(tmp_path: Path):
    # copy user env var device_notes.yaml to a temp file
    # add env var pointing to env device notes
    # provide the path for confirmation
    env_path = tmp_path / 'env_device_notes.yaml'
    notes_path = MODULE_PATH / 'utils' / 'env_device_notes.yaml'
    shutil.copy(notes_path, env_path)
    os.environ[NOTES_VAR] = str(env_path)

    yield env_path

    os.environ.pop(NOTES_VAR)


def test_note_shadowing(qtbot: QtBot, user_notes_path: Path, env_notes_path: Path):
    # user data shadows all other sources
    notes_edit = TyphosNotesEdit()
    qtbot.addWidget(notes_edit)
    notes_edit.setup_data('Syn:Motor')
    assert 'user' in notes_edit.text()

    # no data in user, so fall back to data specified in env var
    accel_edit = TyphosNotesEdit()
    qtbot.addWidget(accel_edit)
    accel_edit.setup_data('Syn:Motor_acceleration')
    assert 'env' in accel_edit.text()


def test_env_note(qtbot: QtBot, env_notes_path: Path):
    # grab only data in env notes
    notes_edit = TyphosNotesEdit()
    qtbot.addWidget(notes_edit)
    notes_edit.setup_data('Syn:Motor')
    assert 'user' not in notes_edit.text()
    assert 'env' in notes_edit.text()

    accel_edit = TyphosNotesEdit()
    qtbot.addWidget(accel_edit)
    accel_edit.setup_data('Syn:Motor_acceleration')
    assert 'env' in accel_edit.text()


def test_user_note(qtbot: QtBot, user_notes_path: Path):
    # user data shadows all other sources
    notes_edit = TyphosNotesEdit()
    qtbot.addWidget(notes_edit)
    notes_edit.setup_data('Syn:Motor')
    assert 'user' in notes_edit.text()
    assert 'env' not in notes_edit.text()

    # no data in user, and nothing to fallback to
    accel_edit = TyphosNotesEdit()
    qtbot.addWidget(accel_edit)
    accel_edit.setup_data('Syn:Motor_acceleration')
    assert '' == accel_edit.text()


def test_note_edit(qtbot: QtBot, user_notes_path: Path):
    notes_edit = TyphosNotesEdit()
    qtbot.addWidget(notes_edit)
    notes_edit.setup_data('Syn:Motor')

    assert 'user' in notes_edit.text()

    notes_edit.setText('new user note')
    notes_edit.editingFinished.emit()
    with open(user_notes_path) as f:
        user_notes = yaml.full_load(f)

    assert 'new user note' == user_notes['Syn:Motor']['note']
