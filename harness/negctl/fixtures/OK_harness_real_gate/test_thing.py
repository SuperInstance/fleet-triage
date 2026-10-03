import sys


def test_add():
    assert 1 + 1 == 2


if __name__ == '__main__':
    try:
        test_add()
    except AssertionError:
        sys.exit(1)
    print('ok')
    sys.exit(0)
