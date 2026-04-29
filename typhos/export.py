"""
Export a typhos screen as a PyDM Screen
"""

from lxml import etree
from ophyd.device import Device
from ophyd.signal import EpicsSignalBase
from qtpy.QtWidgets import QWidget

from .display import TyphosDeviceDisplay
from .panel import TyphosSignalPanel
from .utils import is_signal_ro
from .widgets import determine_widget_type


def from_generic_widget(source_widget: QWidget, name: str) -> etree._Element:
    """
    Replace most typhos widgets with blank QWidgets
    """
    widget = etree.Element("widget")
    widget.set("class", "QWidget")
    widget.set("name", name)
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

    for signal_name, signal_info in source_widget._panel_layout.signal_name_to_info.items():
        signal = signal_info["signal"]
        if not isinstance(signal, EpicsSignalBase):
            continue
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
        label_item.set("row", str(signal_info["row"]))
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
        readback_item.set("row", str(signal_info["row"]))
        readback_item.set("column", "1")
        readback_widget = etree.SubElement(readback_item, "widget")
        readback_widget.set("class", get_widget(read_cls))
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
        setpoint_item.set("row", str(signal_info["row"]))
        setpoint_item.set("column", "2")
        setpoint_widget = etree.SubElement(setpoint_item, "widget")
        setpoint_widget.set("class", get_widget(write_cls))
        setpoint_widget.set("name", f"{short_signal_name}_setpoint")
        setpoint_property = etree.SubElement(setpoint_widget, "property")
        setpoint_property.set("name", "channel")
        setpoint_string = etree.SubElement(setpoint_property, "string")
        setpoint_string.text = f"ca://{signal._write_pv.pvname}"  # type: ignore

    return widget


def get_widget(typhos_widget: QWidget) -> str:
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


DESIGNER_WIDGET_TO_XML = {
    "TyphosAlarmCircle": from_generic_widget,
    "TyphosAlarmEllipse": from_generic_widget,
    "TyphosAlarmPolygon": from_generic_widget,
    "TyphosAlarmRectangle": from_generic_widget,
    "TyphosAlarmTriangle": from_generic_widget,
    "TyphosCompositeSignalPanel": from_generic_widget,
    "TyphosDeviceDisplay": from_generic_widget,
    "TyphosDisplaySwitcher": from_generic_widget,
    "TyphosDisplayTitle": from_generic_widget,
    "TyphosHelpFrame": from_generic_widget,
    "TyphosMethodButton": from_generic_widget,
    "TyphosNotesEdit": from_generic_widget,
    "TyphosPositionerWidget": from_generic_widget,
    "TyphosPositionerRowWidget": from_generic_widget,
    "TyphosRelatedSuiteButton": from_generic_widget,
    "TyphosSignalPanel": from_typhos_signal_panel,
}


def from_template_and_device(template: str, device: Device) -> etree._ElementTree:
    """
    Generate a corresponding ui file xml tree from a source template and an ophyd device.
    """
    display = TyphosDeviceDisplay()
    display.force_template = template
    display.add_device(device)

    tree = etree.parse(template)
    root = tree.getroot()

    # Replace each typhos designer widget as appropriate
    for elem in root.findall(".//widget"):
        cls = str(elem.get("class"))
        try:
            converter = DESIGNER_WIDGET_TO_XML[cls]
        except KeyError:
            continue
        name = str(elem.get("name"))
        widget_obj = display.findChild(QWidget, name)
        new_elem = converter(widget_obj, name)
        parent_elem = elem.getparent()
        if parent_elem is None:
            continue
        parent_elem.replace(elem, new_elem)

    # Finalize the customwidgets section
    # TODO
    return tree


def test():
    from qtpy.QtWidgets import QApplication

    app = QApplication([])  # noqa: F841

    from pcdsdevices.epics_motor import BeckhoffAxis

    device = BeckhoffAxis("IM3L0:PPM:MMS", name="im3l0")
    template = "/cds/home/z/zlentz/github/typhos/typhos/ui/core/detailed_screen.ui"
    tree = from_template_and_device(template, device)
    etree.indent(tree, space=" ", level=0)
    text = etree.tostring(tree, pretty_print=True, encoding="unicode")

    un_macros = {device.prefix: "${prefix}", device.name: "${name}"}

    for unm, macro in un_macros.items():
        text = text.replace(unm, macro)

    print(text)
