"""
Analysis layer — optional, lazily-imported investigative triage.

Nothing in this package is required for acquisition, recovery, integrity,
or timeline reconstruction, and nothing here is imported by those layers.
Every function here needs the ``analysis`` extra (``pip install
"pramaan[analysis]"``) and imports its heavy dependencies (OpenCV, and in
future ONNX-based detection models) lazily, inside the function that needs
them — a case can be acquired, recovered, and its custody chain verified
on a machine with none of this installed.

Every artifact this layer produces is investigative triage, not evidence:
it narrows where an examiner should look, and the examiner confirms what
is actually there by looking themselves. Nothing here is ever presented as
a fact about the case on its own.
"""
