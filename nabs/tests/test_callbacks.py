import bluesky.plans as bp

from ..callbacks import ELogPoster


def test_elog_callback(RE, hw, elog, ipython):
    elogc = ELogPoster(elog, ipython)
    elogc.enable_run_posts = True

    elog_uid = RE.subscribe(elogc)

    ipython.user_ns["In"].append(
        "RE(bp.scan([hw.det], hw.motor, 0, 1, num=10))"
        )
    RE(bp.scan([hw.det], hw.motor, 0, 1, num=10))

    assert len(elog.posts) == 2  # start and table posts
    assert 'plan_info' in elog.posts[0][1]['tags']
    assert 'RE' in elog.posts[0][1]['tags']

    ipython.user_ns["In"].append(
        "RE(bp.scan([hw.det], hw.motor, 0, 1, num=10), post=False)"
        )
    RE(bp.scan([hw.det], hw.motor, 0, 1, num=10), post=False)
    assert len(elog.posts) == 2  # confirm no new entries

    elog.enable_run_posts = False
    ipython.user_ns["In"].append(
        "RE(bp.scan([hw.det], hw.motor, 0, 1, num=10))"
        )
    RE(bp.scan([hw.det], hw.motor, 0, 1, num=10))
    assert len(elog.posts) == 2  # confirm no new entries

    # Test override of elog default
    last_cmd = "RE(bp.scan([hw.det], hw.motor, 10, 0, num=10), post=True)"
    ipython.user_ns["In"].append(last_cmd)
    RE(bp.scan([hw.det], hw.motor, 10, 0, num=10), post=True)
    assert len(elog.posts) == 4
    assert elog.posts[-2][0][0] == last_cmd

    # test behavior when no table is generated
    last_cmd = "RE(bp.count([]), post=True)"
    ipython.user_ns["In"].append(last_cmd)
    RE(bp.count([]), post=True)
    assert len(elog.posts) == 5  # empty table should not be posted

    # cleanup
    RE.unsubscribe(elog_uid)
