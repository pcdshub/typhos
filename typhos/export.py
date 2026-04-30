"""
Export a typhos screen as a PyDM Screen
"""

import json
import logging

from lxml import etree
from ophyd.device import Device
from ophyd.signal import EpicsSignalBase
from qtpy.QtWidgets import QWidget

from .display import TyphosDeviceDisplay, TyphosDisplayTitle
from .panel import TyphosCompositeSignalPanel, TyphosSignalPanel
from .utils import is_signal_ro
from .widgets import determine_widget_type

logger = logging.getLogger(__name__)


def export_as_ui(display: TyphosDeviceDisplay, export_filename: str):
    """
    Main starting point for the export routine called from cli.

    This is meant to be run after generating the standard typhos suite but instead of
    building the main window and executing the QApplication.

    Parameters
    ----------
    suite : TyphosSuite
        The suite whose first display we'll use as an export.
    export_filename : str
        The destination filepath to save the .ui file.
    """
    device: Device = display.devices[0]

    tree = from_display(display)
    etree.indent(tree, space=" ", level=0)
    text = etree.tostring(tree, pretty_print=True, encoding="unicode")

    if display.macros:
        all_macros = {
            key: value
            for key, value in display.macros.items()
            if isinstance(key, str) and isinstance(value, str) and not key.startswith("_")
        }
    else:
        all_macros = {"prefix": device.prefix, "name": device.name}

    un_macros = {value: f"${{{key}}}" for key, value in all_macros.items()}

    for unm, macro in un_macros.items():
        text = text.replace(unm, macro)

    with open(export_filename, "w") as fd:
        fd.write(text)

    logger.info(f"Wrote file {export_filename}")

    used_macros = {key: value for key, value in all_macros.items() if un_macros[value] in text}

    logger.info(f"Run as pydm --macro '{json.dumps(used_macros)}' {export_filename}")


def from_display(display: TyphosDeviceDisplay) -> etree._ElementTree:
    """
    Generate a corresponding ui file xml tree from a source display.
    """
    template = str(display.current_template)
    tree = etree.parse(template)
    root = tree.getroot()

    logger.debug(f"Parsing display: searching for widgets in template {template}")

    # Replace each typhos designer widget as appropriate
    for elem in root.findall(".//widget"):
        name = str(elem.get("name"))
        logger.debug(f"Found widget named {name}")
        widget_obj = display.findChild(QWidget, name)
        try:
            new_elem = convert_widget_to_element(widget_obj, name)
        except TypeError:
            logger.debug(f"Widget {name} was not a replaceable widget type, skipping")
            continue
        parent_elem = elem.getparent()
        if parent_elem is None:
            continue
        parent_elem.replace(elem, new_elem)

    # Finalize the customwidgets section
    # TODO
    return tree


def convert_widget_to_element(source_widget: QWidget, name: str) -> etree._Element:
    """
    Choose which function to use to replace a typhos widget with an xml description of a standard widget.
    """
    try:
        type_name = source_widget.__class__.__name__
    except AttributeError:
        type_name = str(source_widget)
    match type_name:
        case "TyphosSignalPanel" | "TyphosCompositeSignalPanel":
            return from_typhos_composite_signal_panel(source_widget=source_widget, name=name)
        case "TyphosDisplayTitle":
            return from_typhos_display_title(source_widget=source_widget, name=name)
        case (
            "TyphosAlarmCircle"
            | "TyphosAlarmEllipse"
            | "TyphosAlarmPolygon"
            | "TyphosAlarmRectangle"
            | "TyphosAlarmTriangle"
            | "TyphosDisplaySwitcher"
            | "TyphosHelpFrame"
            | "TyphosMethodButton"
            | "TyphosNotesEdit"
            | "TyphosPositionerWidget"
            | "TyphosPositionerRowWidget"
            | "TyphosRelatedSuiteButton"
        ):
            return from_generic_widget(source_widget=source_widget, name=name)
        case _:
            err = f"Unhandled type for {source_widget} of type {type_name}"
            logger.debug(err)
            raise TypeError(err)


def from_generic_widget(source_widget: QWidget, name: str) -> etree._Element:
    """
    Replace most typhos widgets with blank QWidgets
    """
    logger.debug(f"Replace {name} with generic QWidget")
    widget = create_widget_named(name=name, cls="QWidget")

    # Match the size of the original widget just so the screen is recognizable
    original_size = source_widget.sizeHint()
    add_size_property(
        widget=widget, size_name="minimumSize", width=original_size.width(), height=original_size.height()
    )
    add_size_property(
        widget=widget, size_name="maximumSize", width=original_size.width(), height=original_size.height()
    )

    return widget


def from_typhos_display_title(source_widget: TyphosDisplayTitle, name: str) -> etree._Element:
    """
    Just the device name I guess
    """
    logger.debug(f"Replace {name} with title QLabel")
    widget = create_widget_named(name=name, cls="QLabel")
    add_string_property(widget=widget, prop_name="text", prop_value=source_widget.device_display.devices[0].name)
    return widget


def from_typhos_composite_signal_panel(
    source_widget: TyphosSignalPanel | TyphosCompositeSignalPanel, name: str
) -> etree._Element:
    """
    Replace TyphosCompositeSignalPanel with repeated applications of what we do for typhos signal panel

    This also works from TyphosSignalPanel, which is a subset of the composite panel.
    """
    # The composite signal panel works by:
    # 1. call add_device once
    # 2. For each top-level component in order, call add_sub_device if it's a device or _maybe_add_signal otherwise
    # 2a. add_sub_device creates a mini TyphosDeviceDisplay with the subdevice
    #     this subdisplay is a whole new template for us to deal with
    # 2b. _maybe_add_signal, for this purposes of this screen, will add the signal if it matches the kind settings
    #     it has some other behavior otherwise, but it is only relevant for the display switcher we won't support here
    # Note that each thing is added as a new row in a grid layout- so that's our outer structure, a grid
    # We'll try to build this using the primitives we implemented above
    logger.debug(f"Exploring contents of composite signal panel {name}")

    widget = create_widget_named(name=name, cls="QWidget")
    grid = add_grid_layout(widget=widget, layout_name=f"{name}_grid_layout")

    device_name = source_widget.devices[0].name

    # Iterate through the rows in the grid layout
    # Three possibilities:
    # 1. a TyphosDeviceDisplay spanning all columns
    # 2. a Qlabel in col 0, then a readback widget in cols 1-2
    # 3. a Qlabel in col 0, a readback widget in col 1, a setpoint widget in col 2
    # For 1 we can use the display xml builder, but strip out everything except the main widget
    # For 2 and 3 we can use the per-row behavior from the signal panel function

    grid_layout = source_widget._panel_layout
    signal_info_list = list(grid_layout.signal_name_to_info.values())
    output_row = -1

    for row_count in range(grid_layout.rowCount()):
        logger.debug(f"Checking grid row index {row_count}")
        first_item = grid_layout.itemAtPosition(row_count, 0)
        if first_item is None:
            logger.debug("No item in row, skipping")
            continue
        first_widget = first_item.widget()
        if first_widget is None:
            logger.debug("No widget in row, skipping")
            continue
        logger.debug(f"Found {first_widget} named {first_widget.objectName()} on row {row_count}")
        if isinstance(first_widget, TyphosDeviceDisplay):
            output_row += 1
            logger.debug(f"Expanding subdisplay on input row {row_count} for output row {output_row}")
            # A device subdisplay
            tree = from_display(display=first_widget)
            root = tree.getroot()
            top_widget = root.find("widget")
            if top_widget is None:
                raise RuntimeError("Display had no top-level widget?")
            subdisplay_item = etree.SubElement(grid, "item")
            subdisplay_item.set("row", str(output_row))
            subdisplay_item.set("column", "0")
            subdisplay_item.set("colspan", "3")
            subdisplay_item.append(top_widget)
        else:
            logger.debug(f"Expanding signal on row {row_count}")
            # A signal row
            signal_info = None
            for info in signal_info_list:
                if info["row"] == row_count:
                    # We found it
                    signal_info = info
            if signal_info is None:
                raise RuntimeError(f"No signal info for row {row_count}")
            if signal_info["signal"] is None:
                logger.debug(f"Skipping signal info {signal_info}, no signal created")
                continue
            logger.debug(f"Using signal info {signal_info}")

            signal = signal_info["signal"]
            signal_name = signal.name
            if not isinstance(signal, EpicsSignalBase):
                logger.debug("Not an epics signal, skipping")
                continue
            output_row += 1
            logger.debug(f"Assigning output row count {output_row}")
            add_signal_row_to_grid(
                signal_name=signal_name, signal_info=signal_info, device_name=device_name, grid=grid, row=output_row
            )

    return widget


def add_signal_row_to_grid(signal_name: str, signal_info: dict, device_name: str, grid: etree._Element, row: int):
    signal = signal_info["signal"]
    if is_signal_ro(signal):
        logger.debug("Picking read-only widgets")
        read_cls, _ = determine_widget_type(signal=signal, read_only=True)
        write_cls = None
    else:
        logger.debug("Picking read-write widgets")
        read_cls, _ = determine_widget_type(signal=signal, read_only=True)
        write_cls, _ = determine_widget_type(signal=signal, read_only=False)

    short_signal_name = signal_name.removeprefix(device_name + "_")
    if short_signal_name == device_name:
        short_signal_name = "device"
        short_signal_text = device_name
    else:
        short_signal_text = short_signal_name

    # First item in row: signal name
    label_widget = create_widget_in_grid(name=f"{short_signal_name}_label", cls="QLabel", grid=grid, row=row, col=0)
    add_string_property(widget=label_widget, prop_name="text", prop_value=short_signal_text)
    # Second item in row: readback widget
    # Extend to end of no third item in row
    if write_cls is None:
        colspan = 2
    else:
        colspan = 0
    readback_widget = create_widget_in_grid(
        name=f"{short_signal_name}_readback",
        cls=typhos_type_to_pydm_type(read_cls),
        grid=grid,
        row=row,
        col=1,
        colspan=colspan,
    )
    add_string_property(widget=readback_widget, prop_name="channel", prop_value=f"ca://{signal_info['signal'].pvname}")
    if write_cls is None:
        return
    # Third item in row: setpoint widget
    setpoint_widget = create_widget_in_grid(
        name=f"{short_signal_name}_setpoint", cls=typhos_type_to_pydm_type(write_cls), grid=grid, row=row, col=2
    )
    add_string_property(widget=setpoint_widget, prop_name="channel", prop_value=f"ca://{signal._write_pv.pvname}")  # type: ignore


def typhos_type_to_pydm_type(typhos_widget: QWidget) -> str:
    match str(typhos_widget.__name__):
        case "PyDMLabel" | "TyphosLabel" | "WaveformDialogButton" | "ImageDialogButton":
            return "PyDMLabel"
        case "TyphosComboBox":
            return "PyDMEnumComboBox"
        case "PyDMPushButton" | "TyphosCommandButton":
            return "PyDMPushButton"
        case "PyDMEnumButton" | "TyphosCommandEnumButton":
            return "PyDMEnumButton"
        case "PyDMByteIndicator" | "TyphosByteIndicator" | "TyphosCommandIndicator" | "TyphosByteSetpoint":
            return "PyDMByteIndicator"
        case "PyDMSlider" | "TyphosScalarRange":
            return "PyDMSlider"
        case "PyDMWaveformTable" | "TyphosArrayTable":
            return "PyDMWaveformTable"
        case _:
            return "PyDMLineEdit"


def create_widget_named(name: str, cls: str, parent: etree._Element | None = None) -> etree._Element:
    """
    Building block: returns a new widget element.
    """
    if parent is None:
        widget = etree.Element("widget")
    else:
        widget = etree.SubElement(parent, "widget")
    # Set outside of kwargs to mimic designer order and avoid "class" keyword
    widget.set("class", cls)
    widget.set("name", name)
    return widget


def add_string_property(widget: etree._Element, prop_name: str, prop_value: str) -> etree._Element:
    """
    Building block: adds a string property to a widget element and returns the property.
    """
    prop_elem = etree.SubElement(widget, "property", name=prop_name)
    string_elem = etree.SubElement(prop_elem, "string")
    string_elem.text = prop_value
    return prop_elem


def add_size_property(widget: etree._Element, size_name: str, width: int, height: int) -> etree._Element:
    """
    Building block: adds a property with a width and height and returns the property.
    """
    prop_elem = etree.SubElement(widget, "property", name=size_name)
    size_elem = etree.SubElement(prop_elem, "size")
    width_elem = etree.SubElement(size_elem, "width")
    width_elem.text = str(width)
    height_elem = etree.SubElement(size_elem, "width")
    height_elem.text = str(height)
    return prop_elem


def add_grid_layout(widget: etree._Element, layout_name: str) -> etree._Element:
    """
    Building block: adds a grid layout to a widget element and returns the grid layout.
    """
    grid_layout = etree.SubElement(widget, "layout")
    # Set outside of kwargs to mimic designer order and avoid "class" keyword
    grid_layout.set("class", "QGridLayout")
    grid_layout.set("name", layout_name)
    return grid_layout


def add_item_to_grid(grid: etree._Element, row: int, col: int, colspan: int = 0) -> etree._Element:
    """
    Building block: adds an item to a grid layout and returns it. Items can hold widgets.
    """
    grid_item = etree.SubElement(grid, "item", row=str(row), column=str(col))
    if colspan:
        grid_item.set("colspan", str(colspan))
    return grid_item


def create_widget_in_grid(
    name: str, cls: str, grid: etree._Element, row: int, col: int, colspan: int = 0
) -> etree._Element:
    """
    Building block: creates a new widget and a new grid item all at once. Returns the widget.
    """
    grid_item = add_item_to_grid(grid=grid, row=row, col=col, colspan=colspan)
    widget = create_widget_named(name=name, cls=cls, parent=grid_item)
    return widget
