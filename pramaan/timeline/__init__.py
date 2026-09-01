"""
Timeline layer.

- :mod:`pramaan.timeline.model` — segments and gaps, addressed by channel
  and wall-clock time. Knows nothing about profiles, clips, or disk
  images; it takes typed (channel, start, end, kind) data from whatever
  produced it and answers coverage questions.
- :mod:`pramaan.timeline.gaps` — what a gap or a recovered segment
  actually means, grounded in the three-way deletion taxonomy from the
  Honeywell surveillance-filesystem paper (see ``docs/sources.md``):
  format-based deletion, retention-driven expiration, and ordinary
  overwrite each look different in the evidence, and this module states
  the specific evidence behind every classification rather than a bare
  label.
- :mod:`pramaan.timeline.clock` — fitting a recorder's own clock against
  independently-verified true-time anchors, using a regression robust to
  a wrong anchor rather than one a single bad reading can drag off.
"""
