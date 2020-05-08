#!/usr/bin/env python
import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

import pytest

if __name__ == '__main__':
    # Show output results from every test function
    # Show the message output for skipped and expected failures
    # Skip the benchmarking re-runs
    args = ['-v', '-vrxs', '--benchmark-disable']

    # Add extra arguments
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])

    print('pytest arguments: {}'.format(args))

    typhos_logger = logging.getLogger('typhos')
    pydm_logger = logging.getLogger('pydm')
    log_dir = Path(os.path.dirname(__file__)) / 'logs'
    log_file = log_dir / 'run_tests_log.txt'

    if not log_dir.exists():
        log_dir.mkdir(parents=True)
    if log_file.exists():
        do_rollover = True
    else:
        do_rollover = False

    handler = RotatingFileHandler(str(log_file), backupCount=5,
                                  encoding=None, delay=0)
    if do_rollover:
        handler.doRollover()
    formatter = logging.Formatter(fmt=('%(asctime)s.%(msecs)03d '
                                       '%(name)-30s '
                                       '%(levelname)-8s '
                                       '%(threadName)-10s '
                                       '%(message)s'),
                                  datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    for log in (typhos_logger, pydm_logger):
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)

    sys.exit(pytest.main(args))
