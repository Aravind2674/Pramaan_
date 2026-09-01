"""
Integrity layer.

Three independent primitives, deliberately not fused into one abstraction:

- :mod:`pramaan.integrity.merkle` — a general Merkle tree (RFC 6962
  construction) over a set of artifact hashes. Produces one root hash for
  "everything in this case" and inclusion proofs for "this one artifact was
  part of that set" without disclosing the rest.
- :mod:`pramaan.integrity.ledger` — an append-only, hash-chained audit log.
  Every operator action, job, and export gets an entry; each entry commits
  to the previous one, so any edit to history breaks every hash after it.
  This is the chain-of-custody record proper, and it does not need a
  Merkle tree — it is read in full by an examiner or a court, not queried
  for partial membership, so a simple chain is the right tool, not a
  simpler-looking substitute for one.
- :mod:`pramaan.integrity.signing` — Ed25519 keypairs for an examiner to
  sign a ledger's head hash or an export manifest, and to verify a
  signature later.

Composition (signing a ledger head, rooting a case's artifacts) is left to
callers rather than baked in here — each module has exactly one job.
"""
