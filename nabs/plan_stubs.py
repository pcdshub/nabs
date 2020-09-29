import logging
import math

from bluesky.plan_stubs import subscribe
from bluesky.plans import count
from bluesky.preprocessors import stub_wrapper

from .streams import AverageStream
from .utils import as_list

logger = logging.getLogger(__name__)


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
    yield from stub_wrapper(count(detectors, num=num, delay=delay))
    # Return the measured average as a dictionary for use in adaptive plans
    return stream.last_event


# Used to strip `run_wrapper` off of plan
# Should probably be added as bluesky PR
def block_run_control(msg):
    """
    Block open and close run messages
    """
    if msg.command in ['open_run', 'close_run']:
        return None
    return msg


def euclidean_distance(device, device_fields, targets, average=None,
                       filters=None):
    """
    Calculates the euclidean distance between the device_fields and targets.

    Parameters
    ----------
    device : :class:`.Device`
        Device from which to take the value measurements

    device_fields : iterable
        Fields of the device to measure

    targets : iterable
        Target value to calculate the distance from

    average : int, optional
        Number of averages to take for each measurement

    Returns
    -------
    distance : float
        The euclidean distance between the device fields and the targets.
    """
    average = average or 1
    # Turn things into lists
    device_fields = as_list(device_fields)
    targets = as_list(targets, len(device_fields))

    # Get the full detector fields
    prep_dev_fields = [field_prepend(fld, device) for fld in device_fields]

    # Make sure the number of device fields and targets is the same
    if len(device_fields) != len(targets):
        raise ValueError("Number of device fields and targets must be the same."
                         "Got {0} and {1}".format(len(device_fields,
                                                      len(targets))))
    # Measure the average
    read = (yield from measure_average([device], num=average, filters=filters))
    # Get the squared differences between the centroids
    squared_differences = [(read[fld]-target)**2 for fld, target in zip(
        prep_dev_fields, targets)]
    # Combine into euclidean distance
    distance = math.sqrt(sum(squared_differences))
    return distance
