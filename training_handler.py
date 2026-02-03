"""
Training Handler - Interactive Teaching System for Grid Reader
=============================================================

Ported from cryptic-trainer. Provides step-by-step guided solving
for cryptic crossword clues using pre-annotated step data.

Architecture:
- RAW STEP DATA: Loaded from clues_db.json (pre-annotated)
- STEP TEMPLATES: Generic phases for each step type (90% reusable)
- DECORATION: get_render() merges step + template → UI render object

Step Types: standard_definition, abbreviation, synonym, literal,
literal_phrase, anagram, reversal, deletion, letter_selection,
hidden, container_verify, charade_verify, double_definition

API (called from crossword_server.py):
- start_session(clue_id, clue) - Initialize training session
- get_render(clue_id, clue) - Get current UI state
- handle_input(clue_id, clue, value) - Process user input
- handle_continue(clue_id, clue) - Advance to next phase
"""

import re
import json
import os

# =============================================================================
# TEACHING HINTS - Loaded from teaching_hints.json
# =============================================================================

TEACHING_HINTS = {}

def _load_teaching_hints():
    """Load teaching hints from JSON file."""
    global TEACHING_HINTS
    hints_path = os.path.join(os.path.dirname(__file__), "teaching_hints.json")
    try:
        with open(hints_path, "r") as f:
            TEACHING_HINTS = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load teaching_hints.json: {e}")
        TEACHING_HINTS = {"abbreviations": {}, "synonyms": {}, "indicators": {}, "patterns": {}}

# Load hints on module import
_load_teaching_hints()

def get_teaching_hint(category: str, key: str, fallback: str = "") -> str:
    """
    Look up a teaching hint by category and key.

    Args:
        category: One of 'abbreviations', 'synonyms', 'indicators', 'patterns'
        key: The word/phrase to look up (case-insensitive)
        fallback: Value to return if not found

    Returns:
        The hint text, or fallback if not found
    """
    hints = TEACHING_HINTS.get(category, {})
    # Try exact match first, then lowercase
    return hints.get(key, hints.get(key.lower(), fallback))

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_enumeration(enum_str):
    """Parse enumeration like '3-4' or '10' to total letter count."""
    numbers = re.findall(r'\d+', str(enum_str))
    return sum(int(n) for n in numbers) if numbers else 0

# =============================================================================
# STEP TEMPLATES
# =============================================================================

STEP_TEMPLATES = {
    "clue_type_identify": {
        "phases": [
            {
                "id": "choose",
                "actionPrompt": "Select clue type",
                "intro": {
                    "title": "First, identify the clue type",
                    "text": "Before diving in, take a moment to scan the clue structure:\n\n• See instruction words (rearranged, inside, about, sounds like)? → Standard clue\n• Clear definition at start or end with wordplay in the rest? → Standard clue\n• Short clue with no instruction words? → Probably a double definition\n• One playful description with no clear split? → Cryptic definition\n• Every word serves both meaning AND wordplay? → &lit (rare!)"
                },
                "panel": {
                    "title": "WHAT TYPE OF CLUE IS THIS?",
                    "instruction": "Based on the structure, what type of clue do you think this is?"
                },
                "inputMode": "multiple_choice",
                "onCorrect": {"message": "Good eye! Recognizing clue types helps you choose the right solving approach."},
                "onWrong": {"message": "Not quite — look again at the clue structure. Are there instruction words? Is there a clear definition?"}
            }
        ]
    },

    "standard_definition": {
        "phases": [
            {
                "id": "select",
                "actionPrompt": "Tap the definition words",
                "intro": {
                    "title": "Find the Definition",
                    "text": "Every standard cryptic clue has a 'straight' definition — a normal dictionary meaning of the answer.\n\nKey insight: The definition is ALWAYS at the very start OR the very end of the clue. Never in the middle!",
                    "example": "Ignore the misleading surface story. Focus on the start and end — which phrase could define a word?"
                },
                "panel": {
                    "title": "FIND THE DEFINITION",
                    "instruction": "Tap the definition words. Remember: it's always at the start or end of the clue."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "GREEN", "role": "definition"}},
                "onWrong": {"message": "Hint: The definition is always at the very start OR very end — never in the middle."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "DEFINITION FOUND: {definition_text}",
                    "instruction": "Good! The definition, '{definition_text}', is at the {position} of the clue."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
            # Note: "solve" phase added dynamically when recommendedApproach == "definition"
        ]
    },

    "wordplay_overview": {
        # Phases are generated dynamically based on common_vocabulary count
        "phases": []  # Placeholder - built dynamically
    },

    "deletion_discover": {
        # Phases are generated dynamically to build multiple choice options
        "phases": []  # Placeholder - built dynamically by build_deletion_discover_phases
    },

    "container_verify": {
        "phases": [
            {
                "id": "order",
                "actionPrompt": "Select which piece goes inside which",
                "panel": {
                    "title": "CONTAINER ORDER",
                    "instruction": "You have two pieces: {inner} and {outer}. '{indicator}' tells us one goes inside the other. To make {answer}, which arrangement works?"
                },
                "inputMode": "multiple_choice",
                "onCorrect": {"message": "That's right! Container indicators tell you the structure."},
                "onWrong": {"message": "Hint: Look at {answer} — where does {inner} appear? Is it surrounded by letters, or does it surround them?"}
            },
            {
                "id": "teaching",
                "actionPrompt": "Complete training",
                "panel": {
                    "title": "VERIFIED!",
                    "instruction": "{outer_split} = {result} ✓ Your hypothesis is confirmed by the wordplay!"
                },
                "inputMode": "none",
                "button": {"label": "Complete →", "action": "complete"}
            }
        ]
    },

    "charade_verify": {
        "phases": [
            {
                "id": "result",
                "actionPrompt": "Type the combined result",
                "panel": {
                    "title": "COMBINE YOUR PIECES",
                    "instruction": "You've gathered these pieces: {components_display}. Put them together — what do you get?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Great! The pieces chain together nicely."},
                "onWrong": {"message": "Hint: Simply join the pieces in order, left to right."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Complete training",
                "panel": {
                    "title": "SOLVED!",
                    "instruction": "{components_display} = {result} ✓"
                },
                "inputMode": "none",
                "button": {"label": "Complete →", "action": "complete"}
            }
        ]
    },

    "alternation_discover": {
        "phases": [
            {
                "id": "fodder",
                "actionPrompt": "Tap the word the indicator operates on",
                "panel": {
                    "title": "FIND THE FODDER",
                    "instruction": "'{indicator}' tells you to take alternating letters. Which word does it operate on?"
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
                "onWrong": {"message": "Hint: Look for a word right next to the indicator."}
            },
            {
                "id": "result",
                "actionPrompt": "Type the alternating letters",
                "panel": {
                    "title": "EXTRACT THE LETTERS",
                    "instruction": "Take alternating letters from '{fodder}'. Which {letters_needed} letters do you get?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Well done! Alternation is a handy technique to recognize."},
                "onWrong": {"message": "Hint: Take every other letter from '{fodder}' — try odd positions (1st, 3rd) or even (2nd, 4th)."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "ALTERNATION",
                    "instruction": "'{indicator}' on '{fodder}' = {result}"
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "double_definition": {
        "phases": [
            {
                "id": "first_def",
                "actionPrompt": "Tap the first definition",
                "intro": {
                    "title": "Double Definition",
                    "text": "This is a double definition — two separate meanings sitting side by side, both pointing to the same answer.\n\nNo wordplay indicators here. The trick is finding a word that satisfies both meanings.",
                    "example": "Short clue with no obvious wordplay? Think double definition."
                },
                "panel": {
                    "title": "FIND THE FIRST MEANING",
                    "instruction": "Tap the first definition — one meaning of the answer."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "GREEN", "role": "definition1"}},
                "onWrong": {"message": "Hint: Look for a word or phrase that could define the answer on its own."}
            },
            {
                "id": "second_def",
                "actionPrompt": "Tap the second definition",
                "panel": {
                    "title": "FIND THE SECOND MEANING",
                    "instruction": "Good! Now tap the second definition — a different meaning of the same word."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "definition2"}},
                "onWrong": {"message": "Hint: Look for another word or phrase that also defines the answer, but in a different sense."}
            },
            {
                "id": "solve",
                "actionPrompt": "Type the answer",
                "panel": {
                    "title": "WHAT'S THE WORD?",
                    "instruction": "What single word satisfies both definitions?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Excellent! You found the word that bridges both meanings."},
                "onWrong": {"message": "Hint: Think of a word that could mean both things — it's often a word with multiple unrelated meanings."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Complete training",
                "panel": {
                    "title": "SOLVED!",
                    "instruction": "Both definitions point to {result}. Double definitions are elegant — no wordplay needed, just two meanings of one word!"
                },
                "inputMode": "none",
                "button": {"label": "Complete →", "action": "complete"}
            }
        ]
    },

    "literal_phrase": {
        "phases": [
            {
                "id": "fodder",
                "actionPrompt": "Tap the phrase that sounds like something else",
                "intro": {
                    "title": "Literal Phrase",
                    "text": "Some cryptic clues use phrases that sound like something else when spoken aloud.\n\nThe trick is to read the phrase conversationally — what would it sound like if you said it?",
                    "example": "'do you mean?' spoken aloud sounds like 'IS IT' — the question you'd ask for confirmation."
                },
                "panel": {
                    "title": "FIND THE SPOKEN PHRASE",
                    "instruction": "Tap the words that sound like something else when spoken aloud."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
                "onWrong": {"message": "Hint: Look for a phrase that might sound different when spoken conversationally."}
            },
            {
                "id": "result",
                "actionPrompt": "Type what the phrase sounds like",
                "panel": {
                    "title": "SPOKEN SOUND",
                    "instruction": "What does '{fodder}' sound like when spoken aloud?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "That's it! Reading phrases aloud can reveal hidden meanings."},
                "onWrong": {"message": "Hint: Say '{fodder}' out loud — what does it sound like?"}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "LITERAL PHRASE",
                    "instruction": "'{fodder}' sounds like '{result}' when spoken.\n\n**Remember:** Some clues hide letters in how phrases sound when spoken conversationally."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "abbreviation": {
        "phases": [
            {
                "id": "fodder",
                "actionPrompt": "Tap the word to abbreviate",
                "intro": {
                    "title": "Abbreviation",
                    "text": "Cryptic clues frequently use standard abbreviations. Common examples:\n\n• Numbers: five=V, one=I, nothing=O\n• Directions: north=N, east=E\n• Titles: doctor=DR, saint=ST\n• Units: second=S, minute=M",
                    "example": "When you see a number or common word, think about its standard abbreviation."
                },
                "panel": {
                    "title": "FIND THE WORD",
                    "instruction": "Tap the word that represents an abbreviation."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
                "onWrong": {"message": "Hint: Look for a word that has a common abbreviation (numbers, directions, titles, etc.)."}
            },
            {
                "id": "result",
                "actionPrompt": "Type the abbreviation",
                "panel": {
                    "title": "TYPE ABBREVIATION",
                    "instruction": "What is the standard abbreviation for '{fodder}'?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Correct! Abbreviations are a staple of cryptic crosswords."},
                "onWrong": {"message": "Hint: Think of the standard abbreviation for '{fodder}'."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "ABBREVIATION",
                    "instruction": "'{fodder}' = {result}\n\n**Hint:** {hint}"
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "synonym": {
        "phases": [
            {
                "id": "fodder",
                "actionPrompt": "Tap the word to find a synonym for",
                "intro": {
                    "title": "Synonym",
                    "text": "Cryptic clues often require finding synonyms — words with the same or similar meaning.\n\nThe clue gives you one word, and you need to find another word that means the same thing.",
                    "example": "Think of alternative words that could replace the given word."
                },
                "panel": {
                    "title": "FIND THE WORD",
                    "instruction": "Tap the word you need to find a synonym for."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
                "onWrong": {"message": "Hint: Look for a word that needs to be replaced with a synonym."}
            },
            {
                "id": "result",
                "actionPrompt": "Type the synonym",
                "panel": {
                    "title": "TYPE SYNONYM",
                    "instruction": "What's a synonym for '{fodder}' that fits?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Good! Building synonym knowledge is key to cryptic solving."},
                "onWrong": {"message": "Hint: Think of words that mean the same as '{fodder}'."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "SYNONYM",
                    "instruction": "'{fodder}' = {result}\n\n**Hint:** {hint}"
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "deletion": {
        "phases": [
            {
                "id": "indicator",
                "actionPrompt": "Tap the deletion indicator",
                "intro": {
                    "title": "Deletion",
                    "text": "Deletion indicators tell you to remove letters from a word. Common indicators:\n\n• 'a lot of', 'most of' = remove last letter\n• 'headless', 'beheaded' = remove first letter\n• 'heartless' = remove middle letter\n• 'losing', 'without', 'dropping' = remove specified letters",
                    "example": "Look for words suggesting something is missing or shortened."
                },
                "panel": {
                    "title": "FIND THE INDICATOR",
                    "instruction": "Tap the word(s) that signal deletion."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "ORANGE", "role": "indicator"}},
                "onWrong": {"message": "Hint: Look for words suggesting removal or shortening."}
            },
            {
                "id": "result",
                "actionPrompt": "Type what remains after deletion",
                "panel": {
                    "title": "WHAT REMAINS?",
                    "instruction": "After applying the deletion to '{fodder}', what letters remain?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Correct! Deletion is a common cryptic technique."},
                "onWrong": {"message": "Hint: Remove the indicated letter(s) from '{fodder}'."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "DELETION",
                    "instruction": "'{fodder}' with deletion = {result}\n\n**Remember:** Deletion indicators tell you which part of a word to remove."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "reversal": {
        "phases": [
            {
                "id": "indicator",
                "actionPrompt": "Tap the reversal indicator",
                "intro": {
                    "title": "Reversal",
                    "text": "Reversal indicators tell you to reverse letters. Common indicators:\n\n• Across clues: 'back', 'returned', 'reflected', 'west'\n• Down clues: 'up', 'rising', 'climbing', 'overhead'\n• General: 'turned', 'reversed', 'backwards'",
                    "example": "The indicator tells you which direction to read the letters."
                },
                "panel": {
                    "title": "FIND THE INDICATOR",
                    "instruction": "Tap the word(s) that signal reversal."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "ORANGE", "role": "indicator"}},
                "onWrong": {"message": "Hint: Look for words suggesting backwards or reversed."}
            },
            {
                "id": "result",
                "actionPrompt": "Type the reversed letters",
                "panel": {
                    "title": "REVERSE IT",
                    "instruction": "Reverse '{fodder}'. What do you get?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Good! Reversals can hide words in plain sight."},
                "onWrong": {"message": "Hint: Write '{fodder}' backwards."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "REVERSAL",
                    "instruction": "'{fodder}' reversed = {result}\n\n**Remember:** Reversal indicators (back, up, turned) tell you to read letters backwards."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "letter_selection": {
        "phases": [
            {
                "id": "indicator",
                "actionPrompt": "Tap the selection indicator",
                "intro": {
                    "title": "Letter Selection",
                    "text": "Letter selection indicators tell you to take specific letters:\n\n• 'head of', 'first of', 'initially' = first letter\n• 'tail of', 'finally', 'at last' = last letter\n• 'heart of', 'centre of' = middle letter\n• 'edges of', 'borders' = first and last letters",
                    "example": "The indicator specifies which letter(s) to extract."
                },
                "panel": {
                    "title": "FIND THE INDICATOR",
                    "instruction": "Tap the word(s) that tell you which letters to select."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "ORANGE", "role": "indicator"}},
                "onWrong": {"message": "Hint: Look for words indicating position (first, last, heart, etc.)."}
            },
            {
                "id": "fodder",
                "actionPrompt": "Tap the source word(s)",
                "panel": {
                    "title": "FIND THE SOURCE",
                    "instruction": "Tap the word(s) you're extracting letters from."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
                "onWrong": {"message": "Hint: Which word does the indicator operate on?"}
            },
            {
                "id": "result",
                "actionPrompt": "Type the extracted letters",
                "panel": {
                    "title": "EXTRACT THE LETTERS",
                    "instruction": "What letter(s) do you get from '{fodder}'?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Nice! Letter selection is a precise technique."},
                "onWrong": {"message": "Hint: Apply the indicator to '{fodder}' — which letters does it specify?"}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "LETTER SELECTION",
                    "instruction": "From '{fodder}' = {result}\n\n**Remember:** Selection indicators (head of, finally, heart of) pinpoint exact letters."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "literal": {
        "phases": [
            {
                "id": "fodder",
                "actionPrompt": "Tap the literal letters",
                "intro": {
                    "title": "Literal",
                    "text": "Sometimes letters in a clue are used exactly as written — no transformation needed.\n\nAbbreviations like 'IT', 'PC', 'TV' or single letters contribute directly to the answer.",
                    "example": "These letters go straight into the answer unchanged."
                },
                "panel": {
                    "title": "FIND THE LITERAL",
                    "instruction": "Tap the word(s) used literally (as-is) in the answer."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
                "onWrong": {"message": "Hint: Look for letters or abbreviations used unchanged."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "LITERAL",
                    "instruction": "'{fodder}' = {result} (used as-is)\n\n**Remember:** Some letters contribute directly without any transformation."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "connector": {
        "phases": [
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "CONNECTOR",
                    "instruction": "'{fodder}' is a linking word connecting parts of the clue.\n\n**Remember:** Connectors (as, and, in, for) join wordplay elements but don't contribute letters."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "anagram": {
        "phases": [
            {
                "id": "indicator",
                "actionPrompt": "Tap the anagram indicator",
                "intro": {
                    "title": "Anagram",
                    "text": "Anagram indicators suggest letters need rearranging. Common indicators:\n\n• 'mixed', 'scrambled', 'confused', 'crazy'\n• 'working', 'moving', 'dancing', 'drunk'\n• 'broken', 'damaged', 'ruined', 'wild'\n• Any word suggesting disorder or change",
                    "example": "The indicator signals that adjacent letters should be rearranged."
                },
                "panel": {
                    "title": "FIND THE INDICATOR",
                    "instruction": "Tap the word(s) that signal an anagram."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "ORANGE", "role": "indicator"}},
                "onWrong": {"message": "Hint: Look for words suggesting mixing, confusion, or disorder."}
            },
            {
                "id": "result",
                "actionPrompt": "Type the anagrammed word",
                "panel": {
                    "title": "SOLVE THE ANAGRAM",
                    "instruction": "Rearrange the fodder letters. What word do you get?"
                },
                "inputMode": "text",
                "onCorrect": {"message": "Excellent! Anagrams are a cryptic crossword staple."},
                "onWrong": {"message": "Hint: Rearrange all the fodder letters to form a word."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "ANAGRAM",
                    "instruction": "Rearranged = {result}\n\n**Remember:** Anagram indicators signal that letters need shuffling to reveal the answer."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "container": {
        "phases": [
            {
                "id": "indicator",
                "actionPrompt": "Tap the container indicator",
                "intro": {
                    "title": "Container",
                    "text": "Container indicators tell you one thing goes inside another. Common indicators:\n\n• 'in', 'inside', 'within', 'held by'\n• 'around', 'about', 'outside', 'surrounding'\n• 'swallowing', 'eating', 'embracing', 'housing'",
                    "example": "The indicator tells you which piece wraps around which."
                },
                "panel": {
                    "title": "FIND THE INDICATOR",
                    "instruction": "Tap the word(s) that signal a container."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "ORANGE", "role": "indicator"}},
                "onWrong": {"message": "Hint: Look for words suggesting something inside or around something else."}
            },
            {
                "id": "order",
                "actionPrompt": "Select which piece goes inside which",
                "panel": {
                    "title": "CONTAINER ORDER",
                    "instruction": "Which piece goes inside which?"
                },
                "inputMode": "multiple_choice",
                "onCorrect": {"message": "Correct! The container structure is now clear."},
                "onWrong": {"message": "Hint: Look at the indicator — does it say something goes IN, or something goes AROUND?"}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "CONTAINER",
                    "instruction": "{inner} inside {outer} = {result}\n\n**Remember:** Container indicators (in, around, holding) tell you to put one piece inside another."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    },

    "hidden": {
        "phases": [
            {
                "id": "indicator",
                "actionPrompt": "Tap the hidden word indicator",
                "intro": {
                    "title": "Hidden Word",
                    "text": "Hidden word indicators tell you the answer is concealed within consecutive letters. Common indicators:\n\n• 'in', 'within', 'inside', 'part of'\n• 'some', 'partly', 'held by', 'contains'\n• 'buried in', 'hidden in', 'amongst'",
                    "example": "The answer spans across word boundaries in the clue itself."
                },
                "panel": {
                    "title": "FIND THE INDICATOR",
                    "instruction": "Tap the word(s) that signal a hidden word."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "ORANGE", "role": "indicator"}},
                "onWrong": {"message": "Hint: Look for words suggesting something is hidden or contained."}
            },
            {
                "id": "fodder",
                "actionPrompt": "Tap the words containing the hidden answer",
                "panel": {
                    "title": "FIND THE FODDER",
                    "instruction": "Tap the words that contain the hidden answer."
                },
                "inputMode": "tap_words",
                "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
                "onWrong": {"message": "Hint: Look for consecutive letters spanning word boundaries."}
            },
            {
                "id": "teaching",
                "actionPrompt": "Continue to next step",
                "panel": {
                    "title": "HIDDEN WORD",
                    "instruction": "The answer {result} is hidden within '{fodder}'.\n\n**Remember:** Hidden word clues conceal the answer in consecutive letters across words."
                },
                "inputMode": "none",
                "button": {"label": "Continue →", "action": "next_step"}
            }
        ]
    }
}

# =============================================================================
# CLUE TYPE IDENTIFICATION
# =============================================================================

STEP_TO_CLUE_TYPE = {
    "standard_definition": "standard",
    "wordplay_overview": "standard",
    "deletion_discover": "standard",
    "container_verify": "standard",
    "charade_verify": "standard",
    "alternation_discover": "standard",
    "literal_phrase": "standard",
    "abbreviation": "standard",
    "synonym": "standard",
    "deletion": "standard",
    "reversal": "standard",
    "letter_selection": "standard",
    "literal": "standard",
    "connector": "standard",
    "anagram": "standard",
    "container": "standard",
    "hidden": "standard",
    "double_definition": "double_definition",
}

CLUE_TYPE_OPTIONS = [
    {
        "id": "standard",
        "label": "Standard",
        "description": "Definition at start or end, with wordplay indicators in the rest"
    },
    {
        "id": "double_definition",
        "label": "Double Definition",
        "description": "Two separate meanings with no wordplay indicators"
    },
    {
        "id": "cryptic_definition",
        "label": "Cryptic Definition",
        "description": "Whole clue is one whimsical description with no obvious wordplay"
    },
    {
        "id": "and_lit",
        "label": "&lit",
        "description": "Whole clue both describes AND constructs the answer simultaneously"
    }
]

def get_clue_type(clue):
    """Determine the clue type from the first step."""
    steps = clue.get("steps", [])
    if not steps:
        return "standard"
    first_step_type = steps[0].get("type", "")
    return STEP_TO_CLUE_TYPE.get(first_step_type, "standard")

def build_clue_type_step(clue):
    """Build a synthetic clue_type_identify step with correct answer."""
    correct_type = get_clue_type(clue)
    options = []
    for opt in CLUE_TYPE_OPTIONS:
        options.append({
            "label": opt["label"],
            "description": opt["description"],
            "correct": opt["id"] == correct_type
        })
    return {
        "type": "clue_type_identify",
        "options": options
    }

# =============================================================================
# DYNAMIC PHASE GENERATION
# =============================================================================

def build_wordplay_overview_phases(step, clue):
    """Build phases for wordplay_overview based on common_vocabulary count."""
    phases = []

    # Extract what we know for coaching prompts
    # Get definition text from standard_definition step if not in this step
    definition_text = step.get("definition_text")
    if not definition_text:
        steps = clue.get("steps", [])
        for s in steps:
            if s.get("type") == "standard_definition":
                definition_text = s.get("expected", {}).get("text", "unknown")
                break
    if not definition_text:
        definition_text = "unknown"
    answer = clue.get("clue", {}).get("answer", "unknown")

    # Check recommended approach to determine intro text
    recommended_approach = clue.get("difficulty", {}).get("recommendedApproach", "definition")

    # Normalize common_vocabulary to list
    common_vocab = step.get("common_vocabulary", [])
    if isinstance(common_vocab, dict):
        common_vocab = [common_vocab]

    # Phase for each vocabulary item: tap then type
    for i, vocab in enumerate(common_vocab):
        vocab_num = i + 1
        is_first = i == 0

        # Tap phase - instructions differ based on whether user knows the answer
        if recommended_approach == "definition":
            # User has hypothesis - can reference answer
            if is_first:
                tap_instruction = f"Which word has a well-known cryptic synonym that might appear in {answer}?"
            else:
                tap_instruction = f"Look for another word with a well-known cryptic synonym that might appear in {answer}."
        else:
            # User doesn't know answer - can't reference it
            if is_first:
                tap_instruction = "Which word has a well-known cryptic synonym?"
            else:
                tap_instruction = "Look for another word with a well-known cryptic synonym."

        tap_phase = {
            "id": f"vocabulary_tap_{vocab_num}",
            "actionPrompt": "Tap a word with a common cryptic meaning",
            "panel": {
                "title": "FIND ANCHOR",
                "instruction": tap_instruction
            },
            "inputMode": "tap_words",
            "onCorrect": {"highlight": {"color": "BLUE", "role": f"vocabulary_{vocab_num}"}},
            "onWrong": {"message": f"Hint: Look for common cryptic vocabulary — words like 'fool', 'love', 'nothing' have well-known short synonyms."}
        }
        if is_first:
            if recommended_approach == "definition":
                intro_text = f"We have the definition, {definition_text}, and a hypothesis: {answer}. Now let's verify it by scanning the remaining words for anchors — words with obvious cryptic meanings that might support your hypothesis."
            else:
                intro_text = f"We have the definition: {definition_text}. Now let's build the answer from the wordplay by finding anchors — words with obvious cryptic meanings."
            tap_phase["intro"] = {
                "title": "Wordplay Overview",
                "text": intro_text,
                "example": ""
            }
        phases.append(tap_phase)

        # Type phase - get the vocab word text and meaning length for coaching prompt
        vocab_text = vocab.get("text", "this word")
        vocab_meaning = vocab.get("meaning", "")
        meaning_len = len(vocab_meaning) if vocab_meaning else 3

        # Instructions differ based on whether user knows the answer
        if recommended_approach == "definition":
            type_instruction = f"Nice work spotting '{vocab_text}' — this appears frequently in cryptic clues. What's its common {meaning_len}-letter synonym? Check if it appears in {answer}."
            type_wrong_hint = f"Hint: Think of a {meaning_len}-letter word that means '{vocab_text}' and appears in {answer}."
        else:
            type_instruction = f"Nice work spotting '{vocab_text}' — this appears frequently in cryptic clues. What's its common {meaning_len}-letter synonym?"
            type_wrong_hint = f"Hint: Think of a {meaning_len}-letter word that means '{vocab_text}'."

        type_phase = {
            "id": f"vocabulary_type_{vocab_num}",
            "actionPrompt": "Type the synonym",
            "panel": {
                "title": "TYPE SYNONYM",
                "instruction": type_instruction
            },
            "inputMode": "text",
            "onCorrect": {"message": f"That's it! '{vocab_text}' = {vocab_meaning} — a common cryptic pairing worth remembering."},
            "onWrong": {"message": type_wrong_hint}
        }
        phases.append(type_phase)

    # Indicator phases - one at a time
    indicators = step.get("expected_indicators", [])
    num_indicators = len(indicators)
    for i, indicator in enumerate(indicators):
        ind_num = i + 1
        operation = indicator.get("operation", "wordplay")

        if num_indicators == 1:
            instruction = "Now look for an indicator — a word that signals a wordplay operation like deletion, container, or reversal."
        else:
            instruction = f"There are {num_indicators} indicators in this clue. Can you spot one?"

        indicator_phase = {
            "id": f"indicator_tap_{ind_num}",
            "actionPrompt": f"Tap indicator {ind_num}" if num_indicators > 1 else "Tap the indicator",
            "panel": {
                "title": "FIND INDICATOR",
                "instruction": instruction
            },
            "inputMode": "tap_words",
            "onCorrect": {"highlight": {"color": "ORANGE", "role": f"indicator_{ind_num}"}},
            "onWrong": {"message": f"Hint: Look for a word that could signal {operation} — these are the 'recipe words' that tell you what to do."}
        }
        phases.append(indicator_phase)

    # Teaching phase
    teaching_phase = {
        "id": "teaching",
        "actionPrompt": "Continue to next step",
        "panel": {
            "title": "OVERVIEW COMPLETE",
            "instruction": ""  # Built dynamically in get_render
        },
        "inputMode": "none",
        "button": {"label": "Continue →", "action": "next_step"}
    }
    phases.append(teaching_phase)

    return phases

def build_standard_definition_phases(step, clue):
    """Build phases for standard_definition, adding solve phase if recommendedApproach is 'definition'."""
    base_phases = STEP_TEMPLATES["standard_definition"]["phases"].copy()

    # Check if we should add solve phase
    difficulty = clue.get("difficulty", {})
    recommended_approach = difficulty.get("recommendedApproach", "wordplay")

    if recommended_approach == "definition":
        # Get hint from difficulty.definition.hint if available
        definition_hint = difficulty.get("definition", {}).get("hint", "")

        # Standard intro paragraph explaining the strategy
        strategy_intro = "Clues can be solved by starting with the wordplay or the definition. Skilled solvers often hypothesize an answer based on the definition, then verify it using the wordplay."

        # Combine strategy intro with clue-specific hint
        full_text = f"{strategy_intro}\n\n{definition_hint}"

        # Insert solve phase after teaching
        solve_phase = {
            "id": "solve",
            "actionPrompt": "Type your answer",
            "intro": {
                "title": "Solve from Definition",
                "text": full_text,
                "example": ""
            },
            "panel": {
                "title": "SOLVE FROM DEFINITION",
                "instruction": "Based on the definition, type your answer."
            },
            "inputMode": "text",
            "onCorrect": {"message": "Correct!"},
            "onWrong": {"message": "Think of a word that matches the definition."}
        }
        # Insert after teaching (index 1), before any next steps
        phases = base_phases[:2] + [solve_phase]
        return phases

    return base_phases

def build_deletion_discover_phases(step, clue):
    """Build phases for deletion_discover with synonym input and multiple choice deletion."""
    phases = []

    answer = clue.get("clue", {}).get("answer", "")
    indicator_text = step.get("indicator", {}).get("text", "")
    fodder_word = step.get("fodder_word", {}).get("text", "")
    fodder_synonym = step.get("fodder_synonym", "")
    result = step.get("result", "")
    letters_needed = step.get("letters_needed", len(result))

    # Compute anchor_summary from wordplay_overview step
    anchor_summary = ""
    steps = clue.get("steps", [])
    for s in steps:
        if s.get("type") == "wordplay_overview":
            common_vocab = s.get("common_vocabulary", [])
            if isinstance(common_vocab, dict):
                common_vocab = [common_vocab]
            if common_vocab:
                anchor_parts = []
                for vocab in common_vocab:
                    vocab_text = vocab.get("text", "")
                    meaning = vocab.get("meaning", "")
                    letters = vocab.get("letters", len(meaning))
                    anchor_parts.append(f"{meaning} from '{vocab_text}' ({letters} letters)")
                anchor_summary = ", ".join(anchor_parts)
            break

    # Phase 1: Tap the fodder word
    fodder_phase = {
        "id": "fodder",
        "actionPrompt": "Tap the word the indicator operates on",
        "panel": {
            "title": "FIND FODDER",
            "instruction": f"'{indicator_text}' is a deletion indicator — it shortens something. Which adjacent word does it operate on?"
        },
        "inputMode": "tap_words",
        "onCorrect": {"highlight": {"color": "BLUE", "role": "fodder"}},
        "onWrong": {"message": f"Hint: Indicators operate on adjacent words. Look right next to '{indicator_text}'."}
    }
    phases.append(fodder_phase)

    # Phase 2: Type the synonym
    synonym_phase = {
        "id": "synonym",
        "actionPrompt": "Type the synonym",
        "panel": {
            "title": "FIND THE SYNONYM",
            "instruction": f"You have {anchor_summary}. '{indicator_text}' '{fodder_word}' needs to give you {letters_needed} more letters. Shortening '{fodder_word}' directly doesn't fit {answer} — what synonym of '{fodder_word}' might work?"
        },
        "inputMode": "text",
        "onCorrect": {"message": f"Good — '{fodder_word}' = {fodder_synonym}!"},
        "onWrong": {"message": f"Hint: Think of synonyms for '{fodder_word}'. Which one has {letters_needed + 1} letters that could be shortened?"}
    }
    phases.append(synonym_phase)

    # Phase 3: Multiple choice - which letter to delete
    # Generate options for deleting first or last letter
    deletion_options = []
    if len(fodder_synonym) > 0:
        # Delete first letter
        first_deleted = fodder_synonym[1:]
        deletion_options.append({
            "label": f"Delete first letter {fodder_synonym[0]} → {first_deleted}",
            "correct": first_deleted.upper() == result.upper()
        })
        # Delete last letter
        last_deleted = fodder_synonym[:-1]
        deletion_options.append({
            "label": f"Delete last letter {fodder_synonym[-1]} → {last_deleted}",
            "correct": last_deleted.upper() == result.upper()
        })

    result_phase = {
        "id": "result",
        "actionPrompt": "Select which letter to delete",
        "panel": {
            "title": "SHORTEN IT",
            "instruction": f"'{indicator_text}' means to shorten. Which letter do you remove from {fodder_synonym}?"
        },
        "inputMode": "multiple_choice",
        "options": deletion_options,
        "onCorrect": {"message": "Excellent! You discovered the deletion by working backwards from your hypothesis."},
        "onWrong": {"message": f"Hint: Which deletion gives you letters that fit {answer}?"}
    }
    phases.append(result_phase)

    # Phase 4: Teaching
    teaching_phase = {
        "id": "teaching",
        "actionPrompt": "Continue to next step",
        "panel": {
            "title": "DELETION CONFIRMED",
            "instruction": f"'{fodder_word}' = {fodder_synonym}, shortened = {result}. This is a key cryptic technique — working backwards from your hypothesis to discover synonyms."
        },
        "inputMode": "none",
        "button": {"label": "Continue →", "action": "next_step"}
    }
    phases.append(teaching_phase)

    return phases

def build_container_verify_phases(step, clue):
    """Build phases for container_verify with auto-generated options."""
    inner = step.get("inner", "")
    outer = step.get("outer", "")
    result = step.get("result", "")
    indicator_text = step.get("indicator", {}).get("text", "")
    answer = clue.get("clue", {}).get("answer", "")

    # Auto-generate options: determine which is correct by checking if inner appears inside result
    inner_upper = inner.upper()
    result_upper = result.upper()

    # If inner appears inside result (surrounded by other letters), then inner goes inside outer
    inner_inside_correct = inner_upper in result_upper and result_upper != inner_upper

    options = [
        {"label": f"{inner} goes inside {outer}", "correct": inner_inside_correct},
        {"label": f"{outer} goes inside {inner}", "correct": not inner_inside_correct}
    ]

    phases = [
        {
            "id": "order",
            "actionPrompt": "Select which piece goes inside which",
            "panel": {
                "title": "CONTAINER ORDER",
                "instruction": f"You have two pieces: {inner} and {outer}. '{indicator_text}' tells us one goes inside the other. To make {answer}, which arrangement works?"
            },
            "inputMode": "multiple_choice",
            "options": options,
            "onCorrect": {"message": "That's right! Container indicators tell you the structure."},
            "onWrong": {"message": f"Hint: Look at {answer} — where does {inner} appear? Is it surrounded by letters, or does it surround them?"}
        },
        {
            "id": "teaching",
            "actionPrompt": "Complete training",
            "panel": {
                "title": "VERIFIED!",
                "instruction": ""  # Built dynamically in get_render
            },
            "inputMode": "none",
            "button": {"label": "Continue →", "action": "next_step"}
        }
    ]

    return phases

# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

_sessions = {}  # clue_id -> session state

def start_session(clue_id, clue):
    """Initialize a new training session."""
    _sessions[clue_id] = {
        "clue_id": clue_id,
        "step_index": -1,  # Start at -1 for clue type identification step
        "phase_index": 0,
        "highlights": [],
        "learnings": [],
        "answer_known": False,  # True if user solved from definition (now reviewing wordplay)
        "found_indicators": []  # Track which indicator indices have been found (any order)
    }
    return get_render(clue_id, clue)

def get_session(clue_id):
    """Get existing session or None."""
    return _sessions.get(clue_id)

def clear_session(clue_id):
    """Clear session for a clue (e.g., on exit). Returns True if session existed."""
    if clue_id in _sessions:
        del _sessions[clue_id]
        return True
    return False

# =============================================================================
# RENDER
# =============================================================================

def get_step_phases(step, clue):
    """Get phases for a step, handling dynamic phase generation."""
    step_type = step.get("type")

    if step_type == "wordplay_overview":
        return build_wordplay_overview_phases(step, clue)
    elif step_type == "standard_definition":
        return build_standard_definition_phases(step, clue)
    elif step_type == "deletion_discover":
        return build_deletion_discover_phases(step, clue)
    elif step_type == "container_verify":
        return build_container_verify_phases(step, clue)
    else:
        template = STEP_TEMPLATES.get(step_type)
        if template:
            return template["phases"]
        return []

def substitute_variables(text, step, session, clue=None):
    """Replace {variable} placeholders with values from step data."""
    if not isinstance(text, str):
        return text

    subs = {}

    # Handle expected.text for definition
    if "expected" in step and isinstance(step["expected"], dict):
        subs["result"] = step["expected"].get("text", "")
        subs["definition_text"] = step["expected"].get("text", "")

    # Position
    if "position" in step:
        subs["position"] = step["position"]

    # Direct fields
    for key in ["result", "fodder_synonym", "letters_needed", "inner", "outer",
                "letters_so_far", "pattern"]:
        if key in step:
            subs[key] = str(step[key])

    # Handle hint with fallback to teaching_hints.json
    step_type = step.get("type", "")
    fodder_text = ""
    if "fodder" in step:
        f = step["fodder"]
        fodder_text = f.get("text", "") if isinstance(f, dict) else str(f)

    if "hint" in step and step["hint"]:
        # Use hint from metadata if provided
        subs["hint"] = str(step["hint"])
    elif step_type == "abbreviation" and fodder_text:
        # Fallback to teaching_hints.json for abbreviations
        subs["hint"] = get_teaching_hint("abbreviations", fodder_text,
            "Build a mental library of common cryptic abbreviations — they appear frequently!")
    elif step_type == "synonym" and fodder_text:
        # Fallback to teaching_hints.json for synonyms
        subs["hint"] = get_teaching_hint("synonyms", fodder_text,
            "Cryptic crosswords often use unexpected synonyms. This pairing is worth remembering!")

    # Handle indicator
    if "indicator" in step:
        ind = step["indicator"]
        if isinstance(ind, dict):
            subs["indicator"] = ind.get("text", "")
        else:
            subs["indicator"] = str(ind)

    # Handle fodder_word
    if "fodder_word" in step:
        fw = step["fodder_word"]
        if isinstance(fw, dict):
            subs["fodder_word"] = fw.get("text", "")
        else:
            subs["fodder_word"] = str(fw)

    # Handle fodder
    if "fodder" in step:
        f = step["fodder"]
        if isinstance(f, dict):
            subs["fodder"] = f.get("text", "")
        else:
            subs["fodder"] = str(f)

    # Handle components for charade_verify
    if "components" in step:
        components = step["components"]
        subs["components_display"] = " + ".join(components)

    # Handle outer_split for container_verify teaching
    if "inner" in step and "outer" in step and "result" in step:
        inner = step["inner"]
        outer = step["outer"]
        result = step["result"]
        # Find where inner fits in result to show split
        inner_upper = inner.upper()
        result_upper = result.upper()
        idx = result_upper.find(inner_upper)
        if idx > 0:
            before = result_upper[:idx]
            after = result_upper[idx + len(inner_upper):]
            subs["outer_split"] = f"{before} + {inner_upper} + {after}"
        else:
            subs["outer_split"] = f"{outer} around {inner}"

    # Handle definitions for double_definition
    if "definitions" in step:
        definitions = step["definitions"]
        if len(definitions) > 0:
            subs["def1"] = definitions[0].get("text", "")
        if len(definitions) > 1:
            subs["def2"] = definitions[1].get("text", "")

    # Get letterCount from clue enumeration and answer
    if clue:
        enumeration = clue.get("clue", {}).get("enumeration", "")
        if enumeration:
            subs["letterCount"] = str(parse_enumeration(enumeration))
        subs["answer"] = clue.get("clue", {}).get("answer", "")

        # Find anchor info from wordplay_overview step for context
        steps = clue.get("steps", [])
        anchor_letters = 0
        anchor_summary = ""
        for s in steps:
            if s.get("type") == "wordplay_overview":
                common_vocab = s.get("common_vocabulary", [])
                if isinstance(common_vocab, dict):
                    common_vocab = [common_vocab]
                if common_vocab:
                    # Build anchor summary
                    anchor_parts = []
                    for vocab in common_vocab:
                        vocab_text = vocab.get("text", "")
                        meaning = vocab.get("meaning", "")
                        letters = vocab.get("letters", len(meaning))
                        anchor_letters += letters
                        anchor_parts.append(f"{meaning} from '{vocab_text}' ({letters} letters)")
                    anchor_summary = ", ".join(anchor_parts)
                break

        subs["anchor_summary"] = anchor_summary
        subs["letters_have"] = str(anchor_letters)

    # Perform substitution
    for key, val in subs.items():
        text = text.replace("{" + key + "}", str(val))

    return text

def get_render(clue_id, clue):
    """Build render object for current state."""
    session = _sessions.get(clue_id)
    if not session:
        return {"error": "No session"}

    steps = clue.get("steps", [])
    answer = clue.get("clue", {}).get("answer", "")
    enumeration = clue.get("clue", {}).get("enumeration", "")

    # Check if complete
    if session["step_index"] >= len(steps):
        return {
            "complete": True,
            "highlights": session["highlights"],
            "answer": answer,
            "actionPrompt": "Solved!",
            "learnings": session.get("learnings", []),
            "inputMode": "none"
        }

    # Handle clue type identification step (step_index == -1)
    if session["step_index"] == -1:
        step = build_clue_type_step(clue)
        phases = STEP_TEMPLATES["clue_type_identify"]["phases"]
    else:
        step = steps[session["step_index"]]
        phases = get_step_phases(step, clue)

    if not phases:
        return {"error": f"No phases for step type: {step.get('type')}"}

    if session["phase_index"] >= len(phases):
        return {"error": "Phase index out of range"}

    phase = phases[session["phase_index"]]

    # Skip text input for final answer if answer is already known
    if session.get("answer_known") and phase.get("inputMode") == "text":
        step_type = step.get("type", "")
        # For charade_verify or solve phases asking for the final answer, auto-advance
        if step_type == "charade_verify" or phase.get("id") == "solve":
            expected = step.get("result", answer).upper().replace(" ", "")
            handle_input(clue_id, clue, expected)
            return get_render(clue_id, clue)

    # Build render
    render = {
        "stepIndex": session["step_index"],
        "phaseIndex": session["phase_index"],
        "stepType": step["type"],
        "phaseId": phase["id"],
        "inputMode": phase.get("inputMode", "none"),
        "highlights": session["highlights"],
        "answer": answer,
        "actionPrompt": phase.get("actionPrompt", ""),
        "learnings": session.get("learnings", []),
        "answerKnown": session.get("answer_known", False),
        "words": clue.get("words", [])  # Include words array for UI to display
    }

    # Add step progress (for showing "Step 1 of 3" in UI)
    # Count phases excluding teaching phases
    non_teaching_phases = [p for p in phases if p.get("id") != "teaching"]
    current_phase_num = session["phase_index"] + 1
    total_phases = len(non_teaching_phases)

    # Only show progress for interactive phases (not teaching/complete)
    if phase.get("inputMode") != "none" and total_phases > 1:
        # Find which non-teaching phase we're on
        non_teaching_index = 0
        for i, p in enumerate(phases):
            if p.get("id") == "teaching":
                continue
            if i == session["phase_index"]:
                render["stepProgress"] = {
                    "current": non_teaching_index + 1,
                    "total": total_phases,
                    "label": f"Step {non_teaching_index + 1} of {total_phases}"
                }
                break
            non_teaching_index += 1

    # Add difficulty for clue type identification step
    if session["step_index"] == -1:
        difficulty = clue.get("difficulty")
        if difficulty:
            render["difficulty"] = difficulty

    # Add intro if present
    if "intro" in phase:
        render["intro"] = {
            "title": substitute_variables(phase["intro"].get("title", ""), step, session, clue),
            "text": substitute_variables(phase["intro"].get("text", ""), step, session, clue),
            "example": substitute_variables(phase["intro"].get("example", ""), step, session, clue)
        }

    # Add panel
    if "panel" in phase:
        render["panel"] = {
            "title": substitute_variables(phase["panel"].get("title", ""), step, session, clue),
            "instruction": substitute_variables(phase["panel"].get("instruction", ""), step, session, clue)
        }

    # Add button if present
    if "button" in phase:
        render["button"] = phase["button"]

    # Special handling for standard_definition teaching phase - include definition hint
    if step["type"] == "standard_definition" and phase["id"] == "teaching":
        definition_text = step.get("expected", {}).get("text", "")
        position = step.get("position", "")
        definition_hint = clue.get("difficulty", {}).get("definition", {}).get("hint", "")

        instruction = f"Good! The definition, '{definition_text}', is at the {position} of the clue."
        if definition_hint:
            instruction += f"\n\n**Hint:** {definition_hint}"
        render["panel"]["instruction"] = instruction

    # Special handling for wordplay_overview teaching phase
    if step["type"] == "wordplay_overview" and phase["id"] == "teaching":
        render["panel"]["instruction"] = build_wordplay_teaching(step, clue)

    # Special handling for deletion_discover teaching
    if step["type"] == "deletion_discover" and phase["id"] == "teaching":
        fodder_word = step.get("fodder_word", {}).get("text", "")
        fodder_synonym = step.get("fodder_synonym", "")
        result = step.get("result", "")
        render["panel"]["instruction"] = f"{fodder_word} = {fodder_synonym}, shortened = {result}\n\n**Remember:** Deletion indicators often require finding a synonym first, then shortening it."

    # Special handling for container_verify teaching
    if step["type"] == "container_verify" and phase["id"] == "teaching":
        inner = step.get("inner", "")
        outer = step.get("outer", "")
        result = step.get("result", "")
        # Build the split display
        inner_upper = inner.upper()
        result_upper = result.upper()
        idx = result_upper.find(inner_upper)
        if idx > 0:
            before = result_upper[:idx]
            after = result_upper[idx + len(inner_upper):]
            split_display = f"{before} + {inner_upper} + {after}"
        else:
            split_display = f"{outer} around {inner}"

        definition_text = ""
        if steps and steps[0].get("type") == "standard_definition":
            definition_text = steps[0].get("expected", {}).get("text", "")

        render["panel"]["instruction"] = f"{split_display} = {result} ✓\nDefinition: \"{definition_text}\" = {result} ✓\n\n**Remember:** Container indicators (about, holds, around, inside, carries) tell you to put one piece inside another."

    # Special handling for alternation_discover teaching
    if step["type"] == "alternation_discover" and phase["id"] == "teaching":
        fodder = step.get("fodder", {}).get("text", "")
        result = step.get("result", "")
        pattern = step.get("pattern", "even")

        # Get the previous charade result if available
        charade_result = ""
        for i, s in enumerate(steps):
            if s.get("type") == "charade_verify":
                charade_result = s.get("result", "")
                break

        definition_text = ""
        if steps and steps[0].get("type") == "standard_definition":
            definition_text = steps[0].get("expected", {}).get("text", "")

        final_answer = answer
        render["panel"]["instruction"] = f"Taking alternate letters from {fodder}: {result}\n{charade_result} + {result} = {final_answer} ✓\nDefinition: \"{definition_text}\" = {final_answer} ✓\n\n**Remember:** Alternation indicators (by turns, oddly, evenly, regularly) tell you to take every other letter."

    # Special handling for fodder phase - dynamic word count for multiple templates
    if phase["id"] == "fodder" and step["type"] in ["synonym", "abbreviation", "literal", "letter_selection"]:
        fodder_indices = step.get("fodder", {}).get("indices", [])
        word_count = len(fodder_indices)

        if step["type"] == "synonym":
            if word_count == 1:
                render["panel"]["instruction"] = "Tap the word you need to find a synonym for."
                render["actionPrompt"] = "Tap the word to find a synonym for"
            else:
                render["panel"]["instruction"] = f"Tap the {word_count} words you need to find a synonym for."
                render["actionPrompt"] = f"Tap the {word_count} words to find a synonym for"
        elif step["type"] == "abbreviation":
            if word_count == 1:
                render["panel"]["instruction"] = "Tap the word to abbreviate."
                render["actionPrompt"] = "Tap the word to abbreviate"
            else:
                render["panel"]["instruction"] = f"Tap the {word_count} words to abbreviate."
                render["actionPrompt"] = f"Tap the {word_count} words to abbreviate"
        elif step["type"] == "literal":
            if word_count == 1:
                render["panel"]["instruction"] = "Tap the word used literally (as-is) in the answer."
                render["actionPrompt"] = "Tap the literal word"
            else:
                render["panel"]["instruction"] = f"Tap the {word_count} words used literally (as-is) in the answer."
                render["actionPrompt"] = f"Tap the {word_count} literal words"
        elif step["type"] == "letter_selection":
            if word_count == 1:
                render["panel"]["instruction"] = "Tap the word you're extracting letters from."
                render["actionPrompt"] = "Tap the source word"
            else:
                render["panel"]["instruction"] = f"Tap the {word_count} words you're extracting letters from."
                render["actionPrompt"] = f"Tap the {word_count} source words"

    # Add expected for validation
    if phase.get("inputMode") == "tap_words":
        phase_id = phase["id"]
        if phase_id == "select" and "expected" in step:
            render["expected"] = step["expected"]["indices"]
        elif phase_id.startswith("indicator_tap_"):
            # Accept any unfound indicator (user can find in any order)
            indicators = step.get("expected_indicators", [])
            found_indicators = session.get("found_indicators", [])
            num_total = len(indicators)
            num_found = len(found_indicators)
            num_remaining = num_total - num_found

            # Find first unfound indicator for expected (for autoCheck single-word logic)
            unfound_indices = []
            for ind in indicators:
                ind_tuple = tuple(ind.get("indices", []))
                if ind_tuple not in found_indicators:
                    unfound_indices.append(ind.get("indices", []))

            if unfound_indices:
                # Set expected to first unfound for autoCheck calculation
                render["expected"] = unfound_indices[0]

            # Update instruction dynamically based on progress
            if num_total == 1:
                instruction = "Which remaining word signals a wordplay operation?"
            elif num_remaining == num_total:
                instruction = f"There are {num_total} indicators. Find one."
            elif num_remaining == 1:
                instruction = "Find the last indicator."
            else:
                instruction = f"Found {num_found} of {num_total}. Find another indicator."
            render["panel"]["instruction"] = instruction
        elif phase_id.startswith("vocabulary_tap_"):
            # Get the vocabulary index
            vocab_num = int(phase_id.split("_")[-1])
            common_vocab = step.get("common_vocabulary", [])
            if isinstance(common_vocab, dict):
                common_vocab = [common_vocab]
            if vocab_num <= len(common_vocab):
                render["expected"] = common_vocab[vocab_num - 1].get("indices", [])
        elif phase_id == "indicator":
            if "indicator" in step and isinstance(step["indicator"], dict):
                render["expected"] = step["indicator"]["indices"]
        elif phase_id == "fodder":
            if "fodder_word" in step:
                render["expected"] = step["fodder_word"]["indices"]
            elif "fodder" in step and isinstance(step["fodder"], dict):
                render["expected"] = step["fodder"]["indices"]
        elif phase_id == "first_def" and "definitions" in step:
            render["expected"] = step["definitions"][0]["indices"]
        elif phase_id == "second_def" and "definitions" in step:
            render["expected"] = step["definitions"][1]["indices"]

        # Add autoCheck flag for single-word taps
        if "expected" in render and isinstance(render["expected"], list) and len(render["expected"]) == 1:
            render["autoCheck"] = True
        else:
            render["autoCheck"] = False
    elif phase.get("inputMode") == "text":
        phase_id = phase["id"]
        if phase_id.startswith("vocabulary_type_"):
            vocab_num = int(phase_id.split("_")[-1])
            common_vocab = step.get("common_vocabulary", [])
            if isinstance(common_vocab, dict):
                common_vocab = [common_vocab]
            if vocab_num <= len(common_vocab):
                render["expected"] = common_vocab[vocab_num - 1].get("meaning", "")
        elif phase_id == "result":
            render["expected"] = step.get("result", "")
        elif phase_id == "solve":
            render["expected"] = answer
    elif phase.get("inputMode") == "multiple_choice":
        # Check phase options first (for dynamically generated phases), then step options
        options = phase.get("options") or step.get("options")
        if options:
            render["options"] = options

    # Build hint for interactive phases (not teaching/none)
    if phase.get("inputMode") in ["tap_words", "text", "multiple_choice"]:
        hint = None

        # Try step-level hint first
        if step.get("hint"):
            hint = substitute_variables(str(step["hint"]), step, session, clue)

        # Fallback to onWrong message
        if not hint:
            on_wrong_msg = phase.get("onWrong", {}).get("message", "")
            if on_wrong_msg:
                hint = substitute_variables(on_wrong_msg, step, session, clue)

        # Fallback to teaching_hints.json for specific step types
        step_type = step.get("type", "")
        if not hint and step_type == "abbreviation":
            fodder_text = ""
            if "fodder" in step:
                f = step["fodder"]
                fodder_text = f.get("text", "") if isinstance(f, dict) else str(f)
            if fodder_text:
                hint = get_teaching_hint("abbreviations", fodder_text, "")

        if not hint and step_type == "synonym":
            fodder_text = ""
            if "fodder" in step:
                f = step["fodder"]
                fodder_text = f.get("text", "") if isinstance(f, dict) else str(f)
            if fodder_text:
                hint = get_teaching_hint("synonyms", fodder_text, "")

        render["hint"] = hint if hint else None

    return render

def build_wordplay_teaching(step, clue):
    """Build the teaching instruction for wordplay_overview."""
    lines = []

    # Common vocabulary
    common_vocab = step.get("common_vocabulary", [])
    if isinstance(common_vocab, dict):
        common_vocab = [common_vocab]

    total_vocab_letters = 0
    for vocab in common_vocab:
        text = vocab.get("text", "")
        meaning = vocab.get("meaning", "")
        letters = vocab.get("letters", len(meaning))
        total_vocab_letters += letters
        lines.append(f"• {text} = {meaning} ({letters} letters) — your anchor")

    # Indicators
    indicators = step.get("expected_indicators", [])
    for ind in indicators:
        text = ind.get("text", "")
        operation = ind.get("operation", "")
        lines.append(f"• \"{text}\" = {operation} indicator")

    # Letter math
    enumeration = parse_enumeration(clue.get("clue", {}).get("enumeration", "0"))
    letters_needed = enumeration - total_vocab_letters
    lines.append(f"• You have {total_vocab_letters} letters. You need {letters_needed} more.")

    return "\n".join(lines)

# =============================================================================
# INPUT HANDLING
# =============================================================================

def handle_input(clue_id, clue, value):
    """Process user input (tap or text)."""
    session = _sessions.get(clue_id)
    if not session:
        return {"error": "No session"}

    steps = clue.get("steps", [])
    answer = clue.get("clue", {}).get("answer", "")

    # Handle clue type identification step (step_index == -1)
    if session["step_index"] == -1:
        step = build_clue_type_step(clue)
        phases = STEP_TEMPLATES["clue_type_identify"]["phases"]
    else:
        step = steps[session["step_index"]]
        phases = get_step_phases(step, clue)

    phase = phases[session["phase_index"]]

    # Determine expected value
    expected = None
    phase_id = phase["id"]

    if phase.get("inputMode") == "tap_words":
        if phase_id == "select" and "expected" in step:
            expected = step["expected"]["indices"]
        elif phase_id.startswith("indicator_tap_"):
            # Accept ANY unfound indicator (user can find them in any order)
            indicators = step.get("expected_indicators", [])
            found_indicators = session.get("found_indicators", [])
            # Collect all unfound indicator indices
            unfound_indices = []
            for ind in indicators:
                ind_indices = tuple(ind.get("indices", []))
                if ind_indices not in found_indicators:
                    unfound_indices.append(ind.get("indices", []))
            # expected will be checked against any of the unfound indicators
            expected = unfound_indices  # List of valid index lists
        elif phase_id.startswith("vocabulary_tap_"):
            vocab_num = int(phase_id.split("_")[-1])
            common_vocab = step.get("common_vocabulary", [])
            if isinstance(common_vocab, dict):
                common_vocab = [common_vocab]
            if vocab_num <= len(common_vocab):
                expected = common_vocab[vocab_num - 1].get("indices", [])
        elif phase_id == "indicator":
            if "indicator" in step and isinstance(step["indicator"], dict):
                expected = step["indicator"]["indices"]
        elif phase_id == "fodder":
            if "fodder_word" in step:
                expected = step["fodder_word"]["indices"]
            elif "fodder" in step and isinstance(step["fodder"], dict):
                expected = step["fodder"]["indices"]
        elif phase_id == "first_def" and "definitions" in step:
            expected = step["definitions"][0]["indices"]
        elif phase_id == "second_def" and "definitions" in step:
            expected = step["definitions"][1]["indices"]
    elif phase.get("inputMode") == "text":
        if phase_id.startswith("vocabulary_type_"):
            vocab_num = int(phase_id.split("_")[-1])
            common_vocab = step.get("common_vocabulary", [])
            if isinstance(common_vocab, dict):
                common_vocab = [common_vocab]
            if vocab_num <= len(common_vocab):
                expected = common_vocab[vocab_num - 1].get("meaning", "").upper()
        elif phase_id == "synonym":
            # For deletion_discover synonym phase
            expected = step.get("fodder_synonym", "").upper()
        elif phase_id == "result":
            expected = step.get("result", "").upper()
        elif phase_id == "solve":
            expected = answer.upper()
    elif phase.get("inputMode") == "multiple_choice":
        # Check phase options first (for dynamically generated phases), then step options
        options = phase.get("options") or step.get("options", [])
        for i, opt in enumerate(options):
            if opt.get("correct"):
                expected = i
                break

    # Check answer
    correct = False
    matched_indicator = None  # Track which indicator was matched (for any-order indicators)
    if phase.get("inputMode") == "tap_words":
        if isinstance(value, list) and isinstance(expected, list):
            # Check if this is an indicator tap with multiple valid options
            if phase_id.startswith("indicator_tap_") and expected and isinstance(expected[0], list):
                # expected is a list of valid index lists - check if value matches any
                for valid_indices in expected:
                    if set(value) == set(valid_indices):
                        correct = True
                        matched_indicator = valid_indices
                        break
            else:
                correct = set(value) == set(expected)
    elif phase.get("inputMode") == "text":
        if isinstance(value, str) and expected:
            user_letters = re.sub(r'[^A-Z]', '', value.upper())
            expected_letters = re.sub(r'[^A-Z]', '', expected)
            correct = user_letters == expected_letters
    elif phase.get("inputMode") == "multiple_choice":
        correct = value == expected

    if correct:
        # Track found indicator if this was an indicator tap
        if phase_id.startswith("indicator_tap_") and matched_indicator:
            if "found_indicators" not in session:
                session["found_indicators"] = []
            session["found_indicators"].append(tuple(matched_indicator))

        # Add highlight if specified
        if "onCorrect" in phase and "highlight" in phase["onCorrect"]:
            # Use matched_indicator for indicator taps, otherwise use expected
            if matched_indicator:
                highlight_indices = matched_indicator
            elif isinstance(expected, list) and not (expected and isinstance(expected[0], list)):
                highlight_indices = expected
            else:
                highlight_indices = []
            session["highlights"].append({
                "indices": highlight_indices,
                "color": phase["onCorrect"]["highlight"]["color"],
                "role": phase["onCorrect"]["highlight"].get("role", "")
            })

        # Add breadcrumb learnings for key phases
        if phase_id.startswith("vocabulary_type_"):
            # Extract vocab info from step data
            common_vocab = step.get("common_vocabulary", [])
            if isinstance(common_vocab, dict):
                common_vocab = [common_vocab]
            # Find which vocab this is (vocab_num from phase_id)
            try:
                vocab_idx = int(phase_id.split("_")[-1]) - 1
                if vocab_idx < len(common_vocab):
                    vocab = common_vocab[vocab_idx]
                    vocab_text = vocab.get("text", "")
                    vocab_meaning = vocab.get("meaning", "")
                    session["learnings"].append({
                        "title": f"ANCHOR: {vocab_text} = {vocab_meaning}"
                    })
            except (ValueError, IndexError):
                pass

        if phase_id.startswith("indicator_tap_"):
            # Find which indicator was found
            indicators = step.get("expected_indicators", [])
            if matched_indicator:
                # Find the indicator that matches
                for ind in indicators:
                    if ind.get("indices") == list(matched_indicator):
                        ind_text = ind.get("text", "")
                        operation = ind.get("operation", "wordplay")
                        session["learnings"].append({
                            "title": f"INDICATOR: {ind_text} ({operation})"
                        })
                        break

        # Check if this is a solve phase (definition approach)
        if phase_id == "solve" and step["type"] == "standard_definition":
            # User solved from definition - add hypothesis breadcrumb to learnings
            answer = clue.get("clue", {}).get("answer", "")
            session["learnings"].append({
                "title": f"HYPOTHESIS: {answer}"
            })
            # Advance past the standard_definition step to the next step
            session["step_index"] += 1
            session["phase_index"] = 0
            session["answer_known"] = True  # Flag that user already knows answer
            return {
                "correct": True,
                "render": get_render(clue_id, clue)
            }

        # Advance to next phase
        session["phase_index"] += 1
        if session["phase_index"] >= len(phases):
            session["step_index"] += 1
            session["phase_index"] = 0

        return {
            "correct": True,
            "render": get_render(clue_id, clue)
        }
    else:
        message = phase.get("onWrong", {}).get("message", "Try again")
        return {
            "correct": False,
            "message": substitute_variables(message, step, session, clue),
            "render": get_render(clue_id, clue)
        }

def handle_continue(clue_id, clue):
    """Handle continue button press."""
    session = _sessions.get(clue_id)
    if not session:
        return {"error": "No session"}

    steps = clue.get("steps", [])

    # Handle clue type identification step (step_index == -1)
    if session["step_index"] == -1:
        step = build_clue_type_step(clue)
        phases = STEP_TEMPLATES["clue_type_identify"]["phases"]
    else:
        step = steps[session["step_index"]]
        phases = get_step_phases(step, clue)

    phase = phases[session["phase_index"]]

    # If this is a teaching phase, capture the learning
    if phase["id"] == "teaching" and "panel" in phase:
        learning_text = substitute_variables(phase["panel"].get("instruction", ""), step, session, clue)
        learning_title = None  # Will be set later if custom title needed

        # Apply special handling for various step types
        if step["type"] == "wordplay_overview":
            learning_text = None  # Skip - already shown in individual breadcrumbs
        elif step["type"] == "deletion_discover":
            fodder_word = step.get("fodder_word", {}).get("text", "")
            fodder_synonym = step.get("fodder_synonym", "")
            result = step.get("result", "")
            learning_text = f"{fodder_word} = {fodder_synonym}, shortened = {result}\n\n**Remember:** Deletion indicators often require finding a synonym first, then shortening it."
        elif step["type"] == "container_verify":
            inner = step.get("inner", "")
            result = step.get("result", "")
            inner_upper = inner.upper()
            result_upper = result.upper()
            idx = result_upper.find(inner_upper)
            if idx > 0:
                before = result_upper[:idx]
                after = result_upper[idx + len(inner_upper):]
                split_display = f"{before} + {inner_upper} + {after}"
            else:
                split_display = f"{step.get('outer', '')} around {inner}"

            definition_text = ""
            if steps and steps[0].get("type") == "standard_definition":
                definition_text = steps[0].get("expected", {}).get("text", "")

            learning_text = f"{split_display} = {result} ✓\nDefinition: \"{definition_text}\" = {result} ✓\n\n**Remember:** Container indicators (about, holds, around, inside, carries) tell you to put one piece inside another."
        elif step["type"] == "alternation_discover":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            charade_result = ""
            for s in steps:
                if s.get("type") == "charade_verify":
                    charade_result = s.get("result", "")
                    break
            definition_text = ""
            if steps and steps[0].get("type") == "standard_definition":
                definition_text = steps[0].get("expected", {}).get("text", "")
            final_answer = clue.get("clue", {}).get("answer", "")
            learning_text = f"Taking alternate letters from {fodder}: {result}\n{charade_result} + {result} = {final_answer} ✓\nDefinition: \"{definition_text}\" = {final_answer} ✓\n\n**Remember:** Alternation indicators (by turns, oddly, evenly, regularly) tell you to take every other letter."

        # Custom titles for step types that need key info in breadcrumb
        if step["type"] == "abbreviation":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learning_title = f"ABBREVIATION: {fodder} → {result}"
        elif step["type"] == "literal_phrase":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learning_title = f"LITERAL PHRASE: {fodder} → {result}"
        elif step["type"] == "synonym":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learning_title = f"SYNONYM: {fodder} → {result}"
        elif step["type"] == "deletion":
            fodder = step.get("fodder", "")
            result = step.get("result", "")
            learning_title = f"DELETION: {fodder} → {result}"
        elif step["type"] == "reversal":
            fodder = step.get("fodder", "")
            result = step.get("result", "")
            learning_title = f"REVERSAL: {fodder} → {result}"
        elif step["type"] == "letter_selection":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learning_title = f"LETTER SELECTION: {fodder} → {result}"
        elif step["type"] == "literal":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learning_title = f"LITERAL: {fodder} → {result}"
        elif step["type"] == "connector":
            fodder = step.get("fodder", {}).get("text", "")
            learning_title = f"CONNECTOR: {fodder}"
        elif step["type"] == "anagram":
            result = step.get("result", "")
            learning_title = f"ANAGRAM → {result}"
        elif step["type"] == "container":
            inner = step.get("inner", "")
            outer = step.get("outer", "")
            result = step.get("result", "")
            learning_title = f"CONTAINER: {inner} in {outer} → {result}"
        elif step["type"] == "hidden":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learning_title = f"HIDDEN: {result}"

        if learning_text:
            # Use custom title if set, otherwise use template title
            if not learning_title:
                learning_title = substitute_variables(phase["panel"].get("title", ""), step, session, clue)
            session["learnings"].append({
                "title": learning_title,
                "text": learning_text
            })

    # Advance to next phase
    session["phase_index"] += 1
    if session["phase_index"] >= len(phases):
        session["step_index"] += 1
        session["phase_index"] = 0

    return get_render(clue_id, clue)

def get_all_learnings(clue):
    """Generate all learnings for a clue (used when user solves early)."""
    learnings = []
    steps = clue.get("steps", [])
    answer = clue.get("clue", {}).get("answer", "")

    for step in steps:
        step_type = step.get("type")

        if step_type == "standard_definition":
            definition_text = step.get("expected", {}).get("text", "")
            position = step.get("position", "")
            definition_hint = clue.get("difficulty", {}).get("definition", {}).get("hint", "")

            text = f"\"{definition_text}\" is the definition (at {position})."
            if definition_hint:
                text += f"\n\n**Hint:** {definition_hint}"
            learnings.append({
                "title": "DEFINITION FOUND",
                "text": text
            })

        elif step_type == "wordplay_overview":
            # Add individual ANCHOR and INDICATOR learnings
            common_vocab = step.get("common_vocabulary", [])
            if isinstance(common_vocab, dict):
                common_vocab = [common_vocab]
            for vocab in common_vocab:
                vocab_text = vocab.get("text", "")
                vocab_meaning = vocab.get("meaning", "")
                learnings.append({
                    "title": f"ANCHOR: {vocab_text} = {vocab_meaning}"
                })

            indicators = step.get("expected_indicators", [])
            for ind in indicators:
                ind_text = ind.get("text", "")
                operation = ind.get("operation", "wordplay")
                learnings.append({
                    "title": f"INDICATOR: {ind_text} ({operation})"
                })

        elif step_type == "deletion_discover":
            fodder_word = step.get("fodder_word", {}).get("text", "")
            fodder_synonym = step.get("fodder_synonym", "")
            result = step.get("result", "")
            learnings.append({
                "title": "DELETION",
                "text": f"{fodder_word} = {fodder_synonym}, shortened = {result}\n\n**Remember:** Deletion indicators often require finding a synonym first, then shortening it."
            })

        elif step_type == "container_verify":
            inner = step.get("inner", "")
            result = step.get("result", "")
            inner_upper = inner.upper()
            result_upper = result.upper()
            idx = result_upper.find(inner_upper)
            if idx > 0:
                before = result_upper[:idx]
                after = result_upper[idx + len(inner_upper):]
                split_display = f"{before} + {inner_upper} + {after}"
            else:
                split_display = f"{step.get('outer', '')} around {inner}"

            definition_text = ""
            if steps and steps[0].get("type") == "standard_definition":
                definition_text = steps[0].get("expected", {}).get("text", "")

            learnings.append({
                "title": "CONTAINER",
                "text": f"{split_display} = {result} ✓\nDefinition: \"{definition_text}\" = {result} ✓\n\n**Remember:** Container indicators (about, holds, around, inside, carries) tell you to put one piece inside another."
            })

        elif step_type == "charade_verify":
            components = step.get("components", [])
            result = step.get("result", "")
            letters_so_far = step.get("letters_so_far", len(result))
            letters_needed = step.get("letters_needed", parse_enumeration(clue.get("clue", {}).get("enumeration", "0")))
            components_display = " + ".join(components)
            # Use SOLVED! if this completes the answer
            if letters_so_far == letters_needed:
                learnings.append({
                    "title": "SOLVED!",
                    "text": f"{components_display} = {result} ✓"
                })
            else:
                learnings.append({
                    "title": "CHARADE",
                    "text": f"{components_display} = {result} ({letters_so_far} of {letters_needed} letters)"
                })

        elif step_type == "alternation_discover":
            indicator = step.get("indicator", {}).get("text", "")
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learnings.append({
                "title": "ALTERNATION",
                "text": f"'{indicator}' on '{fodder}' = {result}"
            })

        elif step_type == "double_definition":
            definitions = step.get("definitions", [])
            def1 = definitions[0].get("text", "") if len(definitions) > 0 else ""
            def2 = definitions[1].get("text", "") if len(definitions) > 1 else ""
            result = step.get("result", "")
            learnings.append({
                "title": "DOUBLE DEFINITION",
                "text": f"Both \"{def1}\" and \"{def2}\" define {result}. No wordplay needed!"
            })

        elif step_type == "literal_phrase":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learnings.append({
                "title": f"LITERAL PHRASE: {fodder} → {result}",
                "text": f"'{fodder}' sounds like '{result}' when spoken.\n\n**Remember:** Some clues hide letters in how phrases sound when spoken conversationally."
            })

        elif step_type == "abbreviation":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            # Use metadata hint, or fall back to teaching_hints.json
            hint = step.get("hint", "") or get_teaching_hint("abbreviations", fodder,
                "Build a mental library of common cryptic abbreviations — they appear frequently!")
            learnings.append({
                "title": f"ABBREVIATION: {fodder} → {result}",
                "text": f"'{fodder}' = {result}\n\n**Hint:** {hint}"
            })

        elif step_type == "synonym":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            # Use metadata hint, or fall back to teaching_hints.json
            hint = step.get("hint", "") or get_teaching_hint("synonyms", fodder,
                "Cryptic crosswords often use unexpected synonyms. This pairing is worth remembering!")
            learnings.append({
                "title": f"SYNONYM: {fodder} → {result}",
                "text": f"'{fodder}' = {result}\n\n**Hint:** {hint}"
            })

        elif step_type == "deletion":
            indicator = step.get("indicator", {}).get("text", "")
            fodder = step.get("fodder", "")
            result = step.get("result", "")
            learnings.append({
                "title": f"DELETION: {fodder} → {result}",
                "text": f"'{indicator}' removes letters from '{fodder}' = {result}\n\n**Remember:** Deletion indicators tell you which part of a word to remove."
            })

        elif step_type == "reversal":
            indicator = step.get("indicator", {}).get("text", "")
            fodder = step.get("fodder", "")
            result = step.get("result", "")
            learnings.append({
                "title": f"REVERSAL: {fodder} → {result}",
                "text": f"'{indicator}' reverses '{fodder}' = {result}\n\n**Remember:** Reversal indicators (back, up, turned) tell you to read letters backwards."
            })

        elif step_type == "letter_selection":
            indicator = step.get("indicator", {}).get("text", "")
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learnings.append({
                "title": f"LETTER SELECTION: {fodder} → {result}",
                "text": f"'{indicator}' from '{fodder}' = {result}\n\n**Remember:** Selection indicators (head of, finally, heart of) pinpoint exact letters."
            })

        elif step_type == "literal":
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learnings.append({
                "title": f"LITERAL: {fodder} → {result}",
                "text": f"'{fodder}' = {result} (used as-is)\n\n**Remember:** Some letters contribute directly without any transformation."
            })

        elif step_type == "connector":
            fodder = step.get("fodder", {}).get("text", "")
            learnings.append({
                "title": f"CONNECTOR: {fodder}",
                "text": f"'{fodder}' is a linking word.\n\n**Remember:** Connectors join wordplay elements but don't contribute letters."
            })

        elif step_type == "anagram":
            indicator = step.get("indicator", {}).get("text", "")
            fodder = step.get("fodder", [])
            if isinstance(fodder, list):
                fodder_display = " + ".join(fodder)
            else:
                fodder_display = str(fodder)
            result = step.get("result", "")
            learnings.append({
                "title": f"ANAGRAM → {result}",
                "text": f"'{indicator}' rearranges {fodder_display} = {result}\n\n**Remember:** Anagram indicators signal that letters need shuffling."
            })

        elif step_type == "container":
            indicator = step.get("indicator", {}).get("text", "")
            inner = step.get("inner", "")
            outer = step.get("outer", "")
            result = step.get("result", "")
            learnings.append({
                "title": f"CONTAINER: {inner} in {outer} → {result}",
                "text": f"'{indicator}' puts {inner} inside {outer} = {result}\n\n**Remember:** Container indicators (in, around, holding) tell you to put one piece inside another."
            })

        elif step_type == "hidden":
            indicator = step.get("indicator", {}).get("text", "")
            fodder = step.get("fodder", {}).get("text", "")
            result = step.get("result", "")
            learnings.append({
                "title": f"HIDDEN: {result}",
                "text": f"'{indicator}' reveals {result} hidden in '{fodder}'\n\n**Remember:** Hidden word clues conceal the answer in consecutive letters across words."
            })

    return learnings


def handle_hypothesis(clue_id, clue, answer):
    """
    Handle user submitting an answer hypothesis from the answer boxes.

    If the answer matches, we:
    1. Set answer_known = True in the session
    2. Add a learning breadcrumb
    3. Return success with current render state

    If wrong, return error.
    """
    session = _sessions.get(clue_id)
    if not session:
        return {"success": False, "error": "No session"}

    expected_answer = clue.get("clue", {}).get("answer", "").upper()
    user_answer = (answer or "").upper().replace(" ", "")

    if user_answer == expected_answer.replace(" ", ""):
        # Correct! Mark answer as known
        session["answer_known"] = True

        # Add learning breadcrumb
        session["learnings"].append({
            "title": f"HYPOTHESIS: {expected_answer}",
            "text": "Answer entered correctly. Now verifying with wordplay..."
        })

        return {
            "success": True,
            "message": "Correct! Now let's verify with the wordplay...",
            "answerKnown": True,
            "render": get_render(clue_id, clue)
        }
    else:
        return {
            "success": False,
            "error": "Incorrect answer",
            "message": "That's not quite right. Try again or continue with the training steps."
        }


def solve_step(clue_id, clue):
    """
    Reveal the answer for the current step and advance to the next phase.
    Used when user gives up on a step (clicks "Solve Step" button).

    Returns the expected answer for display and advances the phase.
    """
    session = _sessions.get(clue_id)
    if not session:
        return {"success": False, "error": "No session"}

    # Get current step and phase
    step_index = session.get("step_index", -1)
    phase_index = session.get("phase_index", 0)
    steps = clue.get("steps", [])

    # Get the expected value for the current phase
    expected = None
    step = steps[step_index] if 0 <= step_index < len(steps) else {}
    step_type = step.get("type", "")

    # Determine what the expected answer is based on phase
    current_phase_id = session.get("current_phase_id", "")

    if current_phase_id == "fodder":
        # Expected is the fodder word indices - show the fodder text
        fodder = step.get("fodder", {})
        expected = fodder.get("text", "") if isinstance(fodder, dict) else str(fodder)
    elif current_phase_id == "result":
        # Expected is the result text
        expected = step.get("result", "")
    elif current_phase_id == "indicator":
        # Expected is indicator indices - show indicator text
        indicator = step.get("indicator", {})
        expected = indicator.get("text", "") if isinstance(indicator, dict) else str(indicator)
    elif current_phase_id == "select":
        # Expected is definition indices - show definition text
        exp = step.get("expected", {})
        expected = exp.get("text", "") if isinstance(exp, dict) else ""
    elif current_phase_id == "first_def" and "definitions" in step:
        expected = step["definitions"][0].get("text", "")
    elif current_phase_id == "second_def" and "definitions" in step:
        expected = step["definitions"][1].get("text", "")
    elif current_phase_id == "solve":
        expected = clue.get("clue", {}).get("answer", "")
    elif current_phase_id.startswith("vocabulary_type_"):
        vocab_num = int(current_phase_id.split("_")[-1])
        common_vocab = step.get("common_vocabulary", [])
        if isinstance(common_vocab, dict):
            common_vocab = [common_vocab]
        if vocab_num <= len(common_vocab):
            expected = common_vocab[vocab_num - 1].get("meaning", "")
    elif current_phase_id.startswith("vocabulary_tap_"):
        vocab_num = int(current_phase_id.split("_")[-1])
        common_vocab = step.get("common_vocabulary", [])
        if isinstance(common_vocab, dict):
            common_vocab = [common_vocab]
        if vocab_num <= len(common_vocab):
            expected = common_vocab[vocab_num - 1].get("text", "")
    elif current_phase_id.startswith("indicator_tap_"):
        # Find unfound indicators
        indicators = step.get("expected_indicators", [])
        found_indicators = session.get("found_indicators", [])
        for ind in indicators:
            ind_tuple = tuple(ind.get("indices", []))
            if ind_tuple not in found_indicators:
                expected = ind.get("text", "")
                break
    else:
        # Default: try to get from step.expected
        exp = step.get("expected", {})
        expected = exp.get("text", "") if isinstance(exp, dict) else ""

    # Record that the step was solved (not learned)
    session["learnings"].append({
        "title": f"REVEALED: {expected}",
        "text": f"Step answer shown. The answer was: {expected}"
    })

    # Now advance to teaching phase (simulate correct input)
    # We'll use a simulated correct answer to advance
    answer = clue.get("clue", {}).get("answer", "")

    # Try to advance by simulating the correct response
    # This handles the phase transition properly
    result = handle_input(clue_id, clue, expected if expected else "REVEALED")

    return {
        "success": True,
        "revealed": expected,
        "message": f"The answer was: {expected}",
        "render": get_render(clue_id, clue)
    }
