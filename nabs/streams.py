"""Standard data streams for automated routines"""
import streamz
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
        self.n = n
        self.in_node = None
        self.out_node = None
        self.averager = None
        super().__init__()

    def start(self, doc):
        """
        Create the stream after seeing the start document

        The callback looks for the 'average' key in the start document to
        configure itself.
        """
        # Grab the average key
        self.n = doc.get('average', self.n)
        # Define our nodes
        if not self.in_node:
            self.in_node = streamz.Source(stream_name='Input')

        self.averager = self.in_node.partition(self.n)

        def average_events(cache):
            average_evt = dict()
            desc_id = cache[0]['descriptor']
            # Check that all of our events came from the same configuration
            if not all([desc_id == evt['descriptor'] for evt in cache]):
                raise Exception('The events in this bundle are from '
                                'different configurations!')
            # Use the last descriptor to avoid strings and objects
            data_keys = self.raw_descriptors[desc_id]['data_keys']
            for key, info in data_keys.items():
                # Information from non-number fields is dropped
                if info['dtype'] in ('number', 'array'):
                    # Average together
                    average_evt[key] = np.mean([evt['data'][key]
                                                for evt in cache], axis=0)
            return {'data': average_evt, 'descriptor': desc_id}

        self.out_node = self.averager.map(average_events)
        self.out_node.sink(self.process_event)
        super().start(doc)

    def event(self, doc):
        """Send an Event through the stream"""
        self.in_node.emit(doc)

    def stop(self, doc):
        """Delete the stream when run stops"""
        self.in_node = None
        self.out_node = None
        self.averager = None
        super().stop(doc)
