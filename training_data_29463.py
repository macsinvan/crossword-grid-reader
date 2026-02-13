#!/usr/bin/env python3
"""
Training metadata for puzzle 29463 — The Times Cryptic.
Builds and uploads training metadata for all 30 clues.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from puzzle_store_supabase import PuzzleStoreSupabase


def build_all_metadata():
    """Build training metadata for all 30 clues in puzzle 29463."""
    metadata = {}

    # === 1A: CAPUCHIN — "Monkey better run away from roguish child (8)" ===
    # CAP (better) + URCHIN (roguish child) - R (run) = CAPUCHIN
    metadata[("1", "across")] = {
        "words": ["Monkey", "better", "run", "away", "from", "roguish", "child"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "The definition is at the very start — think New World primates"},
            {"type": "indicator", "indices": [3], "indicator_type": "deletion", "hint": "'away' signals removing something from a word"},
            {
                "type": "assembly",
                "result": "CAPUCHIN",
                "transforms": [
                    {"role": "part1", "indices": [1], "type": "synonym", "result": "CAP", "hint": "'To cap' means to surpass or better something"},
                    {"role": "part2", "indices": [5, 6], "type": "synonym", "result": "URCHIN", "hint": "An urchin is a roguish or mischievous child"},
                    {"role": "deletion", "indices": [3], "type": "deletion", "result": "UCHIN", "hint": "Remove R (run — cricket notation) from URCHIN to get UCHIN"}
                ]
            }
        ]
    }

    # === 5A: GAMBIT — "Move doctor taken in carriage (6)" ===
    # MB (doctor) inside GAIT (carriage) = GA(MB)IT
    metadata[("5", "across")] = {
        "words": ["Move", "doctor", "taken", "in", "carriage"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "Think chess — a strategic opening sacrifice"},
            {"type": "indicator", "indices": [2, 3], "indicator_type": "container", "hint": "'taken in' signals one part is placed inside another"},
            {"type": "abbreviation_scan", "indices": [1], "mappings": {"1": "MB"}, "hint": "'Doctor' commonly abbreviates to MB (Medicinae Baccalaureus) in cryptics"},
            {
                "type": "assembly",
                "result": "GAMBIT",
                "transforms": [
                    {"role": "inner", "indices": [1], "type": "abbreviation", "result": "MB", "hint": "MB is a medical degree — one of several abbreviations for 'doctor'"},
                    {"role": "outer", "indices": [4], "type": "synonym", "result": "GAIT", "hint": "'Carriage' as in deportment — how you carry yourself"},
                    {"role": "container", "indices": [2, 3], "type": "container", "result": "GAMBIT", "hint": "MB goes inside GAIT: GA(MB)IT"}
                ]
            }
        ]
    }

    # === 10A: TO THE LIGHTHOUSE — "Eliot's thought muddled about her unfinished work (2,3,10)" ===
    # Anagram of ELIOTS + THOUGHT + HE (HER - R via "unfinished")
    metadata[("10", "across")] = {
        "words": ["Eliot's", "thought", "muddled", "about", "her", "unfinished", "work"],
        "clue_type": "anagram",
        "difficulty": {"definition": "hard", "wordplay": "hard", "overall": "hard"},
        "steps": [
            {"type": "definition", "indices": [6], "hint": "The definition is at the end — a famous Virginia Woolf novel"},
            {"type": "indicator", "indices": [2], "indicator_type": "anagram", "hint": "'muddled' signals the letters need rearranging"},
            {"type": "indicator", "indices": [5], "indicator_type": "deletion", "hint": "'unfinished' signals removing the last letter"},
            {
                "type": "assembly",
                "result": "TO THE LIGHTHOUSE",
                "transforms": [
                    {"role": "part1", "indices": [0], "type": "literal", "result": "ELIOT'S", "hint": "The letters of 'Eliot's' are used as-is — the apostrophe-s gives the S"},
                    {"role": "part2", "indices": [1], "type": "literal", "result": "THOUGHT", "hint": "'thought' provides its letters directly"},
                    {"role": "part3", "indices": [4], "type": "literal", "result": "HER", "hint": "'her' provides the starting letters"},
                    {"role": "deletion", "indices": [5], "type": "deletion", "result": "HE", "hint": "'unfinished' means drop the last letter of HER"},
                    {"role": "anagram", "indices": [2], "type": "anagram", "result": "TO THE LIGHTHOUSE", "hint": "Rearrange ELIOTS + THOUGHT + HE (15 letters) to spell the novel title"}
                ]
            }
        ]
    }

    # === 11A: EPICURE — "Pie cooked with kipper for refined diner (7)" ===
    # PIE* (anagram) + CURE (kipper = to cure)
    metadata[("11", "across")] = {
        "words": ["Pie", "cooked", "with", "kipper", "for", "refined", "diner"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [5, 6], "hint": "Someone with very discerning taste in food and wine"},
            {"type": "indicator", "indices": [1], "indicator_type": "anagram", "hint": "'cooked' signals the letters need rearranging"},
            {
                "type": "assembly",
                "result": "EPICURE",
                "transforms": [
                    {"role": "part1", "indices": [0], "type": "literal", "result": "PIE", "hint": "'Pie' provides the raw letters for the anagram"},
                    {"role": "part1 rearranged", "indices": [1], "type": "anagram", "result": "EPI", "hint": "Rearrange PIE to get EPI"},
                    {"role": "part2", "indices": [3], "type": "synonym", "result": "CURE", "hint": "To kipper fish is to cure it — 'kipper' means cure"}
                ]
            }
        ]
    }

    # === 12A: SEMINAR — "Group discussing reassembled remains (7)" ===
    # Anagram of REMAINS
    metadata[("12", "across")] = {
        "words": ["Group", "discussing", "reassembled", "remains"],
        "clue_type": "anagram",
        "difficulty": {"definition": "easy", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [0, 1], "hint": "A gathering where people discuss a topic together"},
            {"type": "indicator", "indices": [2], "indicator_type": "anagram", "hint": "'reassembled' signals rearranging the letters"},
            {
                "type": "assembly",
                "result": "SEMINAR",
                "transforms": [
                    {"role": "fodder", "indices": [3], "type": "literal", "result": "REMAINS", "hint": "'remains' provides the seven letters to rearrange"},
                    {"role": "anagram", "indices": [2], "type": "anagram", "result": "SEMINAR", "hint": "Rearrange REMAINS to get SEMINAR"}
                ]
            }
        ]
    }

    # === 13A: STRADDLE — "Put pins round seat covering tailor's frame (8)" ===
    # SADDLE (seat) around TR (tailor's frame = first+last letters)
    metadata[("13", "across")] = {
        "words": ["Put", "pins", "round", "seat", "covering", "tailor's", "frame"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0, 1, 2], "hint": "To sit with your legs on either side of something — 'pins' is slang for legs"},
            {"type": "indicator", "indices": [4], "indicator_type": "container", "hint": "'covering' signals one part wraps around another"},
            {"type": "indicator", "indices": [6], "indicator_type": "letter_selection", "hint": "'frame' signals taking the outer letters — first and last"},
            {
                "type": "assembly",
                "result": "STRADDLE",
                "transforms": [
                    {"role": "outer", "indices": [3], "type": "synonym", "result": "SADDLE", "hint": "A saddle is a type of seat"},
                    {"role": "inner", "indices": [5], "type": "synonym", "result": "TR", "hint": "'Frame' means first and last letters of TAILOR → T and R"},
                    {"role": "container", "indices": [4], "type": "container", "result": "STRADDLE", "hint": "Put TR inside SADDLE: S(TR)ADDLE"}
                ]
            }
        ]
    }

    # === 15A: DRIPS — "Ducks mobbing rook in weeds (5)" ===
    # DIPS (ducks) around R (rook)
    metadata[("15", "across")] = {
        "words": ["Ducks", "mobbing", "rook", "in", "weeds"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [4], "hint": "Both 'weeds' and the answer are slang for feeble, dull people"},
            {"type": "indicator", "indices": [1], "indicator_type": "container", "hint": "'mobbing' signals surrounding — one part goes around another"},
            {"type": "abbreviation_scan", "indices": [2], "mappings": {"2": "R"}, "hint": "'Rook' is R in chess notation"},
            {
                "type": "assembly",
                "result": "DRIPS",
                "transforms": [
                    {"role": "outer", "indices": [0], "type": "synonym", "result": "DIPS", "hint": "To duck is to dip — 'ducks' = DIPS"},
                    {"role": "inner", "indices": [2], "type": "abbreviation", "result": "R", "hint": "Rook = R in chess notation"},
                    {"role": "container", "indices": [1], "type": "container", "result": "DRIPS", "hint": "R goes inside DIPS: D(R)IPS"}
                ]
            }
        ]
    }

    # === 18A: ASCOT — "Mum's bed concealing Frenchman's necktie (5)" ===
    # MA'S COT (MASCOT) minus M (Frenchman = Monsieur) = ASCOT
    metadata[("18", "across")] = {
        "words": ["Mum's", "bed", "concealing", "Frenchman's", "necktie"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [4], "hint": "A wide cravat-style neckwear — also a famous racecourse"},
            {"type": "indicator", "indices": [2], "indicator_type": "deletion", "hint": "'concealing' signals a letter is hidden inside and needs removing"},
            {
                "type": "assembly",
                "result": "ASCOT",
                "transforms": [
                    {"role": "part1", "indices": [0, 1], "type": "synonym", "result": "MASCOT", "hint": "Mum's bed = MA'S COT — run together gives MASCOT"},
                    {"role": "deletion", "indices": [2, 3], "type": "deletion", "result": "ASCOT", "hint": "Remove M (Frenchman = Monsieur) from MASCOT to get ASCOT"}
                ]
            }
        ]
    }

    # === 20A: ACERBITY — "Sharpness had effect splitting very fine line (8)" ===
    # ACE (very fine) + R (from railway) + BIT (had effect) + Y (rest of RY)
    # Blog treats as charade: ACE + BIT + RY with BIT splitting the structure
    # Structurally BIT is inserted into ACERY at position 4, but encoded as charade
    metadata[("20", "across")] = {
        "words": ["Sharpness", "had", "effect", "splitting", "very", "fine", "line"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "hard", "overall": "hard"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "A formal word for bitterness or harshness of manner"},
            {"type": "indicator", "indices": [3], "indicator_type": "container", "hint": "'splitting' signals one part is inserted into another"},
            {
                "type": "assembly",
                "result": "ACERBITY",
                "transforms": [
                    {"role": "outer", "indices": [4, 5, 6], "type": "synonym", "result": "ACERY", "hint": "'Very fine' = ACE and 'line' = RY (railway) — combine to get ACERY"},
                    {"role": "inner", "indices": [1, 2], "type": "synonym", "result": "BIT", "hint": "If something 'had effect' you might say it BIT — past tense of bite"},
                    {"role": "container", "indices": [3], "type": "container", "result": "ACERBITY", "hint": "BIT splits ACERY: ACER(BIT)Y = ACERBITY"}
                ]
            }
        ]
    }

    # === 23A: POTTIER — "Backed leading bank as more unstable? (7)" ===
    # TOP reversed + TIER
    metadata[("23", "across")] = {
        "words": ["Backed", "leading", "bank", "as", "more", "unstable?"],
        "clue_type": "standard",
        "difficulty": {"definition": "hard", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [4, 5], "hint": "The comparative form of a slang word for crazy — 'more unstable' is the definition"},
            {"type": "indicator", "indices": [0], "indicator_type": "reversal", "hint": "'Backed' signals reading a word backwards"},
            {
                "type": "assembly",
                "result": "POTTIER",
                "transforms": [
                    {"role": "part1", "indices": [1], "type": "synonym", "result": "TOP", "hint": "'Leading' = TOP — as in the top or leading position"},
                    {"role": "part1 reversed", "indices": [0], "type": "reversal", "result": "POT", "hint": "Reverse TOP to get POT"},
                    {"role": "part2", "indices": [2], "type": "synonym", "result": "TIER", "hint": "'Bank' = TIER — as in a bank or tier of seats"}
                ]
            }
        ]
    }

    # === 25A: SPLURGE — "Records reflecting desire to spend heavily (7)" ===
    # LPS reversed + URGE
    metadata[("25", "across")] = {
        "words": ["Records", "refiecting", "desire", "to", "spend", "heavily"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [3, 4, 5], "hint": "To spend lavishly or extravagantly on something"},
            {"type": "indicator", "indices": [1], "indicator_type": "reversal", "hint": "'reflecting' signals reading letters backwards"},
            {
                "type": "assembly",
                "result": "SPLURGE",
                "transforms": [
                    {"role": "part1", "indices": [0], "type": "synonym", "result": "LPS", "hint": "Records = LPs — vinyl long-playing records"},
                    {"role": "part1 reversed", "indices": [1], "type": "reversal", "result": "SPL", "hint": "Reverse LPS to get SPL"},
                    {"role": "part2", "indices": [2], "type": "synonym", "result": "URGE", "hint": "'Desire' = URGE"}
                ]
            }
        ]
    }

    # === 26A: POCKET BILLIARDS — "Little evil one in poet's pool (6,9)" ===
    # POCKET (little) + ILL+I inside BARDS
    metadata[("26", "across")] = {
        "words": ["Little", "evil", "one", "in", "poet's", "pool"],
        "clue_type": "standard",
        "difficulty": {"definition": "hard", "wordplay": "hard", "overall": "hard"},
        "steps": [
            {"type": "definition", "indices": [5], "hint": "Another name for the cue sport played on a table with pockets"},
            {"type": "indicator", "indices": [3], "indicator_type": "container", "hint": "'in' signals one part goes inside another"},
            {"type": "abbreviation_scan", "indices": [2], "mappings": {"2": "I"}, "hint": "'One' = I — one of the most common cryptic abbreviations"},
            {
                "type": "assembly",
                "result": "POCKET BILLIARDS",
                "transforms": [
                    {"role": "part1", "indices": [0], "type": "synonym", "result": "POCKET", "hint": "'Little' = POCKET — as in pocket-sized"},
                    {"role": "inner_a", "indices": [1], "type": "synonym", "result": "ILL", "hint": "'Evil' = ILL"},
                    {"role": "inner_b", "indices": [2], "type": "abbreviation", "result": "I", "hint": "'One' = I"},
                    {"role": "outer", "indices": [4], "type": "synonym", "result": "BARDS", "hint": "Poets = BARDS — Shakespeare was the Bard"},
                    {"role": "container", "indices": [3], "type": "container", "result": "BILLIARDS", "hint": "ILL+I goes inside BARDS: B(ILLI)ARDS = BILLIARDS"}
                ]
            }
        ]
    }

    # === 27A: ROTTER — "River creature found by water rat (6)" ===
    # R (river) + OTTER
    metadata[("27", "across")] = {
        "words": ["River", "creature", "found", "by", "water", "rat"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [5], "hint": "Slang for a contemptible person — same meaning as 'rat'"},
            {"type": "wordplay_type", "expected": "Charade", "options": ["Charade", "Container", "Anagram", "Hidden word"], "hint": "No indicator words — the parts just join end to end. That's a charade."},
            {"type": "abbreviation_scan", "indices": [0], "mappings": {"0": "R"}, "hint": "'River' is a standard abbreviation for R in cryptics"},
            {
                "type": "assembly",
                "result": "ROTTER",
                "transforms": [
                    {"role": "part1", "indices": [0], "type": "abbreviation", "result": "R", "hint": "River = R — one of the most common cryptic abbreviations"},
                    {"role": "part2", "indices": [1, 2, 3, 4], "type": "synonym", "result": "OTTER", "hint": "An otter is a creature found by water"}
                ]
            }
        ]
    }

    # === 28A: BEWILDER — "Live with increasingly savage fox (8)" ===
    # BE (live) + WILDER (increasingly savage)
    metadata[("28", "across")] = {
        "words": ["Live", "with", "increasingly", "savage", "fox"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [4], "hint": "'To fox' means to confuse or puzzle someone"},
            {"type": "wordplay_type", "expected": "Charade", "options": ["Charade", "Container", "Anagram", "Hidden word"], "hint": "No indicator words here — the parts simply join end to end."},
            {
                "type": "assembly",
                "result": "BEWILDER",
                "transforms": [
                    {"role": "part1", "indices": [0], "type": "synonym", "result": "BE", "hint": "'Live' = BE — to live is to be"},
                    {"role": "part2", "indices": [2, 3], "type": "synonym", "result": "WILDER", "hint": "'Increasingly savage' = WILDER — the comparative form of wild"}
                ]
            }
        ]
    }

    # === 1D: CUTTER — "Small boat first to capsize say (6)" ===
    # C (first of capsize) + UTTER (say)
    metadata[("1", "down")] = {
        "words": ["Small", "boat", "first", "to", "capsize", "say"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [0, 1], "hint": "A type of small sailing vessel — used by the navy and coastguard"},
            {"type": "indicator", "indices": [2], "indicator_type": "letter_selection", "hint": "'first' signals taking the first letter"},
            {
                "type": "assembly",
                "result": "CUTTER",
                "transforms": [
                    {"role": "part1", "indices": [4], "type": "letter_selection", "result": "C", "hint": "'First to capsize' = C — the first letter of 'capsize'"},
                    {"role": "part2", "indices": [5], "type": "synonym", "result": "UTTER", "hint": "'Say' = UTTER — to say is to utter"}
                ]
            }
        ]
    }

    # === 2D: PATRIOTIC — "Loyal Irishman in charge containing insurrection (9)" ===
    # PAT (Irishman) + RIOT (insurrection) + IC (in charge) = PAT-RIOT-IC
    # Blog: "PAT + IC around RIOT" — but letter mechanics are simple charade PAT+RIOT+IC
    # "containing" is part of the surface reading, not a structural container
    metadata[("2", "down")] = {
        "words": ["Loyal", "Irishman", "in", "charge", "containing", "insurrection"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "Devoted to one's country — a single word meaning 'loyal'"},
            {"type": "wordplay_type", "expected": "Charade", "options": ["Charade", "Container", "Anagram", "Hidden word"], "hint": "The parts join end to end: PAT-RIOT-IC. 'Containing' is part of the surface reading — the actual mechanism is a charade."},
            {"type": "abbreviation_scan", "indices": [2, 3], "mappings": {"2": "IC"}, "hint": "'In charge' = IC — a standard abbreviation"},
            {
                "type": "assembly",
                "result": "PATRIOTIC",
                "transforms": [
                    {"role": "part1", "indices": [1], "type": "synonym", "result": "PAT", "hint": "Pat is a stereotypical Irish name — 'Irishman' = PAT"},
                    {"role": "part2", "indices": [5], "type": "synonym", "result": "RIOT", "hint": "An insurrection is a riot or uprising"},
                    {"role": "part3", "indices": [2, 3], "type": "abbreviation", "result": "IC", "hint": "'In charge' = IC — a standard abbreviation"}
                ]
            }
        ]
    }

    # === 3D: CAESURA — "Pause revolutionary scheme air industry group adopts (7)" ===
    # CAA around reversal of RUSE = CA(ESUR)A
    metadata[("3", "down")] = {
        "words": ["Pause", "revolutionary", "scheme", "air", "industry", "group", "adopts"],
        "clue_type": "standard",
        "difficulty": {"definition": "hard", "wordplay": "hard", "overall": "hard"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "A technical term for a pause or break in verse — from poetry and music"},
            {"type": "indicator", "indices": [1], "indicator_type": "reversal", "hint": "'revolutionary' signals reading letters backwards"},
            {"type": "indicator", "indices": [6], "indicator_type": "container", "hint": "'adopts' signals one part takes in another"},
            {
                "type": "assembly",
                "result": "CAESURA",
                "transforms": [
                    {"role": "inner", "indices": [2], "type": "synonym", "result": "RUSE", "hint": "A scheme is a ruse — a cunning plan"},
                    {"role": "inner_r", "indices": [1], "type": "reversal", "result": "ESUR", "hint": "Reverse RUSE to get ESUR"},
                    {"role": "outer", "indices": [3, 4, 5], "type": "synonym", "result": "CAA", "hint": "The air industry group is the CAA — Civil Aviation Authority"},
                    {"role": "container", "indices": [6], "type": "container", "result": "CAESURA", "hint": "ESUR goes inside CAA: CA(ESUR)A = CAESURA"}
                ]
            }
        ]
    }

    # === 4D: IMIDE — "Compound that is entered by unlit turning (5)" ===
    # IE (that is) around DIM reversed (MID)
    metadata[("4", "down")] = {
        "words": ["Compound", "that", "is", "entered", "by", "unlit", "turning"],
        "clue_type": "standard",
        "difficulty": {"definition": "hard", "wordplay": "medium", "overall": "hard"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "A type of chemical compound — the definition is just the first word"},
            {"type": "indicator", "indices": [3, 4], "indicator_type": "container", "hint": "'entered by' signals one part goes inside another"},
            {"type": "indicator", "indices": [6], "indicator_type": "reversal", "hint": "'turning' signals reading letters backwards"},
            {
                "type": "assembly",
                "result": "IMIDE",
                "transforms": [
                    {"role": "outer", "indices": [1, 2], "type": "abbreviation", "result": "IE", "hint": "'That is' = IE — the Latin abbreviation 'id est'"},
                    {"role": "inner", "indices": [5], "type": "synonym", "result": "DIM", "hint": "'Unlit' = DIM — not bright"},
                    {"role": "inner_r", "indices": [6], "type": "reversal", "result": "MID", "hint": "Reverse DIM to get MID"},
                    {"role": "container", "indices": [3, 4], "type": "container", "result": "IMIDE", "hint": "MID goes inside IE: I(MID)E = IMIDE"}
                ]
            }
        ]
    }

    # === 6D: ASHAMED — "Embarrassed where no professional leader at News? (7)" ===
    # AS (where) + HAM (no professional) + ED (leader at News)
    metadata[("6", "down")] = {
        "words": ["Embarrassed", "where", "no", "professional", "leader", "at", "News?"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "Feeling shame — the definition is the first word"},
            {"type": "wordplay_type", "expected": "Charade", "options": ["Charade", "Container", "Anagram", "Hidden word"], "hint": "No indicator words — the parts join end to end in a charade."},
            {
                "type": "assembly",
                "result": "ASHAMED",
                "transforms": [
                    {"role": "part1", "indices": [1], "type": "synonym", "result": "AS", "hint": "In cryptics, 'where' can mean AS — as in 'where' you might say 'as'"},
                    {"role": "part2", "indices": [2, 3], "type": "synonym", "result": "HAM", "hint": "A ham is an amateur — 'no professional' points to HAM"},
                    {"role": "part3", "indices": [4, 5, 6], "type": "synonym", "result": "ED", "hint": "'Leader at News' = ED — an editor leads a newspaper"}
                ]
            }
        ]
    }

    # === 7D: BRUIN — "Bear, black one shut inside chicken enclosure (5)" ===
    # B (black) + I (one) inside RUN (chicken enclosure) = B + RUIN
    metadata[("7", "down")] = {
        "words": ["Bear,", "black", "one", "shut", "inside", "chicken", "enclosure"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "A traditional literary name for this animal — from Reynard the Fox"},
            {"type": "indicator", "indices": [4], "indicator_type": "container", "hint": "'inside' signals one part goes inside another"},
            {"type": "abbreviation_scan", "indices": [1, 2], "mappings": {"1": "B", "2": "I"}, "hint": "'Black' = B (from pencil grades) and 'one' = I"},
            {
                "type": "assembly",
                "result": "BRUIN",
                "transforms": [
                    {"role": "part1", "indices": [1], "type": "abbreviation", "result": "B", "hint": "Black = B — as in pencil grades"},
                    {"role": "inner", "indices": [2], "type": "abbreviation", "result": "I", "hint": "One = I — standard cryptic abbreviation"},
                    {"role": "outer", "indices": [5, 6], "type": "synonym", "result": "RUN", "hint": "A chicken enclosure is a run — where chickens roam"},
                    {"role": "container", "indices": [4], "type": "container", "result": "RUIN", "hint": "I goes inside RUN: RU(I)N = RUIN"}
                ]
            }
        ]
    }

    # === 8D: THEORIST — "Gold secured by one believing speculator (8)" ===
    # OR (gold) inside THEIST (one believing)
    metadata[("8", "down")] = {
        "words": ["Gold", "secured", "by", "one", "believing", "speculator"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [5], "hint": "Someone who speculates or forms ideas — a thinker"},
            {"type": "indicator", "indices": [1, 2], "indicator_type": "container", "hint": "'secured by' signals one part is held inside another"},
            {"type": "abbreviation_scan", "indices": [0], "mappings": {"0": "OR"}, "hint": "'Gold' = OR — from the heraldic term"},
            {
                "type": "assembly",
                "result": "THEORIST",
                "transforms": [
                    {"role": "inner", "indices": [0], "type": "abbreviation", "result": "OR", "hint": "Gold = OR — the heraldic term for gold (French 'or')"},
                    {"role": "outer", "indices": [3, 4], "type": "synonym", "result": "THEIST", "hint": "One who believes = a THEIST — someone with religious belief"},
                    {"role": "container", "indices": [1, 2], "type": "container", "result": "THEORIST", "hint": "OR goes inside THEIST: THE(OR)IST"}
                ]
            }
        ]
    }

    # === 9D: PHOSGENE — "Henry wears tight nose peg in lethal gas (8)" ===
    # H (Henry) inside anagram of NOSEPEG
    metadata[("9", "down")] = {
        "words": ["Henry", "wears", "tight", "nose", "peg", "in", "lethal", "gas"],
        "clue_type": "standard",
        "difficulty": {"definition": "hard", "wordplay": "hard", "overall": "hard"},
        "steps": [
            {"type": "definition", "indices": [6, 7], "hint": "A chemical weapon used in WWI — the definition is the last two words"},
            {"type": "indicator", "indices": [2], "indicator_type": "anagram", "hint": "'tight' signals an anagram — think of being 'tight' as disorderly"},
            {"type": "indicator", "indices": [1], "indicator_type": "container", "hint": "'wears' signals something goes around — Henry wears the rearranged letters"},
            {"type": "abbreviation_scan", "indices": [0], "mappings": {"0": "H"}, "hint": "'Henry' = H — a standard abbreviation"},
            {
                "type": "assembly",
                "result": "PHOSGENE",
                "transforms": [
                    {"role": "inner", "indices": [0], "type": "abbreviation", "result": "H", "hint": "Henry = H"},
                    {"role": "part2", "indices": [3, 4], "type": "literal", "result": "NOSEPEG", "hint": "'nose peg' provides the raw letters for anagramming"},
                    {"role": "outer", "indices": [2], "type": "anagram", "result": "POSGENE", "hint": "Rearrange NOSEPEG to get POSGENE"},
                    {"role": "container", "indices": [1], "type": "container", "result": "PHOSGENE", "hint": "H wears POSGENE: P(H)OSGENE = PHOSGENE"}
                ]
            }
        ]
    }

    # === 14D: DIATRIBE — "Harangue from district attorney about island race (8)" ===
    # DA around I + TRIBE
    metadata[("14", "down")] = {
        "words": ["Harangue", "from", "district", "attorney", "about", "island", "race"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "A forceful and bitter verbal attack — the definition is the first word"},
            {"type": "indicator", "indices": [4], "indicator_type": "container", "hint": "'about' signals one part wraps around another"},
            {"type": "abbreviation_scan", "indices": [5], "mappings": {"5": "I"}, "hint": "'Island' = I — a standard abbreviation"},
            {
                "type": "assembly",
                "result": "DIATRIBE",
                "transforms": [
                    {"role": "outer", "indices": [2, 3], "type": "abbreviation", "result": "DA", "hint": "'District attorney' = DA — a common abbreviation"},
                    {"role": "inner", "indices": [5], "type": "abbreviation", "result": "I", "hint": "Island = I"},
                    {"role": "container", "indices": [4], "type": "container", "result": "DIA", "hint": "I goes inside DA: D(I)A = DIA"},
                    {"role": "part3", "indices": [6], "type": "synonym", "result": "TRIBE", "hint": "A race or people = a TRIBE"}
                ]
            }
        ]
    }

    # === 16D: INTERBRED — "Crossed Bury, picked up money (9)" ===
    # INTER (bury) + BRED (homophone of BREAD = money)
    metadata[("16", "down")] = {
        "words": ["Crossed", "Bury,", "picked", "up", "money"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "To have bred between different types — the definition is the first word"},
            {"type": "indicator", "indices": [2, 3], "indicator_type": "homophone", "hint": "'picked up' signals a word that sounds like another when heard"},
            {
                "type": "assembly",
                "result": "INTERBRED",
                "transforms": [
                    {"role": "part1", "indices": [1], "type": "synonym", "result": "INTER", "hint": "To bury is to inter — to lay to rest"},
                    {"role": "part2", "indices": [4], "type": "synonym", "result": "BREAD", "hint": "'Money' = BREAD — slang for money"},
                    {"role": "homophone", "indices": [2, 3], "type": "homophone", "result": "BRED", "hint": "'picked up' tells us BREAD sounds like BRED"}
                ]
            }
        ]
    }

    # === 17D: BAGPIPER — "Musician's grand spot close to audience in pub (8)" ===
    # G (grand) + PIP (spot) + E (last of audience) inside BAR (pub)
    metadata[("17", "down")] = {
        "words": ["Musician's", "grand", "spot", "close", "to", "audience", "in", "pub"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "hard", "overall": "hard"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "The definition is just the first word — what kind of performer?"},
            {"type": "indicator", "indices": [6], "indicator_type": "container", "hint": "'in' signals the inner parts go inside the outer part"},
            {"type": "indicator", "indices": [3, 4], "indicator_type": "letter_selection", "hint": "'close to' signals taking the last letter"},
            {"type": "abbreviation_scan", "indices": [1], "mappings": {"1": "G"}, "hint": "'Grand' = G — as in a grand (£1000)"},
            {
                "type": "assembly",
                "result": "BAGPIPER",
                "transforms": [
                    {"role": "inner_a", "indices": [1], "type": "abbreviation", "result": "G", "hint": "Grand = G — slang for a thousand"},
                    {"role": "inner_b", "indices": [2], "type": "synonym", "result": "PIP", "hint": "'Spot' = PIP — a pip is a spot on a card or die"},
                    {"role": "inner_c", "indices": [5], "type": "letter_selection", "result": "E", "hint": "'Close to audience' = E — the last letter of 'audience'"},
                    {"role": "outer", "indices": [7], "type": "synonym", "result": "BAR", "hint": "'Pub' = BAR"},
                    {"role": "container", "indices": [6], "type": "container", "result": "BAGPIPER", "hint": "G+PIP+E goes inside BAR: BA(GPIPE)R = BAGPIPER"}
                ]
            }
        ]
    }

    # === 19D: TRIREME — "Galley test sheets read aloud (7)" ===
    # Homophone of TRY + REAM
    metadata[("19", "down")] = {
        "words": ["Galley", "test", "sheets", "read", "aloud"],
        "clue_type": "standard",
        "difficulty": {"definition": "hard", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "An ancient warship with three banks of oars — the definition is the first word"},
            {"type": "indicator", "indices": [3, 4], "indicator_type": "homophone", "hint": "'read aloud' signals the answer sounds like other words"},
            {
                "type": "assembly",
                "result": "TRIREME",
                "transforms": [
                    {"role": "part1", "indices": [1], "type": "synonym", "result": "TRY", "hint": "A test = a try — to test is to try"},
                    {"role": "part2", "indices": [2], "type": "synonym", "result": "REAM", "hint": "Sheets = a ream — 500 sheets of paper"},
                    {"role": "homophone", "indices": [3, 4], "type": "homophone", "result": "TRIREME", "hint": "TRY + REAM read aloud sounds like TRIREME"}
                ]
            }
        ]
    }

    # === 21D: BELLINI — "The Spanish tucked into pancake and mixed drink (7)" ===
    # EL (the Spanish) inside BLINI (pancake)
    metadata[("21", "down")] = {
        "words": ["The", "Spanish", "tucked", "into", "pancake", "and", "mixed", "drink"],
        "clue_type": "standard",
        "difficulty": {"definition": "medium", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [6, 7], "hint": "A cocktail made with prosecco and peach juice, created in Venice"},
            {"type": "indicator", "indices": [2, 3], "indicator_type": "container", "hint": "'tucked into' signals one part goes inside another"},
            {
                "type": "assembly",
                "result": "BELLINI",
                "transforms": [
                    {"role": "inner", "indices": [0, 1], "type": "synonym", "result": "EL", "hint": "'The' in Spanish = EL — basic foreign language knowledge"},
                    {"role": "outer", "indices": [4], "type": "synonym", "result": "BLINI", "hint": "A blini is a type of Russian pancake"},
                    {"role": "container", "indices": [2, 3], "type": "container", "result": "BELLINI", "hint": "EL goes inside BLINI: B(EL)LINI = BELLINI"}
                ]
            }
        ]
    }

    # === 22D: TEASER — "Tricky question from trustee involving labour shortage (6)" ===
    # EASE (labour shortage) inside TR (trustee)
    metadata[("22", "down")] = {
        "words": ["Tricky", "question", "from", "trustee", "involving", "labour", "shortage"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "medium", "overall": "medium"},
        "steps": [
            {"type": "definition", "indices": [0, 1], "hint": "A brain-puzzler — something tricky to work out"},
            {"type": "indicator", "indices": [4], "indicator_type": "container", "hint": "'involving' signals one part contains another"},
            {
                "type": "assembly",
                "result": "TEASER",
                "transforms": [
                    {"role": "outer", "indices": [3], "type": "abbreviation", "result": "TR", "hint": "'Trustee' = TR — a standard abbreviation"},
                    {"role": "inner", "indices": [5, 6], "type": "synonym", "result": "EASE", "hint": "'Labour shortage' = EASE — not labouring means being at ease"},
                    {"role": "container", "indices": [4], "type": "container", "result": "TEASER", "hint": "EASE goes inside TR: T(EASE)R = TEASER"}
                ]
            }
        ]
    }

    # === 24D: TACIT — "Silent, songbird's caught a cold (5)" ===
    # TIT (songbird) around A + C (cold)
    metadata[("24", "down")] = {
        "words": ["Silent,", "songbird's", "caught", "a", "cold"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [0], "hint": "Understood without being spoken — implied rather than stated"},
            {"type": "indicator", "indices": [2], "indicator_type": "container", "hint": "'caught' signals one part is trapped inside another"},
            {"type": "abbreviation_scan", "indices": [4], "mappings": {"4": "C"}, "hint": "'Cold' = C — a standard abbreviation"},
            {
                "type": "assembly",
                "result": "TACIT",
                "transforms": [
                    {"role": "outer", "indices": [1], "type": "synonym", "result": "TIT", "hint": "A songbird = TIT — blue tit, great tit, etc."},
                    {"role": "inner_a", "indices": [3], "type": "literal", "result": "A", "hint": "'a' is used as-is — the letter A"},
                    {"role": "inner_b", "indices": [4], "type": "abbreviation", "result": "C", "hint": "Cold = C"},
                    {"role": "container", "indices": [2], "type": "container", "result": "TACIT", "hint": "A+C goes inside TIT: T(AC)IT = TACIT"}
                ]
            }
        ]
    }

    # === 25D: SOLVE — "One divided by five — find an answer (5)" ===
    # SOLE (one) around V (five)
    metadata[("25", "down")] = {
        "words": ["One", "divided", "by", "five", "\u2014", "find", "an", "answer"],
        "clue_type": "standard",
        "difficulty": {"definition": "easy", "wordplay": "easy", "overall": "easy"},
        "steps": [
            {"type": "definition", "indices": [5, 6, 7], "hint": "The definition is at the end — to work something out"},
            {"type": "indicator", "indices": [1, 2], "indicator_type": "container", "hint": "'divided by' signals one part splits another"},
            {"type": "abbreviation_scan", "indices": [3], "mappings": {"3": "V"}, "hint": "'Five' = V — the Roman numeral"},
            {
                "type": "assembly",
                "result": "SOLVE",
                "transforms": [
                    {"role": "outer", "indices": [0], "type": "synonym", "result": "SOLE", "hint": "'One' = SOLE — sole means only or single"},
                    {"role": "inner", "indices": [3], "type": "abbreviation", "result": "V", "hint": "Five = V in Roman numerals"},
                    {"role": "container", "indices": [1, 2], "type": "container", "result": "SOLVE", "hint": "V divides SOLE: SOL(V)E = SOLVE"}
                ]
            }
        ]
    }

    return metadata


def upload_metadata(metadata):
    """Upload training metadata to Supabase."""
    store = PuzzleStoreSupabase()

    pub = store.client.table('publications').select('id').eq('name', 'The Times').execute()
    pub_id = pub.data[0]['id']
    puzzle = store.client.table('puzzles').select('id').eq('publication_id', pub_id).eq('puzzle_number', '29463').execute()
    puzzle_id = puzzle.data[0]['id']

    # Check lock
    lock_check = store.client.table('puzzles').select('training_locked').eq('id', puzzle_id).execute()
    if lock_check.data and lock_check.data[0].get('training_locked'):
        print("ERROR: Puzzle 29463 is locked! Cannot upload.")
        sys.exit(1)

    count = 0
    for (number, direction), data in sorted(metadata.items(), key=lambda x: (x[0][1], int(x[0][0]))):
        result = store.client.table('clues').update({
            'training_metadata': data
        }).eq('puzzle_id', puzzle_id).eq('number', int(number)).eq('direction', direction).execute()

        label = f"{number}{'A' if direction == 'across' else 'D'}"
        if result.data:
            count += 1
            print(f"  \u2713 {label}: {data.get('steps', [{}])[-1].get('result', '?')}")
        else:
            print(f"  \u2717 {label}: NO MATCH")

    print(f"\nUploaded {count}/{len(metadata)} clues")


if __name__ == '__main__':
    print("Building training metadata for puzzle 29463...")
    metadata = build_all_metadata()
    print(f"Built metadata for {len(metadata)} clues\n")

    if '--dry-run' in sys.argv:
        print("DRY RUN - not uploading")
        for (number, direction), data in sorted(metadata.items(), key=lambda x: (x[0][1], int(x[0][0]))):
            label = f"{number}{'A' if direction == 'across' else 'D'}"
            steps = [s['type'] for s in data.get('steps', [])]
            print(f"  {label}: {data.get('clue_type')} — {steps}")
    else:
        print("Uploading to Supabase...")
        upload_metadata(metadata)
        print("\nDone!")
