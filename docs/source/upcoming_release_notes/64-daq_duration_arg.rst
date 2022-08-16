64 daq_duration_arg
###################

API Changes
-----------
- N/A

Features
--------
- N/A

Bugfixes
--------
- Fix an issue where any of the daq step scans would fail if run with the
  ``duration`` arg instead of the ``events`` arg.

Maintenance
-----------
- Make the test suite pass on Windows
- Make the test suite compatible with bluesky v1.9.0
- Make the test suite compatible with python 3.8

Contributors
------------
- zllentz
