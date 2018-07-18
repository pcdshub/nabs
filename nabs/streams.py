"""Standard data streams for automated routines"""
from bluesky.callbacks.stream import LiveDispatcher
from pandas import DataFrame


class LiveDataFrame(LiveDispatcher):
    """
    DataFrame for Processing Pipeline

    The goal of this callback is to collect event documents as they are emitted
    from the RunEngine and collect them as a ``pandas.DataFrame``. This allows
    for concise on-the-fly analysis by utilizing the DataFrame API. In order to
    facilitate downstream consumers seeing the result of this analysis, we
    emit the result as a secondary stream of event documents. Subscribable in
    the same way that the event stream emitted from the RunEngine is.

    Parameters
    ----------
    func: callable
        Define the analysis done by the pipeline. This should be a function
        that takes a ``pandas.DataFrame`` of size ``cache_size`` and return a
        ``DataFrame`` or ``pandas.Series``.

    cache_size : int, optional
        Appending to a ``DataFrame`` is computationally inefficient, therefore,
        this callback waits until we have a certain number of events before
        condensing our events into a ``DataFrame``.
    """
    def __init__(self, func, cache_size=1):
        super().__init__()
        self.func = func
        self.raw_cache = list()
        self.cache_size = cache_size

    def event(self, doc):
        # Add event to raw cache
        self.raw_cache.append(doc)
        # If we have enough events average
        if len(self.raw_cache) == self.cache_size:
            # Check that all of our events came from the same configuration
            desc_id = self.raw_cache[0]['descriptor']
            if not all([desc_id == evt['descriptor']
                        for evt in self.raw_cache]):
                raise Exception('The events in this bundle are from '
                                'different configurations!')
            # Use the last descriptor to get all key names
            data_keys = self.raw_descriptors[desc_id]['data_keys']
            # Assemble dictionary of all values in the cache
            raw_dict = dict().fromkeys(data_keys.keys(), list())
            for key, info in data_keys.items():
                raw_dict[key] = [evt['data'][key] for evt in self.raw_cache]
            # Transform to a DataFrame
            df = DataFrame.from_dict(raw_dict)
            # Do any processing necessary
            self.process(df, desc_id)
            # Clear cache of events
            self.raw_cache.clear()

    def process(self, df, desc_id):
        # Store data internally
        self.last_event = self.func(df).to_dict()
        evt = {'data': self.last_event, 'descriptor': desc_id}
        # Emit event for subscribers
        return super().event(evt)

    def stop(self, doc):
        """Delete the stream when run stops"""
        self.raw_cache.clear()
        self.last_event = None
        super().stop(doc)


class AverageStream(LiveDataFrame):
    """
    Stream that averages data points together

    As event documents are emitted from the RunEngine they are collected by
    AverageStream, averaged and re-emitted as a secondary event stream. This
    allows callbacks to subscribe to the average stream for more elegant
    visualization and analysis.

    The average stream can either be constructed with a specific number of
    points to average or this information can be passed through in the start
    document metadata. See the :meth:`.start` for more information.

    Parameters
    ----------
    num : int, optional
        Number of points to average together

    Attributes
    ----------
    last_event : dict
        Data from the last event emitted by the stream. Used for limited access
        to processed data without the need for a subscription.
    """
    def __init__(self, num=None):
        # Initialize LiveDispatcher
        super().__init__(lambda x: x.mean(), cache_size=num)

    def start(self, doc):
        """
        Create the stream after seeing the start document

        The callback looks for the 'average' key in the start document to
        configure itself.
        """
        # Grab the average key
        self.cache_size = doc.get('average', self.cache_size)
        super().start(doc)

