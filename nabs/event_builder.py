from threading import RLock

from bluesky.callbacks.stream import LiveDispatcher


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


class SignalEventBuilder(EventBuilder):
    """
    Event builder for ophyd signals.

    This will need to be subclassed to define a proper ``emit_data`` method.

    This works for ``Signal`` objects, or any device that can be
    subscribed to that sends the ``obj``, ``value``, and
    ``timestamp`` kwargs as part of the callback.

    Parameters
    ----------
    timed_signals: ``list of Signal``
        Signals that have matched timestamps. This is your high-rate data that
        will have a new value at every event.

    slow_signals: ``list of Signal``
        Signals with unmatched timestamps. This is your slow data. The last
        value of each will be included in each event.

    auto_clear: ``bool``, optional
        If ``True``, we'll keep clearing out old data as we emit it.
    """
    def __init__(self, timed_signals, slow_signals, auto_clear=True):
        super().__init__([sig.name for sig in timed_signals],
                         [sig.name for sig in slow_signals],
                         auto_clear=auto_clear)
        for sig in slow_signals:
            sig.subscribe(self)
        for sig in timed_signals:
            sig.subscribe(self)

    def __call__(self, obj, value, timestamp, **kwargs):
        self.save_value(obj.name, value, timestamp)


class BlueskyEventBuilder(EventBuilder, LiveDispatcher):
    """
    Event builder for bluesky monitor documents.

    If this is subscribed to the run engine, it will combine the monitor
    document into normal-looking event documents, which will then be emitted.
    """
    def event(self, doc, **kwargs):
        pass
