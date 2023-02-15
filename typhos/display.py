"""Contains the main display widget used for representing an entire device."""

import enum
import inspect
import logging
import os
import pathlib
import webbrowser
from typing import List, Optional, Union

import ophyd
import pcdsutils
import pydm.display
import pydm.exception
import pydm.utilities
from pcdsutils.qt import forward_property
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Q_ENUMS, Property, Qt, Slot

from . import cache
from . import panel as typhos_panel
from . import utils, web, widgets
from .jira import TyphosJiraIssueWidget
from .plugins.core import register_signal

logger = logging.getLogger(__name__)


class DisplayTypes(enum.IntEnum):
    """Enumeration of template types that can be used in displays."""

    embedded_screen = 0
    detailed_screen = 1
    engineering_screen = 2


_DisplayTypes = utils.pyqt_class_from_enum(DisplayTypes)
DisplayTypes.names = [view.name for view in DisplayTypes]


class ScrollOptions(enum.IntEnum):
    """Enumeration of scrollable options for displays."""

    auto = 0
    scrollbar = 1
    no_scroll = 2


_ScrollOptions = utils.pyqt_class_from_enum(ScrollOptions)
ScrollOptions.names = [view.name for view in ScrollOptions]


DEFAULT_TEMPLATES = {
    name: [(utils.ui_dir / 'core' / f'{name}.ui').resolve()]
    for name in DisplayTypes.names
}

DETAILED_TREE_TEMPLATE = (utils.ui_dir / 'core' / 'detailed_tree.ui').resolve()
DEFAULT_TEMPLATES['detailed_screen'].append(DETAILED_TREE_TEMPLATE)

DEFAULT_TEMPLATES_FLATTEN = [f for _, files in DEFAULT_TEMPLATES.items()
                             for f in files]


def normalize_display_type(
    display_type: Union[DisplayTypes, str, int]
) -> DisplayTypes:
    """
    Normalize a given display type.

    Parameters
    ----------
    display_type : DisplayTypes, str, or int
        The display type.

    Returns
    -------
    display_type : DisplayTypes
        The normalized :class:`DisplayTypes`.

    Raises
    ------
    ValueError
        If the input cannot be made a :class:`DisplayTypes`.
    """
    try:
        return DisplayTypes(display_type)
    except ValueError:
        try:
            return DisplayTypes[display_type]
        except KeyError:
            raise ValueError(
                f'Unrecognized display type: {display_type}'
            )


def normalize_scroll_option(
    scroll_option: Union[ScrollOptions, str, int]
) -> ScrollOptions:
    """
    Normalize a given scroll option.

    Parameters
    ----------
    display_type : ScrollOptions, str, or int
        The display type.

    Returns
    -------
    display_type : ScrollOptions
        The normalized :class:`ScrollOptions`.

    Raises
    ------
    ValueError
        If the input cannot be made a :class:`ScrollOptions`.
    """
    try:
        return ScrollOptions(scroll_option)
    except ValueError:
        try:
            return ScrollOptions[scroll_option]
        except KeyError:
            raise ValueError(
                f'Unrecognized scroll option: {scroll_option}'
            )


class TyphosToolButton(QtWidgets.QToolButton):
    """
    Base class for tool buttons used in the TyphosDisplaySwitcher.

    Parameters
    ----------
    icon : QIcon or str, optional
        See :meth:`.get_icon` for options.

    parent : QtWidgets.QWidget, optional
        The parent widget.

    Attributes
    ----------
    DEFAULT_ICON : str
        The default icon from fontawesome to use.
    """

    DEFAULT_ICON = 'circle'

    def __init__(self, icon=None, *, parent=None):
        super().__init__(parent=parent)

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu
        self.clicked.connect(self._clicked)
        self.setIcon(self.get_icon(icon))
        self.setMinimumSize(24, 24)

    def _clicked(self):
        """Clicked callback: override in a subclass."""
        menu = self.generate_context_menu()
        if menu:
            menu.exec_(QtGui.QCursor.pos())

    def generate_context_menu(self):
        """Context menu request: override in subclasses."""
        return None

    @classmethod
    def get_icon(cls, icon=None):
        """
        Get a QIcon, if specified, or fall back to the default.

        Parameters
        ----------
        icon : str or QtGui.QIcon
            If a string, assume it is from fontawesome.
            Otherwise, use the icon instance as-is.
        """
        icon = icon or cls.DEFAULT_ICON
        if isinstance(icon, str):
            return pydm.utilities.IconFont().icon(icon)
        return icon

    def open_context_menu(self, ev):
        """
        Open the instance-specific context menu.

        Parameters
        ----------
        ev : QEvent
        """
        menu = self.generate_context_menu()
        if menu:
            menu.exec_(self.mapToGlobal(ev.pos()))


class TyphosDisplayConfigButton(TyphosToolButton):
    """
    The configuration button used in the :class:`TyphosDisplaySwitcher`.

    This uses the common "vertical ellipse" icon by default.
    """

    DEFAULT_ICON = 'ellipsis-v'

    _kind_to_property = typhos_panel.TyphosSignalPanel._kind_to_property

    def __init__(self, icon=None, *, parent=None):
        super().__init__(icon=icon, parent=parent)
        self.setPopupMode(self.InstantPopup)
        self.setArrowType(Qt.NoArrow)
        self.templates = None
        self.device_display = None

    def set_device_display(self, device_display):
        """Typhos callback: set the :class:`TyphosDeviceDisplay`."""
        self.device_display = device_display

    def create_kind_filter_menu(self, panels, base_menu, *, only):
        """
        Create the "Kind" filter menu.

        Parameters
        ----------
        panels : list of TyphosSignalPanel
            The panels to filter upon triggering of menu actions.

        base_menu : QMenu
            The menu to add actions to.

        only : bool
            False - create "Show Kind" actions.
            True - create "Show only Kind" actions.
        """
        for kind, prop in self._kind_to_property.items():
            def selected(new_value, *, prop=prop):
                if only:
                    # Show *only* the specific kind for all panels
                    for kind, current_prop in self._kind_to_property.items():
                        visible = (current_prop == prop)
                        for panel in panels:
                            setattr(panel, current_prop, visible)
                else:
                    # Toggle visibility of the specific kind for all panels
                    for panel in panels:
                        setattr(panel, prop, new_value)
                self.hide_empty()

            title = f'Show only &{kind}' if only else f'Show &{kind}'
            action = base_menu.addAction(title)
            if not only:
                action.setCheckable(True)
                action.setChecked(all(getattr(panel, prop)
                                      for panel in panels))
            action.triggered.connect(selected)

    def create_name_filter_menu(self, panels, base_menu):
        """
        Create the name-based filtering menu.

        Parameters
        ----------
        panels : list of TyphosSignalPanel
            The panels to filter upon triggering of menu actions.

        base_menu : QMenu
            The menu to add actions to.
        """
        def text_filter_updated():
            text = line_edit.text().strip()
            for panel in panels:
                panel.nameFilter = text
            self.hide_empty()

        line_edit = QtWidgets.QLineEdit()

        filters = list(set(panel.nameFilter for panel in panels
                           if panel.nameFilter))
        if len(filters) == 1:
            line_edit.setText(filters[0])
        else:
            line_edit.setPlaceholderText('/ '.join(filters))

        line_edit.editingFinished.connect(text_filter_updated)
        line_edit.setObjectName('menu_action')

        action = base_menu.addAction('Filter by name:')
        action.setEnabled(False)

        action = QtWidgets.QWidgetAction(self)
        action.setDefaultWidget(line_edit)
        base_menu.addAction(action)

    def hide_empty(self, search=True):
        """
        Wrap hide_empty calls for use with search functions and action clicks.

        Parameters
        ----------
        search : bool
            Whether or not this method is being called from a search/filter
            method.
        """
        if self.device_display.hideEmpty:
            if search:
                show_empty(self.device_display)
            hide_empty(self.device_display, process_widget=False)

    def create_hide_empty_menu(self, panels, base_menu):
        """
        Create the hide empty filtering menu.

        Parameters
        ----------
        panels : list of TyphosSignalPanel
            The panels to filter upon triggering of menu actions.

        base_menu : QMenu
            The menu to add actions to.
        """
        def handle_menu(checked):
            self.device_display.hideEmpty = checked

            if not checked:
                # Force a reboot of the filters
                # since we no longer can figure what was supposed to be
                # visible or not
                for p in panels:
                    p._update_panel()
                show_empty(self.device_display)
            else:
                self.hide_empty(search=False)

        action = base_menu.addAction('Hide Empty Panels')
        action.setCheckable(True)
        action.setChecked(self.device_display.hideEmpty)
        action.triggered.connect(handle_menu)

    def generate_context_menu(self):
        """
        Generate the custom context menu.

        .. code::

            Embedded
            Detailed
            Engineering
            -------------
            Refresh templates
            -------------
            Kind filter > Show hinted
                          ...
                          Show only hinted
            Filter by name
            Hide Empty Panels
        """
        base_menu = QtWidgets.QMenu(parent=self)

        display = self.device_display
        if not display:
            return base_menu

        base_menu.addSection('Templates')
        display._generate_template_menu(base_menu)

        panels = display.findChildren(typhos_panel.TyphosSignalPanel) or []
        if not panels:
            return base_menu

        base_menu.addSection('Filters')
        filter_menu = base_menu.addMenu("&Kind filter")
        self.create_kind_filter_menu(panels, filter_menu, only=False)
        filter_menu.addSeparator()
        self.create_kind_filter_menu(panels, filter_menu, only=True)

        self.create_name_filter_menu(panels, base_menu)

        base_menu.addSeparator()
        self.create_hide_empty_menu(panels, base_menu)

        if utils.DEBUG_MODE:
            base_menu.addSection('Debug')
            action = base_menu.addAction('&Copy to clipboard')
            action.triggered.connect(display.copy_to_clipboard)

        return base_menu


class TyphosDisplaySwitcherButton(TyphosToolButton):
    """A button which switches the TyphosDeviceDisplay template on click."""

    template_selected = QtCore.Signal(pathlib.Path)

    icons = {'embedded_screen': 'compress',
             'detailed_screen': 'braille',
             'engineering_screen': 'cogs'
             }

    def __init__(self, display_type, *, parent=None):
        super().__init__(icon=self.icons[display_type], parent=parent)
        self.templates = None

    def _clicked(self):
        """Clicked callback - set the template."""
        if self.templates is None:
            logger.warning('set_device_display not called on %s', self)
            return

        try:
            template = self.templates[0]
        except IndexError:
            return

        self.template_selected.emit(template)

    def generate_context_menu(self):
        """Context menu request."""
        if not self.templates:
            return

        menu = QtWidgets.QMenu(parent=self)

        duplicates = utils.find_duplicate_filenames_in_paths(self.templates)

        for template in self.templates:
            def selected(*, template=template):
                self.template_selected.emit(template)
            if template.name in duplicates:
                action = menu.addAction(str(template))
            else:
                action = menu.addAction(template.name)
            action.triggered.connect(selected)

        return menu


class TyphosDisplaySwitcher(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """Display switcher set of buttons for use with a TyphosDeviceDisplay."""

    template_selected = QtCore.Signal(pathlib.Path)

    def __init__(self, parent=None, **kwargs):
        # Intialize background variable
        super().__init__(parent=None)

        self.device_display = None
        self.buttons = {}
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.contextMenuEvent = self.open_context_menu

        if parent:
            self.setParent(parent)

        self._create_ui()

    def _create_ui(self):
        layout = self.layout()
        self.buttons.clear()
        self.help_button = None
        self.config_button = None

        self.help_toggle_button = TyphosHelpToggleButton()
        layout.addWidget(self.help_toggle_button, 0, Qt.AlignRight)

        for template_type in DisplayTypes.names:
            button = TyphosDisplaySwitcherButton(template_type)
            self.buttons[template_type] = button
            button.template_selected.connect(self._template_selected)
            layout.addWidget(button, 0, Qt.AlignRight)

            friendly_name = template_type.replace('_', ' ')
            button.setToolTip(f'Switch to {friendly_name}')

        self.config_button = TyphosDisplayConfigButton()
        layout.addWidget(self.config_button, 0, Qt.AlignRight)
        self.config_button.setToolTip('Display settings...')

    def _template_selected(self, template):
        """Template selected hook."""
        self.template_selected.emit(template)
        if self.device_display is not None:
            self.device_display.force_template = template

    def set_device_display(self, display):
        """Typhos hook for setting the associated device display."""
        self.device_display = display

        for template_type in self.buttons:
            templates = display.templates.get(template_type, [])
            self.buttons[template_type].templates = templates
        self.config_button.set_device_display(display)

    def add_device(self, device):
        """Typhos hook for setting the associated device."""
        ...


class TyphosTitleLabel(QtWidgets.QLabel):
    """
    A label class intended for use as a standardized title.

    Attributes
    ----------
    toggle_requested : QtCore.Signal
        A Qt signal indicating that the user clicked on the title.  By default,
        this hides any nested panels underneath the title.
    """

    toggle_requested = QtCore.Signal()

    def mousePressEvent(self, event):
        """Overridden qt hook for a mouse press."""
        if event.button() == Qt.LeftButton:
            self.toggle_requested.emit()

        super().mousePressEvent(event)


class TyphosHelpToggleButton(TyphosToolButton):
    """
    A standard button used to toggle help information display.

    Attributes
    ----------
    pop_out : QtCore.Signal
        A Qt signal indicating a request to pop out the help widget.

    open_in_browser : QtCore.Signal
        A Qt signal indicating a request to open the help in a browser.

    open_python_docs : QtCore.Signal
        A Qt signal indicating a request to open the Python docstring
        information.

    report_jira_issue : QtCore.Signal
        A Qt signal indicating a request to open the Jira issue reporting
        widget.

    toggle_help : QtCore.Signal
        A Qt signal indicating a request to toggle the related help display
        frame.
    """
    pop_out = QtCore.Signal()
    open_in_browser = QtCore.Signal()
    open_python_docs = QtCore.Signal()
    report_jira_issue = QtCore.Signal()
    toggle_help = QtCore.Signal(bool)

    def __init__(self, icon="question", parent=None):
        super().__init__(icon, parent=parent)
        self.setCheckable(True)

    def _clicked(self):
        """Hook for QToolButton.clicked."""
        self.toggle_help.emit(self.isChecked())

    def generate_context_menu(self):
        menu = QtWidgets.QMenu(parent=self)

        if utils.HELP_WEB_ENABLED:
            pop_out_docs = menu.addAction("Pop &out documentation...")
            pop_out_docs.triggered.connect(self.pop_out.emit)

            open_in_browser = menu.addAction("Open in &browser...")
            open_in_browser.triggered.connect(self.open_in_browser.emit)

        open_python_docs = menu.addAction("Open &Python docs...")
        open_python_docs.triggered.connect(self.open_python_docs.emit)

        def toggle():
            self.setChecked(not self.isChecked())
            self._clicked()

        if utils.HELP_WEB_ENABLED:
            toggle_help = menu.addAction("Toggle &help")
            toggle_help.triggered.connect(toggle)

        if utils.JIRA_URL:
            menu.addSeparator()
            report_issue = menu.addAction("&Report Jira issue...")
            report_issue.triggered.connect(self.report_jira_issue.emit)

        return menu


class TyphosHelpFrame(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """
    A frame for help information display.

    Attributes
    ----------
    tooltip_updated : QtCore.Signal
        A signal indicating the help tooltip has changed.
    """
    tooltip_updated = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.help = None
        self.help_web_view = None
        self._delete_timer = None
        self.python_docs_browser = None

        self.setContentsMargins(0, 0, 0, 0)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.devices = []
        self._jira_widget = None

    def new_jira_widget(self):
        """Open a new Jira issue reporting widget."""
        device = self.devices[0] if self.devices else None
        self._jira_widget = TyphosJiraIssueWidget(device=device)
        self._jira_widget.show()

    def open_in_browser(self, new=0, autoraise=True):
        """
        Open the associated help documentation in the browser.

        Parameters
        ----------
        new : int, optional
            0: the same browser window (the default).
            1: a new browser window.
            2: a new browser page ("tab").

        autoraise : bool, optional
            If possible, autoraise raises the window (the default) or not.
        """
        return webbrowser.open(
            self.help_url.toString(), new=new, autoraise=autoraise
        )

    def open_python_docs(self, show: bool = True):
        """Open the Python docstring information in a new window."""
        if self.python_docs_browser is not None:
            if show:
                self.python_docs_browser.show()
                self.python_docs_browser.raise_()
            else:
                self.python_docs_browser.hide()
            return

        if not show:
            return

        self.python_docs_browser = QtWidgets.QTextBrowser()
        help_document = QtGui.QTextDocument()
        contents = self._tooltip or "Unset"
        first_line = contents.splitlines()[0]
        # TODO: later versions of qt will support setMarkdown
        help_document.setPlainText(contents)
        self.python_docs_browser.setWindowTitle(first_line)
        font = QtGui.QFont("Monospace")
        font.setStyleHint(QtGui.QFont.TypeWriter)
        # font.setStyleHint(QtGui.QFont.Monospace)
        self.python_docs_browser.setFont(font)
        self.python_docs_browser.setDocument(help_document)
        self.python_docs_browser.show()
        return self.python_docs_browser

    def _get_tooltip(self):
        """Update the tooltip based on device information."""
        tooltip = []
        # BUG: I'm seeing two devices in `self.devices` for
        # $ typhos --fake-device 'ophyd.EpicsMotor[{"prefix":"b"}]'
        for device in sorted(
            set(self.devices),
            key=lambda dev: self.devices.index(dev)
        ):
            heading = device.name or type(device).__name__
            tooltip.extend([
                heading,
                "-" * len(heading),
                ""
            ])

            tooltip.append(
                inspect.getdoc(device) or
                inspect.getdoc(type(device)) or
                "No docstring"
            )
            tooltip.append("")

        return "\n".join(tooltip)

    def add_device(self, device):
        self.devices.append(device)

        self._tooltip = self._get_tooltip()
        self.tooltip_updated.emit(self._tooltip)

        self.setWindowTitle(f"Help: {device.name}")

    @property
    def help_url(self):
        """The full help URL, generated from ``TYPHOS_HELP_URL``."""
        if not self.devices or not utils.HELP_WEB_ENABLED:
            return QtCore.QUrl("about:blank")

        device, *_ = self.devices
        try:
            device_url = utils.HELP_URL.format(device=device)
        except Exception:
            logger.exception("Failed to format confluence URL for device %s",
                             device)
            return QtCore.QUrl("about:blank")

        return QtCore.QUrl(device_url)

    def show_help(self):
        """Show the help information in a QWebEngineView."""
        if web.TyphosWebEngineView is None:
            logger.error(
                "Failed to import QWebEngineView; "
                "help view is unavailable."
                )
            return

        if self.help_web_view:
            self.help_web_view.show()
            return

        self.help_web_view = web.TyphosWebEngineView()
        self.help_web_view.page().setUrl(self.help_url)

        self.help_web_view.setEnabled(True)
        self.help_web_view.setMinimumSize(QtCore.QSize(100, 400))

        self.layout().addWidget(self.help_web_view)

    def hide_help(self):
        """Hide the help information QWebEngineView."""
        if not self.help_web_view:
            return
        self.help_web_view.hide()
        if self._delete_timer is None:
            self._delete_timer = QtCore.QTimer()
            self._delete_timer.setInterval(20000)
            self._delete_timer.setSingleShot(True)
            self._delete_timer.timeout.connect(self._delete_help_if_hidden)
            self._delete_timer.start()

    def _delete_help_if_hidden(self):
        """
        Slowly react to the help display removal, as setting it back up can be
        slow and painful.
        """
        self._delete_timer = None
        if self.help_web_view and not self.help_web_view.isVisible():
            self.layout().removeWidget(self.help_web_view)
            self.help_web_view.deleteLater()
            self.help_web_view = None

    def toggle_help(self, show):
        """
        Toggle the visibility of the help information QWebEngineView.

        Parameters
        ----------
        show : bool
            Show the help (True) or hide it (False).
        """
        if not self.devices:
            logger.warning("No devices added -> no help")
            return

        if show:
            self.show_help()
        else:
            self.hide_help()


class TyphosDisplayTitle(QtWidgets.QFrame, widgets.TyphosDesignerMixin):
    """
    Standardized Typhos Device Display title.

    Parameters
    ----------
    title : str, optional
        The initial title text, which may contain macros.

    show_switcher : bool, optional
        Show the :class:`TyphosDisplaySwitcher`.

    show_underline : bool, optional
        Show the underline separator.

    parent : QtWidgets.QWidget, optional
        The parent widget.
    """

    def __init__(self, title='${name}', *, show_switcher=True,
                 show_underline=True, parent=None):
        self._show_underline = show_underline
        self._show_switcher = show_switcher
        super().__init__(parent=parent)

        self.label = TyphosTitleLabel(title)
        self.switcher = TyphosDisplaySwitcher()

        self.underline = QtWidgets.QFrame()
        self.underline.setFrameShape(self.underline.HLine)
        self.underline.setFrameShadow(self.underline.Plain)
        self.underline.setLineWidth(10)

        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.addWidget(self.label, 0, 0)
        self.grid_layout.addWidget(self.switcher, 0, 1, Qt.AlignRight)
        self.grid_layout.addWidget(self.underline, 1, 0, 1, 2)

        self.help = TyphosHelpFrame()
        if utils.HELP_WEB_ENABLED:
            # Toggle the help web view if we have documentation to show
            self.switcher.help_toggle_button.toggle_help.connect(
                self.toggle_help
            )
        else:
            # Otherwise, open the python docs as a fallback
            self.switcher.help_toggle_button.toggle_help.connect(
                self.help.open_python_docs
            )
        self.switcher.help_toggle_button.pop_out.connect(self.pop_out_help)
        self.switcher.help_toggle_button.open_in_browser.connect(
            self.help.open_in_browser
        )
        self.switcher.help_toggle_button.open_python_docs.connect(
            self.help.open_python_docs
        )
        self.switcher.help_toggle_button.report_jira_issue.connect(
            self.help.new_jira_widget
        )
        self.help.tooltip_updated.connect(
            self.switcher.help_toggle_button.setToolTip
        )

        self.grid_layout.addWidget(self.help, 2, 0, 1, 2)

        self.grid_layout.setSizeConstraint(self.grid_layout.SetMinimumSize)
        self.setLayout(self.grid_layout)

        # Set the property:
        self.show_switcher = show_switcher
        self.show_underline = show_underline

    def toggle_help(self, show):
        """Toggle the help visibility."""
        if self.help is None:
            return

        self.help.toggle_help(show)
        if self.help.parent() is None:
            self.grid_layout.addWidget(self.help, 2, 0, 1, 2)

    def pop_out_help(self):
        """Pop out the help widget."""
        if self.help is None:
            return

        self.help.setParent(None)
        self.switcher.help_toggle_button.setChecked(True)
        self.help.show_help()
        self.help.show()
        self.help.raise_()

    @Property(bool)
    def show_switcher(self):
        """Get or set whether to show the display switcher."""
        return self._show_switcher

    @show_switcher.setter
    def show_switcher(self, value):
        self._show_switcher = bool(value)
        self.switcher.setVisible(self._show_switcher)

    def add_device(self, device):
        """Typhos hook for setting the associated device."""
        if not self.label.text():
            self.label.setText(device.name)

        if self.help is not None:
            self.help.add_device(device)

    @QtCore.Property(bool)
    def show_underline(self):
        """Get or set whether to show the underline."""
        return self._show_underline

    @show_underline.setter
    def show_underline(self, value):
        self._show_underline = bool(value)
        self.underline.setVisible(self._show_underline)

    def set_device_display(self, display):
        """Typhos callback: set the :class:`TyphosDeviceDisplay`."""
        self.device_display = display

        def toggle():
            toggle_display(display.display_widget)

        self.label.toggle_requested.connect(toggle)

    # Make designable properties from the title label available here as well
    label_alignment = forward_property('label', QtWidgets.QLabel, 'alignment')
    label_font = forward_property('label', QtWidgets.QLabel, 'font')
    label_indent = forward_property('label', QtWidgets.QLabel, 'indent')
    label_margin = forward_property('label', QtWidgets.QLabel, 'margin')
    label_openExternalLinks = forward_property('label', QtWidgets.QLabel,
                                               'openExternalLinks')
    label_pixmap = forward_property('label', QtWidgets.QLabel, 'pixmap')
    label_text = forward_property('label', QtWidgets.QLabel, 'text')
    label_textFormat = forward_property('label', QtWidgets.QLabel,
                                        'textFormat')
    label_textInteractionFlags = forward_property('label', QtWidgets.QLabel,
                                                  'textInteractionFlags')
    label_wordWrap = forward_property('label', QtWidgets.QLabel, 'wordWrap')

    # Make designable properties from the grid_layout
    layout_margin = forward_property('grid_layout', QtWidgets.QHBoxLayout,
                                     'margin')
    layout_spacing = forward_property('grid_layout', QtWidgets.QHBoxLayout,
                                      'spacing')

    # Make designable properties from the underline
    underline_palette = forward_property('underline', QtWidgets.QFrame,
                                         'palette')
    underline_styleSheet = forward_property('underline', QtWidgets.QFrame,
                                            'styleSheet')
    underline_lineWidth = forward_property('underline', QtWidgets.QFrame,
                                           'lineWidth')
    underline_midLineWidth = forward_property('underline', QtWidgets.QFrame,
                                              'midLineWidth')


class TyphosDeviceDisplay(utils.TyphosBase, widgets.TyphosDesignerMixin,
                          _DisplayTypes):
    """
    Main display for a single ophyd Device.

    This contains the widgets for all of the root devices signals, and any
    methods you would like to display. By typhos convention, the base
    initialization sets up the widgets and the :meth:`.from_device` class
    method will automatically populate the resulting display.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget.

    scrollable : bool, optional
        Semi-deprecated parameter. Use scroll_option instead.
        If ``True``, put the loaded template into a :class:`QScrollArea`.
        If ``False``, the display widget will go directly in this widget's
        layout.
        If omitted, scroll_option is used instead.

    composite_heuristics : bool, optional
        Enable composite heuristics, which may change the suggested detailed
        screen based on the contents of the added device.  See also
        :meth:`.suggest_composite_screen`.

    embedded_templates : list, optional
        List of embedded templates to use in addition to those found on disk.

    detailed_templates : list, optional
        List of detailed templates to use in addition to those found on disk.

    engineering_templates : list, optional
        List of engineering templates to use in addition to those found on
        disk.

    display_type : DisplayTypes, str, or int, optional
        The default display type.

    scroll_option : ScrollOptions, str, or int, optional
        The scroll behavior.

    nested : bool, optional
        An optional annotation for a display that may be nested inside another.
    """

    # Template types and defaults
    Q_ENUMS(_DisplayTypes)
    TemplateEnum = DisplayTypes  # For convenience

    device_count_threshold = 0
    signal_count_threshold = 30

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        scrollable: Optional[bool] = None,
        composite_heuristics: bool = True,
        embedded_templates: Optional[List[str]] = None,
        detailed_templates: Optional[List[str]] = None,
        engineering_templates: Optional[List[str]] = None,
        display_type: Union[DisplayTypes, str, int] = 'detailed_screen',
        scroll_option: Union[ScrollOptions, str, int] = 'auto',
        nested: bool = False,
    ):
        self._composite_heuristics = composite_heuristics
        self._current_template = None
        self._forced_template = ''
        self._macros = {}
        self._display_widget = None
        self._scroll_option = ScrollOptions.no_scroll
        self._searched = False
        self._hide_empty = False
        self._nested = nested

        self.templates = {name: [] for name in DisplayTypes.names}
        self._display_type = normalize_display_type(display_type)

        instance_templates = {
            'embedded_screen': embedded_templates or [],
            'detailed_screen': detailed_templates or [],
            'engineering_screen': engineering_templates or [],
        }
        for view, path_list in instance_templates.items():
            paths = [pathlib.Path(p).expanduser().resolve() for p in path_list]
            self.templates[view].extend(paths)

        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setAlignment(Qt.AlignTop)
        self._scroll_area.setObjectName('scroll_area')
        self._scroll_area.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameStyle(QtWidgets.QFrame.NoFrame)

        super().__init__(parent=parent)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll_area)

        if scrollable is None:
            self.scroll_option = scroll_option
        else:
            if scrollable:
                self.scroll_option = ScrollOptions.scrollbar
            else:
                self.scroll_option = ScrollOptions.no_scroll

    @Property(bool)
    def composite_heuristics(self):
        """Allow composite screen to be suggested first by heuristics."""
        return self._composite_heuristics

    @composite_heuristics.setter
    def composite_heuristics(self, composite_heuristics):
        self._composite_heuristics = bool(composite_heuristics)

    @Property(_ScrollOptions)
    def scroll_option(self) -> ScrollOptions:
        """Place the display in a scrollable area."""
        return self._scroll_option

    @scroll_option.setter
    def scroll_option(self, scrollable: ScrollOptions):
        # Switch the scroll area behavior
        opt = normalize_scroll_option(scrollable)
        if opt == self._scroll_option:
            return

        self._scroll_option = opt
        self._move_display_to_layout(self._display_widget)

    @Property(bool)
    def hideEmpty(self):
        """Toggle hiding or showing empty panels."""
        return self._hide_empty

    @hideEmpty.setter
    def hideEmpty(self, checked):
        if checked != self._hide_empty:
            self._hide_empty = checked

    def _move_display_to_layout(self, widget):
        if not widget:
            return

        widget.setParent(None)
        if self.scroll_option == ScrollOptions.auto:
            if self.display_type == DisplayTypes.embedded_screen:
                scrollable = False
            else:
                scrollable = True
        elif self.scroll_option == ScrollOptions.scrollbar:
            scrollable = True
        elif self.scroll_option == ScrollOptions.no_scroll:
            scrollable = False
        else:
            scrollable = True

        if scrollable:
            self._scroll_area.setWidget(widget)
        else:
            self.layout().addWidget(widget)

        self._scroll_area.setVisible(scrollable)

    def _generate_template_menu(self, base_menu):
        """Generate the template switcher menu, adding it to ``base_menu``."""
        for view, filenames in self.templates.items():
            if view.endswith('_screen'):
                view = view.split('_screen')[0]
            menu = base_menu.addMenu(view.capitalize())

            duplicates = utils.find_duplicate_filenames_in_paths(filenames)

            for filename in filenames:
                current_filename = os.path.split(filename)[-1]

                def switch_template(*, filename=filename):
                    self.force_template = filename
                if current_filename in duplicates:
                    action = menu.addAction(str(filename))
                else:
                    action = menu.addAction(os.path.split(filename)[-1])
                action.triggered.connect(switch_template)

        refresh_action = base_menu.addAction("Refresh Templates")
        refresh_action.triggered.connect(self._refresh_templates)

    def _refresh_templates(self):
        """Context menu 'Refresh Templates' clicked."""
        # Force an update of the display cache.
        cache.get_global_display_path_cache().update()
        self.search_for_templates()
        self.load_best_template()

    @property
    def current_template(self):
        """Get the current template being displayed."""
        return self._current_template

    @Property(_DisplayTypes)
    def display_type(self):
        """Get or set the current display type."""
        return self._display_type

    @display_type.setter
    def display_type(self, value):
        value = normalize_display_type(value)
        if self._display_type != value:
            self._display_type = value
            self.load_best_template()

    @property
    def macros(self):
        """Get or set the macros for the display."""
        return dict(self._macros)

    @macros.setter
    def macros(self, macros):
        self._macros.clear()
        self._macros.update(**(macros or {}))

        # If any display macros are specified, re-search for templates:
        if any(view in self._macros for view in DisplayTypes.names):
            self.search_for_templates()

    @Property(str, designable=False)
    def device_class(self):
        """Get the full class with module name of loaded device."""
        device = self.device
        cls = self.device.__class__
        return f'{cls.__module__}.{cls.__name__}' if device else ''

    @Property(str, designable=False)
    def device_name(self):
        """Get the name of the loaded device."""
        device = self.device
        return device.name if device else ''

    @property
    def device(self):
        """Get the device associated with this Device Display."""
        try:
            device, = self.devices
            return device
        except ValueError:
            ...

    def get_best_template(self, display_type, macros):
        """
        Get the best template for the given display type.

        Parameters
        ----------
        display_type : DisplayTypes, str, or int
            The display type.

        macros : dict
            Macros to use when loading the template.
        """
        display_type = normalize_display_type(display_type).name

        templates = self.templates[display_type]
        if templates:
            return templates[0]

        logger.warning("No templates available for display type: %s",
                       self._display_type)

    def _remove_display(self):
        """Remove the display widget, readying for a new template."""
        display_widget = self._display_widget
        if display_widget:
            if self._scroll_area.widget():
                self._scroll_area.takeWidget()
            self.layout().removeWidget(display_widget)
            display_widget.deleteLater()

        self._display_widget = None

    def load_best_template(self):
        """Load the best available template for the current display type."""
        if self.layout() is None:
            # If we are not fully initialized yet do not try and add anything
            # to the layout. This will happen if the QApplication has a
            # stylesheet that forces a template prior to the creation of this
            # display
            return

        if not self._searched:
            self.search_for_templates()

        self._remove_display()

        template = (self._forced_template or
                    self.get_best_template(self._display_type, self.macros))

        if not template:
            widget = QtWidgets.QWidget()
            template = None
        else:
            template = pathlib.Path(template)
            try:
                widget = self._load_template(template)
            except Exception as ex:
                logger.exception("Unable to load file %r", template)
                # If we have a previously defined template
                if self._current_template is not None:
                    # Fallback to it so users have a choice
                    try:
                        widget = self._load_template(self._current_template)
                    except Exception:
                        logger.exception(
                            "Failed to fall back to previous template: %s",
                            self._current_template
                        )
                        template = None
                        widget = None

                    pydm.exception.raise_to_operator(ex)
                else:
                    widget = QtWidgets.QWidget()
                    template = None

        if widget:
            widget.setObjectName('display_widget')

            if widget.layout() is None and widget.minimumSize().width() == 0:
                # If the widget has no layout, use a fixed size for it.
                # Without this, the widget may not display at all.
                widget.setMinimumSize(widget.size())

        self._display_widget = widget
        self._current_template = template

        def size_hint(*args, **kwargs):
            return widget.size()

        # sizeHint is not defined so we suggest the widget size
        widget.sizeHint = size_hint

        # We should _move_display_to_layout as soon as it is created. This
        # allow us to speed up since if the widget is too complex it takes
        # seconds to set it to the QScrollArea
        self._move_display_to_layout(self._display_widget)

        self._update_children()
        utils.reload_widget_stylesheet(self)

    @property
    def display_widget(self):
        """Get the widget generated from the template."""
        return self._display_widget

    @staticmethod
    def _get_templates_from_macros(macros):
        ret = {}
        paths = cache.get_global_display_path_cache().paths
        for display_type in DisplayTypes.names:
            ret[display_type] = None
            try:
                value = macros[display_type]
            except KeyError:
                ...
            else:
                if not value:
                    continue
                try:
                    value = pathlib.Path(value)
                except ValueError as ex:
                    logger.debug('Invalid path specified in macro: %s=%s',
                                 display_type, value, exc_info=ex)
                else:
                    ret[display_type] = list(utils.find_file_in_paths(
                        value, paths=paths))

        return ret

    def _load_template(self, filename):
        """Load template from file and return the widget."""
        filename = pathlib.Path(filename)
        loader = (pydm.display.load_py_file if filename.suffix == '.py'
                  else pydm.display.load_ui_file)

        logger.debug('Load template using %s: %r', loader.__name__, filename)
        return loader(str(filename), macros=self._macros)

    def _update_children(self):
        """Notify child widgets of this device display + the device."""
        device = self.device
        display = self._display_widget
        designer = display.findChildren(widgets.TyphosDesignerMixin) or []
        bases = display.findChildren(utils.TyphosBase) or []

        for widget in set(bases + designer):
            if device and hasattr(widget, 'add_device'):
                widget.add_device(device)

            if hasattr(widget, 'set_device_display'):
                widget.set_device_display(self)

    @Property(str)
    def force_template(self):
        """Force a specific template."""
        return self._forced_template

    @force_template.setter
    def force_template(self, value):
        if value != self._forced_template:
            self._forced_template = value
            self.load_best_template()

    @staticmethod
    def _build_macros_from_device(device, macros=None):
        result = {}
        if hasattr(device, 'md'):
            if isinstance(device.md, dict):
                result = dict(device.md)
            else:
                result = dict(device.md.post())

        if 'name' not in result:
            result['name'] = device.name
        if 'prefix' not in result and hasattr(device, 'prefix'):
            result['prefix'] = device.prefix

        result.update(**(macros or {}))
        return result

    def add_device(self, device, macros=None):
        """
        Add a Device and signals to the TyphosDeviceDisplay.

        The full dictionary of macros is built with the following order of
        precedence::

           1. Macros from the device metadata itself.
           2. If available, `name`, and `prefix` will be added from the device.
           3. The argument ``macros`` is then used to fill/update the final
              macro dictionary.

        This will also register the device's signals in the sig:// plugin.
        This means that any templates can refer to their device's signals by
        name.

        Parameters
        ----------
        device : ophyd.Device
            The device to add.

        macros : dict, optional
            Additional macros to use/replace the defaults.
        """
        # We only allow one device at a time
        if self.devices:
            logger.debug("Removing devices %r", self.devices)
            self.devices.clear()
        # Add the device to the cache
        super().add_device(device)
        logger.debug("Registering signals from device %s", device.name)
        for component_walk in device.walk_signals():
            register_signal(component_walk.item)
        self._searched = False
        self.macros = self._build_macros_from_device(device, macros=macros)
        self.load_best_template()

    def search_for_templates(self):
        """Search the filesystem for device-specific templates."""
        device = self.device
        if not device:
            logger.debug('Cannot search for templates without device')
            return

        self._searched = True
        cls = device.__class__

        logger.debug('Searching for templates for %s', cls.__name__)
        macro_templates = self._get_templates_from_macros(self._macros)

        paths = cache.get_global_display_path_cache().paths
        for display_type in DisplayTypes.names:
            view = display_type
            if view.endswith('_screen'):
                view = view.split('_screen')[0]

            template_list = self.templates[display_type]
            template_list.clear()

            # 1. Highest priority: macros
            for template in set(macro_templates[display_type] or []):
                template_list.append(template)
                logger.debug('Adding macro template %s: %s (total=%d)',
                             display_type, template, len(template_list))

            # 2. Composite heuristics, if enabled
            if self._composite_heuristics and view == 'detailed':
                if self.suggest_composite_screen(cls):
                    template_list.append(DETAILED_TREE_TEMPLATE)

            # 3. Templates based on class hierarchy names
            filenames = utils.find_templates_for_class(cls, view, paths)
            for filename in filenames:
                if filename not in template_list:
                    template_list.append(filename)
                    logger.debug('Found new template %s: %s (total=%d)',
                                 display_type, filename, len(template_list))

            # 4. Default templates
            template_list.extend(
                [templ for templ in DEFAULT_TEMPLATES[display_type]
                 if templ not in template_list]
            )

    @classmethod
    def suggest_composite_screen(cls, device_cls):
        """
        Suggest to use the composite screen for the given class.

        Returns
        -------
        composite : bool
            If True, favor the composite screen.
        """
        num_devices = 0
        num_signals = 0
        for attr, component in utils._get_top_level_components(device_cls):
            num_devices += issubclass(component.cls, ophyd.Device)
            num_signals += issubclass(component.cls, ophyd.Signal)

        specific_screens = cls._get_specific_screens(device_cls)
        if (len(specific_screens) or
                (num_devices <= cls.device_count_threshold and
                 num_signals >= cls.signal_count_threshold)):
            # 1. There's a custom screen - we probably should use them
            # 2. There aren't many devices, so the composite display isn't
            #    useful
            # 3. There are many signals, which should be broken up somehow
            composite = False
        else:
            # 1. No custom screen, or
            # 2. Many devices or a relatively small number of signals
            composite = True

        logger.debug(
            '%s screens=%s num_signals=%d num_devices=%d -> composite=%s',
            device_cls, specific_screens, num_signals, num_devices, composite
        )
        return composite

    @classmethod
    def from_device(cls, device, template=None, macros=None, **kwargs):
        """
        Create a new TyphosDeviceDisplay from a Device.

        Loads the signals in to the appropriate positions and sets the title to
        a cleaned version of the device name

        Parameters
        ----------
        device : ophyd.Device

        template : str, optional
            Set the ``display_template``.

        macros : dict, optional
            Macro substitutions to be placed in template.

        **kwargs
            Passed to the class init.
        """
        display = cls(**kwargs)
        # Reset the template if provided
        if template:
            display.force_template = template
        # Add the device
        display.add_device(device, macros=macros)
        return display

    @classmethod
    def from_class(cls, klass, *, template=None, macros=None, **kwargs):
        """
        Create a new TyphosDeviceDisplay from a Device class.

        Loads the signals in to the appropriate positions and sets the title to
        a cleaned version of the device name.

        Parameters
        ----------
        klass : str or class

        template : str, optional
            Set the ``display_template``.

        macros : dict, optional
            Macro substitutions to be placed in template.

        **kwargs
            Extra arguments are used at device instantiation.

        Returns
        -------
        TyphosDeviceDisplay
        """
        try:
            obj = pcdsutils.utils.get_instance_by_name(klass, **kwargs)
        except Exception:
            logger.exception('Failed to generate TyphosDeviceDisplay from '
                             'class %s', klass)
            return None

        return cls.from_device(obj, template=template, macros=macros)

    @classmethod
    def _get_specific_screens(cls, device_cls):
        """
        Get the list of specific screens for a given device class.

        That is, screens that are not default Typhos-provided screens.
        """
        paths = cache.get_global_display_path_cache().paths
        return [
            template
            for template in utils.find_templates_for_class(
                device_cls, "detailed", paths
            )
            if not utils.is_standard_template(template)
        ]

    def to_image(self):
        """
        Return the entire display as a QtGui.QImage.

        Returns
        -------
        QtGui.QImage
            The display, as an image.
        """
        if self._display_widget is not None:
            return utils.widget_to_image(self._display_widget)

    @Slot()
    def copy_to_clipboard(self):
        """Copy the display image to the clipboard."""
        image = self.to_image()
        if image is not None:
            clipboard = QtGui.QGuiApplication.clipboard()
            clipboard.setImage(image)

    @Slot(object)
    def _tx(self, value):
        """Receive information from happi channel."""
        self.add_device(value['obj'], macros=value['md'])

    def __repr__(self):
        """Get a custom representation for TyphosDeviceDisplay."""
        return (
            f'<{self.__class__.__name__} at {hex(id(self))} '
            f'device={self.device_class}[{self.device_name!r}] '
            f'nested={self._nested}'
            f'>'
        )


def toggle_display(widget, force_state=None):
    """
    Toggle the visibility of all :class:`TyphosSignalPanel` in a display.

    Parameters
    ----------
    widget : QWidget
        The widget in which to look for Panels.

    force_state : bool
        If set to True or False, it will change visibility to the value of
        force_state.
        If not set or set to None, it will flip the current panels state.
    """
    panels = widget.findChildren(typhos_panel.TyphosSignalPanel) or []
    visible = all(panel.isVisible() for panel in panels)

    state = not visible
    if force_state is not None:
        state = force_state

    for panel in panels:
        panel.setVisible(state)


def show_empty(widget):
    """
    Recursively shows all panels and widgets, empty or not.

    Parameters
    ----------
    widget : QWidget
    """
    children = widget.findChildren(TyphosDeviceDisplay) or []
    for ch in children:
        show_empty(ch)
    widget.setVisible(True)
    toggle_display(widget, force_state=True)


def hide_empty(widget, process_widget=True):
    """
    Recursively hide empty panels and widgets.

    Parameters
    ----------
    widget : QWidget
        The widget in which to start the recursive search.

    process_widget : bool
        Whether or not to process the visibility for the widget.
        This is useful since we don't want to hide the top-most
        widget otherwise users can't change the visibility back on.
    """
    def process(item, recursive=True):
        if isinstance(item, TyphosDeviceDisplay) and recursive:
            hide_empty(item)
        elif isinstance(item, typhos_panel.TyphosSignalPanel):
            if recursive:
                hide_empty(item)
            visible = bool(item._panel_layout.visible_elements)
            item.setVisible(visible)

    if isinstance(widget, TyphosDeviceDisplay):
        # Check if the template at this display is one of the defaults
        # otherwise we are not sure if we can safely change it.

        if widget.current_template not in DEFAULT_TEMPLATES_FLATTEN:
            logger.info("Can't hide empty entries in non built-in templates")
            return

    children = widget.findChildren(utils.TyphosBase) or []
    for w in children:
        process(w)

    if process_widget:
        if isinstance(widget, TyphosDeviceDisplay):
            overall_status = any(w.isVisible() for w in children)
        elif isinstance(widget, typhos_panel.TyphosSignalPanel):
            overall_status = bool(widget._panel_layout.visible_elements)
        widget.setVisible(overall_status)
