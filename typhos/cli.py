"""This module defines the ``typhos`` command line utility"""
import argparse
import ast
import inspect
import logging
import re
import sys

import coloredlogs
from qtpy.QtWidgets import QApplication, QMainWindow

import pcdsutils
import typhos
from ophyd.sim import clear_fake_device, make_fake_device

logger = logging.getLogger(__name__)
app = None

# Argument Parser Setup
parser = argparse.ArgumentParser(description='Create a TyphosSuite for '
                                             'device/s stored in a Happi '
                                             'Database')

parser.add_argument('devices', nargs='*',
                    help='Device names to load in the TyphosSuite or '
                         'class name with parameters on the format: '
                         'package.ClassName[{"param1":"val1",...}]')
parser.add_argument('--happi-cfg',
                    help='Location of happi configuration file '
                         'if not specified by $HAPPI_CFG environment variable')
parser.add_argument('--fake-device', action='store_true',
                    help='Create fake devices with no EPICS connections. '
                         'This does not yet work for happi devices. An '
                         'example invocation: '
                         'typhos --fake-device ophyd.EpicsMotor[]')
parser.add_argument('--version', '-V', action='store_true',
                    help='Current version and location '
                         'of Typhos installation.')
parser.add_argument('--verbose', '-v', action='store_true',
                    help='Show the debug logging stream')
parser.add_argument('--dark', action='store_true',
                    help='Use the QDarkStyleSheet shipped with Typhos')
parser.add_argument('--stylesheet',
                    help='Additional stylesheet options')


# Append to module docs
__doc__ += '\n::\n\n    ' + parser.format_help().replace('\n', '\n    ')


def get_qapp():
    global app
    if app is None:
        logger.debug("Creating QApplication ...")
        app = QApplication([])
    return app


def typhos_cli_setup(args):
    # Logging Level handling
    logging.getLogger().addHandler(logging.NullHandler())
    shown_logger = logging.getLogger('typhos')
    if args.verbose:
        level = "DEBUG"
        log_fmt = '[%(asctime)s] - %(levelname)s - Thread (%(thread)d - ' \
                  '%(threadName)s ) - %(name)s -> %(message)s'
    else:
        level = "INFO"
        log_fmt = '[%(asctime)s] - %(levelname)s - %(message)s'
    coloredlogs.install(level=level, logger=shown_logger,
                        fmt=log_fmt)
    logger.debug("Set logging level of %r to %r", shown_logger.name, level)

    # Version endpoint
    if args.version:
        print(f'Typhos: Version {typhos.__version__} from {typhos.__file__}')
        return

    # Deal with stylesheet
    app = get_qapp()

    logger.debug("Applying stylesheet ...")
    typhos.use_stylesheet(dark=args.dark)
    if args.stylesheet:
        logger.info("Loading QSS file %r ...", args.stylesheet)
        with open(args.stylesheet, 'r') as handle:
            app.setStyleSheet(handle.read())


def _create_happi_client(cfg):
    """Create a happi client based on configuration ``cfg``."""
    import happi
    import typhos.plugins.happi

    if typhos.plugins.happi.HappiClientState.client:
        logger.debug("Using happi Client already registered with Typhos")
        return typhos.plugins.happi.HappiClientState.client

    logger.debug("Creating new happi Client from configuration")
    return happi.Client.from_config(cfg=cfg)


def create_suite(devices, cfg=None, fake_devices=False):
    """Create a TyphosSuite from a list of device names"""
    if devices:
        loaded_devs = create_devices(devices, cfg=cfg, fake_devices=fake_devices)
    if loaded_devs or not devices:
       return suite_from_devices(loaded_devs)


def create_devices(devices_arg, cfg=None, fake_devices=False):
    logger.debug("Accessing Happi Client ...")

    try:
        happi_client = _create_happi_client(cfg)
    except Exception:
        logger.debug("Unable to create a happi client.", exc_info=True)
        happi_client = None

    # Load and add each device
    loaded_devs = list()

    klass_regex = re.compile(
        r'([a-zA-Z][a-zA-Z\.\_]*)\[(\{.+})*[\,]*\]'  # noqa
    )

    for device in devices_arg:
        logger.info("Loading %r ...", device)
        result = klass_regex.findall(device)
        if len(result) > 0:
            try:
                klass, args = result[0]
                klass = pcdsutils.utils.import_helper(klass)

                default_kwargs = {"name": "device"}
                if args:
                    kwargs = ast.literal_eval(args)
                    default_kwargs.update(kwargs)

                if fake_devices:
                    klass = make_fake_device(klass)
                    # Give default value to missing positional args
                    # This might fail, but is best effort
                    for arg in inspect.getfullargspec(klass).args:
                        if arg not in default_kwargs and arg != 'self':
                            default_kwargs[arg] = 'FAKE'

                device = klass(**default_kwargs)
                loaded_devs.append(device)

            except Exception:
                logger.exception("Unable to load class entry: %s with args %s",
                                 klass, args)
        else:
            if not happi_client:
                logger.error("Happi not available. Unable to load entry: %r",
                             device)
                continue
            if fake_devices:
                raise NotImplementedError("Fake devices from happi not "
                                          "supported yet")
            try:
                device = happi_client.load_device(name=device)
                loaded_devs.append(device)
            except Exception:
                logger.exception("Unable to load Happi entry: %r", device)
        if fake_devices:
            clear_fake_device(device)
    return loaded_devs


def suite_from_devices(devices):
    logger.debug("Creating empty TyphosSuite ...")
    suite = typhos.TyphosSuite()
    logger.info("Loading Tools ...")
    tools = dict(suite.default_tools)
    for name, tool in tools.items():
        suite.add_tool(name, tool())
    if devices:
        logger.info("Adding devices ...")
    for device in devices:
        try:
            suite.add_device(device)
            suite.show_subdisplay(device)
        except Exception:
            logger.exception("Unable to add %r to TyphosSuite",
                             device.name)
    return suite


def launch_suite(suite):
    window = QMainWindow()
    window.setCentralWidget(suite)
    window.show()
    logger.info("Launching application ...")
    QApplication.instance().exec_()
    logger.info("Execution complete!")
    return window


def launch_from_devices(devices):
    get_qapp()
    suite = suite_from_devices(devices)
    return launch_suite(suite)


def typhos_cli(args):
    """Command Line Application for Typhos"""
    args = parser.parse_args(args)
    typhos_cli_setup(args)
    if not args.version:
        with typhos.utils.no_device_lazy_load():
            suite = create_suite(args.devices, cfg=args.happi_cfg,
                                 fake_devices=args.fake_device)
        if suite:
            return launch_suite(suite)

def main():
    """Execute the ``typhos_cli`` with command line arguments"""
    typhos_cli(sys.argv[1:])
