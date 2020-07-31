"""This module defines the ``typhos`` command line utility"""
import argparse
import ast
import inspect
import logging
import re
import sys

import coloredlogs

import pcdsutils
import typhos
from ophyd.sim import clear_fake_device, make_fake_device
from typhos.app import get_qapp, launch_suite
from typhos.benchmark.cases import run_benchmarks
from typhos.benchmark.profile import profiler_context
from typhos.utils import nullcontext

logger = logging.getLogger(__name__)

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
parser.add_argument('--profile-modules', nargs='*',
                    help='Submodules to profile during the execution. '
                         'If no specific modules are specified, '
                         'profiles all submodules of typhos. '
                         'Turns on line profiling.')
parser.add_argument('--profile-output',
                    help='Filename to output the profile results to. '
                         'If omitted, prints results to stdout. '
                         'Turns on line profiling.')
parser.add_argument('--benchmark', nargs='*',
                    help='Runs the specified benchmarking tests instead of '
                         'launching a screen. '
                         'If no specific tests are specified, '
                         'runs all of them. '
                         'Turns on line profiling.')


# Append to module docs
__doc__ += '\n::\n\n    ' + parser.format_help().replace('\n', '\n    ')


def typhos_cli_setup(args):
    """Setup logging and style."""
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

    # Deal with stylesheet
    qapp = get_qapp()

    logger.debug("Applying stylesheet ...")
    typhos.use_stylesheet(dark=args.dark)
    if args.stylesheet:
        logger.info("Loading QSS file %r ...", args.stylesheet)
        with open(args.stylesheet, 'r') as handle:
            qapp.setStyleSheet(handle.read())


def _create_happi_client(cfg):
    """Create a happi client based on configuration ``cfg``."""
    import happi
    import typhos.plugins.happi

    if typhos.plugins.happi.HappiClientState.client:
        logger.debug("Using happi Client already registered with Typhos")
        return typhos.plugins.happi.HappiClientState.client

    logger.debug("Creating new happi Client from configuration")
    return happi.Client.from_config(cfg=cfg)


def create_suite(device_names, cfg=None, fake_devices=False):
    """Create a TyphosSuite from a list of device names."""
    if device_names:
        devices = create_devices(device_names, cfg=cfg,
                                 fake_devices=fake_devices)
    else:
        devices = []
    if devices or not device_names:
        return typhos.TyphosSuite.from_devices(devices)


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
                logger.exception("Unable to load class entry: %s with args %s",
                                 klass, args)
                continue
        else:
            if not happi_client:
                logger.error("Happi not available. Unable to load entry: %r",
                             device_name)
                continue
            if fake_devices:
                raise NotImplementedError("Fake devices from happi not "
                                          "supported yet")
            try:
                device = happi_client.load_device(name=device_name)
                devices.append(device)
            except Exception:
                logger.exception("Unable to load Happi entry: %r", device_name)
        if fake_devices:
            clear_fake_device(device)
    return devices


def typhos_run(device_names, cfg=None, fake_devices=False):
    """Run the central typhos part of typhos."""
    with typhos.utils.no_device_lazy_load():
        suite = create_suite(device_names, cfg=cfg, fake_devices=fake_devices)
    if suite:
        return launch_suite(suite)


def typhos_cli(args):
    """Command Line Application for Typhos."""
    args = parser.parse_args(args)

    if args.version:
        print(f'Typhos: Version {typhos.__version__} from {typhos.__file__}')
        return

    if any((args.profile_modules is not None, args.profile_output,
            args.benchmark is not None)):
        if args.profile_modules:
            context = profiler_context(module_names=args.profile_modules,
                                       filename=args.profile_output)
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
            suite = typhos_run(args.devices, cfg=args.happi_cfg,
                               fake_devices=args.fake_device)
        return suite


def main():
    """Execute the ``typhos_cli`` with command line arguments."""
    typhos_cli(sys.argv[1:])
