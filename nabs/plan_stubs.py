import logging

from bluesky.callbacks import CallbackCounter
from bluesky.plan_stubs import subscribe, trigger_and_read, repeat
from bluesky.preprocessors import stage_decorator, subs_decorator

from .streams import AverageStream

logger = logging.getLogger(__name__)


def count_events(detectors, num=1, delay=None, *, md=None):
    """
    Extended version of the built-in count that doesn't count dropped events.

    Unlike count, this it NOT a full plan by itself (no run wrapper).
    Otherwise, this will work exactly like normal count unless `drop_wrapper`
    is in effect, in which case we will repeat any dropped reading.
    """
    counter = CallbackCounter()

    def read_and_check_done():
        yield from trigger_and_read(detectors)
        if counter.value >= num:
            raise CountDone()

    @stage_decorator(detectors)
    @subs_decorator({'event': counter})
    def inner_count_events():
        try:
            # Start an infinite count
            yield from repeat(read_and_check_done, num=None, delay=delay)
        except CountDone:
            # Quit when the event counter says so
            return

    return (yield from inner_count_events())


class CountDone(Exception):
    pass


def measure_average(detectors, num, delay=None, stream=None):
    """
    Measure an average over a number of shots from a set of detectors

    Parameters
    ----------
    detectors : list
        List of detectors to read

    num : int
        Number of shots to average together

    delay: iterable or scalar, optional
        Time delay between successive readings. See ``bluesky.count`` for more
        details

    stream : AverageStream, optional
        If a plan will call :func:`.measure_average` multiple times, a single
        ``AverageStream`` instance can be created and then passed in on each
        call. This allows other callbacks to subscribe to the averaged data
        stream. If no ``AverageStream`` is provided then one is created for the
        purpose of this function.

    Returns
    -------
    averaged_event : dict
        A dictionary of all the measurements taken from the list of detectors
        averaged for ``num`` shots. The keys follow the same naming convention
        as that will appear in the event documents i.e "{name}_{field}"

    Notes
    -----
    The returned average dictionary will only contain keys for 'number' or
    'array' fields. Field types that can not be averaged such as 'string' will
    be ignored, do not expect them in the output.
    """
    # Create a stream and subscribe if not given one
    if not stream:
        stream = AverageStream(num=num)
        yield from subscribe('all', stream)
        # Manually kick the LiveDispatcher to emit a start document because we
        # will not see the original one since this is subscribed after open_run
        stream.start({'uid': None})
    # Ensure we sync our stream with request if using a prior one
    else:
        stream.num = num
    # Measure our detectors
    yield from count_events(detectors, num=num, delay=delay)
    # Return the measured average as a dictionary for use in adaptive plans
    return stream.last_event
