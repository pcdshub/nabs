31 hutch_plans
##############

API Changes
-----------
- N/A

Features
--------
- Added the :module:`nabs.plans` module with the following functions:
  - :func:`duration_scan`: A bluesky plan that moves a motor back and
                           forth for a fixed duration.
  - :func:`delay_scan`: A bluesky plan that configures a sweep time
                        for a laser delay stage and runs a
                        :func:`duration scan`.
  - :func:`daq_delay_scan`: A bluesky plan that runs the daq during a
                            :func:`delay_scan`.
  - :func:`daq_count`: A bluesky plan that runs the daq n times while
                       moving no motors.
  - :func:`daq_scan`: A bluesky plan that runs calib cycles at each step
                      while doing the built-in bluesky nd ``scan`` plan,
                      returning motors to their original positions after
                      the scan.
  - :func:`daq_list_scan`: A bluesky plan that runs calib cycles at each
                           step while doing the built-in bluesky
                           ``list_scan`` plan, returning motors to their
                           original positions after the scan.
  - :func:`daq_ascan`: A bluesky plan that runs calib cycles at each step
                       of a traditional 1D ascan (absolute scan),
                       returning motors to their original positions after
                       the scan.
  - :func:`daq_dscan`: A bluesky plan that runs calib cycles at each step
                       of a traditional 1D dscan (delta scan),
                       returning motors to their original positions after
                       the scan.
  - :func:`daq_a2scan`: A 2-dimensional :func:`daq_ascan`.
  - :func:`daq_a3scan`: A 3-dimensional :func:`daq_ascan`.
- Added the nabs.preprocessors module with the following functions:
  - :func:`daq_step_scan_wrapper`: A wrapper that mutates incoming messages
                                   from a plan to also include DAQ calib
                                   cycles as required for a step scan.
  - :func:`daq_step_scan_decorator`: A function decorator that modifies a plan
                                     to add standard DAQ configuration
                                     arguments and to run properly with the
                                     DAQ as a step scan.
  - :func:`daq_during_wrapper`: A wrapper that mutates a plan to run the DAQ
                                in the background as a flyer during plan
                                execution.
  - :func:`daq_during_decorator`: A function decorator that modifies a plan to
                                  execute using the `daq_during_wrapper`.

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
