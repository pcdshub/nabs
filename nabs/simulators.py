"""Simulation and validation functions for plans"""
import itertools
import logging
import sys  # NOQA
from contextlib import contextmanager
from typing import Any, Generator, Iterator, List, Tuple

from bluesky.simulators import check_limits

logger = logging.getLogger(__name__)


class ValidError(Exception):
    pass


def raiser(*args: Any, **kwargs: Any):
    raise ValidError('forbidden method called')


# Be wary of how you specify these, they are keyed based on
# how they were imported.
default_patches = [
            "sys.modules['ophyd'].sim.SynAxis.set",
            "sys.modules['ophyd'].signal.EpicsSignal.put",
]


@contextmanager
def patch_sys_modules(
    modules: List[str] = default_patches
) -> Generator[Any, None, None]:
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


def check_open_close(plan: Iterator[Any]) -> None:
    """
    Check if a plan is open and closed correctly.

    Nested plans are allowed if they are labeled properly
    with run tags.

    Raises if a violation is found
    If a message has as run key, all messages in that run must also.

    Parameters
    ----------
    plan : iterable or generator
        Must yield `Msg` objects

    Raises
    ------
    ValidError
        If plan is not constructed correctly
    """
    open_stack = []
    run_keys = []
    staged_devices = []
    for msg in plan:
        if msg.command == 'open_run':
            if msg.run in run_keys:
                raise ValidError("Duplicate run_key found, plans "
                                 "are nested incorrectly.")
            open_stack.append(msg)
            run_keys.append(msg.run)

        elif msg.command == 'close_run':
            _ = open_stack.pop()
            last_key = run_keys.pop()
            if last_key != msg.run:
                raise ValidError("Mismatched run keys, open_run "
                                 "and close_run misconfigured.")

        elif msg.command == 'stage':
            # keep track of staged devices
            if msg.obj in staged_devices:
                raise ValidError("Plan attempts to stage a device "
                                 "that is already staged.")
            staged_devices.append(msg.obj)

        elif msg.command == 'unstage':
            if msg.obj not in staged_devices:
                raise ValidError("Plan attempts to unstage a device "
                                 "that has not been staged.")
            # Currently assumes devices are unstaged in reverse order
            # of how they were staged.  maybe checks should happen..
            staged_devices.pop()

    # at end of plan, nothing should be left
    if open_stack:
        raise ValidError("Plan ended without all runs being closed.")
    elif run_keys:
        raise ValidError("Plan ended with unmatched run keys.")
    elif staged_devices:
        raise ValidError(
            "Plan ended without unstaging all staged devices."
        )


def check_stray_calls(
    plan: Iterator[Any],
    patches: List[str] = default_patches
) -> None:
    """
    Validate that plan does not invoke any caput functionality
    outside of messages.

    This is rather jank currently, it's entirely possible there is a
    better way around this.

    Relies on the pre-existing knowledge of which methods make calls
    to pyepics/caput functionality.

    Parameters
    ----------
    plan : iterable or generator
        Must yield `Msg` objects

    Raises
    ------
    ValidError
        If attempts to access any forbidden methods
    """

    with patch_sys_modules(patches):
        for _ in plan:
            continue


# check_limits is not hinted, so hinting this becomes miserable
validators = [
    check_stray_calls,
    check_open_close,
    check_limits,
]


def validate_plan(
    plan: Generator,
    validators=validators
) -> Tuple[bool, str]:
    """
    Validate plan with all available checkers.

    Parameters
    ----------
    plan: generator function
        Once called, must yield `Msg` objects.

    validators: list of check functions
        functions to run on the provided plan.  These should take an
        evaluated plan (generator) as input, and raise exceptions on
        failure.  (should NOT take generator functions)

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
        plan_list = itertools.tee(plan, len(validators))
        for i, check in enumerate(validators):
            print(f'running {check.__name__}')
            check(plan_list[i])
    except Exception as ex:
        print(ex)
        msg = (f'Plan validation failed for reason: {str(ex)}')
        success = False

    return success, msg


def summarize_plan(plan: Generator):
    """Print summary of plan

    Prints a minimal version of the plan, showing only moves and
    where events are created.

    Parameters
    ----------
    plan : iterable
        Must yield `Msg` objects
    """
    read_cache: List[str] = []
    daq_keys = ['events', 'record', 'use_l3t', 'duration']
    daq_cfg = {k: None for k in daq_keys}
    for msg in plan:
        cmd = msg.command
        if cmd == 'open_run':
            print('{:=^80}'.format(' Open Run '))
        elif cmd == 'close_run':
            print('{:=^80}'.format(' Close Run '))
        elif cmd == 'configure':
            if msg.obj.name == 'daq':
                daq_cfg = {k: msg.kwargs[k] for k in daq_keys}
                print(
                    f'Configure DAQ -> ('
                    f'events={daq_cfg["events"]}, '
                    f'record={daq_cfg["record"]}, '
                    f'use_l3t={daq_cfg["use_l3t"]}, '
                    f'duration={daq_cfg["duration"]})'
                )
        elif cmd == 'set':
            print('{motor.name} -> {args[0]}'.format(motor=msg.obj,
                                                     args=msg.args))
        elif cmd == 'create':
            read_cache = []
        elif cmd == 'read':
            read_cache.append(msg.obj.name)
            if msg.obj.name == 'daq':
                print(f'  Run DAQ for {daq_cfg["events"]} events, '
                      f'(record={daq_cfg["record"]})')
        elif cmd == 'save':
            print('  Read {}'.format(read_cache))
