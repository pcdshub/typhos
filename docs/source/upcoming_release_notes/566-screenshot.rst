566 screenshot
#################

API Changes
-----------
- Added ``TyphosSuite.save_screenshot`` which takes a screenshot of the entire
  suite as-displayed.
- Added ``TyphosSuite.save_device_screenshots`` which takes individual
  screenshots of each device display in the suite and saves them to the
  provided formatted filename.

Features
--------
- Add ``typhos --screenshot filename_pattern`` to take screenshots of typhos
  displays prior to exiting early (in combination with ``--exit-after``).

Bugfixes
--------
- N/A

Maintenance
-----------
- N/A

Contributors
------------
- klauer
