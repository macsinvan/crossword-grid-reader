#!/usr/bin/env python3
"""
Training Metadata Validator
============================

Hard checks to catch hallucinated or malformed training metadata before
it reaches the server. Run standalone to validate clues_db.json, or
import validate_training_item() for use in upload/load pipelines.

Checks fall into four categories:
  1. Structural — required fields, valid types, indices in bounds
  2. Semantic — transforms concatenate to answer, letter counts match
  3. Convention — deterministic transform checks (reversal, anagram, etc.)
                  plus lookup-based checks (abbreviation dictionary)
  4. Publication — publication-specific conventions (spelling, vocabulary)
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Standard cryptic crossword abbreviations
# ---------------------------------------------------------------------------
# Maps lowercase clue word(s) → set of valid uppercase results.
# Multiple words can map to the same abbreviation.
# This is not exhaustive — a missing entry produces a warning, not an error.

CRYPTIC_ABBREVIATIONS = {
    # Titles / people
    "journalist": {"ED"},
    "editor": {"ED"},
    "doctor": {"DR", "MO", "MB", "GP"},
    "physician": {"DR", "MO", "GP"},
    "nurse": {"EN", "RN", "SEN"},
    "agents": {"CIA", "FBI", "MI5", "MI6"},
    "spies": {"CIA", "MI5", "MI6"},
    "spy": {"MOLE", "AGENT"},
    "soldier": {"GI", "RE", "RA", "RM", "OR", "PTE"},
    "private": {"GI", "PTE"},
    "general": {"GEN"},
    "engineer": {"RE", "CE"},
    "sailor": {"AB", "OS", "TAR", "SALT"},
    "artist": {"RA", "ARA"},
    "king": {"K", "R", "REX"},
    "queen": {"Q", "R", "ER", "QU"},
    "prince": {"P"},
    "princess": {"P"},
    "bishop": {"B", "RR"},
    "knight": {"N", "K", "SIR"},
    "saint": {"S", "ST"},
    "sir": {"S"},
    "lord": {"L"},
    "lady": {"L"},
    "father": {"FR", "PA", "DAD"},
    "mother": {"MA", "MOM", "DAM"},
    "son": {"S"},
    "daughter": {"D"},
    "brother": {"BR", "BRO"},
    "sister": {"SR", "SIS"},
    "wife": {"W"},
    "husband": {"H"},
    "female": {"F"},
    "male": {"M"},
    "man": {"M"},
    "woman": {"W", "F"},
    "boy": {"B", "SON"},
    "girl": {"G"},
    "worker": {"ANT", "BEE", "HAND"},

    # Directions / compass
    "north": {"N"},
    "south": {"S"},
    "east": {"E"},
    "west": {"W"},
    "northeast": {"NE"},
    "northwest": {"NW"},
    "southeast": {"SE"},
    "southwest": {"SW"},
    "direction": {"N", "S", "E", "W", "NE", "NW", "SE", "SW"},
    "point": {"N", "S", "E", "W", "NE", "NW", "SE", "SW"},
    "quarter": {"N", "S", "E", "W"},
    "left": {"L", "PORT"},
    "right": {"R", "RT"},

    # Numbers / letters
    "number": {"N", "NO"},
    "nothing": {"O", "NIL"},
    "zero": {"O"},
    "love": {"O"},
    "duck": {"O"},
    "nil": {"O"},
    "one": {"I", "A", "AN", "ACE", "UN"},
    "two": {"II"},
    "three": {"III"},
    "four": {"IV"},
    "five": {"V"},
    "six": {"VI"},
    "seven": {"VII"},
    "eight": {"VIII"},
    "nine": {"IX"},
    "ten": {"X"},
    "eleven": {"XI"},
    "twelve": {"XII"},
    "fifty": {"L"},
    "hundred": {"C"},
    "five hundred": {"D"},
    "thousand": {"M", "K"},
    "a thousand": {"M", "K"},
    "million": {"M"},
    "unknown": {"X", "Y", "Z"},
    "unknown quantity": {"X", "Y", "Z"},
    "unknown quantity": {"X", "Y", "Z"},

    # Music
    "note": {"A", "B", "C", "D", "E", "F", "G", "DO", "RE", "MI", "FA", "SO", "LA", "TI", "TE"},
    "key": {"A", "B", "C", "D", "E", "F", "G"},
    "sharp": {"S"},
    "flat": {"B"},
    "loud": {"F", "FF"},
    "very loud": {"FF"},
    "goodbye from texter": {"CU"},
    "earnings for salesperson": {"OTE"},
    "very loud": {"FF"},
    "soft": {"P", "PP"},
    "very soft": {"PP"},
    "quietly": {"P"},

    # Countries / places
    "america": {"US", "USA"},
    "american": {"US"},
    "france": {"F", "FR"},
    "french": {"F", "FR"},
    "germany": {"D", "DE"},
    "german": {"D", "G"},
    "italy": {"I", "IT"},
    "italian": {"I", "IT"},
    "spain": {"E", "ES"},
    "spanish": {"E"},
    "greece": {"GR"},
    "greek": {"GR"},
    "roman": {"R"},
    "england": {"E", "ENG"},
    "english": {"E"},
    "scotland": {"S", "SC"},
    "scottish": {"SC"},
    "ireland": {"IRL"},
    "irish": {"IR"},
    "wales": {"W"},
    "welsh": {"W"},

    # Common abbreviations
    "i had": {"ID"},
    "i would": {"ID"},
    "cold": {"C"},
    "piano": {"P"},
    "roughly": {"C", "CA"},
    "about": {"C", "CA", "RE"},
    "touching": {"RE"},
    "regarding": {"RE"},
    "concerning": {"RE"},
    "against": {"V", "VS"},
    "year": {"Y", "YR"},
    "time": {"T"},
    "second": {"S", "SEC", "MO"},
    "minute": {"M", "MIN", "MO"},
    "hour": {"H", "HR"},
    "day": {"D", "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"},
    "week": {"W", "WK"},
    "month": {"M", "MO", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"},
    "age": {"ERA"},
    "area": {"A"},
    "article": {"A", "AN", "THE"},
    "work": {"OP", "OPUS"},
    "piece": {"OP", "BIT"},
    "commercial": {"AD"},
    "advertisement": {"AD"},
    "light source": {"LED"},
    "light": {"L"},
    "advert": {"AD"},
    "short commercial": {"AD"},
    "good": {"G"},
    "bad": {"B"},
    "old": {"O", "EX"},
    "new": {"N"},
    "small": {"S"},
    "large": {"L"},
    "medium": {"M"},
    "little": {"L"},
    "big": {"B"},
    "very": {"V"},
    "not": {"N"},
    "the": {"T"},
    "a": {"A"},
    "an": {"AN", "A"},
    "it": {"IT"},
    "in": {"IN"},
    "is": {"IS"},
    "who's": {"S"},  # contraction: 's gives S
    "on": {"ON"},
    "way": {"ST", "RD", "AVE", "WAY"},
    "road": {"RD", "ST", "AVE"},
    "street": {"ST"},
    "avenue": {"AVE", "AV"},
    "line": {"L", "RY"},
    "railway": {"RY", "BR"},
    "river": {"R"},
    "lake": {"L"},
    "church": {"CH", "CE"},
    "school": {"SCH"},
    "university": {"U", "UNI"},
    "college": {"C"},
    "hospital": {"H"},
    "home": {"IN"},
    "house": {"HO"},
    "ring": {"O"},
    "circle": {"O"},
    "round": {"O"},
    "ball": {"O"},
    "degree": {"D", "BA", "MA"},
    "island": {"I", "IS"},
    "pole": {"N", "S"},
    "party": {"DO", "BALL"},
    "energy": {"E"},
    "power": {"P"},
    "resistance": {"R"},
    "current": {"I", "AC", "DC"},
    "head": {"H"},
    "heart": {"H"},
    "mark": {"M"},
    "penny": {"P", "D"},
    "pound": {"L", "LB"},
    "pounds": {"L", "LB"},
    "bob": {"S"},
    "grand": {"G", "K"},
    "copper": {"CU", "P"},
    "gold": {"AU", "OR"},
    "silver": {"AG"},
    "iron": {"FE"},
    "lead": {"PB"},
    "tin": {"SN"},
    "carbon": {"C"},
    "nitrogen": {"N"},
    "oxygen": {"O"},
    "hydrogen": {"H"},
    "born": {"B", "NEE"},
    "died": {"D"},
    "dead": {"D"},
    "society": {"S", "SOC"},
    "club": {"C"},
    "association": {"A"},
    "united": {"U"},
    "band": {"RING", "O"},
    "record": {"EP", "LP", "CD"},
    "single": {"S"},
    "run": {"R"},
    "wicket": {"W"},
    "over": {"O"},
    "maiden": {"M"},
    "bowled": {"B"},
    "caught": {"C", "CT"},
    "stumped": {"ST"},
    "not out": {"NO"},
    "duck": {"O"},
    "boundary": {"FOUR", "SIX"},
}

# Valid template step types (from render_templates.json)
VALID_STEP_TYPES = {"definition", "wordplay_type", "indicator", "outer_word", "inner_word", "assembly", "fodder", "multi_definition"}

# Valid transform types (from assembly.transformPrompts)
VALID_TRANSFORM_TYPES = {"synonym", "abbreviation", "literal", "reversal", "deletion", "anagram", "container", "letter_selection", "homophone", "substitution"}

# Valid indicator types
VALID_INDICATOR_TYPES = {"container", "anagram", "deletion", "reversal", "ordering", "letter_selection", "hidden_word", "homophone", "substitution"}

# Valid definition_part values for multi_definition steps
VALID_DEFINITION_PARTS = {"first", "second", "third"}

# Dependent transform types that require a matching indicator step
DEPENDENT_TRANSFORM_TYPES = {"reversal", "deletion", "anagram", "container", "homophone", "substitution"}

# Indicator type equivalences (hidden_word covers reversal)
INDICATOR_EQUIVALENCES = {"hidden_word": {"reversal", "hidden_word"}}

# Required fields per step type
STEP_REQUIRED_FIELDS = {
    "definition": ["indices", "hint"],
    "wordplay_type": ["expected", "options", "hint"],
    "indicator": ["indices", "hint", "indicator_type"],
    "fodder": ["indices", "indicator_type", "hint"],
    "multi_definition": ["indices", "hint", "definition_part"],
    "outer_word": ["indices"],
    "inner_word": ["indices"],
    "assembly": ["transforms", "result"],
}

# Required fields per transform
TRANSFORM_REQUIRED_FIELDS = ["role", "indices", "type", "result", "hint"]


# ---------------------------------------------------------------------------
# Publication-specific conventions
# ---------------------------------------------------------------------------
# Each publication has its own flavour. These checks produce WARNINGS
# (not errors) since they're about likelihood, not correctness.

# American spelling patterns → British equivalents
# Each tuple: (american_regex_pattern, description)
# These check the ANSWER field, not clue text.
AMERICAN_SPELLING_PATTERNS = [
    (r'(?<![A-Z])COLOR(?!A)', "American spelling: COLOR (British: COLOUR)"),
    (r'(?<![A-Z])HONOR(?!A)', "American spelling: HONOR (British: HONOUR)"),
    (r'(?<![A-Z])FAVOR(?!I)', "American spelling: FAVOR (British: FAVOUR)"),
    (r'(?<![A-Z])LABOR(?!I)', "American spelling: LABOR (British: LABOUR)"),
    (r'(?<![A-Z])HUMOR(?!E)', "American spelling: HUMOR (British: HUMOUR)"),
    (r'(?<![A-Z])HARBOR', "American spelling: HARBOR (British: HARBOUR)"),
    (r'(?<![A-Z])NEIGHBOR', "American spelling: NEIGHBOR (British: NEIGHBOUR)"),
    (r'(?<![A-Z])RUMOR(?!E)', "American spelling: RUMOR (British: RUMOUR)"),
    (r'(?<![A-Z])SPLENDOR', "American spelling: SPLENDOR (British: SPLENDOUR)"),
    (r'(?<![A-Z])VAPOR', "American spelling: VAPOR (British: VAPOUR)"),
    (r'(?<![A-Z])VIGOR(?!O)', "American spelling: VIGOR (British: VIGOUR)"),
    (r'CENTER(?![A-Z])', "American spelling: CENTER (British: CENTRE)"),
    (r'THEATER(?![A-Z])', "American spelling: THEATER (British: THEATRE)"),
    (r'METER(?![A-Z])', "American spelling: METER (British: METRE)"),
    (r'LITER(?![A-Z])', "American spelling: LITER (British: LITRE)"),
    (r'FIBER(?![A-Z])', "American spelling: FIBER (British: FIBRE)"),
    (r'SABER(?![A-Z])', "American spelling: SABER (British: SABRE)"),
    (r'SOMBER(?![A-Z])', "American spelling: SOMBER (British: SOMBRE)"),
    (r'SPECTER(?![A-Z])', "American spelling: SPECTER (British: SPECTRE)"),
    (r'CALIBER(?![A-Z])', "American spelling: CALIBER (British: CALIBRE)"),
    (r'DEFENSE(?![A-Z])', "American spelling: DEFENSE (British: DEFENCE)"),
    (r'OFFENSE(?![A-Z])', "American spelling: OFFENSE (British: OFFENCE)"),
    (r'LICENSE(?![A-Z])', "American spelling: LICENSE noun (British: LICENCE)"),
    (r'PRETENSE(?![A-Z])', "American spelling: PRETENSE (British: PRETENCE)"),
    (r'CATALOG(?![A-Z])', "American spelling: CATALOG (British: CATALOGUE)"),
    (r'DIALOG(?![A-Z])', "American spelling: DIALOG (British: DIALOGUE)"),
    (r'PROLOG(?![A-Z])', "American spelling: PROLOG (British: PROLOGUE)"),
    (r'ANALOG(?![A-Z])', "American spelling: ANALOG (British: ANALOGUE)"),
    (r'GRAY(?![A-Z])', "American spelling: GRAY (British: GREY)"),
    (r'PLOW(?![A-Z])', "American spelling: PLOW (British: PLOUGH)"),
    (r'PAJAMAS', "American spelling: PAJAMAS (British: PYJAMAS)"),
    (r'ALUMINUM', "American spelling: ALUMINUM (British: ALUMINIUM)"),
    (r'MUSTACHE', "American spelling: MUSTACHE (British: MOUSTACHE)"),
    (r'SKEPTIC', "American spelling: SKEPTIC (British: SCEPTIC)"),
    (r'ARCHEOLOGY', "American spelling: ARCHEOLOGY (British: ARCHAEOLOGY)"),
    (r'PEDIATRIC', "American spelling: PEDIATRIC (British: PAEDIATRIC)"),
    (r'ANESTHETIC', "American spelling: ANESTHETIC (British: ANAESTHETIC)"),
    (r'HEMORRHAGE', "American spelling: HEMORRHAGE (British: HAEMORRHAGE)"),
    (r'ENCYCLOPEDIA(?![A-Z])', "American spelling: ENCYCLOPEDIA (British: ENCYCLOPAEDIA)"),
    (r'MANEUVER', "American spelling: MANEUVER (British: MANOEUVRE)"),
    (r'TRAVELING(?![A-Z])', "American spelling: TRAVELING (British: TRAVELLING)"),
    (r'TRAVELER(?![A-Z])', "American spelling: TRAVELER (British: TRAVELLER)"),
    (r'MODELING(?![A-Z])', "American spelling: MODELING (British: MODELLING)"),
    (r'JEWELRY(?![A-Z])', "American spelling: JEWELRY (British: JEWELLERY)"),
]

# Times-specific abbreviation extensions (beyond the general set above)
# These are particularly common in Times puzzles due to UK focus.
TIMES_ABBREVIATIONS = {
    # British institutions
    "academy": {"RA"},         # Royal Academy
    "gallery": {"RA", "TATE"},
    "trust": {"NT"},           # National Trust
    "corporation": {"BBC"},
    "health service": {"NHS"},
    "museum": {"BM", "VA"},    # British Museum, V&A

    # UK politics
    "conservative": {"C", "CON", "TORY"},
    "labour": {"LAB"},
    "liberal": {"L", "LIB"},
    "member": {"MP"},
    "parliament": {"MP"},
    "minister": {"PM"},
    "prime minister": {"PM"},

    # British royalty / honours
    "monarch": {"ER", "R", "K", "Q"},
    "queen": {"Q", "R", "ER", "QU", "HM"},
    "king": {"K", "R", "REX", "HM"},
    "majesty": {"HM"},
    "honour": {"OBE", "MBE", "CBE"},
    "decoration": {"OBE", "MBE", "CBE", "MC", "DSO", "VC", "MM"},
    "medal": {"MC", "DSO", "VC", "MM", "GM"},

    # British military
    "gunners": {"RA"},        # Royal Artillery
    "sappers": {"RE"},        # Royal Engineers
    "marines": {"RM"},        # Royal Marines
    "fleet": {"RN"},          # Royal Navy
    "navy": {"RN"},
    "reserves": {"TA"},       # Territorial Army
    "volunteers": {"TA"},
    "ranks": {"OR"},          # Other Ranks
    "officer": {"CO", "LT", "COL"},

    # British education
    "don": {"FELLOW"},
    "college": {"C", "ETON"},
    "school": {"SCH", "ETON"},
    "varsity": {"UNI", "U"},

    # UK rivers (common building blocks)
    "river": {"R", "CAM", "DEE", "DON", "EXE", "PO", "TAY", "URE", "USK", "WYE",
              "AXE", "ESK", "OUSE", "AVON", "TEST", "TEES", "NENE", "SPEY",
              "TAFF", "TYNE", "ISIS"},
    "flower": {"R", "CAM", "DEE", "DON", "EXE", "TAY", "URE", "USK", "WYE",
               "AVON", "NILE", "PO"},  # "flower" = thing that flows = river
    "banker": {"R", "CAM", "DEE", "DON", "EXE"},  # thing with banks = river
    "runner": {"R"},  # thing that runs = river

    # Cricket (heavily used in Times)
    "duck": {"O"},
    "maiden": {"M", "OVER"},
    "innings": {"BAT"},
    "test": {"MATCH"},
    "eleven": {"XI", "TEAM", "SIDE"},
    "side": {"ON", "OFF", "XI"},

    # British currency (old)
    "bob": {"S"},            # shilling
    "quid": {"L"},           # pound
    "copper": {"CU", "P", "D"},
    "guinea": {"G", "GN"},
    "groat": {"D"},          # old fourpence
    "crown": {"COIN"},

    # British slang / colloquial
    "chap": {"MAN"},
    "fellow": {"F", "MAN"},
    "bloke": {"MAN"},
    "mate": {"PAL"},
    "pub": {"INN", "LOCAL", "PH"},
    "inn": {"PH", "PUB", "LOCAL"},
    "public house": {"PH", "INN", "PUB"},
    "loo": {"WC", "LAV"},
    "telly": {"TV"},
    "motor": {"CAR"},
    "lorry": {"HGV"},
    "nappy": {"DIAPER"},
    "boot": {"TRUNK"},       # of a car
    "bonnet": {"HOOD"},      # of a car
    "flat": {"B", "APARTMENT"},
    "lift": {"ELEVATOR"},
    "queue": {"LINE"},
    "holiday": {"BREAK", "VAC"},
}

# Publication convention registries — keyed by publication name
PUBLICATION_CONVENTIONS = {
    "times": {
        "spelling_checks": AMERICAN_SPELLING_PATTERNS,
        "extra_abbreviations": TIMES_ABBREVIATIONS,
        "description": "The Times (London) — British English, UK institutions, cricket, military",
    },
    # Future publications can be added here:
    # "guardian": { ... },
    # "telegraph": { ... },
}


def _check_publication_conventions(publication, item):
    """
    Run publication-specific checks on a training item.

    Returns list of warning strings. All publication checks are warnings,
    not errors — they flag implausible data, not provably wrong data.
    """
    warnings = []

    if publication not in PUBLICATION_CONVENTIONS:
        return warnings

    conventions = PUBLICATION_CONVENTIONS[publication]

    # --- British spelling check on answer ---
    answer = item.get("answer", "")
    for pattern, description in conventions.get("spelling_checks", []):
        if re.search(pattern, answer):
            warnings.append(f"Publication '{publication}': {description} — answer is '{answer}'")

    # --- Check abbreviation transforms against publication-specific dictionary ---
    extra_abbrevs = conventions.get("extra_abbreviations", {})
    for step in item.get("steps", []):
        if step.get("type") != "assembly":
            continue
        words = item.get("words", [])
        for ti, transform in enumerate(step.get("transforms", [])):
            if transform.get("type") != "abbreviation":
                continue
            t_words = []
            if "indices" in transform:
                t_words = [words[idx] for idx in transform["indices"]
                           if 0 <= idx < len(words)]
            t_result = transform.get("result", "")
            key = " ".join(t_words).lower()

            # Check general dictionary first (already done in main validator)
            # Here we just add the publication-specific entries as additional
            # known-good mappings for informational purposes
            if key in extra_abbrevs and t_result in extra_abbrevs[key]:
                # Known Times abbreviation — no warning needed
                pass

    return warnings


# ---------------------------------------------------------------------------
# Chain-aware helpers (ported from training_handler.py)
# ---------------------------------------------------------------------------

def _find_consumed_predecessors(transforms, dep_index):
    """Find predecessor indices consumed by a dependent transform.

    Works backwards from dep_index, accumulating predecessors until
    the combined letter count matches the dependent's result length.
    Skips predecessors already consumed by intermediate dependent transforms
    (e.g. a reversal's input is replaced by its output, not added alongside it).
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
            inner_consumed = _find_consumed_predecessors(transforms, j)
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


def _find_terminal_transforms(transforms):
    """Identify terminal transforms — those not consumed by a later dependent."""
    terminal = set(range(len(transforms)))
    for i, t in enumerate(transforms):
        t_type = t.get("type", "")
        if t_type in DEPENDENT_TRANSFORM_TYPES:
            consumed = _find_consumed_predecessors(transforms, i)
            for c in consumed:
                terminal.discard(c)
    return terminal


# ---------------------------------------------------------------------------
# Deterministic transform checks
# ---------------------------------------------------------------------------

def _check_literal(clue_words, result):
    """Literal: result must equal the uppercase of the clue word(s)."""
    expected = " ".join(clue_words).upper().replace(" ", "")
    if result != expected:
        return f"literal check failed: '{' '.join(clue_words)}' should give '{expected}', got '{result}'"
    return None


def _check_reversal(transforms, current_idx, result):
    """Reversal: result must be the reverse of consumed predecessors' combined result."""
    consumed = _find_consumed_predecessors(transforms, current_idx)
    combined = "".join(transforms[c]["result"] for c in consumed)
    # Strip non-alpha characters for comparison (handles multi-word answers like TO ORDER)
    combined_alpha = re.sub(r'[^A-Z]', '', combined.upper())
    result_alpha = re.sub(r'[^A-Z]', '', result.upper())
    if result_alpha == combined_alpha[::-1]:
        return None
    return f"reversal check failed: '{result}' is not the reverse of consumed input '{combined}'"


def _check_deletion(transforms, current_idx, result):
    """Deletion: result must be consumed predecessor(s) with letter(s) removed."""
    consumed = _find_consumed_predecessors(transforms, current_idx)
    combined = "".join(transforms[c]["result"] for c in consumed)

    if len(result) >= len(combined):
        return f"deletion check failed: result '{result}' is not shorter than input '{combined}'"

    # Check that result can be formed by removing letters from combined.
    # Walk through combined, matching result characters in order.
    ri = 0
    for ch in combined:
        if ri < len(result) and ch == result[ri]:
            ri += 1
    if ri == len(result):
        return None

    return f"deletion check failed: '{result}' cannot be formed by deleting letters from '{combined}'"


def _check_anagram(transforms, current_idx, result):
    """Anagram: sorted letters of consumed input must match sorted letters of result."""
    consumed = _find_consumed_predecessors(transforms, current_idx)
    combined = "".join(transforms[c]["result"] for c in consumed)

    # Strip non-alpha characters (spaces, hyphens) for comparison
    combined_alpha = re.sub(r'[^A-Z]', '', combined.upper())
    result_alpha = re.sub(r'[^A-Z]', '', result.upper())

    if sorted(combined_alpha) != sorted(result_alpha):
        return f"anagram check failed: sorted('{combined_alpha}') != sorted('{result_alpha}')"
    return None


def _check_container(transforms, current_idx, result):
    """Container: result must be formed by inserting inner piece(s) inside an outer piece.

    Supports:
    - 2 predecessors: one inserted inside the other (standard case)
    - 3+ predecessors: one is outer, the rest concatenate as inner (e.g. V+AD inside HER)
    """
    consumed = _find_consumed_predecessors(transforms, current_idx)
    if len(consumed) < 2:
        return f"container check failed: need at least 2 consumed predecessors, got {len(consumed)}"

    # Strip non-alpha for comparison (handles multi-word answers like WARTS AND ALL)
    predecessor_results = [re.sub(r'[^A-Z]', '', transforms[c]["result"].upper()) for c in consumed]
    result_alpha = re.sub(r'[^A-Z]', '', result.upper())

    # Try all pairs: for each pair, check if one goes inside the other
    for i, outer in enumerate(predecessor_results):
        for j, inner in enumerate(predecessor_results):
            if i == j:
                continue
            # Try inserting inner into outer at every position
            for pos in range(1, len(outer)):
                combined = outer[:pos] + inner + outer[pos:]
                if combined == result_alpha:
                    return None

    # If more than 2 predecessors, try concatenating all non-outer pieces as inner
    if len(predecessor_results) > 2:
        from itertools import permutations
        for i, outer in enumerate(predecessor_results):
            others = [p for j, p in enumerate(predecessor_results) if j != i]
            # Try all orderings of the inner pieces
            for perm in permutations(others):
                inner = "".join(perm)
                for pos in range(1, len(outer)):
                    combined = outer[:pos] + inner + outer[pos:]
                    if combined == result_alpha:
                        return None

    return f"container check failed: '{result}' cannot be formed by inserting one predecessor inside another (predecessors: {predecessor_results})"


def _check_letter_selection(clue_words, result):
    """Letter selection: result must be extractable from source words by a known method."""
    source = " ".join(clue_words)
    source_upper = source.upper()
    source_no_spaces = source_upper.replace(" ", "")

    # Check hidden word: contiguous letters spanning across words
    if result in source_no_spaces:
        return None

    # Check first letters of each word
    firsts = "".join(w[0].upper() for w in clue_words if w)
    if result in firsts or firsts.startswith(result):
        return None

    # Check last letters of each word
    lasts = "".join(w[-1].upper() for w in clue_words if w)
    if result in lasts or lasts.startswith(result):
        return None

    # Check alternating letters (every other letter)
    evens = "".join(source_no_spaces[i] for i in range(0, len(source_no_spaces), 2))
    odds = "".join(source_no_spaces[i] for i in range(1, len(source_no_spaces), 2))
    if result in evens or result in odds:
        return None

    # Check first letter of single word
    if len(clue_words) == 1 and len(result) == 1 and source_upper[0] == result:
        return None

    # Check last letter of single word
    if len(clue_words) == 1 and len(result) == 1 and source_upper[-1] == result:
        return None

    return f"letter_selection check failed: '{result}' doesn't match first/last/alternating/hidden letters of '{source}'"


def _check_substitution(transforms, current_idx, result):
    """Substitution: result must be same length as consumed predecessor, differing by exactly one letter."""
    consumed = _find_consumed_predecessors(transforms, current_idx)
    combined = "".join(re.sub(r'[^A-Z]', '', transforms[c]["result"].upper()) for c in consumed)
    result_alpha = re.sub(r'[^A-Z]', '', result.upper())

    if len(result_alpha) != len(combined):
        return f"substitution check failed: result '{result}' has different length ({len(result_alpha)}) than input '{combined}' ({len(combined)})"

    diffs = sum(1 for a, b in zip(combined, result_alpha) if a != b)
    if diffs != 1:
        return f"substitution check failed: result '{result}' differs from input '{combined}' at {diffs} positions (expected exactly 1)"
    return None


def _check_abbreviation(clue_words, result, publication=None):
    """Abbreviation: check against known cryptic abbreviation dictionary. Returns warning, not error."""
    key = " ".join(clue_words).lower()

    # Check general dictionary
    if key in CRYPTIC_ABBREVIATIONS:
        if result in CRYPTIC_ABBREVIATIONS[key]:
            return None

    # Try individual words in general dictionary
    for word in clue_words:
        wl = word.lower()
        if wl in CRYPTIC_ABBREVIATIONS:
            if result in CRYPTIC_ABBREVIATIONS[wl]:
                return None

    # Check publication-specific dictionary
    if publication and publication in PUBLICATION_CONVENTIONS:
        extra = PUBLICATION_CONVENTIONS[publication].get("extra_abbreviations", {})
        if key in extra and result in extra[key]:
            return None
        for word in clue_words:
            wl = word.lower()
            if wl in extra and result in extra[wl]:
                return None

    # Not found in any dictionary
    if key in CRYPTIC_ABBREVIATIONS:
        return f"abbreviation warning: '{key}' → '{result}' not in known set {CRYPTIC_ABBREVIATIONS[key]}"
    return f"abbreviation warning: '{key}' → '{result}' not found in abbreviation dictionary"


# ---------------------------------------------------------------------------
# Parse enumeration to total letter count
# ---------------------------------------------------------------------------

def _parse_enumeration(enum_str):
    """Parse enumeration string like '7' or '5,3' or '5-6' to total letter count."""
    # Remove spaces, split on comma or hyphen
    parts = re.split(r'[,\-]', enum_str.replace(" ", ""))
    total = 0
    for p in parts:
        p = p.strip()
        if p.isdigit():
            total += int(p)
    return total


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def _extract_publication(item_id):
    """Extract publication name from item ID like 'times-29453-11a' → 'times'."""
    parts = item_id.split("-")
    if len(parts) >= 2:
        return parts[0].lower()
    return None


def validate_training_item(item_id, item):
    """
    Validate a single training item.

    Returns:
        (errors, warnings) — two lists of strings.
        errors = fatal issues (block upload/load)
        warnings = informational issues (log but don't block)
    """
    errors = []
    warnings = []

    # Extract publication for publication-specific checks
    publication = _extract_publication(item_id)

    # --- 1. Required top-level fields ---
    required_fields = ["clue", "number", "enumeration", "answer", "words", "clue_type", "difficulty", "steps"]
    for field in required_fields:
        if field not in item:
            errors.append(f"Missing required field: '{field}'")

    # If critical fields missing, can't proceed with further checks
    if "words" not in item or "steps" not in item or "answer" not in item:
        return errors, warnings

    words = item["words"]
    answer = item["answer"]
    steps = item["steps"]

    # --- 2. Words match clue text (ignoring enumeration and punctuation) ---
    # clue is display text (with punctuation, enumeration); words is the tokenised breakdown
    if "clue" in item:
        clue_text = item["clue"]
        # Strip trailing enumeration e.g. "(7)", "(5,4)", "(5-4)", "(3,3,4)"
        clue_text = re.sub(r'\s*\([\d,\-]+\)\s*$', '', clue_text)
        # Compare just the alphabetic words from both sides
        clue_words = re.findall(r"[a-zA-Z]+", clue_text)
        meta_words = re.findall(r"[a-zA-Z]+", " ".join(words))
        if clue_words != meta_words:
            errors.append(f"words array doesn't match clue text: words={meta_words} clue={clue_words}")

    # --- 3. Steps is non-empty, each has type ---
    if not isinstance(steps, list) or len(steps) == 0:
        errors.append("'steps' must be a non-empty array")
        return errors, warnings

    for i, step in enumerate(steps):
        if "type" not in step:
            errors.append(f"Step {i}: missing 'type' field")
            continue

        step_type = step["type"]

        # --- 4. Step type is valid ---
        if step_type not in VALID_STEP_TYPES:
            errors.append(f"Step {i}: invalid type '{step_type}', must be one of {VALID_STEP_TYPES}")
            continue

        # --- 5. Indices in bounds ---
        if "indices" in step:
            for idx in step["indices"]:
                if not isinstance(idx, int) or idx < 0 or idx >= len(words):
                    errors.append(f"Step {i} ({step_type}): index {idx} out of bounds (words has {len(words)} items)")

        # --- 6. Step-specific required fields ---
        if step_type in STEP_REQUIRED_FIELDS:
            for field in STEP_REQUIRED_FIELDS[step_type]:
                if field not in step:
                    errors.append(f"Step {i} ({step_type}): missing required field '{field}'")

        # --- 13. Indicator type valid ---
        if step_type == "indicator" and "indicator_type" in step:
            if step["indicator_type"] not in VALID_INDICATOR_TYPES:
                errors.append(f"Step {i} (indicator): invalid indicator_type '{step['indicator_type']}', must be one of {VALID_INDICATOR_TYPES}")

        # --- 13b. Definition part valid ---
        if step_type == "multi_definition" and "definition_part" in step:
            if step["definition_part"] not in VALID_DEFINITION_PARTS:
                errors.append(f"Step {i} (multi_definition): invalid definition_part '{step['definition_part']}', must be one of {VALID_DEFINITION_PARTS}")

        # --- Assembly-specific checks ---
        if step_type == "assembly":
            transforms = step.get("transforms", [])
            assembly_result = step.get("result", "")

            if not isinstance(transforms, list) or len(transforms) == 0:
                errors.append(f"Step {i} (assembly): 'transforms' must be a non-empty array")
                continue

            # --- 7. Assembly result == answer ---
            if assembly_result != answer:
                errors.append(f"Step {i} (assembly): result '{assembly_result}' != answer '{answer}'")

            # --- 8. Terminal transform results must produce assembly result ---
            # Dependent transforms (reversal, deletion, anagram, container) consume
            # their predecessors — only terminal transforms contribute to the final answer.
            terminal = _find_terminal_transforms(transforms)
            terminal_results = [transforms[idx].get("result", "") for idx in sorted(terminal)]
            concat_letters = re.sub(r'[^A-Z]', '', "".join(terminal_results).upper())
            assembly_letters = re.sub(r'[^A-Z]', '', assembly_result.upper())

            # For container clues, terminal results are inserted (not concatenated).
            # For charades with reordering, parts may not be left-to-right.
            # Check: same letters (sorted) must match.
            if sorted(concat_letters) != sorted(assembly_letters):
                errors.append(f"Step {i} (assembly): terminal transform letters '{concat_letters}' don't match assembly result letters '{assembly_letters}'")

            # --- 11. Total letter count matches enumeration ---
            if "enumeration" in item:
                expected_len = _parse_enumeration(item["enumeration"])
                actual_len = len(assembly_letters)
                if actual_len != expected_len:
                    errors.append(f"Step {i} (assembly): total letters {actual_len} != enumeration {expected_len} ('{item['enumeration']}')")

            # Validate each transform
            for ti, transform in enumerate(transforms):
                # --- 9. Transform required fields ---
                for field in TRANSFORM_REQUIRED_FIELDS:
                    if field not in transform:
                        errors.append(f"Step {i}, transform {ti}: missing required field '{field}'")

                if "type" not in transform or "result" not in transform:
                    continue

                t_type = transform["type"]
                t_result = transform["result"]

                # --- 10. Transform type valid ---
                if t_type not in VALID_TRANSFORM_TYPES:
                    errors.append(f"Step {i}, transform {ti}: invalid type '{t_type}', must be one of {VALID_TRANSFORM_TYPES}")
                    continue

                # --- 14. No prompt field on transforms ---
                if "prompt" in transform:
                    errors.append(f"Step {i}, transform {ti}: has 'prompt' field — prompts must come from render_templates.json, not individual transforms")

                # --- 5. Transform indices in bounds ---
                if "indices" in transform:
                    for idx in transform["indices"]:
                        if not isinstance(idx, int) or idx < 0 or idx >= len(words):
                            errors.append(f"Step {i}, transform {ti}: index {idx} out of bounds (words has {len(words)} items)")

                # Get clue words for this transform
                t_words = []
                if "indices" in transform:
                    t_words = [words[idx] for idx in transform["indices"] if 0 <= idx < len(words)]

                # --- Convention checks (15-22) ---
                if t_type == "literal":
                    err = _check_literal(t_words, t_result)
                    if err:
                        errors.append(f"Step {i}, transform {ti}: {err}")

                elif t_type == "reversal":
                    err = _check_reversal(transforms, ti, t_result)
                    if err:
                        errors.append(f"Step {i}, transform {ti}: {err}")

                elif t_type == "deletion":
                    err = _check_deletion(transforms, ti, t_result)
                    if err:
                        errors.append(f"Step {i}, transform {ti}: {err}")

                elif t_type == "anagram":
                    err = _check_anagram(transforms, ti, t_result)
                    if err:
                        errors.append(f"Step {i}, transform {ti}: {err}")

                elif t_type == "container":
                    err = _check_container(transforms, ti, t_result)
                    if err:
                        errors.append(f"Step {i}, transform {ti}: {err}")

                elif t_type == "letter_selection":
                    err = _check_letter_selection(t_words, t_result)
                    if err:
                        errors.append(f"Step {i}, transform {ti}: {err}")

                elif t_type == "abbreviation":
                    warn = _check_abbreviation(t_words, t_result, publication)
                    if warn:
                        warnings.append(f"Step {i}, transform {ti}: {warn}")

                elif t_type == "synonym":
                    # Synonym check: no external API for now, just log for awareness
                    pass

                elif t_type == "homophone":
                    # Homophone check: can't verify pronunciation programmatically
                    pass

                elif t_type == "substitution":
                    err = _check_substitution(transforms, ti, t_result)
                    if err:
                        errors.append(f"Step {i}, transform {ti}: {err}")

    # --- 12. Indicator coverage ---
    # Collect indicator types from indicator steps
    indicator_types_present = set()
    for step in steps:
        if step.get("type") == "indicator" and "indicator_type" in step:
            ind_type = step["indicator_type"]
            # Apply equivalences
            if ind_type in INDICATOR_EQUIVALENCES:
                indicator_types_present.update(INDICATOR_EQUIVALENCES[ind_type])
            else:
                indicator_types_present.add(ind_type)

    # Check each dependent transform has a matching indicator
    for step in steps:
        if step.get("type") != "assembly":
            continue
        for ti, transform in enumerate(step.get("transforms", [])):
            t_type = transform.get("type", "")
            if t_type in DEPENDENT_TRANSFORM_TYPES:
                if t_type not in indicator_types_present:
                    errors.append(f"Transform {ti} ({t_type}): no matching '{t_type}' indicator step found")

    # --- Publication-specific checks ---
    if publication:
        pub_warnings = _check_publication_conventions(publication, item)
        warnings.extend(pub_warnings)

    return errors, warnings


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def validate_all(puzzle_number=None):
    """Validate all training items from Supabase. Returns (total, passed, failed).

    Args:
        puzzle_number: Optional puzzle number to filter (e.g. '29453').
                       If None, validates all items.
    """
    from puzzle_store_supabase import PuzzleStoreSupabase

    store = PuzzleStoreSupabase()
    items = store.get_training_clues()

    if puzzle_number:
        items = {k: v for k, v in items.items() if f'-{puzzle_number}-' in k}
        if not items:
            print(f"ERROR: No training data found for puzzle #{puzzle_number}")
            return 0, 0, 0

    total = len(items)
    passed = 0
    failed = 0

    for item_id, item in sorted(items.items()):
        errors, warnings_list = validate_training_item(item_id, item)

        if errors:
            failed += 1
            print(f"\n✗ {item_id} ({item.get('number', '?')}: {item.get('answer', '?')})")
            for err in errors:
                print(f"  ERROR: {err}")
            for warn in warnings_list:
                print(f"  WARNING: {warn}")
        elif warnings_list:
            passed += 1
            print(f"\n⚠ {item_id} ({item.get('number', '?')}: {item.get('answer', '?')})")
            for warn in warnings_list:
                print(f"  WARNING: {warn}")
        else:
            passed += 1
            print(f"✓ {item_id}")

    print(f"\n{'='*40}")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")

    return total, passed, failed


if __name__ == "__main__":
    puzzle = sys.argv[1] if len(sys.argv) > 1 else None
    total, passed, failed = validate_all(puzzle)
    sys.exit(1 if failed > 0 else 0)
