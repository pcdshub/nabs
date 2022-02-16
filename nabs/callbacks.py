"""
Callbacks for subscription to the Bluesky ``RunEngine``

This is the LCLS counterpart to `bluesky.callbacks`

Callbacks in this module expect and operate on the `start`, `event`,
`stop`, etc documents.
"""

import logging

from bluesky.callbacks.core import CallbackBase, make_class_safe

logger = logging.getLogger(__name__)


@make_class_safe(logger=logger)
class ELogPoster(CallbackBase):
    """
    Callback to post messages to the elog, primarily related to plan setup and
    results. This callback relies on and must be instantiated after the
    BestEffortCallback and HutchELog.

    To subscribe:

    .. code-block:: python

        elogc = ELogPoster(bec, elog)
        elogc_uid = RE.subscribe(elogc)

    To enable posting for a specific run:

    .. code-block:: python

        RE(plan(), post=True)

    Parameters
    ----------
    bec : BestEffortCallback
        Instance of BestEffortCallback subscribed to the current RunEngine

    elog : HutchELog
        Instance of HutchELog connected to the desired logbook
    """
    def __init__(self, bec, elog):
        self._bec = bec
        self._elog = elog

        # TO-DO:
        # - add granular switches as optional arguments
        # - add error handling for misspelled keys
        # - add default lists for start doc keys, elog tags?

    def start(self, doc):
        """ Post plan information on start document"""
        self._send_post = doc.get('post', self._elog.enable_run_posts)

        if self._send_post:
            run_info = str({k: doc[k] for k in ['plan_name', 'plan_args']})
            logger.info("Posting run start information to elog")
            self._elog.post(run_info, tags=['plan_info', 'RE'])

        super().start(doc)

    def stop(self, doc):
        """ Post to ELog on plan close (stop document)"""
        super().stop(doc)
        # need to hold onto BEC, instead of the table it holds?...
        table = self._bec._table._rows
        # Can be None of table isn't generated (ie. bp.count)
        if (table is not None) and self._send_post:
            logger.info("Posting run table information to elog")
            self._elog.post(
                '\n'.join(table),
                tags=['run_table', 'RE']
            )

        # Clean up
        self._send_post = self._elog.enable_run_posts
