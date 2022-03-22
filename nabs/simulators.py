"""Simulation and validation functions for plans"""
import logging
import pprint
import sys  # NOQA
from contextlib import contextmanager

from bluesky.simulators import check_limits

logger = logging.getLogger(__name__)


class ValidError(Exception):
    pass


def check_open_close(plan):
    """
    Check if a plan is open and closed correctly.

    Nested plans are allowed if they are labeled properly
    with run tags.

    Raises if a violation is found
    If a message has as run key, all messages in that run must also.

    Parameters
    ----------
    plan : iterable
        Must yield `Msg` objects

    Raises
    ------
    ValidError
        If plan is not constructed correctly
    """
    stack = []
    run_keys = []

    for msg in plan:
        if msg.command == 'open_run':
            if msg.run in run_keys:
                raise ValidError("Duplicate run_key found, plans "
                                 "are nested incorrectly.")
            stack.append(msg)
            run_keys.append(msg.run)

        elif msg.command == 'close_run':
            _ = stack.pop()
            key = run_keys.pop()
            if key != msg.run:
                raise ValidError("Mismatched run keys, open_run "
                                 "and close_run misconfigured.")

        else:
            # generic message
            if len(stack) == 0:
                raise ValidError("Message found after all runs "
                                 "have closed.")

            if msg.run != stack[-1].run:
                raise ValidError("Message does not match run key "
                                 "of corresponding open_run. Plans "
                                 "are probably nested incorrectly.")

            if msg.run in run_keys[:-1]:
                raise ValidError("Message run key does not match "
                                 "that of nearest open_run.")


def raiser(*args, **kwargs):
    raise ValidError('forbidden method called')


@contextmanager
def patch_sys_modules(modules):
    """
    takes a list of module names as strings and stores them,
    replaces them with a raiser, and replaces them after

    Need to use exec/eval here due to pass-by-reference issues
    """
    cache = {}
    for name in modules:
        try:
            cache[name] = eval(name)
            exec(f'{name} = raiser')
        except Exception as ex:
            logger.debug(f'Failed to replace module {name}, {ex}')

    try:
        yield
    finally:
        # replace the references
        for name in cache:
            exec(f'{name} = cache[name]')


def check_stray_calls(plan):
    """
    Validate that plan does not invoke any caput functionality
    outside of messages.

    This is rather jank currently, it's entirely possible there is a
    better way around this.

    Relies on the pre-existing knowledge of which methods make calls
    to pyepics/caput functionality.  These are:
    - `ophyd.positioner.PositionerBase.move()`
    - `pcdsdevices.interface.MvInterface.move()`
    - ...

    Parameters
    ----------
    plan : iterable
        Must yield `Msg` objects

    Raises
    ------
    ValidError
        If attempts to access any forbidden methods
    """

    # context manager to replace sys.modules functions and replace
    with patch_sys_modules(patches):
        for _ in plan:
            continue


# be wary of how you specify these, they are keyed based on
# how they were imported.
patches = [
            "sys.modules['ophyd.sim'].SynAxis.set",
            "sys.modules['pcdsdevices'].interface.MvInterface.move"
]


validators = [
    check_stray_calls,
    check_limits,
    check_open_close,
]


def validate_plan(plan, validators=validators):
    """
    Validate plan with all available checkers.

    Parameters
    ----------
    plan: generator function
        Once called, must yield `Msg` objects.

    Returns
    -------
    boolean
        Indicates if validation was successful (``True``) or failed
        (``False``).
    str
        Error message that explains the reason for validation
        failure. Empty string if validation is successful.

    """
    success, msg = True, ""
    try:
        for check in validators:
            print(f'running {check.__name__}')
            check(plan())
    except Exception as ex:
        print(ex)
        msg = (f'Plan validation failed: {str(ex)}, for '
               f'plan: {pprint.pformat(plan)}')
        success = False
    return success, msg
