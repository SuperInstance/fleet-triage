# PIXELS-BUILD lab.  No dependencies beyond a C99 compiler and libm.
#   make        build both programs
#   make run    build, run both, write results-*.txt
#   make verify prove the results are stable across optimisation levels, and
#               prove the seed set's own constants fail a one-line build check
CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra -std=c99
LDLIBS  ?= -lm
HDRS     = syz_spreadsheet.h syz_sandbox_seed.h syz_sandbox_fixed.h syz_witness.h

all: lab chatter

lab: lab.c $(HDRS)
	$(CC) $(CFLAGS) lab.c -o lab $(LDLIBS)

chatter: chatter.c
	$(CC) $(CFLAGS) chatter.c -o chatter $(LDLIBS)

run: all
	./lab > results-lab.txt
	./chatter > results-chatter.txt
	@cat results-lab.txt results-chatter.txt

# poolassert.c is EXPECTED TO FAIL.  It is the check the seed harness needs and
# does not have.  A clean compile here means the check is broken.
check-seed-constants:
	@if $(CC) $(CFLAGS) -c poolassert.c -o /dev/null >/tmp/pa.txt 2>&1; then \
	   echo "FAIL: the seed's pool sizing passed a check it should not have passed"; \
	   exit 1; \
	 else \
	   echo "PASS: the seed's own constants are rejected at compile time"; \
	   sed -n '1,4p' /tmp/pa.txt; \
	 fi

verify: all check-seed-constants
	@./lab > /tmp/lab.a; ./lab > /tmp/lab.b; \
	 $(CC) -O0 -std=c99 lab.c -o lab0 $(LDLIBS) && ./lab0 > /tmp/lab.c0; \
	 ./chatter > /tmp/chat.a; $(CC) -O0 -std=c99 chatter.c -o chat0 $(LDLIBS) && ./chat0 > /tmp/chat.c0; \
	 if diff -q /tmp/lab.a /tmp/lab.b >/dev/null && diff -q /tmp/lab.a /tmp/lab.c0 >/dev/null \
	    && diff -q /tmp/chat.a /tmp/chat.c0 >/dev/null; then \
	   echo "PASS: lab and chatter are bit-identical across repeat runs and -O0/-O2"; \
	 else echo "FAIL: unstable, do not trust these numbers"; exit 1; fi

clean:
	rm -f lab chatter lab0 chat0 results-*.txt

.PHONY: all run verify check-seed-constants clean
