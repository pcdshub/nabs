from threading import RLock


class EventBuilder:
    """
    Base class for combining timestamped data into events.

    This is meant to be subclassed and have the ``emit_events`` method
    overridden.

    Parameters
    ----------
    timed_names: ``list of str``
        Data keys with matched timestamps. This is your high-rate data. These
        will make it into every event, in fact events will not be created until
        every timed name is associated with the timestamp.

    slow_names: ``list of str``
        Data keys with unmatched timestamps. This is your slow data. When the
        data updates, these will be associated with the next timestamp.

    auto_clear: ``bool``, optional
        If ``True``, we'll keep clearing out old data as we emit it.
    """
    def __init__(self, timed_names, slow_names, auto_clear=True):
        self.timed_names = timed_names
        self.slow_names = slow_names
        self.auto_clear = auto_clear

        self.lock = RLock()
        self.buckets = {}
        self.slow_values = {}

    def save_value(self, name, value, timestamp):
        """
        Submit new value to event builder. Emit new event if available.

        Parameters
        ----------
        name: ``str``
            Data key of this value

        value: any type
            The raw value

        timestamp: ``float``
            Unix timestamp of the event
        """
        if name in self.slow_names:
            self.slow_values[name] = (value, timestamp)
        elif name in self.timed_names:
            bucket = self.buckets.get(timestamp, {})
            bucket[name] = (value, timestamp)
            with self.lock:
                if self.event_ready(timestamp):
                    event = self.get_event(timestamp)
                    self.emit_data(event)
                    if self.auto_clear:
                        self.clear_data(timestamp, prev=True)

    def event_ready(self, timestamp):
        """
        Return True if there is an event ready for a timestamp.

        Parameters
        ----------
        timestamp: ``float``
            Unix timestamp of the event

        Returns
        -------
        ready: ``bool``
            ``True`` if an event is ready, ``False`` otherwise.
        """
        if len(self.slow_values) < len(self.slow_names):
            return False
        elif timestamp not in self.buckets:
            return False
        elif len(self.buckets[timestamp]) < len(self.slow_names):
            return False
        else:
            return True

    def get_event(self, timestamp):
        """
        Get an event dictionary for a specific timestamp

        Parameters
        ----------
        timestamp: ``float``
            Unix timestamp of the event

        Returns
        -------
        event: ``dict``
            Incomplete ``bluesky`` event, just has ``data``, ``timestamps``,
            and ``time``.
        """
        data = {}
        timestamps = {}
        for key in self.slow_names.keys():
            val, ts = self.slow_names[key]
            data[key] = val
            timestamps[key] = ts
        for key in self.buckets[timestamp].keys():
            val, ts = self.buckets[timestamp][key]
            data[key] = val
            timestamps[key] = ts
        return dict(data=data, timestamps=timestamps, time=timestamp)

    def emit_data(self, event):
        """
        Decide what to do with an event-built event

        Parameters
        ----------
        event: ``dict``
            The data dictionary returned by ``get_event``.
        """
        raise NotImplementedError('Override in subclass')

    def clear_data(self, timestamp, prev=False):
        """
        Remove data associated with a timestamp.

        This is called in ``save_value`` to prevent the data set from getting
        large with old data that will not be re-emitted.

        Parameters
        ----------
        timestamp: ``float``
            Unix timestamp of the event

        prev: ``bool``
            If ``True``, we'll remove all events from before this timestamp,
            including incomplete events.
        """
        del self.buckets[timestamp]
        if prev:
            for ts in sorted(list(self.buckets.keys())):
                if ts <= timestamp:
                    del self.buckets[ts]
                else:
                    break
