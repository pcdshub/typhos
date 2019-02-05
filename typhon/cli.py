"""This module defines the ``typhon`` command line utility"""
import argparse
import logging
import sys

import coloredlogs
from qtpy.QtWidgets import QApplication

import typhon

logger = logging.getLogger(__name__)
app = None

# Argument Parser Setup
parser = argparse.ArgumentParser(description='Create a TyphonSuite for '
                                             'device/s stored in a Happi '
                                             'Database')

parser.add_argument('devices', nargs='*',
                    help='Device names to load in the TyphonSuite')
parser.add_argument('--happi-cfg',
                    help='Location of happi configuration file '
                         'if not specified by $HAPPI_CFG environment variable')
parser.add_argument('--version', '-V', action='store_true',
                    help='Current version and location '
                         'of Typhon installation.')
parser.add_argument('--verbose', '-v', action='store_true',
                    help='Show the debug logging stream')
parser.add_argument('--dark', action='store_true',
                    help='Use the QDarkStyleSheet shipped with typhon')
parser.add_argument('--stylesheet',
                    help='Additional stylesheet options')


# Append to module docs
__doc__ += '\n::\n\n    ' + parser.format_help().replace('\n', '\n    ')


def typhon_cli_setup(args):
    global app
    # Logging Level handling
    if args.verbose:
        level = "DEBUG"
        shown_logger = logging.getLogger('typhon')
    else:
        shown_logger = logging.getLogger()
        level = "INFO"
    coloredlogs.install(level=level, logger=shown_logger,
                        fmt='[%(asctime)s] - %(levelname)s -  %(message)s')
    logger.debug("Set logging level of %r to %r", shown_logger.name, level)

    # Version endpoint
    if args.version:
        print(f'Typhon: Version {typhon.__version__} from {typhon.__file__}')
        return

    # Deal with stylesheet
    logger.debug("Applying stylesheet ...")
    if not app:
        logger.debug("Creating QApplication ...")
        app = QApplication([])

    typhon.use_stylesheet(dark=args.dark)
    if args.stylesheet:
        logger.info("Loading QSS file %r ...", args.stylesheet)
        with open(args.stylesheet, 'r') as handle:
            app.setStyleSheet(handle.read())


def create_suite(devices, cfg=None):
    """Create a TyphonSuite from a list of device names"""
    logger.debug("Accessing Happi Client ...")
    try:
        import happi
        import typhon.plugins.happi
    except (ImportError, ModuleNotFoundError):
        logger.exception("Unable to import happi to load devices!")
        return
    if typhon.plugins.happi._client:
        logger.debug("Using happi Client already registered with Typhon")
        client = typhon.plugins.happi._client
    else:
        logger.debug("Creating new happi Client from configuration")
        client = happi.Client.from_config(cfg=cfg)
    logger.debug("Creating empty TyphonSuite ...")
    suite = typhon.TyphonSuite()
    logger.info("Loading Tools ...")
    for name, tool in suite.default_tools.items():
        suite.add_tool(name, tool())
    # Load and add each device
    for device in devices:
        logger.info("Loading %r ...", device)
        try:
            device = client.load_device(name=device)
            suite.add_device(device)
            suite.show_subdisplay(device)
        except Exception:
            logger.exception("Unable to add %r to TyphonSuite", device)
    return suite


def typhon_cli(args):
    """Command Line Application for Typhon"""
    args = parser.parse_args(args)
    typhon_cli_setup(args)
    if not args.version:
        suite = create_suite(args.devices, cfg=args.happi_cfg)
        if suite:
            suite.show()
            logger.info("Launching application ...")
            QApplication.instance().exec_()
            logger.info("Execution complete!")
            return suite


def main():
    """Execute the ``typhon_cli`` with command line arguments"""
    typhon_cli(sys.argv[1:])
