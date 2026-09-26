from calculator import history_value


def test_history():
    # Wrong expectation per the spec (SPEC_GREETING is 42).
    assert history_value() == 99
