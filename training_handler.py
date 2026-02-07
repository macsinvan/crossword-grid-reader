"""
Training Handler - Interactive Teaching System for Grid Reader
=============================================================

Template-driven teaching engine for cryptic crossword clues.
Uses pre-annotated step data from clues_db.json and render
templates from render_templates.json.

Architecture:
- RAW STEP DATA: Loaded from clues_db.json (pre-annotated)
- RENDER TEMPLATES: External JSON defining phases, prompts, input modes
- ENGINE: get_render() merges step + template → UI render object

API (called from trainer_routes.py):
- start_session(clue_id, clue) - Initialize training session
- get_render(clue_id, clue) - Get current UI state
- handle_input(clue_id, clue, value) - Process user input
- handle_continue(clue_id, clue) - Advance to next phase
"""

import re
import json
import os

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_fodder_text(step, default=""):
    """
    Safely extract fodder text from a step, handling various formats:
    - dict with 'text' key: {"text": "word", "indices": [...]}
    - list of strings: ["OM", "ELECTRA"]
    - plain string: "word"
    """
    fodder = step.get("fodder", default)
    if isinstance(fodder, list):
        return " + ".join(str(f) for f in fodder)
    elif isinstance(fodder, dict):
        return fodder.get("text", default)
    else:
        return str(fodder) if fodder else default

# =============================================================================
# TEACHING HINTS - Loaded from teaching_hints.json
# =============================================================================

TEACHING_HINTS = {}

def _load_teaching_hints():
    """Load teaching hints from JSON file. Raises on failure."""
    global TEACHING_HINTS
    hints_path = os.path.join(os.path.dirname(__file__), "teaching_hints.json")
    with open(hints_path, "r") as f:
        TEACHING_HINTS = json.load(f)
    print(f"Loaded teaching hints from {hints_path}")

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

def build_learning_from_template(step, clue):
    """Build a learning dict from the template's learning block.

    Returns None if the template has no learning or learning is null.
    Uses substitute_variables() for placeholder resolution.
    """
    step_type = step.get("type", "")
    template = RENDER_TEMPLATES.get("templates", {}).get(step_type)
    if not template:
        return None

    learning_spec = template.get("learning")
    if learning_spec is None:
        return None

    # Create a dummy session for substitute_variables (it only uses session for hints)
    dummy_session = {}
    title = substitute_variables(learning_spec.get("title", ""), step, dummy_session, clue)
    text = substitute_variables(learning_spec.get("text", ""), step, dummy_session, clue)

    result = {"title": title}
    if text:
        result["text"] = text
    return result

def resolve_expected(step, phase, clue):
    """Resolve expected value from phase's expected_source declaration.

    expected_source is a dot-path into step data, with special prefixes:
      - "fodder.indices" → step["fodder"]["indices"] (falls back to step["fodder_word"]["indices"])
      - "indicator.indices" → step["indicator"]["indices"]
      - "expected.indices" → step["expected"]["indices"]
      - "definitions.0.indices" → step["definitions"][0]["indices"]
      - "result" → step["result"] (uppercased for text comparison)
      - "$answer" → clue answer (uppercased for text comparison)
    Returns None if expected_source is not declared or path doesn't resolve.
    """
    source = phase.get("expected_source")
    if not source:
        return None

    input_mode = phase.get("inputMode", "")

    # Special prefix: $answer resolves to clue answer
    if source == "$answer":
        answer = clue.get("clue", {}).get("answer", "")
        return answer.upper() if input_mode == "text" else answer

    # Split dot-path and walk the step data
    parts = source.split(".")
    obj = step
    for part in parts:
        if obj is None:
            # Fallback: "fodder.indices" can also come from "fodder_word.indices"
            if parts[0] == "fodder" and "fodder_word" in step:
                obj = step["fodder_word"]
                for fallback_part in parts[1:]:
                    if isinstance(obj, dict):
                        obj = obj.get(fallback_part)
                    elif isinstance(obj, list) and fallback_part.isdigit():
                        idx = int(fallback_part)
                        obj = obj[idx] if idx < len(obj) else None
                    else:
                        return None
                return obj
            return None
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit():
            idx = int(part)
            obj = obj[idx] if idx < len(obj) else None
        else:
            return None

    # Fodder fallback: if fodder path returned None, try fodder_word
    if obj is None and parts[0] == "fodder" and "fodder_word" in step:
        obj = step["fodder_word"]
        for part in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif isinstance(obj, list) and part.isdigit():
                idx = int(part)
                obj = obj[idx] if idx < len(obj) else None
            else:
                return None

    # For text input, uppercase the expected value
    if input_mode == "text" and isinstance(obj, str):
        return obj.upper()

    return obj

# =============================================================================
# RENDER TEMPLATES - Loaded from render_templates.json (EXTERNAL TO CODE)
# =============================================================================

RENDER_TEMPLATES = {}
RENDER_TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "render_templates.json")
RENDER_TEMPLATES_MTIME = 0

def _load_render_templates():
    """Load render templates from JSON file. Errors out if file missing or invalid."""
    global RENDER_TEMPLATES, RENDER_TEMPLATES_MTIME
    current_mtime = os.path.getmtime(RENDER_TEMPLATES_PATH)
    with open(RENDER_TEMPLATES_PATH, "r") as f:
        RENDER_TEMPLATES = json.load(f)
    RENDER_TEMPLATES_MTIME = current_mtime
    print(f"Loaded render_templates.json ({len(RENDER_TEMPLATES.get('templates', {}))} templates, mtime: {current_mtime})")

def maybe_reload_render_templates():
    """Check if render_templates.json has been modified and reload if needed."""
    current_mtime = os.path.getmtime(RENDER_TEMPLATES_PATH)  # raises OSError if deleted
    if current_mtime != RENDER_TEMPLATES_MTIME:
        print(f"[Auto-reload] render_templates.json changed, reloading...")
        _load_render_templates()

# Load on module import — error out if missing
_load_render_templates()

# =============================================================================
# CLUE TYPE IDENTIFICATION
# =============================================================================
# STEP_TEMPLATES, STEP_TO_CLUE_TYPE, and CLUE_TYPE_OPTIONS are now in
# render_templates.json under "templates", "clue_type.step_to_clue_type",
# and "clue_type.options" respectively.


def get_clue_type(clue):
    """Determine the clue type from the first step."""
    steps = clue.get("steps", [])
    if not steps:
        return "standard"
    first_step_type = steps[0].get("type", "")
    return RENDER_TEMPLATES.get("clue_type", {}).get("step_to_clue_type", {}).get(first_step_type, "standard")

def build_clue_type_step(clue):
    """Build a synthetic clue_type_identify step with correct answer."""
    correct_type = get_clue_type(clue)
    options = []
    for opt in RENDER_TEMPLATES.get("clue_type", {}).get("options", []):
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


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

_sessions = {}  # clue_id -> session state

def start_session(clue_id, clue, cross_letters=None, enumeration=None):
    """Initialize a new training session."""
    _sessions[clue_id] = {
        "clue_id": clue_id,
        "step_index": -2,  # Start at -2 for step menu, -1 for clue type, 0+ for steps
        "phase_index": 0,
        "highlights": [],
        "learnings": [],
        "answer_known": False,  # True if user solved from definition (now reviewing wordplay)
        "completed_steps": [],  # Track completed step indices for status indicators
        # UI state (server-driven, client is dumb)
        "selected_indices": [],  # Words selected in tap_words mode
        "user_answer": [],  # Letters typed in answer boxes
        "step_text_input": [],  # Letters typed in step input boxes
        "hint_visible": False,  # Whether hint is shown
        "answer_locked": False,  # Whether answer boxes are locked (correct answer typed)
        # Step menu state (server-driven completion tracking)
        "menu_completed_items": {},  # idx_str -> {"title": "DEFINITION: ..."}
        "menu_selected_words": {},  # idx_str -> [word_idx, ...] for partially-completed tap_words
        # Grid context (passed from client, stored for all renders)
        "cross_letters": cross_letters or [],
        "enumeration": enumeration or clue.get("clue", {}).get("enumeration", "")
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


def reset_step_ui_state(session):
    """Reset UI state when advancing to a new step.

    Called when step_index changes to clear step-specific state like
    hint visibility, selections, and text input.
    """
    session["selected_indices"] = []
    session["step_text_input"] = []
    session["hint_visible"] = False
    # Note: user_answer and answer_locked persist across steps (answer boxes)
    return False

# =============================================================================
# RENDER
# =============================================================================

def evaluate_condition(condition, step, clue):
    """Evaluate a condition string against step and clue data.

    Format: "dotpath == value" or "dotpath != value"
    dotpath walks clue data first, then step data.
    Example: "difficulty.recommendedApproach == definition"
    """
    if not condition:
        return True

    # Parse "path == value" or "path != value"
    for op in ["!=", "=="]:
        if op in condition:
            path, expected_value = [s.strip() for s in condition.split(op, 1)]
            # Walk the dot-path in clue first, then step
            parts = path.split(".")
            obj = clue
            for part in parts:
                if isinstance(obj, dict):
                    obj = obj.get(part)
                else:
                    obj = None
                    break
            if obj is None:
                # Try step data
                obj = step
                for part in parts:
                    if isinstance(obj, dict):
                        obj = obj.get(part)
                    else:
                        obj = None
                        break
            result = str(obj) == expected_value if obj is not None else False
            return result if op == "==" else not result

    return True  # No recognized operator, treat as always true


def expand_template_phases(template, step, clue):
    """Expand template phases, handling condition and repeat_for directives.

    - condition: phase is only included if condition evaluates to True
    - repeat_for: generates N copies of sub-phases, one per item in the array
    """
    raw_phases = template.get("phases", [])
    expanded = []

    for phase in raw_phases:
        # Check condition
        condition = phase.get("condition")
        if condition and not evaluate_condition(condition, step, clue):
            continue

        # Handle repeat_for
        repeat_for = phase.get("repeat_for")
        if repeat_for:
            items = step.get(repeat_for, [])
            if isinstance(items, dict):
                items = [items]
            sub_phases = phase.get("phases", [])
            for i, item in enumerate(items):
                n = i + 1
                for sub in sub_phases:
                    # Deep copy and substitute {n} in IDs
                    expanded_sub = {}
                    for k, v in sub.items():
                        if isinstance(v, str):
                            expanded_sub[k] = v.replace("{n}", str(n))
                        else:
                            expanded_sub[k] = v
                    # Attach the repeat item data for runtime resolution
                    expanded_sub["_repeat_index"] = i
                    expanded_sub["_repeat_item"] = item
                    expanded.append(expanded_sub)
            continue

        expanded.append(phase)

    return expanded


def get_step_phases(step, clue):
    """Get phases for a step from template, expanding directives if present."""
    step_type = step.get("type")
    template = RENDER_TEMPLATES.get("templates", {}).get(step_type)
    if not template:
        return []

    raw_phases = template.get("phases", [])

    # Check if template has any directives (condition, repeat_for, options_generator)
    has_directives = any(
        p.get("condition") or p.get("repeat_for") or p.get("options_generator")
        for p in raw_phases
    )

    if has_directives:
        return expand_template_phases(template, step, clue)

    return raw_phases

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
    for key in ["result", "inner", "outer"]:
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

    # Build hint_suffix for standard_definition teaching
    definition_hint = step.get("hint", "")
    subs["hint_suffix"] = f"\n\n**Hint:** {definition_hint}" if definition_hint else ""

    # Provide definition_text from clue's first step (for teaching summaries)
    if clue:
        clue_steps = clue.get("steps", [])
        if "definition_text" not in subs:
            if clue_steps and clue_steps[0].get("type") == "standard_definition":
                subs["definition_text"] = clue_steps[0].get("expected", {}).get("text", "")
    # Handle indicator
    if "indicator" in step:
        ind = step["indicator"]
        if isinstance(ind, dict):
            subs["indicator"] = ind.get("text", "")
        else:
            subs["indicator"] = str(ind)

    # Handle fodder
    if "fodder" in step:
        f = step["fodder"]
        if isinstance(f, dict):
            subs["fodder"] = f.get("text", "")
        else:
            subs["fodder"] = str(f)

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

    # Perform substitution
    for key, val in subs.items():
        text = text.replace("{" + key + "}", str(val))

    return text

def _fmt(template_str, vars_dict):
    """Simple {var} substitution for template strings from render_templates.json."""
    result = template_str
    for key, val in vars_dict.items():
        result = result.replace("{" + key + "}", str(val))
    return result

def _build_step_vars(step, clue=None):
    """Extract all template variables from step data in one place."""
    step_type = step.get("type", "")
    indicator = step.get("indicator", {})
    outer = step.get("outer", {})
    inner = step.get("inner", {})
    result = step.get("result", "")
    answer = clue.get("clue", {}).get("answer", "") if clue else ""
    enumeration = clue.get("clue", {}).get("enumeration", "") if clue else ""

    return {
        "step_type": step_type,
        "step_type_title": step_type.replace("_", " ").title(),
        "ind_text": indicator.get("text", "") if isinstance(indicator, dict) else "",
        "outer_fodder": outer.get("fodder", {}).get("text", "") if isinstance(outer, dict) else "",
        "inner_fodder": inner.get("fodder", {}).get("text", "") if isinstance(inner, dict) else "",
        "outer_fodder_text": outer.get("fodder", {}).get("text", "") if isinstance(outer, dict) else "",
        "inner_fodder_text": inner.get("fodder", {}).get("text", "") if isinstance(inner, dict) else "",
        "assembly": step.get("assembly", ""),
        "result": result,
        "expected_text": step.get("expected", {}).get("text", ""),
        "position": step.get("position", "start"),
        "answer_length": len(answer.replace(" ", "")) if answer else 0,
        "enumeration": enumeration,
        "fodder_combined": step.get("fodder_combined", ""),
        # For assembly failure_message vars (charade)
        "raw_parts_display": "",
        "raw_text_upper": "",
        "raw_length": 0,
        "expected_length": len(result.replace(" ", "")) if result else 0,
    }


def _build_element_vars(element, index):
    """Extract template variables from a repeating element (part/piece/chain step)."""
    if not isinstance(element, dict):
        return {"n": index}
    fodder = element.get("fodder", "")
    fodder_text = fodder.get("text", "") if isinstance(fodder, dict) else str(fodder)
    part_type = element.get("type", "transform")
    return {
        "n": index,
        "fodder_text": fodder_text,
        "part_type": part_type,
        "part_role": part_type.title(),
        "chain_result": element.get("result", ""),
        "step_type_name": part_type,
        "step_type_title": part_type.title(),
        "step_type_upper": part_type.upper(),
        "reasoning": element.get("reasoning", ""),
    }


def _resolve_expected(step, sub_step):
    """Map sub_step name to expected_indices from step data."""
    if sub_step == "indicator":
        return step.get("indicator", {}).get("indices", [])
    elif sub_step == "outer":
        return step.get("outer", {}).get("fodder", {}).get("indices", [])
    elif sub_step == "inner":
        return step.get("inner", {}).get("fodder", {}).get("indices", [])
    elif sub_step.startswith("part_"):
        part_idx = int(sub_step.split("_")[1]) - 1
        parts = step.get("parts", [])
        if part_idx < len(parts):
            return parts[part_idx].get("fodder", {}).get("indices", [])
    elif sub_step.startswith("piece_"):
        piece_idx = int(sub_step.split("_")[1]) - 1
        pieces = step.get("pieces", [])
        if piece_idx < len(pieces):
            return pieces[piece_idx].get("fodder", {}).get("indices", [])
    # Fallback for select-type steps
    return step.get("expected", {}).get("indices", [])


def _make_menu_item(sub_cfg, v, index, step, clue):
    """Build a single menu item from a sub-step config and variables."""
    sub_step = _fmt(sub_cfg.get("sub_step_template", sub_cfg.get("sub_step", "")), v)
    expanded_type = sub_cfg.get("expanded_type", "tap_words")

    hint = _fmt(sub_cfg.get("hint", ""), v)
    # Fall back to element reasoning if JSON hint is empty
    if not hint:
        hint = v.get("reasoning", "") or step.get("reasoning", "")

    item = {
        "index": index,
        "title": _fmt(sub_cfg.get("title", ""), v),
        "type": _fmt(sub_cfg.get("type", step.get("type", "")), v),
        "step_data": step,
        "sub_step": sub_step,
        "hint": hint,
        "expanded_type": expanded_type,
        "completion_title": _fmt(sub_cfg.get("completion_title", ""), v),
    }

    # Add expected_indices for tap_words items
    if expanded_type in ("tap_words", "tap_words_with_fallback_button"):
        item["expected_indices"] = _resolve_expected(step, sub_step)

    # Add assembly_config for assembly items
    if expanded_type == "assembly":
        item["assembly_config"] = _build_assembly_config(step, clue)

    # Add fallback_button if specified
    if "fallback_button_label" in sub_cfg:
        item["fallback_button"] = {"label": sub_cfg["fallback_button_label"]}

    return item


def _get_assembly_parts(step):
    """Return uniform parts list for assembly config: [{fodder_text, part_type, part_role, length}]."""
    step_type = step.get("type", "")
    if step_type == "container":
        outer = step.get("outer", {})
        inner = step.get("inner", {})
        outer_result = outer.get("result", "") if isinstance(outer, dict) else ""
        inner_result = inner.get("result", "") if isinstance(inner, dict) else ""
        outer_fodder = outer.get("fodder", {}).get("text", "") if isinstance(outer, dict) else ""
        inner_fodder = inner.get("fodder", {}).get("text", "") if isinstance(inner, dict) else ""
        return [
            {"fodder_text": outer_fodder, "part_type": "outer", "part_role": "Outer", "length": len(outer_result.replace(" ", ""))},
            {"fodder_text": inner_fodder, "part_type": "inner", "part_role": "Inner", "length": len(inner_result.replace(" ", ""))},
        ]
    elif step_type == "charade":
        parts = step.get("parts", [])
        result = []
        for p in parts:
            part_result = p.get("result", "")
            part_type = p.get("type", "transformation")
            fodder = p.get("fodder", "")
            fodder_text = fodder.get("text", "") if isinstance(fodder, dict) else str(fodder)
            result.append({"fodder_text": fodder_text, "part_type": part_type, "part_role": part_type.title(), "length": len(part_result.replace(" ", ""))})
        return result
    return []


def _build_assembly_config(step, clue=None):
    """Build assembly_config for assembly items. Unified for container and charade."""
    step_type = step.get("type", "")
    result = step.get("result", "")
    enumeration = clue.get("clue", {}).get("enumeration", "") if clue else ""
    asm_cfg = RENDER_TEMPLATES.get("assembly_config", {})
    type_cfg = asm_cfg.get(step_type, {})

    raw_parts = _get_assembly_parts(step)
    v = _build_step_vars(step, clue)

    # Compute charade-specific failure vars
    if step_type == "charade":
        parts = step.get("parts", [])
        raw_text = "".join(p.get("fodder", {}).get("text", "") if isinstance(p.get("fodder"), dict) else str(p.get("fodder", "")) for p in parts)
        v["raw_parts_display"] = " + ".join(p.get("fodder", {}).get("text", "") if isinstance(p.get("fodder"), dict) else str(p.get("fodder", "")) for p in parts)
        v["raw_text_upper"] = raw_text.upper()
        v["raw_length"] = len(raw_text.replace(" ", ""))

    return {
        "instruction": _fmt(asm_cfg.get("instruction", ""), v),
        "final_label": _fmt(asm_cfg.get("final_label", ""), {"enumeration": enumeration}),
        "final_parts": [len(p) for p in result.split(" ")] if result else [0],
        "failure_message": _fmt(type_cfg.get("failure_message", ""), v),
        "parts": [
            {"label": _fmt(type_cfg.get("part_label", ""), {**v, **pv}), "length": pv["length"]}
            for pv in raw_parts
        ],
    }


def _expand_step_to_menu_items(step, base_index, clue=None):
    """
    Expand a step into atomic menu items using JSON config.
    All step types use the same generic loop over JSON arrays.
    """
    step_type = step.get("type", "")
    template = step.get("template", "")
    menu_cfg = RENDER_TEMPLATES.get("menu_items", {})

    # Find config: type-specific template, type default, or global default
    type_cfg = menu_cfg.get(step_type, menu_cfg.get("default", []))
    if isinstance(type_cfg, dict):
        # Nested by template name (container, charade, etc.)
        sub_steps = type_cfg.get(template, type_cfg.get("default", menu_cfg.get("default", [])))
    else:
        # Direct array (standard_definition, default)
        sub_steps = type_cfg

    # Normalize to array
    if isinstance(sub_steps, dict):
        sub_steps = [sub_steps]

    v = _build_step_vars(step, clue)
    items = []
    counter = 1

    for sub_cfg in sub_steps:
        repeat_for = sub_cfg.get("repeat_for")
        if repeat_for:
            elements = step.get(repeat_for, [])
            for i, element in enumerate(elements, 1):
                if isinstance(element, dict):
                    ev = _build_element_vars(element, i)
                    idx = f"{base_index}.{counter}"
                    items.append(_make_menu_item(sub_cfg, {**v, **ev}, idx, step, clue))
                    counter += 1
        else:
            idx = f"{base_index}.{counter}" if len(sub_steps) > 1 else base_index
            items.append(_make_menu_item(sub_cfg, v, idx, step, clue))
            counter += 1

    return items

def _build_menu_render(session, clue):
    """
    Builds menu view showing all steps with status indicators.
    Template-driven: generates step titles from step types and data.
    Auto-expands template-based steps into atomic menu items.
    """
    steps_data = clue.get("steps", [])
    menu_items = []
    all_word_indices = set(range(len(clue.get("words", []))))
    used_indices = set()

    for idx, step in enumerate(steps_data):
        # Expand step into atomic menu items
        expanded_items = _expand_step_to_menu_items(step, idx, clue)

        for item in expanded_items:
            # Determine status based on completed steps
            # For now, all atomic steps start as pending
            item["status"] = "pending"

            # Compute available word indices (all words except already used)
            item["available_indices"] = sorted(list(all_word_indices - used_indices))

            menu_items.append(item)

        # After each step, mark its indices as used
        # Collect all indices referenced in this step
        step_indices = set()
        if step.get("type") == "standard_definition":
            step_indices.update(step.get("expected", {}).get("indices", []))
        elif step.get("type") == "container":
            if "indicator" in step:
                step_indices.update(step.get("indicator", {}).get("indices", []))
            if "outer" in step:
                step_indices.update(step.get("outer", {}).get("fodder", {}).get("indices", []))
            if "inner" in step:
                step_indices.update(step.get("inner", {}).get("fodder", {}).get("indices", []))
        elif step.get("type") == "charade":
            for part in step.get("parts", []):
                if isinstance(part, dict) and "fodder" in part:
                    step_indices.update(part.get("fodder", {}).get("indices", []))
        elif step.get("type") == "anagram":
            for piece in step.get("pieces", []):
                if isinstance(piece, dict):
                    step_indices.update(piece.get("indices", []))

        used_indices.update(step_indices)

    # Apply completed status and selected words from session state
    completed = session.get("menu_completed_items", {})
    selected = session.get("menu_selected_words", {})
    for idx, item in enumerate(menu_items):
        idx_str = str(idx)
        if idx_str in completed:
            item["status"] = "completed"
            item["title"] = completed[idx_str]["title"]
        # Include currently selected words for partially-completed items
        if idx_str in selected:
            item["selected_words"] = selected[idx_str]

    return {
        "mode": "step_menu",
        "inputMode": "none",
        "menuItems": menu_items,
        "words": clue.get("words", []),
        "answer": clue.get("clue", {}).get("answer", ""),
        "userAnswer": session.get("user_answer", []),
        "enumeration": session.get("enumeration", ""),
        "crossLetters": session.get("cross_letters", []),
        "answerLocked": session.get("answer_locked", False),
        "actionPrompt": "Click any step to begin",
        "button": {"label": "Start", "action": "start_first_step"}
    }

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
        # Build breakdown for summary display
        breakdown, techniques, definition = build_breakdown(steps)
        # Get difficulty ratings for summary
        difficulty = clue.get("difficulty", {})
        return {
            "complete": True,
            "highlights": session["highlights"],
            "answer": answer,
            "actionPrompt": "Solved!",
            "learnings": session.get("learnings", []),
            "inputMode": "none",
            # Include UI state for answer display
            "userAnswer": session.get("user_answer", []),
            "answerLocked": session.get("answer_locked", False),
            "crossLetters": session.get("cross_letters", []),
            "enumeration": enumeration,
            "words": clue.get("words", []),
            # Summary/breakdown data
            "breakdown": breakdown,
            "techniques": techniques,
            "definition": definition,
            # Difficulty ratings for plain English summary
            "difficulty": difficulty
        }

    # Handle step menu (step_index == -2)
    if session["step_index"] == -2:
        return _build_menu_render(session, clue)

    # Handle clue type identification step (step_index == -1)
    if session["step_index"] == -1:
        step = build_clue_type_step(clue)
        phases = RENDER_TEMPLATES["templates"]["clue_type_identify"]["phases"]
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
        if phase.get("id") == "solve":
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
        "words": clue.get("words", []),  # Include words array for UI to display
        # UI state (server-driven, client is dumb)
        "selectedIndices": session.get("selected_indices", []),
        "userAnswer": session.get("user_answer", []),
        "stepTextInput": session.get("step_text_input", []),
        "hintVisible": session.get("hint_visible", False),
        "answerLocked": session.get("answer_locked", False),
        # Grid context (stored in session)
        "crossLetters": session.get("cross_letters", []),
        "enumeration": session.get("enumeration", enumeration)
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

    # Fodder phase: use plural variants when multiple words expected
    if phase["id"] == "fodder" and "instruction_plural" in phase.get("panel", {}):
        fodder_indices = step.get("fodder", {}).get("indices", [])
        word_count = len(fodder_indices)
        if word_count > 1:
            v = {"word_count": word_count}
            render["panel"]["instruction"] = _fmt(phase["panel"]["instruction_plural"], v)
            if "actionPrompt_plural" in phase:
                render["actionPrompt"] = _fmt(phase["actionPrompt_plural"], v)

    # Add expected for validation
    input_mode = phase.get("inputMode", "")
    if input_mode in ("tap_words", "text"):
        phase_id = phase["id"]

        # Resolve expected from phase's expected_source declaration
        resolved = resolve_expected(step, phase, clue)
        if resolved is not None:
            render["expected"] = resolved

        # Add autoCheck flag for single-word tap_words
        if input_mode == "tap_words":
            if "expected" in render and isinstance(render["expected"], list) and len(render["expected"]) == 1:
                render["autoCheck"] = True
            else:
                render["autoCheck"] = False
    elif input_mode == "multiple_choice":
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

# =============================================================================
# MENU NAVIGATION
# =============================================================================

def handle_menu_selection(clue_id, clue, step_index):
    """
    Jump to selected step from menu.
    """
    session = get_session(clue_id)
    if not session:
        return {"error": "No session"}

    session["step_index"] = step_index
    session["phase_index"] = 0
    reset_step_ui_state(session)

    return get_render(clue_id, clue)

def return_to_menu(clue_id, clue):
    """
    Return to step menu from any step.
    """
    session = get_session(clue_id)
    if not session:
        return {"error": "No session"}

    session["step_index"] = -2
    session["phase_index"] = 0
    return get_render(clue_id, clue)


def handle_menu_action(clue_id, clue, action, data):
    """
    Handle user interactions within the step menu (word clicks, assembly checks,
    fallback buttons). Validates input server-side and updates menu completion state.

    Returns updated menu render on success, or {correct: false} for wrong answers.
    """
    session = get_session(clue_id)
    if not session:
        return {"error": "No session"}

    # Rebuild menu items to access expected_indices and completion_title
    steps_data = clue.get("steps", [])
    menu_items = []
    for idx, step in enumerate(steps_data):
        expanded_items = _expand_step_to_menu_items(step, idx, clue)
        menu_items.extend(expanded_items)

    item_idx = data.get("item_idx")
    if item_idx is None or item_idx < 0 or item_idx >= len(menu_items):
        return {"error": f"Invalid item_idx: {item_idx}"}

    menu_item = menu_items[item_idx]
    idx_str = str(item_idx)

    if action == "word_click":
        word_idx = data.get("word_idx")
        if word_idx is None:
            return {"error": "Missing word_idx"}

        expected_indices = menu_item.get("expected_indices", [])

        if word_idx in expected_indices:
            # Correct word - add to selected words for this item
            if idx_str not in session["menu_selected_words"]:
                session["menu_selected_words"][idx_str] = []
            if word_idx not in session["menu_selected_words"][idx_str]:
                session["menu_selected_words"][idx_str].append(word_idx)

            # Check if all expected words are now selected
            selected = set(session["menu_selected_words"][idx_str])
            if set(expected_indices) == selected:
                # Step completed - store completion title and clear selected words
                session["menu_completed_items"][idx_str] = {
                    "title": menu_item.get("completion_title", menu_item.get("title", ""))
                }
                del session["menu_selected_words"][idx_str]

            return _build_menu_render(session, clue)
        else:
            # Wrong word - return error for ephemeral flash
            return {"correct": False, "flash_word_idx": word_idx}

    elif action == "assembly_check":
        parts_input = data.get("parts", [])
        result_input = data.get("result", "").upper().replace(" ", "")

        step_data = menu_item.get("step_data", {})
        result_expected = (step_data.get("result", "") or "").upper().replace(" ", "")

        # Build expected parts based on step type
        part_expected = []
        if step_data.get("outer") and step_data.get("inner"):
            # Container: outer and inner
            part_expected.append(
                (step_data["outer"].get("result", "") or "").upper().replace(" ", "")
            )
            part_expected.append(
                (step_data["inner"].get("result", "") or "").upper().replace(" ", "")
            )
        elif step_data.get("parts"):
            # Charade: multiple parts
            for part in step_data["parts"]:
                part_expected.append(
                    (part.get("result", "") or "").upper().replace(" ", "")
                )

        # Validate all parts
        parts_correct = len(parts_input) == len(part_expected) and all(
            p.upper().replace(" ", "") == e for p, e in zip(parts_input, part_expected)
        )
        result_correct = result_input == result_expected

        if parts_correct and result_correct:
            # Mark as completed
            session["menu_completed_items"][idx_str] = {
                "title": menu_item.get("completion_title", f"ASSEMBLY: <strong>{result_expected}</strong>")
            }
            render = _build_menu_render(session, clue)
            render["apply_to_grid"] = True
            return render
        else:
            return {"correct": False}

    elif action == "fallback_button":
        # Mark as completed with the pre-computed completion title
        session["menu_completed_items"][idx_str] = {
            "title": menu_item.get("completion_title", menu_item.get("title", ""))
        }
        return _build_menu_render(session, clue)

    else:
        return {"error": f"Unknown menu action: {action}"}


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
        phases = RENDER_TEMPLATES["templates"]["clue_type_identify"]["phases"]
    else:
        step = steps[session["step_index"]]
        phases = get_step_phases(step, clue)

    phase = phases[session["phase_index"]]

    # Determine expected value
    expected = None
    phase_id = phase["id"]

    input_mode = phase.get("inputMode", "")
    if input_mode in ("tap_words", "text"):
        # Resolve expected from phase's expected_source declaration
        resolved = resolve_expected(step, phase, clue)
        if resolved is not None:
            expected = resolved
    elif input_mode == "multiple_choice":
        # Check phase options first (for dynamically generated phases), then step options
        options = phase.get("options") or step.get("options", [])
        for i, opt in enumerate(options):
            if opt.get("correct"):
                expected = i
                break

    # Check answer
    correct = False
    if phase.get("inputMode") == "tap_words":
        if isinstance(value, list) and isinstance(expected, list):
            correct = set(value) == set(expected)
    elif phase.get("inputMode") == "text":
        if isinstance(value, str) and expected:
            user_letters = re.sub(r'[^A-Z]', '', value.upper())
            expected_letters = re.sub(r'[^A-Z]', '', expected)
            correct = user_letters == expected_letters
    elif phase.get("inputMode") == "multiple_choice":
        correct = value == expected

    if correct:
        # Add highlight if specified
        if "onCorrect" in phase and "highlight" in phase["onCorrect"]:
            highlight_indices = expected if isinstance(expected, list) else []
            session["highlights"].append({
                "indices": highlight_indices,
                "color": phase["onCorrect"]["highlight"]["color"],
                "role": phase["onCorrect"]["highlight"].get("role", "")
            })

        # Check if this is a solve phase (definition approach)
        if phase_id == "solve" and step["type"] == "standard_definition":
            # User solved from definition - add hypothesis breadcrumb to learnings (if not already added)
            answer = clue.get("clue", {}).get("answer", "")
            hypothesis_title = f"HYPOTHESIS: {answer}"
            # Avoid duplicate hypothesis entries
            if not any(l.get("title") == hypothesis_title for l in session["learnings"]):
                session["learnings"].append({
                    "title": hypothesis_title
                })
            # Advance past the standard_definition step to the next step
            session["step_index"] += 1
            session["phase_index"] = 0
            session["answer_known"] = True  # Flag that user already knows answer
            reset_step_ui_state(session)  # Clear hint, selections, etc.
            return {
                "correct": True,
                "render": get_render(clue_id, clue)
            }

        # Check if step result matches final answer (auto-populate when wordplay produces answer)
        # Do this BEFORE advancing phase, so answer is populated when going to teaching phase
        if phase_id == "result":
            step_result = step.get("result", "").upper().replace(" ", "")
            final_answer = clue.get("clue", {}).get("answer", "").upper().replace(" ", "")
            if step_result and step_result == final_answer and not session.get("answer_locked"):
                # Auto-populate and lock the answer
                session["user_answer"] = list(final_answer)
                session["answer_locked"] = True

        # Advance to next phase
        session["phase_index"] += 1
        if session["phase_index"] >= len(phases):
            session["step_index"] += 1
            session["phase_index"] = 0
            reset_step_ui_state(session)  # Clear hint, selections, etc.

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
        phases = RENDER_TEMPLATES["templates"]["clue_type_identify"]["phases"]
    else:
        step = steps[session["step_index"]]
        phases = get_step_phases(step, clue)

    phase = phases[session["phase_index"]]

    # If this is a teaching phase, capture the learning from template
    if phase["id"] == "teaching":
        learning = build_learning_from_template(step, clue)
        if learning:
            session["learnings"].append(learning)

    # Advance to next phase
    session["phase_index"] += 1
    if session["phase_index"] >= len(phases):
        # Check if the completed step's result matches the final answer
        step_result = step.get("result", "").upper()
        final_answer = clue.get("clue", {}).get("answer", "").upper()
        if step_result and step_result == final_answer and not session.get("answer_locked"):
            # Auto-populate and lock the answer
            session["user_answer"] = list(final_answer)
            session["answer_locked"] = True

        # Mark step as completed before advancing
        current_step = session["step_index"]
        if current_step >= 0 and current_step not in session["completed_steps"]:
            session["completed_steps"].append(current_step)

        session["step_index"] += 1
        session["phase_index"] = 0
        reset_step_ui_state(session)  # Clear hint, selections, etc.

    return get_render(clue_id, clue)



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

        # Add learning breadcrumb (avoid duplicates)
        hypothesis_title = f"HYPOTHESIS: {expected_answer}"
        if not any(l.get("title") == hypothesis_title for l in session["learnings"]):
            session["learnings"].append({
                "title": hypothesis_title,
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

    # Get the expected value for the current phase using declarative resolution
    step = steps[step_index] if 0 <= step_index < len(steps) else {}
    phases = get_step_phases(step, clue)
    phase = phases[phase_index] if phase_index < len(phases) else {}
    expected = resolve_expected(step, phase, clue)
    # For display purposes, convert indices to text
    if isinstance(expected, list):
        # expected is indices — get the text representation instead
        exp = step.get("expected", {})
        expected = exp.get("text", "") if isinstance(exp, dict) else str(expected)

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


def build_breakdown(steps):
    """
    Build breakdown array showing how the answer is constructed.
    Used for summary page display.

    Returns:
        tuple: (breakdown list, techniques list, definition string or None)

    Simple step types (synonym, abbreviation, reversal, deletion, letter_selection, literal)
    use the breakdown declaration from render_templates.json.
    Complex step types (charade, container, anagram, hidden, transformation_chain) have
    nested data requiring explicit handling.
    """
    breakdown = []
    techniques = []
    definition = None

    for step in steps:
        step_type = step.get("type", "")

        if step_type == "standard_definition":
            definition = step.get("expected", {}).get("text", "")
            continue

        # Check template for simple breakdown declaration
        tmpl = RENDER_TEMPLATES.get("templates", {}).get(step_type, {})
        bd = tmpl.get("breakdown")
        if bd is not None:
            # Simple type: use template declaration
            fodder = get_fodder_text(step)
            result = step.get("result", fodder if step_type == "literal" else "")
            breakdown.append({
                "type": step_type,
                "from": fodder,
                "to": result,
                "icon": bd["icon"]
            })
            technique_name = bd["technique"]
            if technique_name not in [t["name"] for t in techniques]:
                techniques.append({"name": technique_name, "icon": bd["icon"]})
            continue

        # Complex types: explicit handling for nested data structures
        if step_type == "anagram":
            template = step.get("template", "")
            indicator_obj = step.get("indicator", {})
            indicator = indicator_obj.get("text", "") if isinstance(indicator_obj, dict) else ""
            result = step.get("result", "")
            if template == "anagram_with_fodder_pieces":
                breakdown.append({
                    "type": "anagram", "template": template,
                    "indicator": indicator, "pieces": step.get("pieces", []),
                    "to": result, "assembly": step.get("assembly", ""), "icon": "🔀"
                })
            else:
                fodder_raw = step.get("fodder", {})
                if isinstance(fodder_raw, list):
                    fodder = " + ".join(str(f) for f in fodder_raw)
                elif isinstance(fodder_raw, dict):
                    fodder = fodder_raw.get("text", "")
                else:
                    fodder = str(fodder_raw)
                breakdown.append({
                    "type": "anagram", "from": fodder, "to": result,
                    "indicator": indicator, "icon": "🔀"
                })
            if "Anagram" not in [t["name"] for t in techniques]:
                techniques.append({"name": "Anagram", "icon": "🔀"})

        elif step_type == "container":
            template = step.get("template", "")
            indicator = step.get("indicator", {})
            outer_obj = step.get("outer", {})
            inner_obj = step.get("inner", {})
            result = step.get("result", "")

            if isinstance(outer_obj, dict):
                outer_fodder = outer_obj.get("fodder", {}).get("text", "")
                outer_result = outer_obj.get("result", "")
                outer_reasoning = outer_obj.get("reasoning", "")
            else:
                outer_fodder, outer_result, outer_reasoning = "", outer_obj, ""

            if isinstance(inner_obj, dict):
                if "pieces" in inner_obj:
                    inner_breakdown = inner_obj
                else:
                    inner_breakdown = {
                        "fodder": inner_obj.get("fodder", {}).get("text", ""),
                        "result": inner_obj.get("result", ""),
                        "reasoning": inner_obj.get("reasoning", "")
                    }
            else:
                inner_breakdown = {"fodder": "", "result": inner_obj, "reasoning": ""}

            breakdown.append({
                "type": "container", "template": template,
                "indicator": indicator.get("text", ""),
                "outer": {"fodder": outer_fodder, "result": outer_result, "reasoning": outer_reasoning},
                "inner": inner_breakdown, "to": result,
                "assembly": step.get("assembly", ""), "icon": "📦"
            })
            if "Container" not in [t["name"] for t in techniques]:
                techniques.append({"name": "Container", "icon": "📦"})

        elif step_type == "charade":
            breakdown.append({
                "type": "charade", "template": step.get("template", ""),
                "parts": step.get("parts", []), "to": step.get("result", ""),
                "assembly": step.get("assembly", ""), "icon": "🔗"
            })
            if "Charade" not in [t["name"] for t in techniques]:
                techniques.append({"name": "Charade", "icon": "🔗"})

        elif step_type == "transformation_chain":
            breakdown.append({
                "type": "transformation_chain", "template": step.get("template", ""),
                "steps": step.get("steps", []), "to": step.get("result", ""), "icon": "🔄"
            })
            if "Transformation" not in [t["name"] for t in techniques]:
                techniques.append({"name": "Transformation", "icon": "🔄"})

        elif step_type == "hidden":
            indicator = step.get("indicator", {})
            breakdown.append({
                "type": "hidden", "template": step.get("template", ""),
                "from": get_fodder_text(step), "to": step.get("result", ""),
                "indicator": indicator.get("text", "") if isinstance(indicator, dict) else "",
                "hidden_letters": step.get("hidden_letters", ""),
                "reasoning": step.get("reasoning", ""), "icon": "👁️"
            })
            if "Hidden word" not in [t["name"] for t in techniques]:
                techniques.append({"name": "Hidden word", "icon": "👁️"})

    return breakdown, techniques, definition


def _build_learnings_from_breakdown(breakdown):
    """Convert a breakdown list into learnings entries for display.

    Shared by reveal_answer() and get_solved_view() — the sole source of
    truth for how breakdown items become user-visible learnings.
    """
    learnings = []
    for item in breakdown:
        item_type = item["type"]
        template = item.get("template", "")

        if item_type == "charade":
            parts = item.get("parts", [])
            assembly = item.get("assembly", "")
            if template != "charade_with_parts":
                raise ValueError(f"Charade type requires a valid template. Got template='{template}' with parts={parts}")
            learnings.append({"title": "🔗 CHARADE: Parts join together", "text": ""})
            for part in parts:
                if isinstance(part, dict):
                    part_display = f"   \"{part.get('fodder', {}).get('text', '')}\" → {part.get('result', '')}"
                    if part.get("reasoning"):
                        part_display += f" ({part['reasoning']})"
                    learnings.append({"title": part_display, "text": ""})
                else:
                    learnings.append({"title": f"   {part}", "text": ""})
            learnings.append({"title": f"   {assembly} ✓", "text": ""})

        elif item_type == "transformation_chain":
            chain_steps = item.get("steps", [])
            result = item.get("to", "")
            if template != "transformation_chain":
                raise ValueError(f"Transformation chain requires a valid template. Got template='{template}'")
            learnings.append({"title": "🔄 TRANSFORMATION CHAIN: Word transforms through steps", "text": ""})
            for cs in chain_steps:
                cs_type = cs.get("type", "")
                fodder_raw = cs.get("fodder", "")
                fodder_text = fodder_raw.get("text", "") if isinstance(fodder_raw, dict) else fodder_raw
                cs_result = cs.get("result", "")
                reasoning = cs.get("reasoning", "")
                ind_raw = cs.get("indicator", {})
                ind_text = ind_raw.get("text", "") if isinstance(ind_raw, dict) else ""
                if cs_type == "synonym":
                    step_display = f"   \"{fodder_text}\" → {cs_result}"
                elif cs_type == "deletion":
                    step_display = f"   \"{ind_text}\" removes from {fodder_text} → {cs_result}"
                elif cs_type == "reversal":
                    step_display = f"   \"{ind_text}\" reverses {fodder_text} → {cs_result}"
                else:
                    step_display = f"   {fodder_text} → {cs_result}"
                if reasoning:
                    step_display += f" ({reasoning})"
                learnings.append({"title": step_display, "text": ""})
            learnings.append({"title": f"   → {result} ✓", "text": ""})

        elif item_type == "container":
            outer = item.get("outer", {})
            inner = item.get("inner", {})
            indicator = item.get("indicator", "")
            answer = item.get("to", "")
            if isinstance(outer, dict):
                outer_fodder = outer.get("fodder", "")
                outer_result = outer.get("result", "")
                outer_reasoning = outer.get("reasoning", "")
            else:
                outer_fodder, outer_result, outer_reasoning = "", outer, ""
            if isinstance(inner, dict):
                inner_fodder = inner.get("fodder", "")
                inner_result = inner.get("result", "")
                inner_reasoning = inner.get("reasoning", "")
            else:
                inner_fodder, inner_result, inner_reasoning = "", inner, ""

            if template == "insertion_with_two_synonyms":
                learnings.append({"title": f"📦 CONTAINER: \"{indicator}\" tells us A takes B inside (A {indicator} B)", "text": ""})
                outer_words = outer_fodder.upper().split()
                inner_words = inner_fodder.upper().split()
                if len(outer_words) >= 2:
                    literal_attempt = f"{outer_words[0]} + {' '.join(inner_words)} + {outer_words[-1]}"
                else:
                    literal_attempt = f"{outer_fodder.upper()} + {inner_fodder.upper()}"
                learnings.append({"title": f"   Literal attempt:\n   A = \"{outer_fodder}\", B = \"{inner_fodder}\"\n   → {literal_attempt} = ❌ doesn't work", "text": ""})
                synonym_text = f"   Need synonyms:\n   A: \"{outer_fodder}\" → {outer_result}"
                if outer_reasoning:
                    synonym_text += f" ({outer_reasoning})"
                synonym_text += f"\n   B: \"{inner_fodder}\" → {inner_result}"
                if inner_reasoning:
                    synonym_text += f" ({inner_reasoning})"
                learnings.append({"title": synonym_text, "text": ""})
                assembly = item.get("assembly", f"{outer_result[0]} + {inner_result} + {outer_result[1:]} = {answer}")
                learnings.append({"title": f"   Assembly with synonyms:\n   {assembly} ✓", "text": ""})
            elif template == "insertion_with_one_synonym_outer":
                learnings.append({"title": f"📦 CONTAINER: \"{indicator}\" tells us A takes B inside", "text": ""})
                learnings.append({"title": f"   B: \"{inner_fodder}\" → {inner_result} ({inner_reasoning})", "text": ""})
                learnings.append({"title": f"   A: \"{outer_fodder}\" → {outer_result} ({outer_reasoning})", "text": ""})
                assembly = item.get("assembly", "")
                learnings.append({"title": f"   Assembly: {assembly} ✓", "text": ""})
            elif template == "insertion_with_charade_inner":
                learnings.append({"title": f"📦 CONTAINER: \"{indicator}\" tells us A takes B inside", "text": ""})
                learnings.append({"title": f"   A: \"{outer_fodder}\" → {outer_result} ({outer_reasoning})", "text": ""})
                learnings.append({"title": "   B built from pieces:", "text": ""})
                inner_obj = item.get("inner", {})
                inner_pieces = inner_obj.get("pieces", []) if isinstance(inner_obj, dict) else []
                for piece in inner_pieces:
                    piece_fodder = piece.get("fodder", {})
                    ft = piece_fodder.get("text", "") if isinstance(piece_fodder, dict) else str(piece_fodder)
                    piece_display = f"      \"{ft}\" → {piece.get('result', '')}"
                    if piece.get("reasoning"):
                        piece_display += f" ({piece['reasoning']})"
                    learnings.append({"title": piece_display, "text": ""})
                inner_assembly = inner_obj.get("assembly", "") if isinstance(inner_obj, dict) else ""
                learnings.append({"title": f"   B: {inner_assembly}", "text": ""})
                assembly = item.get("assembly", "")
                learnings.append({"title": f"   Assembly: {assembly} ✓", "text": ""})
            else:
                raise ValueError(f"Container type requires a valid template. Got template='{template}' for container with outer={outer}, inner={inner}")

        elif item_type == "anagram":
            indicator = item.get("indicator", "")
            pieces = item.get("pieces", [])
            result = item.get("to", "")
            if template == "anagram_with_fodder_pieces":
                learnings.append({"title": "🔀 ANAGRAM: Pieces combine then rearrange", "text": ""})
                fodder_parts = []
                for piece in pieces:
                    piece_fodder = piece.get("fodder", {})
                    ft = piece_fodder.get("text", "") if isinstance(piece_fodder, dict) else str(piece_fodder)
                    fodder_parts.append(piece.get("result", ""))
                    piece_display = f"   \"{ft}\" → {piece.get('result', '')}"
                    if piece.get("reasoning"):
                        piece_display += f" ({piece['reasoning']})"
                    learnings.append({"title": piece_display, "text": ""})
                learnings.append({"title": f"   \"{indicator}\" rearranges {' + '.join(fodder_parts)} → {result}", "text": ""})
                learnings.append({"title": f"   → {result} ✓", "text": ""})
            else:
                fodder = item.get("from", "")
                learnings.append({"title": f"🔀 \"{indicator}\" rearranges {fodder} → {result}", "text": ""})

        elif item_type == "hidden":
            indicator = item.get("indicator", "")
            fodder = item.get("from", "")
            result = item.get("to", "")
            hidden_letters = item.get("hidden_letters", "")
            if template == "hidden_reversed":
                learnings.append({"title": f"👁️↩️ HIDDEN REVERSED: \"{indicator}\" reveals answer hidden backwards", "text": ""})
                learnings.append({"title": f"   In \"{fodder}\" find: {hidden_letters}", "text": ""})
                learnings.append({"title": f"   Reversed: {hidden_letters} → {result} ✓", "text": ""})
            else:
                learnings.append({"title": f"👁️ \"{indicator}\" reveals {result} hidden in \"{fodder}\"", "text": ""})

        else:
            learnings.append({"title": f"{item['icon']} {item.get('from', '')} → {item['to']}", "text": ""})

    return learnings


def _build_highlights_from_steps(steps):
    """Build highlights array from all steps for summary display.

    Shared by reveal_answer() and get_solved_view().
    """
    highlights = []
    for step in steps:
        if "fodder" in step and isinstance(step["fodder"], dict):
            highlights.append({"indices": step["fodder"].get("indices", []), "color": "BLUE"})
        if "indicator" in step and isinstance(step["indicator"], dict):
            highlights.append({"indices": step["indicator"].get("indices", []), "color": "YELLOW"})
        if "expected" in step and isinstance(step["expected"], dict):
            highlights.append({"indices": step["expected"].get("indices", []), "color": "GREEN"})
        if "outer" in step and isinstance(step["outer"], dict):
            outer_fodder = step["outer"].get("fodder", {})
            if isinstance(outer_fodder, dict) and "indices" in outer_fodder:
                highlights.append({"indices": outer_fodder.get("indices", []), "color": "BLUE"})
        if "inner" in step and isinstance(step["inner"], dict):
            inner_fodder = step["inner"].get("fodder", {})
            if isinstance(inner_fodder, dict) and "indices" in inner_fodder:
                highlights.append({"indices": inner_fodder.get("indices", []), "color": "BLUE"})
    return highlights


def reveal_answer(clue_id, clue):
    """
    Reveal the full answer and skip to the final teaching/summary step.
    Used when user gives up entirely.

    Returns a clean summary with:
    - breakdown: visual chain showing how answer is constructed
    - techniques: list of techniques used (no redundant text)
    """
    session = _sessions.get(clue_id)
    if not session:
        # Start a session if none exists
        start_session(clue_id, clue)
        session = _sessions.get(clue_id)

    steps = clue.get("steps", [])
    answer = clue.get("clue", {}).get("answer", "")

    # Use helper to build breakdown
    breakdown, techniques, definition = build_breakdown(steps)

    learnings = _build_learnings_from_breakdown(breakdown)

    # Update session to final state
    session["learnings"] = learnings
    session["step_index"] = len(steps)  # Past all steps

    highlights = _build_highlights_from_steps(steps)

    # Get difficulty ratings for summary
    difficulty = clue.get("difficulty", {})

    return {
        "success": True,
        "revealed": True,
        "answer": answer,
        "definition": definition,
        "complete": False,  # Show summary first
        "phaseId": "teaching",
        "inputMode": "none",
        "stepType": "summary",
        "button": {"label": "Done", "action": "complete"},
        "breakdown": breakdown,  # New: visual transformation chain
        "techniques": techniques,  # New: unique techniques used
        "learnings": learnings,  # Legacy format for backward compatibility
        "highlights": highlights,
        "words": clue.get("words", []),
        "difficulty": difficulty  # Difficulty ratings for plain English summary
    }


def get_solved_view(clue_id, clue):
    """
    Get the solved view for a clue - shows full breakdown immediately.
    No step-by-step interaction, just a static summary display.

    This is used for the "exploration mode" UX where users see the
    answer breakdown upfront and can explore any step.
    """
    steps = clue.get("steps", [])
    answer = clue.get("clue", {}).get("answer", "")
    clue_text = clue.get("clue", {}).get("text", "")
    enumeration = clue.get("clue", {}).get("enumeration", "")

    # Use helper to build breakdown (same as reveal_answer)
    breakdown, techniques, definition = build_breakdown(steps)

    learnings = _build_learnings_from_breakdown(breakdown)
    highlights = _build_highlights_from_steps(steps)

    # Get definition hint from standard_definition step (new schema)
    definition_hint = ""
    for step in steps:
        if step.get("type") == "standard_definition":
            definition_hint = step.get("hint", "")
            break

    return {
        "success": True,
        "mode": "solved_view",  # Tells client to use solved view renderer
        "clueText": clue_text,
        "answer": answer,
        "enumeration": enumeration,
        "definition": definition,
        "definitionHint": definition_hint,
        "breakdown": breakdown,
        "techniques": techniques,
        "learnings": learnings,
        "highlights": highlights,
        "words": clue.get("words", [])
    }


def update_ui_state(clue_id, clue, action, data):
    """
    Update UI state in session (server-driven, client is dumb).

    Actions:
    - select_word: Toggle word selection at given index
    - type_answer: Set letter at position in answer boxes
    - type_step: Set letter at position in step input boxes
    - toggle_hint: Toggle hint visibility
    - clear_selections: Clear all word selections
    - clear_answer: Clear user answer
    - clear_step_input: Clear step text input
    """
    session = _sessions.get(clue_id)
    if not session:
        return {"error": "No session", "success": False}

    answer = clue.get("clue", {}).get("answer", "").upper().replace(" ", "")

    if action == "select_word":
        index = data.get("index")
        if index is not None:
            selected = session.get("selected_indices", [])
            if index in selected:
                selected.remove(index)
            else:
                selected.append(index)
            session["selected_indices"] = selected

    elif action == "type_answer":
        position = data.get("position")
        letter = data.get("letter", "").upper()
        cross_letters = data.get("crossLetters", [])
        if position is not None:
            user_answer = session.get("user_answer", [])
            # Extend list if needed
            while len(user_answer) <= position:
                user_answer.append("")
            user_answer[position] = letter[:1] if letter else ""
            session["user_answer"] = user_answer

            # Check if answer is complete and correct (including cross letters)
            full_answer = []
            for i in range(len(answer)):
                cross = next((cl for cl in cross_letters if cl.get("position") == i), None)
                if cross and cross.get("letter"):
                    full_answer.append(cross["letter"].upper())
                elif i < len(user_answer) and user_answer[i]:
                    full_answer.append(user_answer[i].upper())
                else:
                    full_answer.append("")

            user_full = "".join(full_answer)
            if len(user_full) == len(answer) and user_full == answer:
                session["answer_locked"] = True

    elif action == "type_step":
        position = data.get("position")
        letter = data.get("letter", "").upper()
        if position is not None:
            step_input = session.get("step_text_input", [])
            while len(step_input) <= position:
                step_input.append("")
            step_input[position] = letter[:1] if letter else ""
            session["step_text_input"] = step_input

    elif action == "toggle_hint":
        session["hint_visible"] = not session.get("hint_visible", False)

    elif action == "clear_selections":
        session["selected_indices"] = []

    elif action == "clear_answer":
        session["user_answer"] = []
        session["answer_locked"] = False

    elif action == "clear_step_input":
        session["step_text_input"] = []

    # Return updated render
    result = get_render(clue_id, clue)
    result["success"] = True
    return result
