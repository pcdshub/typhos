from __future__ import annotations

import os
import pathlib
import tempfile

import pytest
from ophyd import Component as Cpt
from ophyd import Device
from qtpy.QtCore import QRect
from qtpy.QtGui import QPaintEvent
from qtpy.QtWidgets import QWidget

import typhos
import typhos.utils
from typhos.utils import (TyphosBase, clean_name, compose_stylesheets,
                          load_suite, no_device_lazy_load, saved_template,
                          use_stylesheet)

from . import conftest


class NestedDevice(Device):
    phi = Cpt(Device)


class LayeredDevice(Device):
    radial = Cpt(NestedDevice)


def test_clean_name():
    device = LayeredDevice(name='test')
    assert clean_name(device.radial, strip_parent=False) == 'test radial'
    assert clean_name(device.radial, strip_parent=True) == 'radial'
    assert clean_name(device.radial.phi,
                      strip_parent=False) == 'test radial phi'
    assert clean_name(device.radial.phi, strip_parent=True) == 'phi'
    assert clean_name(device.radial.phi, strip_parent=device) == 'radial phi'


@pytest.mark.parametrize("dark", [True, False])
@pytest.mark.parametrize("include_pydm", [True, False])
@pytest.mark.parametrize("pydm_include_default", [True, False])
@pytest.mark.parametrize(
    "pydm_stylesheet",
    [
        "",
        str(conftest.MODULE_PATH / "utils" / "big_stylesheet.qss"),
        str(conftest.MODULE_PATH / "utils" / "big_stylesheet.qss")
        + os.pathsep
        + str(conftest.MODULE_PATH / "utils" / "big_stylesheet.qss"),
    ],
)
@pytest.mark.parametrize(
    "explicit_path",
    [None, str(conftest.MODULE_PATH / "utils" / "tiny_stylesheet.qss")],
)
def test_stylesheet(
    qtbot,
    monkeypatch,
    dark: bool,
    include_pydm: bool,
    pydm_include_default: bool,
    pydm_stylesheet: str,
    explicit_path: str | None,
):
    widget = QWidget()
    qtbot.addWidget(widget)
    original_stylesheet = "QPushButton { color: red }"
    widget.setStyleSheet(original_stylesheet)

    monkeypatch.setattr(typhos.utils, "PYDM_INCLUDE_DEFAULT", pydm_include_default)
    monkeypatch.setattr(typhos.utils, "PYDM_USER_STYLESHEET", pydm_stylesheet)

    compose_stylesheets(
        dark=dark,
        path=explicit_path,
        include_pydm=include_pydm,
        widget=widget,
    )
    new_stylesheet = widget.styleSheet()

    assert original_stylesheet in new_stylesheet, "Original stylesheet was deleted"
    if dark:
        assert "qdarkstyle.qss" in new_stylesheet, "Dark stylesheet did not load"
    else:
        assert "TyphosBase" in new_stylesheet, "Typhos stylesheet did not load"

    if include_pydm and pydm_include_default:
        assert "PyDMDrawing" in new_stylesheet, "PyDM default stylesheet did not load"
    else:
        assert "PyDMDrawing" not in new_stylesheet, "PyDM default stylesheet loaded unexpectedly"

    if include_pydm and pydm_stylesheet:
        assert "ApertureValve" in new_stylesheet, "PyDM user stylesheet did not load"
    else:
        assert "ApertureValve" not in new_stylesheet, "PyDM user stylesheet loaded unexpectedly"

    if explicit_path:
        assert "tiny test stylesheet" in new_stylesheet, "Explicit user stylesheet did not load"
    else:
        assert "tiny test stylesheet" not in new_stylesheet, "Explicit user stylesheet loaded unexpectedly"


def test_stylesheet_legacy(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    use_stylesheet(widget=widget)
    use_stylesheet(widget=widget, dark=True)


def test_typhosbase_repaint_smoke(qtbot):
    tp = TyphosBase()
    qtbot.addWidget(tp)
    pe = QPaintEvent(QRect(1, 2, 3, 4))
    tp.paintEvent(pe)


def test_load_suite(qtbot, happi_cfg):
    # Setup new saved file
    module = saved_template.format(devices=['test_motor'])
    module_file = str(pathlib.Path(tempfile.gettempdir()) / 'my_suite.py')
    with open(module_file, 'w+') as handle:
        handle.write(module)

    suite = load_suite(module_file, happi_cfg)
    qtbot.addWidget(suite)
    assert isinstance(suite, typhos.TyphosSuite)
    assert len(suite.devices) == 1
    assert suite.devices[0].name == 'test_motor'
    os.remove(module_file)


def test_load_suite_with_bad_py_file():
    with pytest.raises(AttributeError):
        load_suite(typhos.utils.__file__)


def test_no_device_lazy_load():
    class TestDevice(Device):
        c = Cpt(Device, suffix='Test')

    dev = TestDevice(name='foo')

    old_val = Device.lazy_wait_for_connection
    assert dev.lazy_wait_for_connection is old_val
    assert dev.c.lazy_wait_for_connection is old_val

    with no_device_lazy_load():
        dev2 = TestDevice(name='foo')

        assert Device.lazy_wait_for_connection is False
        assert dev2.lazy_wait_for_connection is False
        assert dev2.c.lazy_wait_for_connection is False

    assert Device.lazy_wait_for_connection is old_val
    assert dev.lazy_wait_for_connection is old_val
    assert dev.c.lazy_wait_for_connection is old_val


class Class1:
    ...


Class1.full_name = Class1.__module__ + '.' + Class1.__name__


@pytest.mark.parametrize(
    'cls, view_type, expected, create',
    [pytest.param(
        Class1, 'detailed',
        # Expected
        ['Class1.detailed.ui'],
        # Create these:
        ['foo.bar.ui', 'Class1.detailed.ui'],
    ),
        pytest.param(
        Class1, 'detailed',
        # Expected
        [Class1.full_name + '.detailed.ui', 'Class1.detailed.ui',
         'Class1.ui'],
        # Create these:
        ['a.ui', Class1.full_name + '.detailed.ui', 'Class1.detailed.ui',
         'Class1.ui'],
    ),
        pytest.param(
        Class1, 'detailed',
        # Expected
        [Class1.full_name + '.detailed.ui', 'Class1.detailed.ui'],
        # Create these:
        [Class1.full_name + '.detailed.ui', 'b.ui', 'Class1.detailed.ui'],
    ),
        pytest.param(
        Class1, 'detailed',
        # Expected
        ['Class1.ui'],
        # Create these:
        ['Class1.ui', 'c.ui', 'Class1.engineering.ui'],
    ),
        pytest.param(
        Class1, 'detailed',
        # Expected
        ['Class1.py', 'Class1.ui'],
        # Create these:
        ['Class1.ui', 'Class1.py', 'c.ui', 'Class1.engineering.ui'],
    ),
    ]
)
def test_path_search(tmpdir, cls, view_type, create, expected):
    for to_create in create:
        file = tmpdir.join(to_create)
        file.write('')

    results = typhos.utils.find_templates_for_class(
        cls, view_type, paths=[tmpdir])

    assert list(r.name for r in results) == expected
