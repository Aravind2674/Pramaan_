# Sources

Every technical or legal claim this project makes in code comments, profile
files, the report generator, or public-facing documentation must trace to an
entry here. If it isn't here, it isn't confirmed — see the confidence labels
used throughout `pramaan/fs/profiles/`.

## Filesystem and container formats

**Hikvision Master Sector / HIKBTREE**
Han, J., Jeong, D., Lee, S. (2015). "Analysis of the HIKVISION DVR File
System." *ICDF2C 2015*, Springer LNICST vol. 157, pp. 189–199.
DOI: [10.1007/978-3-319-25512-5_13](https://doi.org/10.1007/978-3-319-25512-5_13).
Full text read 2026-09-01 via https://eudl.eu/pdf/10.1007/978-3-319-25512-5_13.
Confirmed: Master Sector at offset 0x200, signature `HIKVISION@HANGZHOU`,
HIKBTREE structure and Data Block Entry layout, the "no delete function
short of full system initialization" behaviour. Not confirmed: exact byte
offsets for individual Master Sector fields beyond the signature itself —
see `hikvision_master_sector.yaml` for exactly what is and isn't claimed.
Independent evidence that the format drifts across firmware/hardware
generations: [fmpfeifer/hikextractor](https://github.com/fmpfeifer/hikextractor)
README (GPLv3), field-tested against two different Hikvision models, notes
the on-disk layout did not exactly match this paper though the overall
structure did.

**Dahua DHAV container chunk**
Read directly from `libavformat/dhav.c` in the FFmpeg source tree
(`read_chunk()`, `dhav_probe()`, `get_timeinfo()`), fetched 2026-09-01 from
https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavformat/dhav.c.
© 2018 Paul B Mahol, licensed LGPL-2.1-or-later. `dahua_dhav.yaml`
documents the on-disk structure this code parses, expressed as data for
Pramaan's own independent interpreter — no FFmpeg source is reproduced.
The underlying block/index filesystem name "DHFS" appears only in
commercial marketing copy (UFS Explorer) and is not independently
confirmed from a primary source; treat as a working label, not a fact.

**Honeywell surveillance filesystem (methodology reference, not a target
vendor for this project's initial scope)**
Yoon, J., Hwang, S. "Forensic analysis of video data deletion and recovery
in Honeywell surveillance file system." arXiv:2605.07430, accepted DFRWS
USA 2026. Full text read via https://arxiv.org/html/2605.07430v1. The
three-way deletion taxonomy (format-based / expiration / overwrite, each
with different recoverability) is the model `pramaan.timeline`'s deletion-
intent classifier is designed around.

**Xiongmai/XM, Uniview, TVT, Tiandy, Hanwha, Bosch, Vivotek**
No byte-level public documentation was found for any of these during this
project's research pass. This is treated as the strongest justification for
the unknown-vendor structural profiler, not hidden as a gap.

## Legal and statutory framework (India)

**Bharatiya Sakshya Adhiniyam, 2023, Section 63** (replaces Indian Evidence
Act Section 65B). Full text: https://indiankanoon.org/doc/125020475/,
§63(4): https://indiankanoon.org/doc/90089205/.

**BSA 2023 Schedule (referenced by §63(4)(c))** — Part A (device custodian)
and Part B (technical expert) certificate format, including a hash-algorithm
checkbox for SHA1/SHA256/MD5/Other, with "DVR" as a named device/source
category. Confirmed via https://www.advocatekhoj.com/library/bareacts/bharatiyaaakshya2023/b.php
(bare-act reproduction) on 2026-09-01. **This is a secondary reproduction,
not the primary indiacode.nic.in text** (which blocked automated fetch at
the time of writing) — re-verify the exact wording against the primary bare
act before the certificate PDF template in `pramaan/report/certificate.py`
is finalized.

**Bharatiya Nagarik Suraksha Sanhita, 2023, Section 105** — search/seizure
must be recorded via audio-video and forwarded without delay to a
magistrate. Full text: https://indiankanoon.org/doc/2838436/.

**Arjun Panditrao Khotkar v. Kailash Kushanrao Gorantyal**, (2020) 7 SCC 1 /
2020 INSC 453, decided 14 July 2020. https://indiankanoon.org/doc/172105947/.
Certificate mandatory for secondary electronic evidence; exception if the
original device is produced and its owner testifies; a court can compel a
non-responding custodian to produce a certificate. Overrules *Shafhi
Mohammad v. State of H.P.* — this was decided in 2020, not any later year;
do not cite a different date for this holding.

## Competitive landscape

Magnet DVR Examiner (Magnet Forensics, Canada; acquired DME Forensics 2021):
https://www.magnetforensics.com/products/magnet-witness/,
CAQ page (unknown-recorder and RAID limitations):
https://docs.magnetforensics.com/docs/dvr/html/sections/help/caq.html.
SalvationDATA VIP (PRC): https://www.salvationdata.com/. GFR Rule 144(xi)
(PRC-origin government-procurement registration requirement):
https://www.pib.gov.in/PressReleasePage.aspx?PRID=1640778.
Amped FIVE/DVRConv/Authenticate (Italy): https://ampedsoftware.com/.
UFS Explorer Video Recovery (~130 named formats, published pricing):
https://www.ufsexplorer.com/ufs-explorer-video-recovery/.
MeitY/C-DAC Blockchain India Challenge (the reason this project does not
build a literal blockchain for chain of custody): https://challenge.cdac.in/.

## A note on how this file is meant to be used

Every claim above is either a primary source read directly (a paper, a bare
act, source code) or is explicitly marked as a secondary reproduction with
an instruction to re-verify. Nothing in this project should be cited to a
jury, a report, or a certificate at a higher confidence than what is
recorded here.
