from api_gateway.routing import max_body_bytes_for_path, resolve_upstream


def test_resolve_upstream_matches_by_first_segment():
    assert resolve_upstream("employees") == "http://localhost:8002"
    assert resolve_upstream("employees/abc-123") == "http://localhost:8002"
    assert resolve_upstream("documents") == "http://localhost:8008"
    assert resolve_upstream("search") == "http://localhost:8008"


def test_resolve_upstream_returns_none_for_unknown_path():
    assert resolve_upstream("nonexistent") is None


def test_upload_path_gets_higher_limit_than_everything_else():
    assert max_body_bytes_for_path("documents") > max_body_bytes_for_path("employees")
    assert max_body_bytes_for_path("employees") == max_body_bytes_for_path("chat")
