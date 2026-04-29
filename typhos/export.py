"""
Export a typhos screen as a PyDM Screen
"""

from lxml import etree
from ophyd.device import Device
from ophyd.signal import EpicsSignalBase
from qtpy.QtWidgets import QWidget

from typhos.alarm import (
    TyphosAlarmCircle,
    TyphosAlarmEllipse,
    TyphosAlarmPolygon,
    TyphosAlarmRectangle,
    TyphosAlarmTriangle,
)
from typhos.func import TyphosMethodButton
from typhos.notes import TyphosNotesEdit
from typhos.positioner import TyphosPositionerRowWidget, TyphosPositionerWidget
from typhos.related_display import TyphosRelatedSuiteButton

from .display import TyphosDeviceDisplay, TyphosDisplaySwitcher, TyphosDisplayTitle, TyphosHelpFrame
from .panel import TyphosCompositeSignalPanel, TyphosSignalPanel
from .utils import is_signal_ro
from .widgets import determine_widget_type


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
        un_macros = {
            value: f"${{{key}}}"
            for key, value in display.macros.items()
            if isinstance(key, str) and isinstance(value, str) and not key.startswith("_")
        }
    else:
        un_macros = {device.prefix: "${prefix}", device.name: "${name}"}

    for unm, macro in un_macros.items():
        text = text.replace(unm, macro)

    with open(export_filename, "w") as fd:
        fd.write(text)


def from_display(display: TyphosDeviceDisplay) -> etree._ElementTree:
    """
    Generate a corresponding ui file xml tree from a source display.
    """
    template = str(display.current_template)
    tree = etree.parse(template)
    root = tree.getroot()

    # Replace each typhos designer widget as appropriate
    for elem in root.findall(".//widget"):
        name = str(elem.get("name"))
        widget_obj = display.findChild(QWidget, name)
        try:
            new_elem = convert_widget_to_element(widget_obj, name)
        except TypeError:
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
    match source_widget:
        case TyphosSignalPanel():
            return from_typhos_signal_panel(source_widget=source_widget, name=name)
        case TyphosCompositeSignalPanel():
            return from_generic_widget(source_widget=source_widget, name=name)
        case TyphosDisplayTitle():
            return from_typhos_display_title(source_widget=source_widget, name=name)
        case (
            TyphosAlarmCircle()
            | TyphosAlarmEllipse()
            | TyphosAlarmPolygon()
            | TyphosAlarmRectangle()
            | TyphosAlarmTriangle()
            | TyphosDisplaySwitcher()
            | TyphosHelpFrame()
            | TyphosMethodButton()
            | TyphosNotesEdit()
            | TyphosPositionerWidget()
            | TyphosPositionerRowWidget()
            | TyphosRelatedSuiteButton()
        ):
            return from_generic_widget(source_widget=source_widget, name=name)
        case _:
            raise TypeError(f"Unhandled type for {source_widget}")


def from_generic_widget(source_widget: QWidget, name: str) -> etree._Element:
    """
    Replace most typhos widgets with blank QWidgets
    """
    widget = etree.Element("widget")
    widget.set("class", "QWidget")
    widget.set("name", name)
    return widget


def from_typhos_display_title(source_widget: TyphosDisplayTitle, name: str) -> etree._Element:
    """
    Just the device name I guess
    """
    widget = etree.Element("widget")
    widget.set("class", "QLabel")
    widget.set("name", name)
    text_property = etree.SubElement(widget, "property")
    text_property.set("name", "text")
    text_string = etree.SubElement(text_property, "string")
    text_string.text = source_widget.device_display.devices[0].name
    return widget


def from_typhos_signal_panel(source_widget: TyphosSignalPanel, name: str) -> etree._Element:
    """
    Replace TyphosSignalPanel with a QWidget containing a simple QGridLayout
    """
    widget = etree.Element("widget")
    widget.set("class", "QWidget")
    widget.set("name", name)
    grid = etree.SubElement(widget, "layout")
    grid.set("class", "QGridLayout")
    grid.set("name", f"{name}_grid_layout")

    device_name = source_widget.devices[0].name
    device_name_prefix = device_name + "_"

    row = -1

    for signal_name, signal_info in source_widget._panel_layout.signal_name_to_info.items():
        signal = signal_info["signal"]
        if not isinstance(signal, EpicsSignalBase):
            continue
        row += 1
        if is_signal_ro(signal):
            read_cls, _ = determine_widget_type(signal=signal, read_only=True)
            write_cls = None
        else:
            read_cls, _ = determine_widget_type(signal=signal, read_only=True)
            write_cls, _ = determine_widget_type(signal=signal, read_only=False)

        short_signal_name = signal_name.removeprefix(device_name_prefix)
        if short_signal_name == device_name:
            short_signal_name = "device"
            short_signal_text = device_name
        else:
            short_signal_text = short_signal_name

        # First item in row: signal name
        label_item = etree.SubElement(grid, "item")
        label_item.set("row", str(row))
        label_item.set("column", "0")
        label_widget = etree.SubElement(label_item, "widget")
        label_widget.set("class", "QLabel")
        label_widget.set("name", f"{short_signal_name}_label")
        label_property = etree.SubElement(label_widget, "property")
        label_property.set("name", "text")
        label_string = etree.SubElement(label_property, "string")
        label_string.text = short_signal_text
        # Second item in row: readback widget
        readback_item = etree.SubElement(grid, "item")
        readback_item.set("row", str(row))
        readback_item.set("column", "1")
        readback_widget = etree.SubElement(readback_item, "widget")
        readback_widget.set("class", typhos_type_to_pydm_type(read_cls))
        readback_widget.set("name", f"{short_signal_name}_readback")
        readback_property = etree.SubElement(readback_widget, "property")
        readback_property.set("name", "channel")
        readback_string = etree.SubElement(readback_property, "string")
        readback_string.text = f"ca://{signal_info['signal'].pvname}"
        # Extend to end of no third item in row
        if write_cls is None:
            readback_item.set("colspan", "2")
            continue
        # Third item in row: setpoint widget
        setpoint_item = etree.SubElement(grid, "item")
        setpoint_item.set("row", str(row))
        setpoint_item.set("column", "2")
        setpoint_widget = etree.SubElement(setpoint_item, "widget")
        setpoint_widget.set("class", typhos_type_to_pydm_type(write_cls))
        setpoint_widget.set("name", f"{short_signal_name}_setpoint")
        setpoint_property = etree.SubElement(setpoint_widget, "property")
        setpoint_property.set("name", "channel")
        setpoint_string = etree.SubElement(setpoint_property, "string")
        setpoint_string.text = f"ca://{signal._write_pv.pvname}"  # type: ignore

    return widget


def typhos_type_to_pydm_type(typhos_widget: QWidget) -> str:
    match str(typhos_widget.__name__):
        case "PyDMLabel" | "TyphosLabel" | "WaveformDialogButton" | "ImageDialogButton":
            return "PyDMLabel"
        case "PyDMLabel" | "TyphosComboBox":
            return "PyDMLabel"
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
