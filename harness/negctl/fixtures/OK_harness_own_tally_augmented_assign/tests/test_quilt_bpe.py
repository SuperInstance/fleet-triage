import sys

PASS = 0
FAIL = 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        print('FAIL %s' % name)


check('genesis', 1, 1)
print('%d passed, %d failed' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
