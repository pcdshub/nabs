Release History
###############

v1.2.0 (2022-02-07)
===================

Features
--------
- Add daq_d2scan
- Add n-dimensional daq scans: daq_dnscan, daq_anscan

Contributors
------------
- tangkong


v1.1.3 (2021-09-28)
===================

Bugfixes
--------
- Fix an issue where passing in a PseudoSingle to a daq-wrapped scan
  would result in duplicate controls entries in the DAQ data stream.

Contributors
------------
- zllentz


v1.1.2 (2021-04-27)
===================

Maintenance
-----------
Tweak the signatures of the daq step scans for ease of inspection

Contributors
------------
- zllentz


v1.1.1 (2021-03-03)
===================

Maintenance
-----------
- Fix various issues with the documentation builds
- Add ophyd as an explicit runtime dependency because it is imported
  directly in nabs.utils.
- Require a bluesky>=1.6.5 dependency to ensure a function we're using
  is included.

Contributors
------------
- zllentz


v1.1.0 (2021-02-10)
===================

Features
--------
- Add a new plan for fixed target scanning, as used in XPP for the start of
  lu8318. This uses the ``XYGridStage`` from ``pcdsdevices`` to scan motors
  across a skewed path grid. It is feature-rich with things like path
  memory and incorporating a third motor.

Contributors
------------
- cristinasewell


v1.0.0 (2020-12-22)
===================

API Changes
-----------
- All plans now have a detectors argument to allow plotting during scans.
  If no plot is desired, simply pass in an empty list instead.

Bugfixes
--------
- Fix issue where the stage in the daq_delay_scan was erroneously included
  in the DAQ control variables. This actually slows down the scan and dumps
  extra, redundant data into the data stream.

Contributors
------------
- zllentz
- ZryletTC


v0.1.0 (2020-11-17)
===================

Features
--------
- Added the `nabs.plans` module with the following functions:

  - `nabs.plans.duration_scan`:
    A bluesky plan that moves a motor back and forth for a fixed duration.
  - `nabs.plans.delay_scan`:
    A bluesky plan that configures a sweep time for a laser delay stage
    and runs a `nabs.plans.duration_scan`.
  - `nabs.plans.daq_delay_scan`:
    A bluesky plan that runs the daq during a `nabs.plans.delay_scan`.
  - `nabs.plans.daq_count`:
    A bluesky plan that runs the daq n times while moving no motors.
  - `nabs.plans.daq_scan`:
    A bluesky plan that runs calib cycles at each step while doing the built-in bluesky nd ``scan`` plan, returning motors to their original positions after the scan.
  - `nabs.plans.daq_list_scan`:
    A bluesky plan that runs calib cycles at each step while doing the built-in bluesky ``list_scan`` plan, returning motors to their original positions after the scan.
  - `nabs.plans.daq_ascan`:
    A bluesky plan that runs calib cycles at each step of a traditional 1D ascan (absolute scan), returning motors to their original positions after the scan.
  - `nabs.plans.daq_dscan`:
    A bluesky plan that runs calib cycles at each step of a traditional 1D dscan (delta scan), returning motors to their original positions after the scan.
  - `nabs.plans.daq_a2scan`:
    A 2-dimensional `nabs.plans.daq_ascan`.
  - `nabs.plans.daq_a3scan`:
    A 3-dimensional `nabs.plans.daq_ascan`.

- Added the `nabs.preprocessors` module with the following functions:

  - `nabs.preprocessors.daq_step_scan_wrapper`:
    A wrapper that mutates incoming messages from a plan to also include DAQ calib cycles as required for a step scan.
  - `nabs.preprocessors.daq_step_scan_decorator`:
    A function decorator that modifies a plan to add standard DAQ configuration arguments and to run properly with the DAQ as a step scan.
  - `nabs.preprocessors.daq_during_wrapper`:
    A wrapper that mutates a plan to run the DAQ in the background as a flyer during plan execution.
  - `nabs.preprocessors.daq_during_decorator`:
    A function decorator that modifies a plan to execute using the `nabs.preprocessors.daq_during_wrapper`.

Bugfixes
--------
- Fix issues related to SignalRO moving around in the ophyd API
- Fix issues related to measure_average not working for integer values

Maintenance
-----------
- Restructure the repository to accumulate CI/structural changes that
  we've been making to other repositories.
- Add missing numpy requirement
- Accumulate a toolz requirement (was already implicit via bluesky)
- Add dev requirements for pcdsdevices and pcdsdaq
- Allow python 3.7/3.8 travis builds to fail, because pcdsdaq does not work
  on these python versions.
- Rework the API docs, expand docs to include the new plans and preprocessors.
- Various other docs additions and changes.
- Fix issue with automated documentation uploads.

Contributors
------------
- zllentz


v0.0.0 (2018-04-19)
===================

Initial tag
