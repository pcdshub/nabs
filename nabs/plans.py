from bluesky.plans import scan

from .plan_stubs import monitor_step


def monitor_scan(detectors, *args, num=None, events=None, duration=None,
                 md=None):
    """
    Scan over a multi-motor trajectory for number of epics events or duration.

    Either events, duration, or both must be provided. If both are provided,
    we'll wait for both a number of events and a duration, not moving on
    until both are satisfied.

    The events counter applies to all detectors.

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    *args :
        For one dimension, ``motor, start, stop``.
        In general:

        .. code-block:: python

            motor1, start1, stop1,
            motor2, start2, start2,
            ...,
            motorN, startN, stopN

        Motors can be any 'settable' object (motor, temp controller, etc.)
    num : integer
        number of points
    events : ``int``, optional
        The number of epics updates to monitor for at each point.
    duration : ``float``, optional
        The fixed duration in seconds to monitor for at each point.
    md : dict, optional
        metadata
    """
    # I was also surprised this became a 2-liner
    per_step = monitor_step(events=events, duration=duration)
    yield from scan(detectors, *args, num=num, per_step=per_step, md=md)
