"""
Alignment plans for the HXRSnD
"""

import logging

import numpy as np
from bluesky import Msg
from bluesky.plan_stubs import abs_set, checkpoint, trigger_and_read
from bluesky.plans import list_scan, scan
from bluesky.preprocessors import msg_mutator, subs_decorator
from bluesky.utils import short_uid as _short_uid
from lmfit.models import LorentzianModel
from pswalker.callbacks import LiveBuild
from pswalker.plans import measure_average

from ..exceptions import UndefinedBounds
from .plan_stubs import block_run_control

logger = logging.getLogger(__name__)


def maximize_lorentz(detector, motor, read_field, step_size=1,
                     bounds=None, average=None, filters=None,
                     position_field='user_readback', initial_guess=None):
    """
    Maximize a signal with a Lorentzian relationship to a motor

    The following plan does a linear step scan through the parameter space
    while collecting information to create a Lorentzian model. After the scan
    has completed, the created model will be queried to find the estimated
    motor position that will yield the absolute maximum of the Lorentz equation

    Parameters
    ----------
    detector : obj
        The object to be read during the plan

    motor : obj
        The object to be moved via the plan.

    read_field : str
        Field of detector to maximize

    nsteps : int, optional
        The step size used by the initial linear scan to create the Lorentzian
        model. A smaller step size will create a more accurate model, while a
        larger step size will increase the speed of the entire operation.

    bounds : tuple, optional
        The lower and higher limit of the search space. If no value is given
        the :attr:`.limits` property of the motor will be queried next. If this
        does not yield anything useful an exception will be raised

    average : int, optional
        The number of shots to average at every step of the scan. If left as
        None, no average will be used

    filters : dict, optional
        Filters used to drop shots from the analysis

    position_field : str, optional
        Motor field that will have the Lorentzian relationship with the given
        signal

    initial_guess : dict, optional
        Initial guess to the Lorentz model parameters of `sigma` `center`
        `amplitude`
    """
    average = average or 1
    # Define bounds
    if not bounds:
        try:
            bounds = motor.limits
            logger.debug("Bounds were not specified, the area "
                         "between %s and %s will searched",
                         bounds[0], bounds[1])
        except AttributeError as exc:
            raise UndefinedBounds("Bounds are not defined by motor {} or "
                                  "plan".format(motor.name)) from exc
    # Calculate steps
    steps = np.arange(bounds[0], bounds[1], step_size)
    # Include the last step even if this is smaller than the step_size
    steps = np.append(steps, bounds[1])
    # Create Lorentz fit and live model build
    fit    = LorentzianModel(missing='drop')
    i_vars = {'x' : position_field}
    model  = LiveBuild(fit, read_field, i_vars, filters=filters,
                       average=average, init_guess=initial_guess)#,
                       # update_every=len(steps)) # Set to fit only on last step

    # Create per_step plan
    def measure(detectors, motor, step):
        # Perform step
        logger.debug("Measuring average at step %s ...", step)
        yield from checkpoint()
        yield from abs_set(motor, step, wait=True)
        # Measure the average
        return (yield from measure_average([motor, detector],
                                           num=average,
                                           filters=filters))
    # Create linear scan
    plan = list_scan([detector], motor, steps, per_step=measure)

    @subs_decorator(model)
    def inner():
        # Run plan (stripping open/close run messages)
        yield from msg_mutator(plan, block_run_control)

        # Yield result of Lorentz model
        logger.debug(model.result.fit_report())
        max_position = model.result.values['center']

        # Check that the estimated position is reasonable
        if not bounds[0] < max_position  < bounds[1]:
            raise ValueError("Predicted maximum position of {} is outside the "
                             "bounds {}".format(max_position, bounds))
        # Order move to maximum position
        logger.debug("Travelling to maximum of Lorentz at %s", max_position)
        yield from abs_set(motor, model.result.values['center'], wait=True)

    # Run the assembled plan
    yield from inner()
    # Return the fit
    return model


def rocking_curve(detector, motor, read_field, coarse_step, fine_step,
                  bounds=None, average=None, fine_space=5, initial_guess=None,
                  position_field='user_readback', show_plot=True):
    """
    Travel to the maxima of a bell curve

    The rocking curve scan is two repeated calls of :func:`.maximize_lorentz`.
    The first is a rough step scan which searches the area given by ``bounds``
    using ``coarse_step``, the idea is that this will populate the model enough
    such that we can do a more accurate scan of a smaller region of the search
    space. Once the rough scan is completed, the maxima of the fit is used as
    the center of the new fine scan that probes a region of space with a region
    twice as large as the ``fine_space`` parameter. After this, the motor is
    translated to the calculated maxima of the model

    Parameters
    ----------
    detector : obj
        The object to be read during the plan

    motor : obj
        The object to be moved via the plan.

    read_field : str
        Field of detector to maximize

    coarse_step : float
        Step size for the initial rough scan

    fine_step : float
        Step size for the fine scan

    bounds : tuple, optional
        Bounds for the original rough scan. If not provided, the soft limits of
        the motor are used

    average : int, optional
        Number of shots to average at each step

    fine_space : float, optional
        The amount to scan on either side of the rough scan result. Note that
        the rocking_curve will never tell the secondary scan to travel outside

    position_field : str, optional
        Motor field that will have the Lorentzian relationship with the given
        signal

    initial_guess : dict, optional
        Initial guess to the Lorentz model parameters of `sigma` `center`
        `amplitude`
        of the ``bounds``, so this region may be truncated.

    show_plot : bool, optional
        Create a plot displaying the progress of the `rocking_curve`
    """
    # Define bounds
    if not bounds:
        try:
            bounds = motor.limits
            logger.debug("Bounds were not specified, the area "
                         "between %s and %s will searched",
                         bounds[0], bounds[1])
        except AttributeError as exc:
            raise UndefinedBounds("Bounds are not defined by motor {} or "
                                  "plan".format(motor.name)) from exc
    if show_plot:
        # Create plot
        # subscribe first plot to rough_scan
        pass
    # Run the initial rough scan
    try:
        model = yield from maximize_lorentz(detector, motor, read_field,
                                            step_size=coarse_step,
                                            bounds=bounds, average=average,
                                            position_field=position_field,
                                            initial_guess=initial_guess)
    except ValueError as exc:
        raise ValueError("Unable to find a proper maximum value"
                         "during rough scan") from exc
    # Define new bounds
    center = model.result.values['center']
    bounds = (max(center - fine_space, bounds[0]),
              min(center + fine_space, bounds[1]))

    logger.info("Rough scan of region yielded maximum of %s, "
                "performing fine scan from %s to %s ...",
                center, bounds[0], bounds[1])

    if show_plot:
        # Highlight search space on first plot
        # Subscribe secondary plot
        pass

    # Run the initial rough scan
    try:
        fit = yield from maximize_lorentz(detector, motor, read_field,
                                          step_size=fine_step, bounds=bounds,
                                          average=average,
                                          position_field=position_field,
                                          initial_guess=model.result.values)
    except ValueError as exc:
        raise ValueError("Unable to find a proper maximum value"
                         "during fine scan") from exc

    if show_plot:
        # Draw final calculated max on plots
        pass

    return fit
