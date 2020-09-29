"""
Scans for HXRSnD
"""
import logging

import numpy as np
import pandas as pd
from bluesky import Msg
from bluesky.plan_stubs import abs_set, checkpoint, trigger_and_read
from bluesky.plans import scan
from bluesky.preprocessors import (msg_mutator, run_decorator, stage_decorator,
                                   stub_wrapper)
from bluesky.utils import short_uid as _short_uid
from pswalker.plans import measure_average
from pswalker.utils import field_prepend

from ..utils import as_list
from .preprocessors import return_to_start as _return_to_start

logger = logging.getLogger(__name__)

def linear_scan(motor, start, stop, num, use_diag=True, return_to_start=True,
                md=None, *args, **kwargs):
    """
    Linear scan of a motor without a detector.

    Performs a linear scan using the inputted motor, optionally using the
    diagnostics, and optionally moving the motor back to the original start
    position. This scan is different from the regular scan because it does not
    take a detector, and simply scans the motor.

    Parameters
    ----------
    motor : object
        any 'setable' object (motor, temp controller, etc.)

    start : float
        starting position of motor

    stop : float
        ending position of motor

    num : int
        number of steps

    use_diag : bool, optional
        Include the diagnostic motors in the scan.

    md : dict, optional
        metadata
    """
    # Save some metadata on this scan
    _md = {'motors': [motor.name],
           'num_points': num,
           'num_intervals': num - 1,
           'plan_args': {'num': num,
                         'motor': repr(motor),
                         'start': start,
                         'stop': stop},
           'plan_name': 'daq_scan',
           'plan_pattern': 'linspace',
           'plan_pattern_module': 'numpy',
           'plan_pattern_args': dict(start=start, stop=stop, num=num),
           'hints': {},
          }
    _md.update(md or {})

    # Build the list of steps
    steps = np.linspace(**_md['plan_pattern_args'])

    # Let's store this for now
    start = motor.position

    # Define the inner scan
    # @stage_decorator([motor])
    @run_decorator(md=_md)
    def inner_scan():

        for i, step in enumerate(steps):
            logger.info("\nStep {0}: Moving to {1}".format(i+1, step))
            grp = _short_uid('set')
            yield Msg('checkpoint')
            # Set wait to be false in set once the status object is implemented
            yield Msg('set', motor, step, group=grp, *args, **kwargs)
            yield Msg('wait', None, group=grp)
            yield from trigger_and_read([motor])

        if return_to_start:
            logger.info("\nScan complete. Moving back to starting position: {0}"
                        "\n".format(start))
            yield Msg('set', motor, start, group=grp, *args, **kwargs)
            yield Msg('wait', None, group=grp)

    return (yield from inner_scan())

def centroid_scan(detector, motor, start, stop, steps, average=None,
                  detector_fields=['stats2_centroid_x', 'stats2_centroid_y'],
                  motor_fields=None, system=None, system_fields=None,
                  filters=None, return_to_start=True, *args, **kwargs):
    """
    Performs a scan and returns the centroids of the inputted detector.

    The returned centroids can be absolute or relative to the initial value. The
    values are returned in a pandas DataFrame where the indices are the target
    motor positions.

    Parameters
    ----------
    detector : :class:`.BeamDetector`
        Detector from which to take the value measurements

    motor : :class:`.Motor`
        Main motor to perform the scan

    start : float
        Starting position of motor

    stop : float
        Ending position of motor

    steps : int
        Number of steps to take

    average : int, optional
        Number of averages to take for each measurement

    detector_fields : iterable, optional
        Fields of the detector to add to the returned dataframe

    motor_fields : iterable, optional
        Fields of the motor to add to the returned dataframe

    system : list, optional
        Extra devices to include in the datastream as we measure the average

    system_fields : list, optional
        Fields of the extra devices to add to the returned dataframe

    filters : dict, optional
        Key, callable pairs of event keys and single input functions that
        evaluate to True or False. For more infromation see
        :meth:`.apply_filters`

    return_to_start : bool, optional
        Move the scan motor back to its initial position after the scan

    Returns
    -------
    df : pd.DataFrame
        DataFrame containing the detector, motor, and system fields at every
        step of the scan.
    """
    average = average or 1
    system = as_list(system or [])
    all_devices = [motor] + system + [detector]

    # Ensure all fields are lists
    detector_fields = as_list(detector_fields)
    motor_fields = as_list(motor_fields or motor.name)
    system_fields = as_list(system_fields or [])

    # Get the full detector fields
    prep_det_fields = [field_prepend(fld, detector) for fld in detector_fields]
    # Put all the fields together into one list
    all_fields = motor_fields + system_fields + prep_det_fields

    # Build the dataframe with the centroids
    df = pd.DataFrame(columns=all_fields, index=np.linspace(start, stop, steps))

    # Create a basic measuring plan
    def per_step(detectors, motor, step):
        # Perform step
        yield from checkpoint()
        logger.debug("Measuring average at step {0} ...".format(step))
        yield from abs_set(motor, step, wait=True)
        # Measure the average
        reads = (yield from measure_average(all_devices, num=average,
                                            filters=filters, *args, **kwargs))
        # Fill the dataframe at this step with the centroid difference
        for fld in all_fields:
            df.loc[step, fld] = reads[fld]

    # Run the inner plan
    @_return_to_start(motor, perform=return_to_start)
    def inner():
        plan = scan([detector], motor, start, stop, steps, per_step=per_step)
        yield from stub_wrapper(plan)
    yield from inner()

    # Return the filled dataframe
    return df
