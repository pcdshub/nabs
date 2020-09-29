"""
Calibration of the delay macromotor
"""
import logging

import numpy as np
import pandas as pd
from bluesky.plan_stubs import abs_set, rel_set
from bluesky.plan_stubs import wait as plan_wait
from bluesky.plans import scan
from bluesky.preprocessors import msg_mutator, stub_wrapper
from bluesky.utils import short_uid
from ophyd.utils import LimitError
from pswalker.plans import measure_average, walk_to_pixel
from scipy.signal import savgol_filter

from ..utils import as_list, flatten
from .preprocessors import return_to_start as _return_to_start
from .scans import centroid_scan

logger = logging.getLogger(__name__)

def calibrate_motor(detector, detector_fields, motor, motor_fields,
                    calib_motors, calib_fields, start, stop, steps,
                    confirm_overwrite=True, *args, **kwargs):
    """Performs a calibration scan using the inputted detector, motor, and
    calibration motors, then configures the motor using the resulting
    calibration.

    Parameters
    ----------
    detector : :class:`.BeamDetector`
        Detector from which to take the value measurements

    detector_fields : iterable
        Fields of the detector to measure

    motor : :class:`.Motor`
        Main motor to perform the scan

    calib_motors : iterable, :class:`.Motor`
        Motor to calibrate each detector field with

    start : float
        Starting position of motor

    stop : float
        Ending position of motor

    steps : int
        Number of steps to take

    confirm_overwrite : bool, optional
        Prompt the user if this plan will overwrite an existing calibration

    Returns
    -------
    configs : tuple of dict
        Old configuration and the new configuration.
    """
    calib_motors = as_list(calib_motors)
    # Check for motor having a _calib field
    motor_config = motor.read_configuration()
    if motor_config['calib']['value'] and motor_config['motors']['value']:
        logger.warning("Running the calibration procedure will overwrite the "
                       "existing calibration.")
        # If a calibration is loaded, prompt the user for verification
        if confirm_overwrite:
            # Prompt the user about the move before making it
            try:
                response = input("\nConfirm Overwrite [y/n]: ")
            except Exception as e:
                logger.warning("Exception raised: {0}".format(e))
                response = "n"
            if response.lower() != "y":
                logger.info("\Calibration cancelled.")
                return
            logger.debug("\nOverwrite confirmed.")

    # Perform the calibration scan
    df_calib, df_scan, scaling, start_pos = yield from calibration_scan(
        detector,
        detector_fields,
        motor,
        motor_fields,
        calib_motors,
        calib_fields,
        start, stop, steps,
        *args, **kwargs)

    # Load the calibration into the motor
    return motor.configure(calib=df_calib,
                           scan=df_scan,
                           motors=[motor]+calib_motors,
                           scale=scaling,
                           start=start_pos)

def calibration_scan(detector, detector_fields, motor, motor_fields,
                     calib_motors, calib_fields, start, stop, steps,
                     first_step=0.01, average=None, filters=None,
                     return_to_start=True, *args, **kwargs):
    """Performs a calibration scan for the main motor and returns a correction
    table for the calibration motors.

    This adds to ``calibration_scan`` by moving the motors to their original
    positions and and running the calibration calculation function. It returns
    the expected motor calibration given the results from the scan, as well as
    the dataframe from the scan with all the data.

    Parameters
    ----------
    detector : :class:`.BeamDetector`
        Detector from which to take the value measurements

    detector_fields : iterable
        Fields of the detector to measure

    motor : :class:`.Motor`
        Main motor to perform the scan

    calib_motors : iterable, :class:`.Motor`
        Motor to calibrate each detector field with

    start : float
        Starting position of motor

    stop : float
        Ending position of motor

    steps : int
        Number of steps to take

    first_step : float, optional
        First step to take on each calibration motor when performing the
        correction

    average : int, optional
        Number of averages to take for each measurement

    delay : float, optional
        Time to wait inbetween reads

    tolerance : float, optional
        Tolerance to use when applying the correction to detector field

    max_steps : int, optional
        Limit the number of steps the correction will take before exiting

    gradients : float, optional
        Assume an initial gradient for the relationship between detector value
        and calibration motor position

    return_to_start : bool, optional
        Move all the motors to their original positions after the scan has been
        completed

    Returns
    -------
    df_calibration : pd.DataFrame
        Dataframe containing the points to be used for the calibration by the
        calibration motors

    df_calibration_scan : pd.DataFrame
        DataFrame containing the positions of the detector,  motor, and
        calibration motor fields during the initial scan. The indices are the
        target motor positions.

    scaling : list
        List of the scaling values in units of motor egu / detector value used
        to calculate the calibration.

    start_positions : list
        List of starting positions used to perform the calibration calculation.
    """
    num = len(detector_fields)
    calib_motors = as_list(calib_motors)
    calib_fields = as_list(calib_fields or [m.name for m in calib_motors])
    motor_fields = as_list(motor_fields or motor.read().keys())
    if len(calib_motors) != num:
        raise ValueError("Must have same number of calibration motors as "
                         "detector fields.")
    if len(calib_fields) != num:
        raise ValueError("Must have same number of calibration fields as "
                         "detector fields.")

    @_return_to_start(motor, *calib_motors, perform=return_to_start)
    def inner():
        # Perform the main scan, reading the positions of all the devices
        logger.debug("Beginning calibration scan")
        df_scan = yield from calibration_centroid_scan(
            detector, motor, calib_motors,
            start, stop, steps,
            detector_fields=detector_fields,
            motor_fields=motor_fields,
            calib_fields=calib_fields,
            average=average,
            filters=filters)

        # Find the distance per detector value scaling and initial positions
        scaling, start_positions = yield from detector_scaling_walk(
            df_scan,
            detector,
            calib_motors,
            first_step=first_step,
            average=average,
            filters=filters,
            system=[motor],
            *args, **kwargs)

        # Build the calibration table
        df_calibration = build_calibration_df(df_scan, scaling, start_positions,
                                              detector)

        logger.debug("Completed calibration scan.")
        return df_calibration, df_scan, scaling, start_positions

    return (yield from inner())

def calibration_centroid_scan(detector, motor, calib_motors, start, stop, steps,
                              calib_fields=None, *args, **kwargs):
    """Performs a centroid scan producing a dataframe with the values of the
    detector, motor, and calibration motor fields.

    Parameters
    ----------
    detector : :class:`.BeamDetector`
        Detector from which to take the value measurements

    motor : :class:`.Motor`
        Main motor to perform the scan

    calib_motors : iterable
        Calibration motors

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

    calib_fields : list, optional
        Fields of the of the calibration motors to add to the returned dataframe

    Returns
    -------
    df : pd.DataFrame
        DataFrame containing the detector, motor, and calibration motor fields
        at every step of the scan.

    Raises
    ------
    ValueError
        If the inputted number of calibration motors does not have the same
        length as the number of calibration fields.
    """
    calib_fields = as_list(calib_fields or [m.name for m in calib_motors])

    # Make sure the same number of calibration fields as motors are passed
    if len(calib_motors) != len(calib_fields):
        raise ValueError("Must one calibration field for every calibration "
                         "motor, but got {0} fields for {1} motors.".format(
                             len(calib_fields), len(calib_motors)))

    # Perform the main scan, correctly passing the calibration parameters
    df = yield from centroid_scan(detector, motor,
                                  start, stop, steps,
                                  system=calib_motors,
                                  system_fields=calib_fields,
                                  return_to_start=False
                                  *args, **kwargs)

    # Let's adjust the column names of the calib motors
    df.columns = [c+"_pre" if c in calib_fields else c for c in df.columns]
    return df

def detector_scaling_walk(df_scan, detector, calib_motors,
                          first_step=0.01, average=None, filters=None,
                          tolerance=1, delay=None, max_steps=5, system=None,
                          drop_missing=True, gradients=None, *args, **kwargs):
    """Performs a walk to to the detector value farthest from the current value
    using each of calibration motors, and then determines the motor to detector
    scaling

    Using the inputted scan dataframe, the plan loops through each detector
    field, then finds the value that is farthest from the current value, and
    then performs a walk_to_pixel to that value using the corresponding
    calibration motor. Since the final absolute position does not matter so long
    as it is recorded, if a RuntimeError or LimitError is raised, the plan will
    simply use the current motor position for the scaling calculation.

    Parameters
    ----------
    df_scan : pd.DataFrame
        Dataframe containing the results of a centroid scan performed using the
        detector, motor, and calibration motors.

    detector : :class:`.Detector`
        Detector from which to take the value measurements

    calib_motors : iterable, :class:`.Motor`
        Motor to calibrate each detector field with

    first_step : float, optional
        First step to take on each calibration motor when performing the
        correction

    average : int, optional
        Number of averages to take for each measurement

    delay : float, optional
        Time to wait inbetween reads

    tolerance : float, optional
        Tolerance to use when applying the correction to detector field

    max_steps : int, optional
        Limit the number of steps the correction will take before exiting

    drop_missing : bool, optional
        Choice to include events where event keys are missing

    gradients : float, optional
        Assume an initial gradient for the relationship between detector value
        and calibration motor position

    Returns
    -------
    scaling : list
        List of scales in the units of motor egu / detector value

    start_positions : list
        List of the initial positions of the motors before the walk
    """
    detector_fields = [col for col in df_scan.columns if detector.name in col]
    calib_fields = [col[:-4] for col in df_scan.columns if col.endswith("_pre")]
    if len(detector_fields) != len(calib_fields):
        raise ValueError("Must have same number of calibration fields as "
                         "detector fields, but got {0} and {1}.".format(
                             len(calib_fields), len(detector_fields)))

    # Perform all the initial necessities
    num = len(detector_fields)
    average = average or 1
    calib_motors = as_list(calib_motors)
    first_step = as_list(first_step, num, float)
    tolerance = as_list(tolerance, num)
    gradients = as_list(gradients, num)
    max_steps = as_list(max_steps, num)
    system = as_list(system or []) + calib_motors

    # Define the list that will hold the scaling
    scaling, start_positions = [], []

    # Now let's get the detector value to motor position conversion for each fld
    for i, (dfld, cfld, cmotor) in enumerate(zip(detector_fields,
                                                 calib_fields,
                                                 calib_motors)):
        # Get a list of devices without the cmotor we are inputting
        inp_system = list(system)
        inp_system.remove(cmotor)

        # Store the current motor and detector value and position
        reads = yield from measure_average([detector]+system,
                                            num=average,
                                            filters=filters)
        motor_start = reads[cfld]
        dfld_start = reads[dfld]

        # Get the farthest detector value we know we can move to from the
        # current position
        idx_max = abs(df_scan[dfld] - dfld_start).values.argmax()

        # Walk the cmotor to the first pre-correction detector entry
        try:
            logger.debug("Beginning walk to {0} on {1} using {2}".format(
                df_scan.iloc[idx_max][dfld], detector.name, cmotor.name))
            yield from walk_to_pixel(detector,
                                     cmotor,
                                     df_scan.iloc[idx_max][dfld],
                                     filters=filters,
                                     gradient=gradients[i],
                                     target_fields=[dfld, cfld],
                                     first_step=first_step[i],
                                     tolerance=tolerance[i],
                                     system=inp_system,
                                     average=average,
                                     max_steps=max_steps[i]
                                     *args, **kwargs)

        except RuntimeError:
            logger.warning("walk_to_pixel raised a RuntimeError for motor '{0}'"
                           ". Using its current position {1} for scale "
                           "calulation.".format(cmotor.desc, cmotor.position))
        except LimitError:
            logger.warning("walk_to_pixel tried to exceed the limits of motor "
                           "'{0}'. Using current position '{1}' for scale "
                           "calculation.".format(cmotor.desc, cmotor.position))

        # Get the positions and values we moved to
        reads = (yield from measure_average([detector]+system,
                                            num=average,
                                            filters=filters))
        motor_end = reads[cfld]
        dfld_end = reads[dfld]

        # Now lets find the conversion from signal value to motor distance
        scaling.append((motor_end - motor_start)/(dfld_end - dfld_start))
        # Add the starting position to the motor start list
        start_positions.append(motor_start)

    # Return the final scaling list
    return scaling, start_positions

def build_calibration_df(df_scan, scaling, start_positions, detector):
    """Takes the scan dataframe, scaling, and starting positions to build a
    calibration table for the calibration motors.

    The resulting dataframe will contain all the scan motor read fields as well
    as two columns for each calibration motor that has an absolute correction
    relative correction.

    Parameters
    ----------
    df_scan : pd.DataFrame
        Dataframe containing the results of a centroid scan performed using the
        detector, motor, and calibration motors.

    scaling : list
        List of scales in the units of motor egu / detector value

    start_positions : list
        List of the initial positions of the motors before the walk

    detector : :class:`.Detector`
        Detector from which to take the value measurements

    Returns
    -------
    df_calibration : pd.DataFrame
        Calibration dataframe that has all the scan motor fields and the
        corrections required of the calibration motors in both absolute and
        relative corrections.
    """
    # Get the fields being used in the scan df
    detector_fields = [col for col in df_scan.columns if detector.name in col]
    calib_fields = [col[:-4] for col in df_scan.columns if col.endswith("_pre")]
    motor_fields = [col for col in df_scan.columns
                    if col not in detector_fields and not col.endswith("_pre")]

    # Ensure these two are equal
    if len(detector_fields) != len(calib_fields):
        raise ValueError("Must have same number of calibration fields as "
                         "detector fields, but got {0} and {1}.".format(
                             len(calib_fields), len(detector_fields)))

    df_corrections = pd.DataFrame(index=df_scan.index)

    # Use the conversion to create an expected correction table
    for scale, start, cfld, dfld in zip(scaling, start_positions, calib_fields,
                                        detector_fields):
        # Absolute move to make to perform correction for this motor
        df_corrections[cfld+"_post"] = \
          start - (df_scan[dfld] - df_scan[dfld].iloc[0]) * scale

    # Put together the calibration table
    df_calibration = pd.concat([df_scan[motor_fields], df_corrections], axis=1)

    return df_calibration
