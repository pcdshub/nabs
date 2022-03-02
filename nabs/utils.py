import inspect
import logging
from collections import Iterable
from typing import Any, Callable, Dict, Union

from ophyd.signal import DerivedSignal, SignalRO

from ._html import collapse_list_head, collapse_list_tail

logger = logging.getLogger(__name__)


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


def format_ophyds_to_html(obj, allow_child=False):
    """
    Recursively construct html that contains the output from .status() for
    each object provided.  Base case is being passed a single ophyd object
    with a `.status()` method.  Any object without a `.status()` method is
    ignored.

    Creates divs and buttons based on styling
    from `nabs._html.collapse_list_head` and `nabs._html.collapse_list_tail`

    Parameters
    ----------
    obj : ophyd object or Iterable of ophyd objects
        Objects to format into html

    allow_child : bool, optional
        Whether or not to post child devices to the elog.  Defaults to False,
        to keep long lists of devices concise

    Returns
    -------
    out : string
        html body containing ophyd object representations (sans styling, JS)
    """
    if isinstance(obj, Iterable):
        content = ""

        for o in obj:
            content += format_ophyds_to_html(o, allow_child=allow_child)

        # Don't return wrapping if there's no content
        if content == "":
            return content

        # HelpfulNamespaces tend to lack names, maybe they won't some day
        parent_default = ('Ophyd status: ' +
                          ', '.join('[...]' if isinstance(o, Iterable)
                                    else o.name for o in obj))
        parent_name = getattr(obj, '__name__', parent_default[:60] + ' ...')

        # Wrap in a parent div
        out = (
            "<button class='collapsible'>" +
            f"{parent_name}" +  # should be a namespace name
            "</button><div class='parent'>" +
            content +
            "</div>"
        )
        return out

    # check if parent level ophyd object
    elif (callable(getattr(obj, 'status', None)) and
            ((getattr(obj, 'parent', None) is None and
              getattr(obj, 'biological_parent', None) is None) or
             allow_child)):
        content = ""
        try:
            content = (
                f"<button class='collapsible'>{obj.name}</button>" +
                f"<div class='child content'><pre>{obj.status()}</pre></div>"
            )
        except Exception as ex:
            logger.info(f'skipped {str(obj)}, due to Exception: {ex}')

        return content

    # fallback base case (if ignoring obj)
    else:
        return ""


def post_ophyds_to_elog(elog, objs, allow_child=False):
    """
    Take a list of ophyd objects and post their status representations
    to the elog.  Handles singular objects, lists of objects, and
    HelpfulNamespace's provided in hutch-python

    .. code-block:: python

        # pass in an object
        post_ophyds_to_elog(elog, at2l0)

        # or a list of objects
        post_ophyds_to_elog(elog, [at2l0, im3l0])

        # devices with no parents are ignored by default :(
        post_ophyds_to_elog(elog, [at2l0, at2l0.blade_01], allow_child=True)

        # or a HelpfulNamespace
        post_ophyds_to_elog(elog, m)

    Parameters
    ----------
    elog : HutchELog
        elog instance to post to

    objs : ophyd object or Iterable of ophyd objects
        Objects to format and post

    allow_child : bool, optional
        Whether or not to post child devices to the elog.  Defaults to False,
        to keep long lists of devices concise

    """
    post = format_ophyds_to_html(objs, allow_child=allow_child)

    if post == "":
        logger.info("No valid devices found, no post submitted")
        return

    # wrap post in head and tail
    final_post = collapse_list_head + post + collapse_list_tail

    elog.post(final_post, tags=['ophyd_status'], title='ophyd status report')
