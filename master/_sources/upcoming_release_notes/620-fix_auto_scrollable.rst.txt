620 fix_auto_scrollable
#######################

API Breaks
----------
- N/A

Features
--------
- N/A

Bugfixes
--------
- Fix an issue where detailed tree screens would automatically load without
  scrollbars. Now, the "auto" scrollbar setting is based primarily on the
  apparent display type of the screen, not of the originally requested
  display type, which may not be used if no such template exists.

Maintenance
-----------
- N/A

Contributors
------------
- zllentz
