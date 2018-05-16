from collections import defaultdict
from functools import partial
from threading import Event, Thread
import math
import time

from ophyd.status import Status


class EventBuilder:
    def __init__(self, signals, rate, timeout=10.0, duplicates='closest'):
        self.signals = signals
        self.rate = rate
        self.timeout = timeout
        self.duplicates = duplicates
        self.cbid = {}
        self.start_ts = 0
        self.name = 'event_builder'
        self._clear_events()

    def add(self, name, *, value, timestamp, **kwargs):
        if timestamp > self.start_ts:
            bin_ts = self._nearest_ts(timestamp)
            delta = timestamp - bin_ts
            event = self.bins[bin_ts]
            event[name].append({'value': value,
                                'timestamp': timestamp,
                                'delta': delta})
            if len(event) == len(self.signals):
                self._has_evt.set()

    def _nearest_ts(self, timestamp):
        expanded = timestamp * self.rate
        floor = math.floor(expanded) / self.rate
        ceil = math.ceil(expanded) / self.rate
        if timestamp - floor < ceil - timestamp:
            return floor
        else:
            return ceil

    def _monitor_events(self):
        if not self.cbid:
            self.start_ts = time.time()
            for sig in self.signals:
                cbid = sig.subscribe(partial(self.add, sig.name))
                self.cbid[sig.name] = cbid

    def _stop_events(self):
        if self.cbid:
            for sig in self.signals:
                sig.unsubscribe(self.cbid[sig.name])
        self.cbid = {}

    def _clear_events(self):
        self._stop_events()
        self._has_evt = Event()
        self.bins = defaultdict(partial(defaultdict, list))

    def trigger(self):
        self._clear_events()
        self._monitor_events()
        status = Status(obj=self)
        Thread(target=self._wait_trigger, args=(status,)).start()
        return status

    def _wait_trigger(self, status):
        success = self._has_evt.wait(timeout=self.timeout)
        self._stop_events()
        status._finished(success=success)

    def read(self):
        timestamps = sorted(self.bins.keys())
        for ts in reversed(timestamps):
            raw_event = self.bins[ts]
            if len(raw_event) == len(self.signals):
                event = {}
                for name, data in raw_event.items():
                    if self.duplicates == 'first':
                        index = 0
                    elif self.duplicates == 'last':
                        index = -1
                    elif self.duplicates == 'closest':
                        index = 0
                        delta = math.inf
                        for i, dct in enumerate(data):
                            abs_del = abs(dct['delta'])
                            if abs_del < delta:
                                delta = abs_del
                                index = i
                    event[name] = {'value': data[index]['value'],
                                   'timestamp': data[index]['timestamp']}
                return event
        raise RuntimeError('Did not have a full event')

    def _delegate_dict_method(self, methodname):
        dct = {}
        for sig in self.signals:
            method = getattr(sig, methodname)
            dct.update(method())
        return dct

    def read_configuration(self):
        return self._delegate_dict_method('read_configuration')

    def describe(self):
        return self._delegate_dict_method('describe')

    def describe_configuration(self):
        return self._delegate_dict_method('describe_configuration')
