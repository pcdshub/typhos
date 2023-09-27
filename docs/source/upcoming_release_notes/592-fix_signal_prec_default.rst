592 fix_signal_prec_default
###########################

API Changes
-----------
- N/A

Features
--------
- N/A

Bugfixes
--------
- Fix an issue where ophyd signals with floats would always display with a
  precision of 0 without special manual configuration. Floating-point signals
  now default to a precision of 3.

Maintenance
-----------
- N/A

Contributors
------------
- zllentz
