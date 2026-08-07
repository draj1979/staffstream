from skill_marketplace.connectors.base import has_real_value


def test_has_real_value_rejects_unset_default():
    assert has_real_value("not-set") is False
    assert has_real_value("not-set-configure-GOOGLE_CLIENT_ID") is False


def test_has_real_value_rejects_none():
    assert has_real_value(None) is False


def test_has_real_value_rejects_empty_string():
    # The exact bug this guards against: a docker-compose env file can
    # declare `GITHUB_CLIENT_ID=` with nothing after the `=` (e.g. its
    # GitHub Actions secret was never set), which overrides
    # pydantic-settings' "not-set" default with "". A naive
    # `.startswith("not-set")` check treats "" as configured, since
    # `"".startswith("not-set")` is False — silently letting /authorize
    # redirect to the provider with an empty client_id, which the
    # provider then rejects with its own raw error page.
    assert has_real_value("") is False


def test_has_real_value_accepts_a_real_looking_value():
    assert has_real_value("Iv1.abc123def456") is True
