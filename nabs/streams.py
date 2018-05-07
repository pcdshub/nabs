"""Standard data streams for automated routines"""
import numpy as np
from bluesky.callbacks.stream import LiveDispatcher


class AverageStream(LiveDispatcher):
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
    n : int, optional
        Number of points to average together
    """
    def __init__(self, n=None):
        # Initialize LiveDispatcher
        super().__init__()
        self.n = n
        self.last_event = None
        self.raw_cache = list()

    def start(self, doc):
        """
        Create the stream after seeing the start document

        The callback looks for the 'average' key in the start document to
        configure itself.
        """
        # Grab the average key
        self.n = doc.get('average', self.n)
        super().start(doc)

    def event(self, doc):
        """Send an Event through the stream"""
        # Add event to raw cache
        self.raw_cache.append(doc)
        # If we have enough events average
        if len(self.raw_cache) == self.n:
            average_evt = dict()
            # Check that all of our events came from the same configuration
            desc_id = self.raw_cache[0]['descriptor']
            if not all([desc_id == evt['descriptor']
                        for evt in self.raw_cache]):
                raise Exception('The events in this bundle are from '
                                'different configurations!')
            # Use the last descriptor to avoid strings and objects
            data_keys = self.raw_descriptors[desc_id]['data_keys']
            for key, info in data_keys.items():
                # Information from non-number fields is dropped
                if info['dtype'] in ('number', 'array'):
                    # Average together
                    average_evt[key] = np.mean([evt['data'][key]
                                                for evt in self.raw_cache],
                                               axis=0)
            self.last_event = {'data': average_evt, 'descriptor': desc_id}
            # Clear cache of events
            self.raw_cache.clear()
            # Emit event for subscribers
            return super().event(self.last_event)

    def stop(self, doc):
        """Delete the stream when run stops"""
        self.raw_cache.clear()
        self.last_event = None
        super().stop(doc)
