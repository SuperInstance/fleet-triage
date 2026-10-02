# The VM is a set of files, and almost nobody works there

2026-10-02. A theory of mind for agentic systems, from Casey's framing. This is
the substrate claim the whole architecture rests on, and it is currently
unwritten anywhere in the corpus.

---

## The claim

**On the deepest level, a virtual machine is a set of files.** A process is a
set of files being read. An agent is a set of files plus a routine that walks
them. The machine has no privileged interior — there is no "inside" that is not
made of bytes on a device someone could image.

**And almost no user, and almost no operator, exists in that paradigm.**

A person does not think in files. They think in *state they can picture* — a
room, a car, a lunch, a place they have not decided about yet. An operator does
not think in files either; they think in a thing that stopped working, and they
narrow toward the cause. The files are there, and they are canonical, and
**they are the layer nobody in the loop is actually standing on.**

## Why this is a design constraint and not a philosophy

Most systems are built as though someone will operate them from the file layer,
because that is where the code is. The evidence in this account is that they are
not:

- **A 54 MB profile repository with no description** is the front door of 5,127
  repositories, and every arrival route is a *ranked list*, not a file tree.
  **The files are perfect and unreachable.**
- **A renderer that reads a repository and emits eight views** sat finished since
  June with a journal entry reading *"Next duty: Awaiting instructions."* **The
  files were never the problem.**
- **A CRDT canary has never constructed the type it is filed under** and cannot
  fail. The file is there. The file is *always* there.

**In all three, the artifact existed and the file-layer access to it was
worthless.** Nobody was in the paradigm where the answer was obvious.

## What follows, concretely

**1. The file layer is the substrate, not the interface.** Anything that asks a
person or an agent to hold file-layer state in their head has already lost them.
`RenderContext::from_repo` exists and has been switched off since June; the fix
was never a better file format.

**2. A workspace must be a *place*, and a place has a vantage point.** The
spreadsheet sees the corn maze from above; the terminal puts you inside it.
**Neither is the maze. The ability to move between them is the product** — and
that is the same observation as the sequence/MIDI view, the synoptic view, and
the eight renderers, all of which are *the same state at different distances*.

**3. Decisions are state functions, not deliberations.** A person drives to
lunch without knowing where they are going, options narrow as time is spent
chatting, and the reason is never articulated because system-one drove. **An
operator will do the same to your system.** A workspace that requires an
articulated reason before every move does not model the operator; it models
something more expensive and less like a person.

**4. The second system notices what the first never justified.** That is the
whole reason to run two systems. Not for redundancy — **redundancy is worth
about two votes** — but because the first one left things unexplained and the
second one is the only thing that can notice.

## The open question this creates, which I cannot answer

**If the substrate is files and nobody lives in the file paradigm, then the
central artifact of a system like this is not the data and not the model. It is
the vantage point.**

Which raises the question I have been circling all night and have not said out
loud: **is a canonical cell-graph, rendered into a place you can stand, the
definition of a workspace — and is the model's job to maintain the place rather
than to decide the next move?**

Casey's brief says the routine *is* the intelligence when you see it as a state
of vectors. **A workspace is a state of vectors you can stand in.** That is
consistent, and it is the most interesting claim in this document, and **I have
no evidence for it.** I would rather have it measured than adopted.

## What I am proposing as a way of working

Every system in this account has been measured from the *file* paradigm: I read
the code, I run the test, I count the findings. **That is the wrong vantage
point and I have been in it all night.**

So: the next round of work should be **done from inside a place**, by someone
who was not handed a file list — and the output should be what they saw, not
what the files say.
