"""
Plan pieces that may be useful for assembling plans.

This is the LCLS counterpart to `bluesky.plan_stubs`.

The plans in this module are not meant to be run individually, instead these
are intended as building blocks for other complete plans.
"""
import logging

import yaml
from bluesky.plan_stubs import subscribe
from bluesky.plans import count
from bluesky.preprocessors import stub_wrapper

from nabs.streams import AverageStream

logger = logging.getLogger(__name__)


def measure_average(detectors, num, delay=None, stream=None):
    """
    Measure an average over a number of shots from a set of detectors.

    Parameters
    ----------
    detectors : list
        List of detectors to read

    num : int
        Number of shots to average together

    delay : iterable or scalar, optional
        Time delay between successive readings. See `bluesky.plans.count`
        for more details

    stream : :py:class:`nabs.streams.AverageStream`, optional
        If a plan will call `measure_average` multiple times, a single
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


def update_sample(sample_name, path, n_shots):
    """
    Update the current sample information after a run.

    Updates the ``status`` values of each target in the sample,
    from `False` to `True` to indicate that it is shot.

    Parameters
    ----------
    sample_name : str
        A name to identify the sample grid, should be snake_case style.
    path : str
        Path to the ``.yml`` file. Defaults to the path defined when
        creating this object.
    n_shots : int
        Indicates how many targets have been shot.

    """
    info = get_sample_targets(sample_name, path)
    data = {}
    # list of dictionaries
    xx = info[0]
    yy = info[1]
    # find the index of the targets that is next to be shot
    x_index = next((index for (index, d) in enumerate(xx)
                    if d["status"] is False), None)
    if x_index is None:
        raise IndexError('Could not get a target index that has not been shot,'
                         ' probably all targets were shot from this sample?')

    temp_x, temp_y = [], []
    for i in range(n_shots):
        # update the status for the next target where the status is False
        x_target = next((item for item in xx if item['status'] is False), None)
        y_target = next((item for item in yy if item["status"] is False), None)
        # should not be getting here but just in case:
        if x_target is None:
            raise IndexError('Could not update the status of targets. '
                             'Probably all targets from this sample were shot '
                             'already....')
        x_target['status'] = True
        y_target['status'] = True
        temp_x.append(x_target)
        temp_y.append(y_target)

    # update the list original list of target
    xx[x_index:(x_index + len(temp_x))] = temp_x
    yy[x_index:(x_index + len(temp_y))] = temp_y
    data['xx'] = xx
    data['yy'] = yy

    with open(path) as sample_file:
        yaml_dict = yaml.safe_load(sample_file) or {}
        yaml_dict[sample_name].update(data)
    with open(path, 'w') as sample_file:
        yaml.safe_dump(yaml_dict, sample_file,
                       sort_keys=False, default_flow_style=False)


def get_sample_targets(sample_name, path):
    """
    Get the ``xx`` and ``yy`` target information from a saved sample.

    Given a sample name, get the x, y grid points that are mapped for that
    sample.

    Parameters
    ----------
    sample_name : str
        The name of the sample to get the mapped points from. To see the
        available mapped samples call the ``mapped_samples`` method.
    path : str, optional
        Path to the samples yaml file.

    Returns
    -------
    ``xx``, ``yy`` : tuple
        Returns two lists of dictionaries, with information about the targets.
    """
    data = None
    with open(path) as sample_file:
        try:
            data = yaml.safe_load(sample_file)
        except yaml.YAMLError as err:
            logger.error('Error when loading the samples yaml file: %s',
                         err)
            raise err
    if data is None:
        raise Exception('The file is empty, no sample grid yet. '
                        'Please use `save_presets` to insert grids '
                        'in the file.')
    try:
        sample = data[str(sample_name)]
        xx = sample['xx']
        yy = sample['yy']
        return xx, yy
    except Exception:
        err_msg = (f'This sample {sample_name} might not exist in the file.')
        raise Exception(err_msg)
