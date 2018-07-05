from ophyd.signal import DerivedSignal
from ophyd.sim import SignalRO


class InvertedSignal(DerivedSignal):
    """
    Invert another Ophyd Signal

    Parameters
    ----------
    derived_from: ophyd.Signal
        Ophyd Signal
    """
    def __init__(self, derived_from, *, name=None, **kwargs):
        # Create a name if None is given
        if not name:
            name = derived_from.name + '_inverted'
        # Initialize the DerivedSignal
        super().__init__(derived_from, name=name, **kwargs)

    def forward(self, value):
        """Invert the value"""
        return -value

    def inverse(self, value):
        """Invert the value"""
        return -value

    def trigger(self):
        return self.derived_from.trigger()


class ErrorSignal(SignalRO, DerivedSignal):
    """
    Signal that reports the absolute error from a provided target

    Parameters
    ----------
    derived_from : ophyd.Signal

    target : float
        Position of zero error
    """
    def __init__(self, derived_from, target, *, name=None, **kwargs):
        # Create a name if None is given
        if not name:
            name = derived_from.name + '_error'
        # Store the target
        self.target = target
        # Initialize the DerivedSignal
        super().__init__(derived_from, name=name, **kwargs)

    def forward(self, value):
        """Invert the value"""
        return NotImplemented

    def inverse(self, value):
        """Invert the value"""
        return abs(value - self.target)

    def trigger(self):
        return self.derived_from.trigger()
