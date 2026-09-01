"""
Recovery layer.

Three distinct ways footage comes back, in increasing order of how little
the tool is told going in:

1. :mod:`pramaan.recovery.index_walk` — a known vendor profile's own index
   is intact. This is not really "recovery" so much as normal reading, and
   it exists here because it shares the ClipRecord model with the other two.
2. :mod:`pramaan.recovery.carver` — the index entry for a clip is gone
   (deleted, corrupted, or the block was never covered by any profile), but
   the video payload survives in what the filesystem considers unallocated
   space. Recovered by scanning for H.264 elementary-stream structure
   directly, with no help from any index.
3. :mod:`pramaan.recovery.profiler` — the vendor's filesystem itself is
   unknown; there is no profile to walk and no declared "unallocated space"
   to carve, because nothing has told the tool what "allocated" means on
   this disk. Structural inference from the raw bytes alone.
"""
