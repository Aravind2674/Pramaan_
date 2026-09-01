"""
Filesystem layer.

A DVR/NVR "vendor profile" is a YAML document describing the byte-level
structure of that recorder's on-disk format — signature, field offsets,
types, and endianness. :mod:`pramaan.fs.profile` compiles a profile into a
working struct reader; :mod:`pramaan.fs.registry` uses a collection of
profiles to fingerprint an unknown image.

The design commitment this package exists to keep: **adding a vendor is a
data change, not a code change.** If completing a new vendor ever requires
touching this package's Python, that is a bug in the profile schema, not a
reason to hand-write another one-off parser.
"""
