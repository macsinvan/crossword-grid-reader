"""
Training Constants & Utilities — Shared Definitions
====================================================

Single source of truth for constants and transform-analysis functions
used across training_handler.py, validate_training.py, and test_regression.py.
"""

import re

# Transform types that consume predecessor transforms (their input comes from earlier transforms)
DEPENDENT_TRANSFORM_TYPES = frozenset({"deletion", "reversal", "anagram", "container", "homophone", "substitution"})


def find_consumed_predecessors(transforms, dep_index):
    """Find predecessor indices consumed by a dependent transform.

    Works backwards from dep_index, accumulating predecessors until
    the combined letter count matches the dependent's result length.
    Skips predecessors already consumed by intermediate dependent transforms
    (e.g. a reversal's input is replaced by its output, not added alongside it).

    Returns a list of predecessor indices in ascending order.
    """
    t = transforms[dep_index]
    t_type = t.get("type", "")
    result_len = len(re.sub(r'[^A-Z]', '', t["result"].upper()))

    # Deletion needs one more letter than the result
    if t_type == "deletion":
        target_len = result_len + 1
    else:
        target_len = result_len

    # Find predecessors already consumed by intermediate dependent transforms
    already_consumed = set()
    for j in range(dep_index - 1, -1, -1):
        jt = transforms[j].get("type", "")
        if jt in DEPENDENT_TRANSFORM_TYPES:
            inner_consumed = find_consumed_predecessors(transforms, j)
            already_consumed.update(inner_consumed)

    consumed = []
    accumulated = 0
    for j in range(dep_index - 1, -1, -1):
        if j in already_consumed:
            continue
        pred_len = len(re.sub(r'[^A-Z]', '', transforms[j]["result"].upper()))
        consumed.append(j)
        accumulated += pred_len
        if accumulated >= target_len:
            break

    consumed.reverse()
    return consumed


def find_terminal_transforms(transforms):
    """Identify terminal transforms — those not consumed by a later dependent.

    Returns a set of terminal transform indices.
    """
    terminal = set(range(len(transforms)))
    for i, t in enumerate(transforms):
        if "type" not in t:
            raise ValueError(f"Transform {i} is missing 'type' field")
        if i > 0 and t["type"] in DEPENDENT_TRANSFORM_TYPES:
            consumed = find_consumed_predecessors(transforms, i)
            for c in consumed:
                terminal.discard(c)
    return terminal
