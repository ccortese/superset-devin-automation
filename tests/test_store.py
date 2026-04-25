from app import store


def test_add_session_returns_running_status():
    s = store.add_session("abc", 1, "SQL injection", "http://issue", "http://devin")
    assert s["status"] == "running"
    assert s["pr_url"] is None
    assert s["finished_at"] is None
    assert s["started_at"] is not None


def test_add_session_is_retrievable():
    store.add_session("abc", 1, "title", "http://issue", "http://devin")
    sessions = store.get_all_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == "abc"


def test_update_session_to_finished():
    store.add_session("abc", 1, "SQL injection", "http://issue", "http://devin")
    updated = store.update_session("abc", "finished", pr_url="https://github.com/user/repo/pull/1")
    assert updated["status"] == "finished"
    assert updated["pr_url"] == "https://github.com/user/repo/pull/1"
    assert updated["finished_at"] is not None


def test_update_session_to_failed_sets_finished_at():
    store.add_session("abc", 1, "title", "url", "url")
    updated = store.update_session("abc", "failed")
    assert updated["status"] == "failed"
    assert updated["pr_url"] is None
    assert updated["finished_at"] is not None


def test_update_session_nonexistent_returns_none():
    result = store.update_session("does-not-exist", "finished")
    assert result is None


def test_get_active_sessions_excludes_finished():
    store.add_session("running-1", 1, "title", "url", "url")
    store.add_session("done-1", 2, "title2", "url", "url")
    store.update_session("done-1", "finished")
    active = store.get_active_sessions()
    assert len(active) == 1
    assert active[0]["id"] == "running-1"


def test_log_event_and_retrieve():
    store.log_event("webhook_received", "Issue #1 received", issue_number=1)
    events = store.get_recent_events()
    assert len(events) == 1
    assert events[0]["type"] == "webhook_received"
    assert events[0]["issue_number"] == 1


def test_get_recent_events_most_recent_first():
    store.log_event("first", "msg1")
    store.log_event("second", "msg2")
    events = store.get_recent_events()
    assert events[0]["type"] == "second"
    assert events[1]["type"] == "first"


def test_get_recent_events_respects_limit():
    for i in range(10):
        store.log_event(f"event-{i}", f"msg-{i}")
    events = store.get_recent_events(limit=3)
    assert len(events) == 3


def test_clear_wipes_all_state():
    store.add_session("abc", 1, "title", "url", "url")
    store.log_event("test", "msg")
    store.clear()
    assert store.get_all_sessions() == []
    assert store.get_recent_events() == []


def test_has_session_for_issue_returns_true_when_exists():
    store.add_session("abc", 42, "title", "url", "url")
    assert store.has_session_for_issue(42) is True


def test_has_session_for_issue_returns_false_when_missing():
    assert store.has_session_for_issue(99) is False


def test_has_session_for_issue_after_clear():
    store.add_session("abc", 1, "title", "url", "url")
    store.clear()
    assert store.has_session_for_issue(1) is False
