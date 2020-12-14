29 delay-controls
#################

API Changes
-----------
- N/A

Features
--------
- N/A

Bugfixes
--------
- Fix issue where the stage in the daq_delay_scan was erroneously included
  in the DAQ control variables. This actually slows down the scan and dumps
  extra, redundant data into the data stream.

Maintenance
-----------
- N/A

Contributors
------------
- N/A
