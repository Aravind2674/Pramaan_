# ADR 0003 — Integrity layer

**Status:** accepted
**Scope:** `pramaan/integrity/`

## What was built

Three independent primitives, deliberately not fused into one class:

- `merkle.py` — an RFC 6962-construction Merkle tree over a case's
  artifact hashes: a leaf/internal-node domain-separation prefix and a
  power-of-two split for odd-sized trees, avoiding the classic
  duplicate-leaf second-preimage weakness a naively hand-rolled pairwise
  tree has. Produces a root hash for "everything in this case" and
  inclusion proofs for "this one artifact was part of that set" without
  disclosing the rest.
- `ledger.py` — the actual chain-of-custody record: an append-only,
  hash-chained audit log. Every entry commits to its own content and the
  previous entry's hash, so altering any past entry breaks every hash
  after it. `verify_chain()` reports exactly where a break happens.
- `signing.py` — Ed25519 keypairs for an examiner to sign a ledger head or
  export manifest and verify that signature later.

Why a ledger *and* a Merkle tree, not one structure doing both jobs: a
custody log is read start to finish by an examiner or a court — there is
no scenario where someone needs to prove one entry exists without showing
the others, so a straight hash chain is the right tool for it. The Merkle
tree exists for the different, real case of proving one artifact's
inclusion in a case's evidence set without handing over the whole set.

## Two real bugs found and fixed during review

**`verify_inclusion`'s recursive verification consumed the audit path in
the wrong order on the "far" branch of the split.** Construction
(`audit_path`) always appends the recursive sub-path before the current
level's own sibling; verification's "index falls in the right half" branch
consumed the sibling from the path iterator *before* recursing, rather than
after. Every leaf whose path exercises this branch more than one level
deep gets the wrong bytes assigned to the wrong tree level — but any test
whose recursion bottoms out in one step never touches the bug, which is
exactly why hand-traced examples during design looked correct. Caught by a
parametrized test across a spread of sizes (a single hand-picked size, or
too few of them, would have missed this the same way manual tracing did);
kept as a permanent exhaustive test (every size 1–64, every index) rather
than trusting a handful of samples again.

**`Ledger.append`'s own `json.dumps` call for defensively copying `detail`
sat outside any exception handling**, so a non-serializable value raised a
raw `TypeError` from inside the standard library instead of the documented
`LedgerError`. Fixed by wrapping that specific call, matching the handling
`_canonical_content` already had for the same failure mode reached a
different way (via `recompute_hash()` on a directly-constructed entry,
which bypasses `append()`'s own validation — kept as its own test rather
than assuming one code path's coverage implies the other's).

## What review confirmed was safe, on purpose

A frozen `LedgerEntry`'s `detail` field can still be mutated in place
(freezing blocks attribute *reassignment*, not mutation of a mutable
attribute's contents) — checked directly with a test that does exactly
that and confirms `verify_chain` reports the tamper at the right index.
This is the correct behavior for a tool whose stated guarantee is
tamper-*evident*, not tamper-proof: detection after the fact is the
promise being kept, not physical immutability.

## Verification run before this was committed

- `pytest`: 157/157 passing, 100% line coverage across
  `pramaan.integrity` (and every layer under it), zero warnings with
  `DeprecationWarning` promoted to an error.
- `ruff check` and `mypy`: clean.
- All of the above run under **both** a real Python 3.11 and a real
  Python 3.12 interpreter — the gap that let two CI failures through
  earlier in this project was verifying only one of the two, so this
  layer was checked against both before being pushed, not after a CI
  run caught something.

## Consequences

Composition — signing a ledger's head hash, rooting a case's artifact
list — is left to whatever calls these modules (the future case-management
layer), not implemented here. Each module does exactly one job and is
tested as a standalone primitive.
