"""
Step Display Templates for Solved View
======================================

Templates define how to render the breakdown for different wordplay patterns.
Each template specifies the display flow for a particular combination of steps.

Metadata in clues_db.json references templates by name.
Renderer looks up template and applies clue-specific data.
"""

# =============================================================================
# STEP DISPLAY TEMPLATES
# =============================================================================

STEP_DISPLAY_TEMPLATES = {

    # =========================================================================
    # CONTAINER TEMPLATES
    # =========================================================================

    "insertion_with_two_synonyms": {
        "name": "Container with two implicit synonyms",
        "description": "Both inner and outer pieces require synonym discovery",
        "example_clue": "1A: Cover up in shower? Not after nurses turn round (6) = BROLLY",
        "display_flow": [
            {
                "id": "indicator",
                "title": "📦 CONTAINER: \"{indicator}\" tells us A takes B inside (A {indicator} B)",
            },
            {
                "id": "literal_attempt",
                "title": "   Literal attempt:\n   A = \"{outer_fodder}\", B = \"{inner_fodder}\"\n   → {literal_result} = ❌ doesn't work",
            },
            {
                "id": "synonyms",
                "title": "   Need synonyms:\n   A: \"{outer_fodder}\" → {outer_result} ({outer_reasoning})\n   B: \"{inner_fodder}\" → {inner_result} ({inner_reasoning})",
            },
            {
                "id": "assembly",
                "title": "   Assembly with synonyms:\n   {assembly} ✓",
            }
        ],
        "required_fields": ["indicator", "outer", "inner", "result", "assembly"]
    },

    "insertion_with_one_synonym_outer": {
        "name": "Container with outer synonym",
        "description": "Outer piece requires synonym, inner is explicit",
        "display_flow": [
            {
                "id": "indicator",
                "title": "📦 CONTAINER: \"{indicator}\" tells us A takes B inside",
            },
            {
                "id": "inner_explicit",
                "title": "   B = \"{inner_fodder}\" → {inner_result}",
            },
            {
                "id": "outer_synonym",
                "title": "   A: \"{outer_fodder}\" → {outer_result} ({outer_reasoning})",
            },
            {
                "id": "assembly",
                "title": "   Assembly: {assembly} ✓",
            }
        ],
        "required_fields": ["indicator", "outer", "inner", "result"]
    },

    "insertion_with_one_synonym_inner": {
        "name": "Container with inner synonym",
        "description": "Inner piece requires synonym, outer is explicit",
        "display_flow": [
            {
                "id": "indicator",
                "title": "📦 CONTAINER: \"{indicator}\" tells us A takes B inside",
            },
            {
                "id": "outer_explicit",
                "title": "   A = \"{outer_fodder}\" → {outer_result}",
            },
            {
                "id": "inner_synonym",
                "title": "   B: \"{inner_fodder}\" → {inner_result} ({inner_reasoning})",
            },
            {
                "id": "assembly",
                "title": "   Assembly: {assembly} ✓",
            }
        ],
        "required_fields": ["indicator", "outer", "inner", "result"]
    },

    "insertion_explicit": {
        "name": "Container with explicit pieces",
        "description": "Both inner and outer are explicit (abbreviations, literals)",
        "display_flow": [
            {
                "id": "indicator",
                "title": "📦 CONTAINER: \"{indicator}\" tells us A takes B inside",
            },
            {
                "id": "pieces",
                "title": "   A = {outer_result}, B = {inner_result}",
            },
            {
                "id": "assembly",
                "title": "   Assembly: {assembly} ✓",
            }
        ],
        "required_fields": ["indicator", "outer", "inner", "result"]
    },

    "insertion_with_charade_inner": {
        "name": "Container with charade inner",
        "description": "Outer requires synonym, inner is formed from charade of pieces",
        "example_clue": "10A: Flatter track takes very little time (5,4) = SWEET TALK",
        "display_flow": [
            {
                "id": "indicator",
                "title": "📦 CONTAINER: \"{indicator}\" tells us A takes B inside",
            },
            {
                "id": "outer",
                "title": "   A: \"{outer_fodder}\" → {outer_result} ({outer_reasoning})",
            },
            {
                "id": "inner_pieces",
                "title": "   B built from pieces:",
            },
            {
                "id": "inner_assembly",
                "title": "   B: {inner_assembly} = {inner_result}",
            },
            {
                "id": "assembly",
                "title": "   Assembly: {assembly} ✓",
            }
        ],
        "required_fields": ["indicator", "outer", "inner", "result", "assembly"]
    },

    # =========================================================================
    # CHARADE TEMPLATES
    # =========================================================================

    "charade_simple": {
        "name": "Simple charade",
        "description": "Parts join in sequence, all explicit",
        "display_flow": [
            {
                "id": "parts",
                "title": "🔗 CHARADE: {parts_display}",
            },
            {
                "id": "assembly",
                "title": "   {assembly} ✓",
            }
        ],
        "required_fields": ["components", "result"]
    },

    "charade_with_parts": {
        "name": "Charade with mixed parts",
        "description": "Parts join in sequence, each with its own transformation",
        "example_clue": "11A: Come by five, do you mean? (5) = VISIT",
        "display_flow": [
            {
                "id": "intro",
                "title": "🔗 CHARADE: Parts join together",
            },
            {
                "id": "parts",
                "title": "   {part_display}",
                "repeat": "parts"
            },
            {
                "id": "assembly",
                "title": "   {assembly} ✓",
            }
        ],
        "required_fields": ["parts", "result", "assembly"]
    },

    "charade_with_synonyms": {
        "name": "Charade with synonyms",
        "description": "Parts join in sequence, some require synonyms",
        "display_flow": [
            {
                "id": "parts",
                "title": "🔗 CHARADE: Parts join together",
            },
            {
                "id": "each_part",
                "title": "   {part_fodder} → {part_result}",
                "repeat": "parts"
            },
            {
                "id": "assembly",
                "title": "   {assembly} ✓",
            }
        ],
        "required_fields": ["components", "result"]
    },

    # =========================================================================
    # TRANSFORMATION CHAIN TEMPLATES
    # =========================================================================

    "transformation_chain": {
        "name": "Transformation chain",
        "description": "Word transformed through multiple operations in sequence",
        "example_clue": "5D: A lot of sharp turns, I'm afraid (3) = EEK",
        "display_flow": [
            {
                "id": "intro",
                "title": "🔄 TRANSFORMATION CHAIN: Word transforms through steps",
            },
            {
                "id": "steps",
                "title": "   {step_display}",
                "repeat": "steps"
            },
            {
                "id": "final",
                "title": "   → {result} ✓",
            }
        ],
        "required_fields": ["steps", "result"]
    },

    # =========================================================================
    # SINGLE STEP TEMPLATES
    # =========================================================================

    "abbreviation": {
        "name": "Abbreviation",
        "description": "Word/phrase converts to standard abbreviation",
        "display_flow": [
            {
                "id": "abbrev",
                "title": "✂️ {fodder} → {result}",
                "hint_field": "hint"
            }
        ],
        "required_fields": ["fodder", "result"]
    },

    "synonym_explicit": {
        "name": "Explicit synonym",
        "description": "Standard/common synonym",
        "display_flow": [
            {
                "id": "synonym",
                "title": "📖 {fodder} → {result}",
            }
        ],
        "required_fields": ["fodder", "result"]
    },

    "synonym_implicit": {
        "name": "Implicit synonym",
        "description": "Clue-specific synonym requiring reasoning",
        "display_flow": [
            {
                "id": "synonym",
                "title": "📖 {fodder} → {result} ({reasoning})",
            }
        ],
        "required_fields": ["fodder", "result", "reasoning"]
    },

    "literal": {
        "name": "Literal",
        "description": "Word used as-is",
        "display_flow": [
            {
                "id": "literal",
                "title": "📝 {fodder} → {result}",
            }
        ],
        "required_fields": ["fodder", "result"]
    },

    "reversal": {
        "name": "Reversal",
        "description": "Word reversed by indicator",
        "display_flow": [
            {
                "id": "reversal",
                "title": "↩️ \"{indicator}\" reverses {fodder} → {result}",
            }
        ],
        "required_fields": ["indicator", "fodder", "result"]
    },

    "deletion": {
        "name": "Deletion",
        "description": "Letters removed from word",
        "display_flow": [
            {
                "id": "deletion",
                "title": "✂️ \"{indicator}\" removes from {fodder} → {result}",
            }
        ],
        "required_fields": ["indicator", "fodder", "result"]
    },

    "anagram": {
        "name": "Anagram",
        "description": "Letters rearranged",
        "display_flow": [
            {
                "id": "anagram",
                "title": "🔀 \"{indicator}\" rearranges {fodder} → {result}",
            }
        ],
        "required_fields": ["indicator", "fodder", "result"]
    },

    "anagram_with_fodder_pieces": {
        "name": "Anagram with fodder pieces",
        "description": "Multiple pieces combine then anagram",
        "example_clue": "12A: Concerning sight as head of office IT struggles with PC (5) = OPTIC",
        "display_flow": [
            {
                "id": "intro",
                "title": "🔀 ANAGRAM: Pieces combine then rearrange",
            },
            {
                "id": "pieces",
                "title": "   {piece_display}",
                "repeat": "pieces"
            },
            {
                "id": "anagram",
                "title": "   \"{indicator}\" rearranges {fodder_combined} → {result}",
            },
            {
                "id": "final",
                "title": "   → {result} ✓",
            }
        ],
        "required_fields": ["indicator", "pieces", "result"]
    },

    "hidden": {
        "name": "Hidden word",
        "description": "Answer hidden in consecutive letters",
        "display_flow": [
            {
                "id": "hidden",
                "title": "👁️ \"{indicator}\" reveals {result} hidden in \"{fodder}\"",
            }
        ],
        "required_fields": ["indicator", "fodder", "result"]
    },

    "hidden_reversed": {
        "name": "Reversed hidden word",
        "description": "Answer hidden reversed in consecutive letters",
        "example_clue": "23D: Pretend authority raised undue spending limits (5) = PSEUD",
        "display_flow": [
            {
                "id": "hidden",
                "title": "👁️↩️ HIDDEN REVERSED: \"{indicator}\" reveals answer hidden backwards",
            },
            {
                "id": "fodder",
                "title": "   In \"{fodder}\" find: {hidden_letters}",
            },
            {
                "id": "reverse",
                "title": "   Reversed: {hidden_letters} → {result}",
            }
        ],
        "required_fields": ["indicator", "fodder", "result"]
    },

    "letter_selection": {
        "name": "Letter selection",
        "description": "Specific letters selected from word",
        "display_flow": [
            {
                "id": "selection",
                "title": "🔤 \"{indicator}\" selects from {fodder} → {result}",
            }
        ],
        "required_fields": ["indicator", "fodder", "result"]
    },

    # =========================================================================
    # DEFINITION TEMPLATE
    # =========================================================================

    "definition": {
        "name": "Definition",
        "description": "The straight definition part of the clue",
        "display_flow": [
            {
                "id": "definition",
                "title": "📗 Definition: \"{text}\" = {answer}",
                "hint_field": "hint"
            }
        ],
        "required_fields": ["text", "answer"]
    },
}


def get_template(template_name):
    """Get a template by name, or None if not found."""
    return STEP_DISPLAY_TEMPLATES.get(template_name)


def list_templates():
    """List all available template names with descriptions."""
    return {
        name: tmpl.get("description", "")
        for name, tmpl in STEP_DISPLAY_TEMPLATES.items()
    }
