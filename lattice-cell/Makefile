.PHONY: all test matrix pins
all: test
test:
	node tests/invariants.mjs
	node tests/contest.mjs
matrix:
	./harness/crash-matrix.sh
pins: test matrix
	node tests/mutation.mjs
