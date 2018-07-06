import asyncio

from bluesky.callbacks import CallbackCounter


class CallbackCounterFuture(CallbackCounter):
    """
    A callback counter that marks a Future when the count reaches max_count
    """
    def __init__(self, max_count):
        super().__init__(self)
        self.max_count = max_count
        loop = asyncio.get_event_loop()
        self.future = loop.create_future()

    def __call__(self, name, doc):
        super().__call__(self, name, doc)
        if self.value >= self.max_count and not self.future.done():
            self.future.set_result('reached {}'.format(self.value))
