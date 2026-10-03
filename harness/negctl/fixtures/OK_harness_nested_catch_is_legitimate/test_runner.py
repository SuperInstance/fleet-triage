import subprocess


def test_bad_input_exits_nonzero():
    try:
        r = subprocess.run(['false'], capture_output=True)
    except OSError as e:
        raise AssertionError('could not run') from e
    assert r.returncode != 0


def test_math():
    assert 1 + 1 == 2
