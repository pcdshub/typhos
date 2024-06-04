606 enh_wait_status
###################

API Breaks
----------
- ``TyphosStatusThread`` now has a dramatically different signal API.
  This is an improved version but if you were using this class take note
  of the changes.

Features
--------
- Make the timeout messages friendlier and more accurate when the
  timeouts come from the ``TyphosPositionerWidget``.
- Make error messages in general (including status timeouts) clearer
  when they come from the positioner device class controlled by the
  ``TyphosPositionerWidget``.

Bugfixes
--------
- N/A

Maintenance
-----------
- Refactor ``TyphosStatusThread`` to facilitate timeout message changes.

Contributors
------------
- zllentz
