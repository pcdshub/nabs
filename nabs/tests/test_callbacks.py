import bluesky.plans as bp
from bluesky.callbacks.best_effort import BestEffortCallback

from ..callbacks import ELogPoster


def _compare_tables(fout, known_table):
    # Stolen shamelessly from bluesky tests
    for ln, kn in zip(fout.split('\n'), known_table.split('\n')):
        # this is to strip the `\n` from the print output
        ln = ln.rstrip()
        if ln[0] == '+':
            # test the full line on the divider lines
            assert ln == kn
        else:
            # skip the 'time' column on data rows
            # this is easier than faking up times in the scan!
            assert ln[:13] == kn[:13]
            assert ln[25:] == kn[25:]


def test_elog_callback(RE, hw, elog):
    bec = BestEffortCallback()
    elogc = ELogPoster(bec, elog)
    elogc.enable_run_posts = True

    bec_uid = RE.subscribe(bec)
    elog_uid = RE.subscribe(elogc)

    RE(bp.scan([hw.det], hw.motor, 0, 1, num=10))

    assert len(elog.posts) == 2  # start and table posts
    assert 'plan_info' in elog.posts[0][1]['tags']
    assert 'RE' in elog.posts[0][1]['tags']
    KNOWN_TABLE = """+-----------+------------+------------+------------+
|   seq_num |       time |      motor |        det |
+-----------+------------+------------+------------+
|         1 | 12:50:56.8 |      0.000 |      1.000 |
|         2 | 12:50:56.8 |      0.111 |      0.994 |
|         3 | 12:50:56.9 |      0.222 |      0.976 |
|         4 | 12:50:56.9 |      0.333 |      0.946 |
|         5 | 12:50:56.9 |      0.444 |      0.906 |
|         6 | 12:50:57.0 |      0.556 |      0.857 |
|         7 | 12:50:57.0 |      0.667 |      0.801 |
|         8 | 12:50:57.0 |      0.778 |      0.739 |
|         9 | 12:50:57.1 |      0.889 |      0.674 |
|        10 | 12:50:57.1 |      1.000 |      0.607 |
+-----------+------------+------------+------------+"""
    _compare_tables(elog.posts[1][0][0], KNOWN_TABLE)

    RE(bp.scan([hw.det], hw.motor, 0, 1, num=10), post=False)
    assert len(elog.posts) == 2  # confirm no new entries

    elog.enable_run_posts = False
    RE(bp.scan([hw.det], hw.motor, 0, 1, num=10))
    assert len(elog.posts) == 2  # confirm no new entries

    # cleanup
    RE.unsubscribe(bec_uid)
    RE.unsubscribe(elog_uid)
