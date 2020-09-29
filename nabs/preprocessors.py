import logging
from functools import wraps

from bluesky.plan_stubs import abs_set, checkpoint
from bluesky.plan_stubs import wait as plan_wait
from bluesky.utils import short_uid


def return_to_start(*devices, perform=True):
    """
    Decorator that will find the current positions of all the inputted devices,
    and them move them back to those positions after running the inner plan.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the initial positions of all the inputted devices
            initial_positions = {dev : dev.position for dev in devices}
            try:
                return (yield from func(*args, **kwargs))
            finally:
                # Start returning all the devices to their initial positions
                if perform:
                    group = short_uid('set')
                    for dev, pos in initial_positions.items():
                        yield from abs_set(dev, pos, group=group)
                    # Wait for all the moves to finish if they haven't already
                    yield from plan_wait(group=group)
        return wrapper
    return decorator
