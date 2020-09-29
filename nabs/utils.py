import typing

import ophyd
from ophyd.signal import DerivedSignal, Signal
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


def field_prepend(field, obj):
    """
    Prepend the name of the Ophyd object to the field name

    Parameters
    ----------
    field : str
        Field name

    obj : object
        Object with :attr:`.name`

    Returns
    -------
    target_field : str
        The field maybe prepended with the object name
    """
    if isinstance(obj, ophyd.Device) and obj.name not in field:
        field = "{}_{}".format(obj.name, field)
    elif isinstance(obj, Signal):
        field = obj.name

    return field


def as_list(obj, length=None, tp=None, iter_to_list=True):
    """
    Force an argument to be a list, optionally of a given length, optionally
    with all elements cast to a given type if not None.

    Paramters
    ---------
    obj : Object
        The obj we want to convert to a list.

    length : int or None, optional
        Length of new list. Applies if the inputted obj is not an iterable and
        iter_to_list is false.

    tp : type, optional
        Type to cast the values inside the list as.

    iter_to_list : bool, optional
        Determines if we should cast an iterable (not str) obj as a list or to
        enclose it in one.

    Returns
    -------
    obj : list
        The object enclosed or cast as a list.
    """
    # If the obj is None, return empty list or fixed-length list of Nones
    if obj is None:
        if length is None:
            return []
        return [None] * length

    # If it is already a list do nothing
    elif isinstance(obj, list):
        pass

    # If it is an iterable (and not str), convert it to a list
    elif isiterable(obj) and iter_to_list:
        obj = list(obj)

    # Otherwise, just enclose in a list making it the inputted length
    else:
        try:
            obj = [obj] * length
        except TypeError:
            obj = [obj]

    # Cast to type; Let exceptions here bubble up to the top.
    if tp is not None:
        obj = [tp(o) for o in obj]
    return obj


def isiterable(obj):
    """
    Function that determines if an object is an iterable, not including
    str.

    Parameters
    ----------
    obj : object
        Object to test if it is an iterable.

    Returns
    -------
    bool : bool
        True if the obj is an iterable, False if not.
    """
    return isinstance(obj, typing.Iterable) and not isinstance(obj, str)
