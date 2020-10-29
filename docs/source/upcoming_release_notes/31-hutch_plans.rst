31 hutch_plans
##############

API Changes
-----------
- N/A

Features
--------
- Added the :mod:`nabs.plans` module with the following functions:
  - :func:`nabs.plans.duration_scan`:
    A bluesky plan that moves a motor back and forth for a fixed duration.
  - :func:`nabs.plans.delay_scan`:
    A bluesky plan that configures a sweep time for a laser delay stage
    and runs a :func:`nabs.plans.duration scan`.
  - :func:`nabs.plans.daq_delay_scan`:
    A bluesky plan that runs the daq during a :func:`nabs.plans.delay_scan`.
  - :func:`nabs.plans.daq_count`:
    A bluesky plan that runs the daq n times while moving no motors.
  - :func:`nabs.plans.daq_scan`:
    A bluesky plan that runs calib cycles at each step while doing the built-in bluesky nd ``scan`` plan, returning motors to their original positions after the scan.
  - :func:`nabs.plans.daq_list_scan`:
    A bluesky plan that runs calib cycles at each step while doing the built-in bluesky ``list_scan`` plan, returning motors to their original positions after the scan.
  - :func:`nabs.plans.daq_ascan`:
    A bluesky plan that runs calib cycles at each step of a traditional 1D ascan (absolute scan), returning motors to their original positions after the scan.
  - :func:`nabs.plans.daq_dscan`:
    A bluesky plan that runs calib cycles at each step of a traditional 1D dscan (delta scan), returning motors to their original positions after the scan.
  - :func:`nabs.plans.daq_a2scan`:
    A 2-dimensional :func:`nabs.plans.daq_ascan`.
  - :func:`nabs.plans.daq_a3scan`:
    A 3-dimensional :func:`nabs.plans.daq_ascan`.
- Added the :mod:`nabs.preprocessors` module with the following functions:
  - :func:`nabs.preprocessors.daq_step_scan_wrapper`:
    A wrapper that mutates incoming messages from a plan to also include DAQ calib cycles as required for a step scan.
  - :func:`nabs.preprocessors.daq_step_scan_decorator`:
    A function decorator that modifies a plan to add standard DAQ configuration arguments and to run properly with the DAQ as a step scan.
  - :func:`nabs.preprocessors.daq_during_wrapper`:
    A wrapper that mutates a plan to run the DAQ in the background as a flyer during plan execution.
  - :func:`nabs.preprocessors.daq_during_decorator`:
    A function decorator that modifies a plan to execute using the :func:`nabs.preprocessors.daq_during_wrapper`.

Bugfixes
--------
- N/A

Maintenance
-----------
- Add missing numpy requirement
- Accumulate a toolz requirement (was already implicit via bluesky)
- Add dev requirements for pcdsdevices and pcdsdaq
- Allow python 3.7/3.8 travis builds to fail, because pcdsdaq does not work
  on these python versions.
- Rework the API docs, expand docs to include the new plans and preprocessors.
- Various other docs additions and changes.

Contributors
------------
- zllentz
