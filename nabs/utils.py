import inspect
import multiprocessing as mp
import numbers
import traceback
from typing import Any, Callable, Dict, Union

import numpy as np
from ophyd.signal import DerivedSignal, SignalRO


class InvertedSignal(DerivedSignal):
    """
    Invert another `ophyd` Signal

    Parameters
    ----------
    derived_from: `ophyd.signal.Signal`
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
    derived_from : `ophyd.signal.Signal`

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


def add_named_kwargs_to_signature(
    func_or_signature: Union[inspect.Signature, Callable],
    kwargs: Dict[str, Any]
) -> inspect.Signature:
    """
    Add named keyword arguments with default values to a function signature.

    Parameters
    ----------
    func_or_signature : inspect.Signature or callable
        The function or signature.

    kwargs : dict
        The dictionary of kwarg_name to default_value.

    Returns
    -------
    modified_signature : inspect.Signature
        The modified signature with additional keyword arguments.
    """

    if isinstance(func_or_signature, inspect.Signature):
        sig = func_or_signature
    else:
        sig = inspect.signature(func_or_signature)

    params = list(sig.parameters.values())
    keyword_only_indices = [
        idx for idx, param in enumerate(params)
        if param.kind == inspect.Parameter.KEYWORD_ONLY
    ]
    if not keyword_only_indices:
        start_params, end_params = params, []
    else:
        insert_at = keyword_only_indices[0]
        start_params, end_params = params[:insert_at], params[insert_at:]

    wrapper_params = list(
        inspect.Parameter(
            name, kind=inspect.Parameter.KEYWORD_ONLY, default=value
        )
        for name, value in kwargs.items()
        if name not in sig.parameters
    )

    return sig.replace(parameters=start_params + wrapper_params + end_params)


class Process(mp.Process):
    """
    A subclass of multiprocessing.Process that makes exceptions
    accessible by the parent process.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pconn, self._cconn = mp.Pipe()
        self._exception = None

    def run(self):
        try:
            super().run()
            self._cconn.send(None)
        except Exception as e:
            tb = traceback.format_exc()
            self._cconn.send((e, tb))

    def join_and_raise(self):
        super().join()
        # raise exceptions after process is finished
        if self.exception:
            raise self.exception[0]

    @property
    def exception(self):
        if self._pconn.poll():
            self._exception = self._pconn.recv()
        return self._exception


def orange(start, stop, num, rtol=1.e-5, atol=1.e-7):
    """
    Get scan points based on the type of `num`.  If `num` is an
    integer, interpret as the number of points in a scan.  If `num`
    is a float, interpret it as a step size.

    Modified to include end points.

    Parameters
    ----------
    start : int or float
        The first point in the scan

    end : int or float
        The last point in the scan

    num : int or float
        if int, the number of points in the scan.
        if float, step size

    Returns
    -------
    list
        a list of scan points
    """
    moves = []
    if isinstance(num, numbers.Integral):
        moves = list(np.linspace(start, stop, num))
    elif isinstance(num, numbers.Real):
        num = np.sign(stop - start) * np.abs(num)
        moves = list(np.arange(start, stop + num, num))

    return moves
