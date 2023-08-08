"""This module defines the ``typhos`` command line utility"""
from __future__ import annotations

import argparse
import ast
import inspect
import logging
import re
import signal
import sys
import types
import typing
from typing import Optional

import coloredlogs
import pcdsutils
from ophyd.sim import clear_fake_device, make_fake_device
from pydm.widgets.template_repeater import FlowLayout
from qtpy import QtCore, QtWidgets

import typhos
from typhos.app import get_qapp, launch_suite
from typhos.benchmark.cases import run_benchmarks
from typhos.benchmark.profile import profiler_context
from typhos.display import DisplayTypes, ScrollOptions
from typhos.suite import TyphosSuite
from typhos.utils import (apply_standard_stylesheets, compose_stylesheets,
                          nullcontext)

logger = logging.getLogger(__name__)


class TyphosArguments(types.SimpleNamespace):
    """Type hints for ``typhos`` CLI entrypoint arguments."""

    devices: list[str]
    layout: str
    cols: int
    display_type: str
    scrollable: str
    size: Optional[str]
    hide_displays: bool
    happi_cfg: Optional[str]
    fake_device: bool
    version: bool
    verbose: bool
    dark: bool
    stylesheet_override: Optional[list[str]]
    stylesheet_add: Optional[list[str]]
    profile_modules: Optional[list[str]]
    profile_output: Optional[str]
    benchmark: Optional[list[str]]
    exit_after: Optional[float]
    screenshot_filename: Optional[str]


# Argument Parser Setup
parser = argparse.ArgumentParser(
    description=(
        'Create a TyphosSuite for device/s stored in a Happi Database'
    ),
)

parser.add_argument(
    'devices',
    nargs='*',
    help=(
        'Device names to load in the TyphosSuite or class name with '
        'parameters on the format: package.ClassName[{"param1":"val1",...}]'
    ),
)
parser.add_argument(
    '--layout',
    default='horizontal',
    help=(
        'Select a alternate layout for suites of many '
        'devices. Valid options are "horizontal" (default), '
        '"vertical", "grid", "flow", and any unique '
        'shortenings of those options.'
    ),
)
parser.add_argument(
    '--cols',
    default=3,
    help=(
        'The number of columns to use for the grid layout '
        'if selected in the layout argument. This will have '
        'no effect for other layouts.'
    ),
)
parser.add_argument(
    '--display-type',
    default='detailed',
    help=(
        'The kind of display to open for each device at '
        'initial load. Valid options are "embedded", '
        '"detailed" (default), "engineering", and any '
        'unique shortenings of those options.'
    ),
)
parser.add_argument(
    '--scrollable',
    default='auto',
    help=(
        'Whether or not to include the scrollbar. '
        'Valid options are "auto", "true", "false", '
        'and any unique shortenings of those options. '
        'Selecting "auto" will include a scrollbar for '
        'non-embedded layouts.'
    ),
)
parser.add_argument(
    '--size',
    help=(
        'A starting x,y size for the typhos suite. '
        'Useful if the default size is not suitable for '
        'your application. Example: --size 1000,1000'
    ),
)
parser.add_argument(
    '--hide-displays',
    action='store_true',
    help=(
        'Option to start with subdisplays hidden instead '
        'of shown.'
    )
)
parser.add_argument(
    '--happi-cfg',
    help=(
        'Location of happi configuration file '
        'if not specified by $HAPPI_CFG environment variable'
    ),
)
parser.add_argument(
    '--fake-device',
    action='store_true',
    help=(
        'Create fake devices with no EPICS connections. '
        'This does not yet work for happi devices. An '
        'example invocation: '
        'typhos --fake-device ophyd.EpicsMotor[]'
    ),
)
parser.add_argument(
    '--version',
    '-V',
    action='store_true',
    help='Current version and location ' 'of Typhos installation.',
)
parser.add_argument(
    '--verbose',
    '-v',
    action='store_true',
    help='Show the debug logging stream',
)
parser.add_argument(
    '--dark',
    action='store_true',
    help='Use the QDarkStyleSheet shipped with Typhos',
)
parser.add_argument(
    "--stylesheet-override", "--stylesheet",
    action="append",
    help="Override all built-in stylesheets, using this stylesheet instead.",
)
parser.add_argument(
    "--stylesheet-add",
    action="append",
    help=(
        "Include an additional stylesheet in the loading process. "
        "This stylesheet will take priority over all built-in stylesheets, "
        "but not over a template or widget's styleSheet property."
    )
)
parser.add_argument(
    '--profile-modules',
    nargs='*',
    help=(
        'Submodules to profile during the execution. '
        'If no specific modules are specified, '
        'profiles all submodules of typhos. '
        'Turns on line profiling.'
    ),
)
parser.add_argument(
    '--profile-output',
    help=(
        'Filename to output the profile results to. '
        'If omitted, prints results to stdout. '
        'Turns on line profiling.'
    ),
)
parser.add_argument(
    '--benchmark',
    nargs='*',
    help=(
        'Runs the specified benchmarking tests instead of '
        'launching a screen. '
        'If no specific tests are specified, '
        'runs all of them. '
        'Turns on line profiling.'
    ),
)
parser.add_argument(
    '--exit-after',
    type=float,
    help=(
        "(For profiling purposes) Exit typhos after the provided number of "
        "seconds"
    ),
)
parser.add_argument(
    '--screenshot',
    dest="screenshot_filename",
    help=(
        "Save a screenshot of the generated display(s) prior to exiting to "
        "this filename"
    ),
)


# Append to module docs
__doc__ += '\n::\n\n    ' + parser.format_help().replace('\n', '\n    ')


def typhos_cli_setup(args):
    """Setup logging and style."""
    # Logging Level handling
    logging.getLogger().addHandler(logging.NullHandler())
    shown_logger = logging.getLogger('typhos')
    if args.verbose:
        level = "DEBUG"
        log_fmt = (
            '[%(asctime)s] - %(levelname)s - Thread (%(thread)d - '
            '%(threadName)s ) - %(name)s -> %(message)s'
        )
    else:
        level = "INFO"
        log_fmt = '[%(asctime)s] - %(levelname)s - %(message)s'
    coloredlogs.install(level=level, logger=shown_logger, fmt=log_fmt)
    logger.debug("Set logging level of %r to %r", shown_logger.name, level)

    qapp = get_qapp()
    logger.debug("Applying stylesheet ...")
    if args.stylesheet_override:
        # Includes some non-stylesheet style settings
        apply_standard_stylesheets(
            include_pydm=False,
            widget=qapp,
        )
        for filename in args.stylesheet_override:
            logger.info("Loading QSS file %r ...", filename)
        qapp.setStyleSheet(compose_stylesheets(args.stylesheet_override))
    else:
        apply_standard_stylesheets(
            dark=args.dark,
            paths=args.stylesheet_add,
            widget=qapp,
        )


def _create_happi_client(cfg):
    """Create a happi client based on configuration ``cfg``."""
    import happi

    import typhos.plugins.happi

    if typhos.plugins.happi.HappiClientState.client:
        logger.debug("Using happi Client already registered with Typhos")
        return typhos.plugins.happi.HappiClientState.client

    logger.debug("Creating new happi Client from configuration")
    return happi.Client.from_config(cfg=cfg)


def create_suite(
    device_names: list[str],
    cfg: Optional[str] = None,
    fake_devices: bool = False,
    layout: str = 'horizontal',
    cols: int = 3,
    display_type: str = 'detailed',
    scroll_option: str = 'auto',
    show_displays: bool = True,
) -> TyphosSuite:
    """
    Create a TyphosSuite from a list of device names.

    Parameters
    ----------
    device_names : list of str
        The happi names associated with the devices to instantiate,
        or the full class specifications from the cli. These two
        styles can be mixed.
    cfg : str, optional
        The happi configuration file to use. If omitted, uses
        the environment variables specified by happi.
    fake_devices : bool, optional
        If True, use fake devices behind the screen instead of
        making real connections.
    layout : str, optional
        The layout to use for the suite. See the cli help for
        valid options.
    cols : int, optional
        The number of columns to use when we create a grid
        layout.
    display_type : str, optional
        The type of display to use in the suite. See the
        cli help for valid options.
    scroll_option : str, optional
        Options for the scrollbar. See the cli help for valid options.
    show_displays : bool, optional
        If True (default), open all the included device displays.
        If False, do not open any of the displays.

    Returns
    -------
    suite : TyphosSuite
        A suite that has been populated with devices.
    """
    if device_names:
        devices = create_devices(
            device_names, cfg=cfg, fake_devices=fake_devices
        )
    else:
        devices = []
    if devices or not device_names:
        layout_obj = get_layout_from_cli(layout, cols)
        display_type_enum = get_display_type_from_cli(display_type)
        scroll_enum = get_scrollable_from_cli(scroll_option)
        return typhos.TyphosSuite.from_devices(
            devices,
            content_layout=layout_obj,
            default_display_type=display_type_enum,
            scroll_option=scroll_enum,
            show_displays=show_displays,
            pin=not show_displays,
        )


def get_layout_from_cli(
    layout: str,
    cols: int,
) -> QtWidgets.QLayout:
    """
    Return a correct layout object based on user input.

    Parameters
    ----------
    layout : str
        String representation of the layout.
    cols : int
        Number of columns to use for the grid layout.

    Returns
    -------
    qlayout : QLayout
        The qt layout object, instantiated.
    """
    if 'horizontal'.startswith(layout):
        return QtWidgets.QHBoxLayout()
    if 'vertical'.startswith(layout):
        return QtWidgets.QVBoxLayout()
    if 'grid'.startswith(layout):
        return FixedColGrid(cols=cols)
    if 'flow'.startswith(layout):
        return FlowLayout()
    else:
        raise ValueError(
            f'{layout} is not a valid layout name. '
            'The allowed values are "horizontal", '
            '"vertical", "grid", and "flow".'
        )


class FixedColGrid(QtWidgets.QGridLayout):
    """
    A QGridLayout with fixed number of columns.

    QGridLayout allows us to add widgets at any row or column, but
    for the purposes of typhos we'd like to be able to pass in just
    the widget like for other layouts. As such, we select a fixed
    number of columns and fill devices in row-by-row, left-to-right
    first and then top-to-bottom.
    """

    def __init__(
        self,
        *args,
        cols: int = 3,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._n_cols = cols
        self._widget_index = 0

    def addWidget(
        self,
        widget: QtWidgets.QWidget,
        *args,
    ):
        row = self._widget_index // self._n_cols
        col = self._widget_index % self._n_cols
        super().addWidget(widget, row, col, *args)
        self._widget_index += 1


def get_display_type_from_cli(display_type: str) -> DisplayTypes:
    """Convert the cli string to the appropriate DisplayTypes enum."""
    display_type = display_type.lower()
    if 'embedded'.startswith(display_type):
        return DisplayTypes.embedded_screen
    if 'detailed'.startswith(display_type):
        return DisplayTypes.detailed_screen
    if 'engineering'.startswith(display_type):
        return DisplayTypes.engineering_screen
    raise ValueError(
        f'{display_type} is not a valid display type. '
        'The allowed values are "embedded", "detailed", '
        'and "engineering".'
    )


def get_scrollable_from_cli(scrollable: str) -> ScrollOptions:
    """Convert the cli string to the appropriate ScrollOptions enum."""
    scrollable = scrollable.lower()
    if 'auto'.startswith(scrollable):
        return ScrollOptions.auto
    if 'true'.startswith(scrollable):
        return ScrollOptions.scrollbar
    if 'false'.startswith(scrollable):
        return ScrollOptions.no_scroll
    raise ValueError(
        f'{scrollable} is not a valid scroll option. '
        'The allowed values are "auto", "true", '
        'and "false".'
    )


def create_devices(device_names, cfg=None, fake_devices=False):
    """Returns a list of devices to be included in the typhos suite."""
    logger.debug("Accessing Happi Client ...")

    try:
        happi_client = _create_happi_client(cfg)
    except Exception:
        logger.debug("Unable to create a happi client.", exc_info=True)
        happi_client = None

    # Load and add each device
    devices = list()

    klass_regex = re.compile(
        r'([a-zA-Z][a-zA-Z0-9\.\_]*)\[(\{.+})*[\,]*\]'  # noqa
    )

    for device_name in device_names:
        logger.info("Loading %r ...", device_name)
        result = klass_regex.findall(device_name)
        if len(result) > 0:
            try:
                klass, args = result[0]
                klass = pcdsutils.utils.import_helper(klass)

                default_kwargs = {"name": klass.__name__}
                if args:
                    kwargs = ast.literal_eval(args)
                    default_kwargs.update(kwargs)

                if fake_devices:
                    klass = make_fake_device(klass)
                    # Give default value to missing positional args
                    # This might fail, but is best effort
                    for arg in inspect.getfullargspec(klass).args:
                        if arg not in default_kwargs and arg != 'self':
                            if arg == 'prefix':
                                default_kwargs[arg] = 'FAKE_PREFIX:'
                            else:
                                default_kwargs[arg] = 'FAKE'

                device = klass(**default_kwargs)
                devices.append(device)

            except Exception:
                logger.exception(
                    "Unable to load class entry: %s with args %s", klass, args
                )
                continue
        else:
            if not happi_client:
                logger.error(
                    "Happi not available. Unable to load entry: %r",
                    device_name,
                )
                continue
            if fake_devices:
                raise NotImplementedError(
                    "Fake devices from happi not " "supported yet"
                )
            try:
                device = happi_client.load_device(name=device_name)
                devices.append(device)
            except Exception:
                logger.exception(
                    "Unable to load Happi entry: %r", device_name
                )
        if fake_devices:
            clear_fake_device(device)
    return devices


def typhos_run(
    device_names: list[str],
    cfg: Optional[str] = None,
    fake_devices: bool = False,
    layout: str = 'horizontal',
    cols: int = 3,
    display_type: str = 'detailed',
    scroll_option: str = 'auto',
    initial_size: Optional[str] = None,
    show_displays: bool = True,
    exit_after: Optional[float] = None,
    screenshot_filename: Optional[str] = None,
) -> Optional[QtWidgets.QMainWindow]:
    """
    Run the central typhos part of typhos.

    Parameters
    ----------
    device_names : list of str
        The happi names associated with the devices to instantiate,
        or the full class specifications from the cli. These two
        styles can be mixed.
    cfg : str, optional
        The happi configuration file to use. If omitted, uses
        the environment variables specified by happi.
    fake_devices : bool, optional
        If True, use fake devices behind the screen instead of
        making real connections.
    layout : str, optional
        The layout to use for the suite. See the cli help for
        valid options.
    cols : int, optional
        The number of columns to use when we create a grid
        layout.
    display_type : str, optional
        The type of display to use in the suite. See the
        cli help for valid options.
    scroll_option : str, optional
        Options for the scrollbar. See the cli help for valid options.
    initial_size : str, optional
        Specification for the starting width,height of the window.
    show_displays : bool, optional
        If True (default), open all the included device displays.
        If False, do not open any of the displays.
    screenshot_filename : str, optional
        Save a screenshot to this file prior to exiting early.

    Returns
    -------
    suite : QMainWindow
        The window created. This is returned after the application
        is done running. Primarily used in unit tests.
    """
    with typhos.utils.no_device_lazy_load():
        suite = create_suite(
            device_names,
            cfg=cfg,
            fake_devices=fake_devices,
            layout=layout,
            cols=cols,
            display_type=display_type,
            scroll_option=scroll_option,
            show_displays=show_displays,
        )

    if suite is None:
        logger.debug("Suite creation failure")
        return None

    if initial_size is not None:
        try:
            initial_size = QtCore.QSize(
                *(int(opt) for opt in initial_size.split(','))
            )
        except TypeError as exc:
            raise ValueError(
                "Invalid --size argument. Expected a two-element pair "
                "of comma-separated integers, e.g. --size 1000,1000"
            ) from exc

    def exit_early():
        logger.warning(
            "Exiting typhos early due to --exit-after=%s CLI argument.",
            exit_after
        )

        if screenshot_filename is not None:
            suite.save_device_screenshots(screenshot_filename)

        sys.exit(0)

    if exit_after is not None and exit_after >= 0:
        QtCore.QTimer.singleShot(exit_after * 1000.0, exit_early)

    return launch_suite(suite, initial_size=initial_size)


def typhos_cli(args):
    """Command Line Application for Typhos."""
    args = typing.cast(TyphosArguments, parser.parse_args(args))

    if args.version:
        print(f'Typhos: Version {typhos.__version__} from {typhos.__file__}')
        return

    if any(
        (
            args.profile_modules is not None,
            args.profile_output,
            args.benchmark is not None,
        )
    ):
        if args.profile_modules:
            context = profiler_context(
                module_names=args.profile_modules,
                filename=args.profile_output,
            )
        else:
            context = profiler_context(filename=args.profile_output)
    else:
        context = nullcontext()

    with context:
        typhos_cli_setup(args)
        if args.benchmark is not None:
            # Note: actually a list of suites
            suite = run_benchmarks(args.benchmark)
        else:

            suite = typhos_run(
                args.devices,
                cfg=args.happi_cfg,
                fake_devices=args.fake_device,
                layout=args.layout,
                cols=int(args.cols),
                display_type=args.display_type,
                scroll_option=args.scrollable,
                initial_size=args.size,
                show_displays=not args.hide_displays,
                exit_after=args.exit_after,
                screenshot_filename=args.screenshot_filename,
            )

        return suite


def _sigint_handler(signal, frame):
    logger.info("Caught Ctrl-C (SIGINT); exiting.")
    sys.exit(1)


def main():
    """Execute the ``typhos_cli`` with command line arguments."""
    signal.signal(signal.SIGINT, _sigint_handler)
    typhos_cli(sys.argv[1:])
