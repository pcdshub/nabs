"""
Callbacks for subscription to the Bluesky ``RunEngine``

This is the LCLS counterpart to `bluesky.callbacks`

Callbacks in this module expect and operate on the `start`, `event`,
`stop`, etc documents.
"""

import logging
from datetime import datetime

import pandas as pd
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
    _FMTLOOKUP = {'string': '{:.5s}',
                  'float': '{:.2f}',
                  'number': '{:.3g}',
                  'integer': '{:d}'}

    _html_head = """<!DOCTYPE html>
<html>
<head>
<style>
table {
  font-family: arial, sans-serif;
  border-collapse: collapse;
  width: 100%;
}

td, th {
  border: 1px solid #dddddd;
  text-align: left;
  padding: 8px;
}

tr:nth-child(even) {
  background-color: #dddddd;
}
</style>
</head>
<body>
"""

    _html_tail = "</body> </html>"

    def __init__(self, elog, ipython):
        self._elog = elog
        self._ipython = ipython
        self._data = dict()
        self._descriptors = set()
        self._data_keys = []
        self._format_info = dict()

        # TO-DO:
        # - add granular switches as optional arguments
        # - add error handling for misspelled keys
        # - add default lists for start doc keys, elog tags?
        # - handling if data key collides with seq_num, time?
        # - consider pulling precision from data

    def start(self, doc):
        """ Post plan information on start document"""
        self._send_post = doc.get('post', self._elog.enable_run_posts)

        # Clean up before starting new run
        self._data = dict()
        self._descriptors = set()
        self._data_keys = []
        self._format_info = dict()

        if self._send_post:
            # Grab last ipython input
            run_info = self._ipython.user_ns["In"][-1]
            logger.info("Posting run start information to elog")
            self._elog.post(run_info, tags=['plan_info', 'RE'])

        super().start(doc)

    def descriptor(self, doc):
        """ Initialize table information """
        # these always exist
        self._data = dict(seq_num=[], time=[])
        for k, dk_entry in doc['data_keys'].items():

            if dk_entry['dtype'] not in self._FMTLOOKUP:
                logger.warn(f'skipping {k}, format not recognized')
                continue

            self._data[k] = []
            self._data_keys.append(k)
            self._format_info.update({k: dk_entry['dtype']})

        self._descriptors.add(doc['uid'])
        # To-do: consider signals with mismatched keys

    def event(self, doc):
        if doc['descriptor'] not in self._descriptors:
            return

        self._data['seq_num'].append(doc['seq_num'])
        self._data['time'].append(
            str(datetime.fromtimestamp(doc['time']).time())[:-4]
            )

        # this might break for unfilled data, but do we deal with that?
        for k in self._data_keys:
            try:
                dtype = self._format_info[k]
                style = self._FMTLOOKUP[dtype]
                self._data[k].append(style.format(doc['data'][k]))
            except Exception as ex:
                logger.warning(f'Entry {k} failed with exception {ex}')

    def _create_html_table(self):
        df = pd.DataFrame(dict(self._data))
        return df.to_html(index=False)

    def stop(self, doc):
        """ Post to ELog on plan close (stop document)"""
        super().stop(doc)

        # if no events were generated, don't send an empty table
        if self._data and self._send_post:
            html_body = self._create_html_table()
            final_message = self._html_head + html_body + self._html_tail

            logger.info("Posting run table information to elog")
            self._elog.post(
                final_message,
                tags=['run_table', 'RE'],
                title='run_table'
            )
