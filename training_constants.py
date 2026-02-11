"""
Training Constants — Shared Definitions
========================================

Single source of truth for constants used across training_handler.py,
validate_training.py, and test_regression.py.
"""

# Transform types that consume predecessor transforms (their input comes from earlier transforms)
DEPENDENT_TRANSFORM_TYPES = frozenset({"deletion", "reversal", "anagram", "container", "homophone", "substitution"})
