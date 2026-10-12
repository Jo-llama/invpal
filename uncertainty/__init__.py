"""Uncertainty layer: combines per-field signals into a calibrated confidence score and
finds the threshold for a target field precision (step 4). Scoped to Lieferscheine --
the headline metric's target -- since Rechnung's nested line items don't yet have the
position-level comparison granularity this needs (see uncertainty/dataset.py).
"""
