=========================
Plans and Data Collection
=========================

Overview
========
The ``nabs`` module contains general data collection support for the
LCLS hutches. This relies entirely on the upstream ``bluesky`` support
for running scans and on the ``DAQ`` group's infrastructure for
collecting and event-matching data at high rates.

Implementation
==============
The ``bluesky`` module features a ``plan mutator`` concept, which allows
us to intercept messages and modify what execution instructions the
run engine recieves. In this way, we can "magically" include DAQ support
in any existing ``bluesky`` plan in a standardized way.

See :ref:`Preprocessors API` for the various magic methods we use to
hook the ``DAQ`` into any ``bluesky`` plan.

Selected Plans
==============
See :ref:`Plans API` for a full listing of these functions and their API.
This section will draw attention to the most useful plans and examples.

.. autosummary::
   :nosignatures:
   :toctree: generated

   ~nabs.plans.daq_count
   ~nabs.plans.daq_scan
   ~nabs.plans.daq_list_scan
   ~nabs.plans.daq_delay_scan
