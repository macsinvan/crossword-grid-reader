#!/usr/bin/env python3
"""
Trainer Regression Tests
========================

Tests all trainer API endpoints against a running server.
Walks through all 30 converted clues covering all step flow patterns,
all indicator types, all transform types, and key edge cases.

Usage:
    python3 test_regression.py
    python3 test_regression.py --server http://127.0.0.1:8080

Requires: a running crossword_server.py instance.
Dependencies: stdlib only (urllib).
"""

import json
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SERVER = "http://127.0.0.1:8080"

# ---------------------------------------------------------------------------
# 30 Test Clues — 100% coverage of all converted clues
# ---------------------------------------------------------------------------
#
# Each clue dict contains:
#   id, clue_text, puzzle_number, clue_number, direction, answer
#   steps: list of {type, inputMode, value, ...} for the happy-path walkthrough
#     - tap_words steps: value = list of indices
#     - multiple_choice steps: value = string (the expected answer)
#     - assembly steps: transforms = [{index, value}, ...]
#   has_indicator_steps: bool — whether any step is type "indicator"
#   indicator_types: list of indicator_type strings (for template text tests)
#   assembly_explicit: bool — whether assembly has explicit=True
#   num_assembly_transforms: int — total transform count
#   dependent_transform_indices: list of int — which transforms are dependent
#   wrong_value_step0: a wrong value for the definition step (for negative test)

TEST_CLUES = [
    # 1. 11A VISIT — def→wordplay→assembly (simplest charade, 2 independent)
    {
        "id": "times-29453-11a",
        "clue_text": "Come by five, do you mean?",
        "puzzle_number": "29453",
        "clue_number": "11",
        "direction": "across",
        "answer": "VISIT",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "V"}, {"index": 1, "value": "ISIT"}]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [3, 4],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["five", "mean"],
    },

    # 2. 6D RAVEN — def→indicator(ordering)→assembly
    {
        "id": "times-29453-6d",
        "clue_text": "Any number after dance party are starving",
        "puzzle_number": "29453",
        "clue_number": "6",
        "direction": "down",
        "answer": "RAVEN",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [5, 6]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "RAVE"}, {"index": 1, "value": "N"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["ordering"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [0, 1],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["dance", "number"],
    },

    # 3. 1A BROLLY — def→indicator(container)→outer→inner→assembly
    {
        "id": "times-29453-1a",
        "clue_text": "Cover up in shower? Not after nurses turn round",
        "puzzle_number": "29453",
        "clue_number": "1",
        "direction": "across",
        "answer": "BROLLY",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1, 2, 3]},
            {"type": "indicator", "inputMode": "tap_words", "value": [6]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [4, 5]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [7, 8]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "BY"}, {"index": 1, "value": "ROLL"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [5, 6],
    },

    # 4. 2D OMERTA — def→indicator(anagram)→fodder→assembly (anagram dependent)
    {
        "id": "times-29453-2d",
        "clue_text": "Crooked old mater \u2014 which strongly suggests criminal is mum",
        "puzzle_number": "29453",
        "clue_number": "2",
        "direction": "down",
        "answer": "OMERTA",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [4, 5, 6, 7, 8, 9]},
            {"type": "indicator", "inputMode": "tap_words", "value": [0]},
            {"type": "fodder", "inputMode": "tap_words", "value": [1, 2]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "O"},
                 {"index": 1, "value": "MATER"},
                 {"index": 2, "value": "OMERTA"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["anagram"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # anagram at index 2 depends on 0, 1
        "wrong_value_step0": [0, 1],
    },

    # 5. 3D LATECOMER — def→indicator(letter_selection)→indicator(anagram)→assembly (explicit=True)
    {
        "id": "times-29453-3d",
        "clue_text": "One missing initially, admitted to Electra with some upheaval?",
        "puzzle_number": "29453",
        "clue_number": "3",
        "direction": "down",
        "answer": "LATECOMER",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "indicator", "inputMode": "tap_words", "value": [7, 8]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "OM"},
                 {"index": 1, "value": "ELECTRA"},
                 {"index": 2, "value": "LATECOMER"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["letter_selection", "anagram"],
        "assembly_explicit": True,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # anagram at index 2
        "wrong_value_step0": [3, 4],
    },

    # 6. 17D ASWAN DAM — def→wordplay(Container)→indicator(container)→outer→inner→assembly (hybrid)
    {
        "id": "times-29453-17d",
        "clue_text": "Embankment architect lengthened with cob?",
        "puzzle_number": "29453",
        "clue_number": "17",
        "direction": "down",
        "answer": "ASWAN DAM",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Container"},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [1]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "ADAM"}, {"index": 1, "value": "SWAN"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [1, 2],
    },

    # 7. 5D EEK — def→indicator(deletion)→fodder→indicator(reversal)→assembly (chain)
    {
        "id": "times-29453-5d",
        "clue_text": "A lot of sharp turns, I'm afraid",
        "puzzle_number": "29453",
        "clue_number": "5",
        "direction": "down",
        "answer": "EEK",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [5, 6]},
            {"type": "indicator", "inputMode": "tap_words", "value": [0, 1, 2]},
            {"type": "fodder", "inputMode": "tap_words", "value": [3]},
            {"type": "indicator", "inputMode": "tap_words", "value": [4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "KEEN"},
                 {"index": 1, "value": "KEE"},
                 {"index": 2, "value": "EEK"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["deletion", "reversal"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [1, 2],  # deletion at 1, reversal at 2
        "wrong_value_step0": [0, 1],
    },

    # 8. 13A ANDANTINO — def→wordplay→assembly (3 independent synonyms)
    {
        "id": "times-29453-13a",
        "clue_text": "Moderate movement also opposed to one referendum option",
        "puzzle_number": "29453",
        "clue_number": "13",
        "direction": "across",
        "answer": "ANDANTINO",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "AND"},
                 {"index": 1, "value": "ANTI"},
                 {"index": 2, "value": "NO"},
             ]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [],
        "wrong_value_step0": [2, 3],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["also", "opposed", "referendum"],
    },

    # 9. 4A REPROACH — def→indicator(deletion)→assembly (charade with deletion)
    {
        "id": "times-29453-4a",
        "clue_text": "Twit copying antique with pine, mostly",
        "puzzle_number": "29453",
        "clue_number": "4",
        "direction": "across",
        "answer": "REPROACH",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "indicator", "inputMode": "tap_words", "value": [5]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "REPRO"},
                 {"index": 1, "value": "ACHE"},
                 {"index": 2, "value": "ACH"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["deletion"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # deletion at index 2
        "wrong_value_step0": [1, 2],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["antique"],
    },

    # 10. 28A CAESAR — def→indicator(reversal)→assembly (reversal chain)
    {
        "id": "times-29453-28a",
        "clue_text": "Tsar\u2019s like, roughly level after revolution",
        "puzzle_number": "29453",
        "clue_number": "28",
        "direction": "across",
        "answer": "CAESAR",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [5]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "CA"},
                 {"index": 1, "value": "RASE"},
                 {"index": 2, "value": "ESAR"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["reversal"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # reversal at index 2
        "wrong_value_step0": [2, 3],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["roughly"],
    },

    # 11. 26A WINDSWEPT — def→indicator(reversal)→indicator(container)→assembly (5 transforms, mixed chain)
    {
        "id": "times-29453-26a",
        "clue_text": "Turn bench back in street exposed to blasts",
        "puzzle_number": "29453",
        "clue_number": "26",
        "direction": "across",
        "answer": "WINDSWEPT",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [5, 6, 7]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "indicator", "inputMode": "tap_words", "value": [3]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "WIND"},
                 {"index": 1, "value": "PEW"},
                 {"index": 2, "value": "WEP"},
                 {"index": 3, "value": "ST"},
                 {"index": 4, "value": "SWEPT"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["reversal", "container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 5,
        "dependent_transform_indices": [2, 4],  # reversal at 2, container at 4
        "wrong_value_step0": [0, 1],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["Turn"],
    },

    # 12. 23D PSEUD — def→indicator(hidden_word)→fodder→assembly
    {
        "id": "times-29453-23d",
        "clue_text": "Pretend authority raised undue spending limits",
        "puzzle_number": "29453",
        "clue_number": "23",
        "direction": "down",
        "answer": "PSEUD",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2, 5]},
            {"type": "fodder", "inputMode": "tap_words", "value": [3, 4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "DUESP"},
                 {"index": 1, "value": "PSEUD"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["hidden_word"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [1],  # reversal at index 1
        "wrong_value_step0": [3, 4],
    },

    # 13. 19A SOLAR ECLIPSE — def→indicator(container)→outer→inner→assembly (container with charade inner)
    {
        "id": "times-29453-19a",
        "clue_text": "Are cold kissers coming inside only when it\u2019s dark?",
        "puzzle_number": "29453",
        "clue_number": "19",
        "direction": "across",
        "answer": "SOLAR ECLIPSE",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [6, 7, 8]},
            {"type": "indicator", "inputMode": "tap_words", "value": [3, 4]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [5]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [0, 1, 2]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "SOLE"},
                 {"index": 1, "value": "ARE"},
                 {"index": 2, "value": "C"},
                 {"index": 3, "value": "LIPS"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 4,
        "dependent_transform_indices": [],
        "wrong_value_step0": [0, 1],
        "is_container": True,  # flag for container-specific completion text test
    },

    # 14. 16D DISHDASHA — def→indicator(anagram)→fodder→assembly (charade with anagram chain)
    {
        "id": "times-29453-16d",
        "clue_text": "Arab robe ad has misrepresented with superior beauty",
        "puzzle_number": "29453",
        "clue_number": "16",
        "direction": "down",
        "answer": "DISHDASHA",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [4]},
            {"type": "fodder", "inputMode": "tap_words", "value": [2, 3]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "DISH"},
                 {"index": 1, "value": "ADHAS"},
                 {"index": 2, "value": "DASHA"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["anagram"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # anagram at index 2
        "wrong_value_step0": [2, 3],
        "has_anagram_chain": True,  # flag for anagram breakdown test
        "expected_breakdown_contains": "(ADHAS \u2192 DASHA)",  # arrow must be parenthesised to show only ADHAS transforms
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["beauty"],
    },

    # 15. 1D BISHOP — charade: def→wordplay→assembly (2 independent synonyms)
    {
        "id": "times-29453-1d",
        "clue_text": "See boss bungle work",
        "puzzle_number": "29453",
        "clue_number": "1",
        "direction": "down",
        "answer": "BISHOP",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "BISH"}, {"index": 1, "value": "OP"}]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [2, 3],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["bungle", "work"],
    },

    # 16. 7D AUSPICES — container: def→indicator(container)→outer→inner→assembly
    {
        "id": "times-29453-7d",
        "clue_text": "Summits welcoming American patronage",
        "puzzle_number": "29453",
        "clue_number": "7",
        "direction": "down",
        "answer": "AUSPICES",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [3]},
            {"type": "indicator", "inputMode": "tap_words", "value": [1]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [0]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [2]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "APICES"}, {"index": 1, "value": "US"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [0, 1],
        "is_container": True,
    },

    # 17. 8D HOTHOUSE — container: def→indicator(container)→outer→inner→assembly
    {
        "id": "times-29453-8d",
        "clue_text": "Steamy in here, but you must wear socks",
        "puzzle_number": "29453",
        "clue_number": "8",
        "direction": "down",
        "answer": "HOTHOUSE",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1, 2]},
            {"type": "indicator", "inputMode": "tap_words", "value": [6]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [7]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "HOSE"}, {"index": 1, "value": "THOU"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [4, 5],
        "is_container": True,
    },

    # 18. 9D MADAGASCAR — charade: def→wordplay→assembly (4 independent)
    {
        "id": "times-29453-9d",
        "clue_text": "State coach for Turkish leader who\u2019s out to lunch?",
        "puzzle_number": "29453",
        "clue_number": "9",
        "direction": "down",
        "answer": "MADAGASCAR",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "MAD"},
                 {"index": 1, "value": "AGA"},
                 {"index": 2, "value": "S"},
                 {"index": 3, "value": "CAR"},
             ]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 4,
        "dependent_transform_indices": [],
        "wrong_value_step0": [1, 2],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["lunch", "Turkish", "coach"],
    },

    # 19. 10A SWEET TALK — container with charade inner: def→indicator→outer→inner→assembly
    {
        "id": "times-29453-10a",
        "clue_text": "Flatter track takes very little time",
        "puzzle_number": "29453",
        "clue_number": "10",
        "direction": "across",
        "answer": "SWEET TALK",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [1]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [3, 4, 5]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "STALK"},
                 {"index": 1, "value": "WEE"},
                 {"index": 2, "value": "T"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [],
        "wrong_value_step0": [1, 2],
        "is_container": True,
    },

    # 20. 12A OPTIC — dual indicators + explicit assembly: def→indicator(letter_sel)→indicator(anagram)→assembly
    {
        "id": "times-29453-12a",
        "clue_text": "Concerning sight as head of office IT struggles with PC",
        "puzzle_number": "29453",
        "clue_number": "12",
        "direction": "across",
        "answer": "OPTIC",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [3, 4]},
            {"type": "indicator", "inputMode": "tap_words", "value": [7]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "O"},
                 {"index": 1, "value": "IT"},
                 {"index": 2, "value": "PC"},
                 {"index": 3, "value": "OPTIC"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["letter_selection", "anagram"],
        "assembly_explicit": True,
        "num_assembly_transforms": 4,
        "dependent_transform_indices": [3],
        "wrong_value_step0": [3, 4],
    },

    # 21. 14D DISCIPLINE — reversal chain: def→indicator(reversal)→fodder→assembly
    {
        "id": "times-29453-14d",
        "clue_text": "Photos I had mounted cover the inside of school",
        "puzzle_number": "29453",
        "clue_number": "14",
        "direction": "down",
        "answer": "DISCIPLINE",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [8]},
            {"type": "indicator", "inputMode": "tap_words", "value": [3]},
            {"type": "fodder", "inputMode": "tap_words", "value": [0, 1, 2]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "PICS"},
                 {"index": 1, "value": "ID"},
                 {"index": 2, "value": "DISCIP"},
                 {"index": 3, "value": "LINE"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["reversal"],
        "assembly_explicit": False,
        "num_assembly_transforms": 4,
        "dependent_transform_indices": [2],
        "wrong_value_step0": [0, 1],
        "has_multi_predecessor_chain": True,  # reversal at index 2 consumes PICS(4)+ID(2)=6 letters
        "expected_breakdown_contains": "(PICS + ID \u2192 DISCIP)",  # NOT just (ID → DISCIP)
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["cover"],
    },

    # 22. 15A AMBASSADRESS — charade: def→wordplay→assembly (4 independent)
    {
        "id": "times-29453-15a",
        "clue_text": "Live singer with a costume representative of her country",
        "puzzle_number": "29453",
        "clue_number": "15",
        "direction": "across",
        "answer": "AMBASSADRESS",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [5, 6, 7, 8]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "AM"},
                 {"index": 1, "value": "BASS"},
                 {"index": 2, "value": "A"},
                 {"index": 3, "value": "DRESS"},
             ]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 4,
        "dependent_transform_indices": [],
        "wrong_value_step0": [0, 1],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["Live", "singer", "costume"],
    },

    # 23. 18D FLEETING — charade with reversal: def→indicator(reversal)→assembly
    {
        "id": "times-29453-18d",
        "clue_text": "Fugitive\u2019s attempt to escape upset good egg",
        "puzzle_number": "29453",
        "clue_number": "18",
        "direction": "down",
        "answer": "FLEETING",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "indicator", "inputMode": "tap_words", "value": [4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "FLEE"},
                 {"index": 1, "value": "G"},
                 {"index": 2, "value": "NIT"},
                 {"index": 3, "value": "TING"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["reversal"],
        "assembly_explicit": False,
        "num_assembly_transforms": 4,
        "dependent_transform_indices": [3],
        "wrong_value_step0": [1, 2],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["escape"],
    },

    # 24. 20D DOZENS — container: def→indicator(container)→outer→inner→assembly
    {
        "id": "times-29453-20d",
        "clue_text": "Many academics divided by gender-neutral pronoun",
        "puzzle_number": "29453",
        "clue_number": "20",
        "direction": "down",
        "answer": "DOZENS",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [1]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [4, 5]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "DONS"}, {"index": 1, "value": "ZE"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [1, 2],
        "is_container": True,
    },

    # 25. 21D LOW TAR — charade: def→wordplay→assembly (2 independent)
    {
        "id": "times-29453-21d",
        "clue_text": "Sailor in the doldrums relatively OK for tobacco?",
        "puzzle_number": "29453",
        "clue_number": "21",
        "direction": "down",
        "answer": "LOW TAR",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [4, 5, 6, 7]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "LOW"}, {"index": 1, "value": "TAR"}]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [0, 1],
        "check_clue_word_attribution": True,  # assembly title must show clue words, not just results
        "expected_clue_words_in_breakdown": ["doldrums", "Sailor"],  # each transform's source word
    },

    # 26. 22A ATEMPORAL — charade with anagram: def→indicator(anagram)→assembly (4 transforms)
    {
        "id": "times-29453-22a",
        "clue_text": "Friend taking minute to finish piano exam out of time",
        "puzzle_number": "29453",
        "clue_number": "22",
        "direction": "across",
        "answer": "ATEMPORAL",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [7, 8, 9]},
            {"type": "indicator", "inputMode": "tap_words", "value": [1]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "MATE"},
                 {"index": 1, "value": "ATEM"},
                 {"index": 2, "value": "P"},
                 {"index": 3, "value": "ORAL"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["anagram"],
        "assembly_explicit": False,
        "num_assembly_transforms": 4,
        "dependent_transform_indices": [1],
        "wrong_value_step0": [0, 1],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["piano", "exam"],
    },

    # 27. 24A DUOMO — charade: def→wordplay→assembly (2 independent)
    {
        "id": "times-29453-24a",
        "clue_text": "Couple taken with second sight of Florence?",
        "puzzle_number": "29453",
        "clue_number": "24",
        "direction": "across",
        "answer": "DUOMO",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [4, 5, 6]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "DUO"}, {"index": 1, "value": "MO"}]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [0, 1],
        "check_clue_word_attribution": True,
        "expected_clue_words_in_breakdown": ["Couple", "second"],
    },

    # 28. 26D WAS — deletion chain: def→indicator(deletion)→fodder→assembly
    {
        "id": "times-29453-26d",
        "clue_text": "In Republican\u2019s absence, conflicts happened",
        "puzzle_number": "29453",
        "clue_number": "26",
        "direction": "down",
        "answer": "WAS",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [4]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "fodder", "inputMode": "tap_words", "value": [3]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "WARS"}, {"index": 1, "value": "WAS"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["deletion"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [1],
        "wrong_value_step0": [0, 1],
    },

    # 29. 27A MEGADOSE — anagram: def→indicator(anagram)→fodder→assembly
    {
        "id": "times-29453-27a",
        "clue_text": "See Dogma remade as massive hit",
        "puzzle_number": "29453",
        "clue_number": "27",
        "direction": "across",
        "answer": "MEGADOSE",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [4, 5]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "fodder", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "SEE"},
                 {"index": 1, "value": "DOGMA"},
                 {"index": 2, "value": "MEGADOSE"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["anagram"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],
        "wrong_value_step0": [2, 3],
    },

    # 30. 25A DRIVE — deletion chain: def→indicator(deletion)→fodder→assembly
    {
        "id": "times-29453-25a",
        "clue_text": "Urge removal of line from silly speech",
        "puzzle_number": "29453",
        "clue_number": "25",
        "direction": "across",
        "answer": "DRIVE",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "indicator", "inputMode": "tap_words", "value": [1]},
            {"type": "fodder", "inputMode": "tap_words", "value": [5, 6]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "DRIVEL"},
                 {"index": 1, "value": "DRIVE"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["deletion"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [1],  # deletion at index 1
        "wrong_value_step0": [5, 6],
    },
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api_post(server, path, payload):
    """POST JSON to server, return parsed response and status code."""
    url = f"{server}/trainer{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8"))
        return e.code, body


def start_session(server, clue):
    """Start a training session, return render dict."""
    status, body = api_post(server, "/start", {
        "clue_text": clue["clue_text"],
        "puzzle_number": clue["puzzle_number"],
        "clue_number": clue["clue_number"],
        "direction": clue["direction"],
    })
    if status != 200:
        raise RuntimeError(f"Start failed ({status}): {body}")
    return body


def submit_input(server, clue_id, value, transform_index=None):
    """Submit input for the current step. Returns (correct, render)."""
    payload = {"clue_id": clue_id, "value": value}
    if transform_index is not None:
        payload["transform_index"] = transform_index
    status, body = api_post(server, "/input", payload)
    if status != 200:
        raise RuntimeError(f"Input failed ({status}): {body}")
    return body["correct"], body["render"]


def check_answer(server, clue_id, answer):
    """Check a typed answer. Returns (correct, render)."""
    status, body = api_post(server, "/check-answer", {"clue_id": clue_id, "answer": answer})
    if status != 200:
        raise RuntimeError(f"Check-answer failed ({status}): {body}")
    return body["correct"], body["render"]


def reveal(server, clue_id):
    """Reveal the full answer. Returns render."""
    status, body = api_post(server, "/reveal", {"clue_id": clue_id})
    if status != 200:
        raise RuntimeError(f"Reveal failed ({status}): {body}")
    return body


# ---------------------------------------------------------------------------
# Assembly submission helper
# ---------------------------------------------------------------------------

def submit_assembly_transforms(server, clue_id, transforms, render, answer=None):
    """Submit assembly transforms in order, handling status and auto-completion.

    If all transforms complete but auto-skip doesn't trigger (check phase),
    submits the final assembled result using the answer parameter.

    Returns the final render after all transforms are submitted.
    """
    for t in transforms:
        idx = t["index"]
        val = t["value"]

        # Check current step — if assembly already auto-completed, stop
        if render.get("complete") or render.get("currentStep") is None:
            break
        current = render["currentStep"]
        if current["type"] != "assembly":
            break  # step already advanced past assembly

        # Find this transform's status
        assembly_data = current.get("assemblyData", {})
        transform_list = assembly_data.get("transforms", [])

        # Find the transform entry by index
        t_entry = None
        for te in transform_list:
            if te["index"] == idx:
                t_entry = te
                break

        if t_entry is None:
            raise RuntimeError(f"Transform index {idx} not found in assembly data")

        status = t_entry["status"]
        if status == "completed":
            continue  # auto-superseded
        if status == "locked":
            raise RuntimeError(f"Transform {idx} is locked — test data ordering error")

        correct, render = submit_input(server, clue_id, val, transform_index=idx)
        if not correct:
            raise RuntimeError(f"Transform {idx} value '{val}' rejected as incorrect")

    # If assembly entered check phase (auto-skip didn't fire), submit the full result
    current = render.get("currentStep")
    if current and current["type"] == "assembly":
        assembly_data = current.get("assemblyData", {})
        if assembly_data.get("phase") == "check" and answer:
            correct, render = submit_input(server, clue_id, answer)
            if not correct:
                raise RuntimeError(f"Assembly check phase rejected answer '{answer}'")

    return render


# ---------------------------------------------------------------------------
# Walk to assembly step (submit all steps before assembly)
# ---------------------------------------------------------------------------

def walk_to_assembly(server, clue):
    """Walk through all steps up to (but not including) the assembly step.
    Returns (clue_id, render) with currentStep pointing to assembly.
    """
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            break
        correct, render = submit_input(server, clue_id, step["value"])
        if not correct:
            raise RuntimeError(f"Pre-assembly step {step['type']} failed for {clue['id']}")

    return clue_id, render


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_full_walkthrough(server, clue):
    """Happy path: correct input at every step -> complete."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            render = submit_assembly_transforms(
                server, clue_id, step["transforms"], render, answer=clue["answer"]
            )
        else:
            correct, render = submit_input(server, clue_id, step["value"])
            if not correct:
                return False, f"Step {step['type']} was rejected as incorrect"

    # Verify completion
    if not render.get("complete"):
        return False, f"Expected complete=True, got {render.get('complete')}"
    if not render.get("answerLocked"):
        return False, f"Expected answerLocked=True, got {render.get('answerLocked')}"
    # Answer should be populated
    user_answer = render.get("userAnswer", [])
    if not user_answer:
        return False, "userAnswer is empty after completion"
    answer_str = "".join(user_answer)
    expected = clue["answer"].replace(" ", "")
    if answer_str != expected:
        return False, f"Answer mismatch: got '{answer_str}', expected '{expected}'"

    return True, ""


def test_wrong_input(server, clue):
    """Wrong value at step 0 -> correct=False, step doesn't advance."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    # Get current step index before wrong input
    step_before = render["currentStep"]["index"]

    # Submit wrong value
    correct, render = submit_input(server, clue_id, clue["wrong_value_step0"])

    if correct:
        return False, "Wrong input was accepted as correct"

    step_after = render["currentStep"]["index"]
    if step_after != step_before:
        return False, f"Step advanced from {step_before} to {step_after} on wrong input"

    return True, ""


def test_assembly_transform_status(server, clue):
    """Walk to assembly -> verify all transforms are active (no locking)."""
    clue_id, render = walk_to_assembly(server, clue)

    current = render.get("currentStep")
    if not current or current["type"] != "assembly":
        return False, f"Expected assembly step, got {current.get('type') if current else 'None'}"

    assembly_data = current.get("assemblyData", {})
    transform_list = assembly_data.get("transforms", [])

    if len(transform_list) != clue["num_assembly_transforms"]:
        return False, f"Expected {clue['num_assembly_transforms']} transforms, got {len(transform_list)}"

    for t in transform_list:
        idx = t["index"]
        status = t["status"]
        if status != "active":
            return False, f"Transform {idx} should be 'active', got '{status}'"

    return True, ""


def test_check_answer(server, clue):
    """Wrong answer -> rejected. Correct answer -> locked."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    # Wrong answer
    correct, render = check_answer(server, clue_id, "ZZZZZ")
    if correct:
        return False, "Wrong answer was accepted"
    if render.get("answerLocked"):
        return False, "answerLocked should be False after wrong answer"

    # Correct answer
    correct, render = check_answer(server, clue_id, clue["answer"])
    if not correct:
        return False, f"Correct answer '{clue['answer']}' was rejected"
    if not render.get("answerLocked"):
        return False, "answerLocked should be True after correct answer"

    return True, ""


def test_reveal(server, clue):
    """Reveal -> all steps completed, complete=True, answerLocked=True."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    render = reveal(server, clue_id)

    if not render.get("complete"):
        return False, f"Expected complete=True after reveal, got {render.get('complete')}"
    if not render.get("answerLocked"):
        return False, f"Expected answerLocked=True after reveal, got {render.get('answerLocked')}"

    # All steps should be completed
    steps = render.get("steps", [])
    for s in steps:
        if s["status"] != "completed":
            return False, f"Step {s['index']} ({s['type']}) status='{s['status']}', expected 'completed'"

    return True, ""


def test_template_text(server, clue):
    """Indicator menuTitles contain indicator_type text. Prompts are type-specific."""
    render = start_session(server, clue)

    # Check indicator steps in the step list
    steps = render.get("steps", [])
    indicator_step_idx = 0

    for s in steps:
        if s["type"] == "indicator":
            if indicator_step_idx >= len(clue["indicator_types"]):
                return False, f"More indicator steps than expected indicator_types"

            expected_type = clue["indicator_types"][indicator_step_idx]
            display_type = expected_type.replace("_", " ")

            # menuTitle should contain the indicator type
            title = s.get("title", "")
            if display_type not in title.lower():
                return False, (
                    f"Indicator step title '{title}' does not contain "
                    f"indicator type '{display_type}'"
                )

            indicator_step_idx += 1

    if indicator_step_idx != len(clue["indicator_types"]):
        return False, (
            f"Expected {len(clue['indicator_types'])} indicator steps, "
            f"found {indicator_step_idx}"
        )

    # If no indicator steps expected, verify none are present
    if not clue["has_indicator_steps"]:
        for s in steps:
            if s["type"] == "indicator":
                return False, "Found unexpected indicator step"

    return True, ""


def test_assembly_completion_text(server, clue):
    """Verify assembly completion title shows correct notation for the clue type."""
    if (not clue.get("is_container") and not clue.get("has_anagram_chain")
            and not clue.get("has_multi_predecessor_chain") and not clue.get("check_clue_word_attribution")):
        return True, ""  # skip for clues without specific completion text requirements

    # Walk through entire clue to completion
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            render = submit_assembly_transforms(
                server, clue_id, step["transforms"], render, answer=clue["answer"]
            )
        else:
            correct, render = submit_input(server, clue_id, step["value"])
            if not correct:
                return False, f"Step {step['type']} was rejected"

    if not render.get("complete"):
        return False, "Clue did not complete"

    # Find the assembly step in the completed step list
    assembly_step = None
    for s in render.get("steps", []):
        if s["type"] == "assembly":
            assembly_step = s
            break

    if not assembly_step:
        return False, "No assembly step found in completed steps"

    title = assembly_step.get("title", "")

    if clue.get("is_container"):
        # Container clue: title must NOT be plain "A + B + C + D" concatenation
        transform_results = [t["value"] for t in clue["steps"][-1]["transforms"]]
        plain_concat = " + ".join(transform_results)
        if title == plain_concat:
            return False, (
                f"Assembly completion title is plain concatenation '{title}' — "
                f"should show container insertion, not charade-style joining"
            )

    if clue.get("has_anagram_chain"):
        # Charade with anagram: the final answer must appear after the arrow
        expected = clue["expected_breakdown_contains"]
        if expected not in title:
            return False, (
                f"Assembly completion title '{title}' doesn't contain "
                f"the expected '{expected}' — anagram arrow should "
                f"show the full assembled result, not just the anagram output"
            )

    if clue.get("has_multi_predecessor_chain"):
        # Dependent transform consumes multiple predecessors (e.g. reversal of PICS+ID → DISCIP)
        expected = clue["expected_breakdown_contains"]
        if expected not in title:
            return False, (
                f"Assembly completion title '{title}' doesn't contain "
                f"the expected '{expected}' — dependent transform should "
                f"show ALL consumed predecessors in brackets, not just the immediate one"
            )

    if clue.get("check_clue_word_attribution"):
        # Assembly title must attribute results to their source clue words
        for word in clue["expected_clue_words_in_breakdown"]:
            if word.lower() not in title.lower():
                return False, (
                    f"Assembly completion title '{title}' doesn't mention "
                    f"clue word '{word}' — breakdown should show where each "
                    f"result comes from, not just the results"
                )

    return True, ""


def test_indicator_coverage(server, clue):
    """Verify that dependent transforms (reversal/deletion/anagram) have matching indicator steps.

    If a clue has a reversal, deletion, or anagram transform in the assembly,
    the word indices used by that transform should also appear in a prior
    indicator step — so the student gets to identify the indicator word before
    the assembly.
    """
    import os
    clues_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clues_db.json")
    with open(clues_db_path) as f:
        clues_db = json.load(f)

    training_items = clues_db.get("training_items", clues_db)
    clue_entry = training_items.get(clue["id"])
    if not clue_entry:
        return True, ""  # can't check without metadata

    steps = clue_entry.get("steps", [])
    INDICATOR_TYPES = {"deletion", "reversal", "anagram", "container"}

    # Collect indicator types covered by indicator steps
    # hidden_word indicators also cover reversal (reversed hidden words)
    indicator_types_covered = set()
    for s in steps:
        if s["type"] == "indicator":
            ind_type = s.get("indicator_type", "")
            indicator_types_covered.add(ind_type)
            if ind_type == "hidden_word":
                indicator_types_covered.add("reversal")

    # Check assembly transforms: if a dependent type appears, a matching indicator step should exist
    # Map transform types to their indicator types
    TYPE_TO_INDICATOR = {
        "reversal": "reversal",
        "deletion": "deletion",
        "anagram": "anagram",
        "container": "container",
    }

    for s in steps:
        if s["type"] != "assembly":
            continue
        for t in s.get("transforms", []):
            t_type = t.get("type", "")
            if t_type not in INDICATOR_TYPES:
                continue
            expected_indicator = TYPE_TO_INDICATOR[t_type]
            if expected_indicator not in indicator_types_covered:
                words = clue_entry.get("words", [])
                t_indices = t.get("indices", [])
                t_words = [words[i] for i in t_indices if i < len(words)]
                return False, (
                    f"Assembly has a '{t_type}' transform ('{' '.join(t_words)}') "
                    f"but no indicator step of type '{expected_indicator}' exists — "
                    f"student never gets to identify the indicator word"
                )

    return True, ""


def test_assembly_combined_check(server, clue):
    """Combined check: submit only terminal transforms (as the UI does) -> complete.

    The combined letter display groups inputs by terminal transform index.
    When a dependent transform (reversal/anagram) is submitted, its predecessors
    must be recursively auto-completed so auto-skip can fire.
    """
    assembly_step = None
    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            assembly_step = step
            break
    if not assembly_step:
        return True, ""  # no assembly step

    # Only test clues that have dependent transforms (chains with predecessors)
    if not clue.get("dependent_transform_indices"):
        return True, ""

    clue_id, render = walk_to_assembly(server, clue)

    # Get position map from server to find terminal transforms
    assembly_data = render["currentStep"]["assemblyData"]
    pos_map = assembly_data.get("positionMap", {})

    # Terminal transform indices are the keys in positionMap
    terminal_indices = {int(k) for k in pos_map.keys()}

    # Submit only terminal transforms (what the combined Check button does)
    for t in assembly_step["transforms"]:
        if t["index"] in terminal_indices:
            correct, render = submit_input(server, clue_id, t["value"],
                                           transform_index=t["index"])
            if not correct:
                return False, (
                    f"Terminal transform {t['index']} value '{t['value']}' "
                    f"was rejected"
                )

    # After submitting only terminal transforms, clue should auto-complete
    if not render.get("complete"):
        # Check what's left
        current = render.get("currentStep", {})
        assembly_data = current.get("assemblyData", {})
        transforms = assembly_data.get("transforms", [])
        incomplete = [t for t in transforms if t["status"] != "completed"]
        incomplete_desc = ", ".join(
            f"{t['index']}({t['role']})" for t in incomplete
        )
        return False, (
            f"Expected auto-complete after terminal transforms, "
            f"but these transforms are still incomplete: {incomplete_desc}"
        )

    return True, ""


def test_dependent_prompt_update(server, clue):
    """Dependent transform prompts update when predecessors are solved.

    Before predecessor is solved: generic prompt (no letters shown).
    After predecessor is solved: prompt includes predecessor letters.
    Skips transforms that have per-clue prompt overrides (they bypass templates).
    """
    if not clue.get("dependent_transform_indices"):
        return True, ""  # no dependent transforms

    assembly_step = None
    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            assembly_step = step
            break
    if not assembly_step:
        return True, ""

    clue_id, render = walk_to_assembly(server, clue)

    assembly_data = render["currentStep"]["assemblyData"]
    transforms = assembly_data["transforms"]

    # Find first dependent transform
    dep_idx = clue["dependent_transform_indices"][0]
    dep_transform = None
    for t in transforms:
        if t["index"] == dep_idx:
            dep_transform = t
            break
    if dep_transform is None:
        return False, f"Dependent transform {dep_idx} not found in assembly data"

    initial_prompt = dep_transform["prompt"]

    # Get the predecessor transform's expected result (what should appear in prompt)
    predecessor_value = None
    for t in assembly_step["transforms"]:
        if t["index"] == dep_idx - 1:
            predecessor_value = t["value"]
            break

    # Solve the predecessor(s) for this dependent transform
    for t in assembly_step["transforms"]:
        if t["index"] < dep_idx:
            correct, render = submit_input(server, clue_id, t["value"],
                                           transform_index=t["index"])
            if not correct:
                return False, f"Predecessor transform {t['index']} rejected"

    # Re-check the dependent transform's prompt
    assembly_data = render["currentStep"]["assemblyData"]
    transforms = assembly_data["transforms"]
    for t in transforms:
        if t["index"] == dep_idx:
            dep_transform = t
            break

    updated_prompt = dep_transform["prompt"]

    # If prompt didn't change, check if this is a per-clue override.
    # Template-driven prompts use patterns like "tells you to reverse",
    # "tells you to shorten", "rearrange those letters". If the initial
    # prompt doesn't match these, it's a per-clue override — skip.
    TEMPLATE_MARKERS = ["tells you to reverse", "tells you to shorten",
                        "rearrange those letters",
                        "tells you one piece goes inside another"]
    uses_template = any(m in initial_prompt for m in TEMPLATE_MARKERS)

    if updated_prompt == initial_prompt:
        if not uses_template:
            return True, ""  # per-clue override, skip
        return False, (
            f"Dependent transform {dep_idx} template prompt did not update "
            f"after predecessors solved. Still: '{updated_prompt}'"
        )

    return True, ""


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    ("Full walkthrough", test_full_walkthrough),
    ("Wrong input", test_wrong_input),
    ("Assembly transform status", test_assembly_transform_status),
    ("Check answer", test_check_answer),
    ("Reveal", test_reveal),
    ("Template text", test_template_text),
    ("Assembly completion text", test_assembly_completion_text),
    ("Indicator coverage", test_indicator_coverage),
    ("Assembly combined check", test_assembly_combined_check),
    ("Dependent prompt update", test_dependent_prompt_update),
]


def run_tests(server):
    """Run all tests and print results."""
    passed = 0
    failed = 0
    errors = []

    print(f"=== Trainer Regression Tests ===")
    print(f"Server: {server}")
    print()

    for clue in TEST_CLUES:
        label = f"{clue['clue_number']}{'A' if clue['direction'] == 'across' else 'D'} {clue['answer']}"
        print(f"--- {label} ---")

        for test_name, test_fn in ALL_TESTS:
            full_name = f"{label} - {test_name}"
            try:
                ok, msg = test_fn(server, clue)
                if ok:
                    print(f"  [PASS] {full_name}")
                    passed += 1
                else:
                    print(f"  [FAIL] {full_name}: {msg}")
                    failed += 1
                    errors.append((full_name, msg))
            except Exception as e:
                print(f"  [ERROR] {full_name}: {e}")
                failed += 1
                errors.append((full_name, str(e)))

        print()

    print(f"=== Summary ===")
    print(f"Passed: {passed}/{passed + failed}")
    print(f"Failed: {failed}")

    if errors:
        print()
        print("Failures:")
        for name, msg in errors:
            print(f"  {name}: {msg}")

    return failed == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    server = DEFAULT_SERVER

    # Simple arg parsing (no argparse needed)
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--server" and i < len(sys.argv) - 1:
            server = sys.argv[i + 1]
        elif sys.argv[i - 1] == "--server":
            pass  # already consumed
        elif arg.startswith("--server="):
            server = arg.split("=", 1)[1]

    # Quick connectivity check
    try:
        req = urllib.request.Request(f"{server}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as e:
        print(f"Cannot connect to server at {server}: {e}")
        print("Make sure crossword_server.py is running.")
        sys.exit(1)

    success = run_tests(server)
    sys.exit(0 if success else 1)
