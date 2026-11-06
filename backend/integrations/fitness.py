"""Exercise coach tools for agents with the `fitness` mechanism: an offline, curated exercise catalog.

No network, API key, database or personal data: the tools only look up general exercise guidance
(per muscle group and fitness level) and always append safety guidelines and a medical disclaimer.
Results stay under MAX_CHARS to fit Groq's free-tier TPM cap.
CLI: `uv run python -m backend.integrations.fitness plan legs beginner [none]` | `... warmup 10`.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass

LEVELS = ("beginner", "intermediate", "advanced")
MAX_EXERCISES = 4
MAX_CHARS = 1800  # keep tool results small for Groq's free-tier TPM cap


@dataclass(frozen=True)
class Exercise:
    name: str
    equipment: str  # "none" = bodyweight only (floor, wall or pillow at most)
    rx: dict[str, str]  # level -> prescription; the keys are the levels it suits
    cues: tuple[str, ...]
    avoid: str


_ex = Exercise


B, I, A = LEVELS
E = {
    # quadriceps
    "squat": _ex("Bodyweight squat", "none", {B: "3x10-12, rest 60s", I: "3x15-20, 3s down, rest 60s"},
                 ("feet shoulder-width, knees track over toes", "sit hips back and down, chest up"),
                 "knees caving inward"),
    "split_squat": _ex("Split squat", "none",
                       {B: "2x8/leg, rest 60s", I: "3x10/leg, rest 60s", A: "3x12/leg holding dumbbells, rest 90s"},
                       ("front knee over mid-foot", "lower straight down, torso tall"), "front heel lifting"),
    "bulgarian": _ex("Bulgarian split squat", "bench", {I: "3x8/leg, rest 90s", A: "4x8/leg with dumbbells, rest 90s"},
                     ("rear foot laces-down on bench", "front shin near vertical, control the descent"),
                     "standing too close to the bench"),
    "step_up": _ex("Step-up", "step or bench",
                   {B: "2x8/leg on a low step, rest 60s", I: "3x10/leg, rest 60s", A: "3x8/leg holding dumbbells, rest 90s"},
                   ("whole foot on the step", "drive through the top leg's heel"), "pushing off the bottom foot"),
    "wall_sit": _ex("Wall sit", "none", {B: "3x20-30s hold, rest 45s", I: "3x45s, rest 45s", A: "3x60s, rest 60s"},
                    ("thighs near parallel, knees over ankles", "back flat on the wall, breathe"), "knees past toes"),
    "goblet": _ex("Goblet squat", "dumbbell", {I: "3x10, rest 90s", A: "4x8 heavier, rest 2min"},
                  ("hold the weight at your chest", "elbows inside knees at the bottom"), "rounding the lower back"),
    "jump_squat": _ex("Jump squat", "none", {I: "3x8, rest 90s", A: "4x8, rest 90s"},
                      ("land softly, knees bent", "reset between reps"), "stiff-legged landings"),
    # hamstrings
    "bridge": _ex("Glute bridge", "none", {B: "3x12, rest 45s", I: "3x15 with 2s squeeze, rest 45s"},
                  ("feet flat, hip-width", "squeeze glutes, ribs down"), "arching the lower back"),
    "rdl": _ex("Romanian deadlift", "dumbbells",
               {B: "2x10 light, rest 90s", I: "3x10, rest 90s", A: "4x8 heavier, rest 2min"},
               ("hinge at hips, soft knees", "weights close to legs, back flat"), "rounding the back"),
    "sl_rdl": _ex("Single-leg Romanian deadlift", "none",
                  {B: "2x6/leg, fingertip on a wall, rest 60s", I: "3x8/leg, rest 60s", A: "3x10/leg holding a dumbbell, rest 60s"},
                  ("hips square to the floor", "reach back with the free heel"), "twisting the hips open"),
    "slider_curl": _ex("Sliding leg curl", "towel or slider",
                       {B: "2x6, rest 60s", I: "3x8, rest 60s", A: "3x8/leg single-leg, rest 90s"},
                       ("hips lifted in a bridge", "pull heels in slowly"), "letting hips sag"),
    "good_morning": _ex("Bodyweight good morning", "none", {B: "3x12, rest 45s", I: "3x15 slow, rest 45s"},
                        ("hands behind head, soft knees", "hinge until hamstrings stretch"), "bending the spine"),
    "nordic": _ex("Nordic hamstring curl", "none", {A: "3x4-6, slow lowering, rest 2min"},
                  ("feet anchored under a sofa or by a partner", "lower as slowly as you can, push back up"),
                  "bending at the hips"),
    # glutes
    "sl_bridge": _ex("Single-leg glute bridge", "none", {I: "3x10/leg, rest 60s", A: "3x15/leg, rest 60s"},
                     ("drive through the heel", "keep hips level"), "hips dropping to one side"),
    "hip_thrust": _ex("Hip thrust", "bench + weight", {I: "3x10, rest 90s", A: "4x8 heavy, rest 2min"},
                      ("upper back on bench, chin tucked", "shins vertical at the top"), "overarching at lockout"),
    "clamshell": _ex("Clamshell", "none", {B: "2x15/side, rest 30s", I: "3x15/side with a band, rest 30s"},
                     ("lie on side, heels together", "open the knee without rolling back"), "rocking the pelvis"),
    "band_walk": _ex("Lateral band walk", "band",
                     {B: "2x10 steps each way", I: "3x12 each way", A: "3x15 each way, heavier band"},
                     ("quarter squat, band above knees", "small steps, tension stays on"), "feet snapping together"),
    "donkey_kick": _ex("Quadruped hip extension", "none", {B: "2x12/side, rest 30s", I: "3x15/side, rest 30s"},
                       ("hands under shoulders, knee bent 90°", "lift heel to ceiling with the glute"),
                       "arching the lower back"),
    "reverse_lunge": _ex("Reverse lunge", "none",
                         {B: "2x8/leg, rest 60s", I: "3x10/leg, rest 60s", A: "3x12/leg, add dumbbells if easy"},
                         ("step back, both knees ~90°", "push through the front heel"), "front knee caving in"),
    # calves
    "calf_raise": _ex("Standing calf raise", "none",
                      {B: "3x15, rest 45s", I: "3x20, 2s pause on top", A: "3x25 holding a dumbbell"},
                      ("rise onto the big toe", "lower slowly, full range"), "bouncing out of the bottom"),
    "sl_calf": _ex("Single-leg calf raise", "none", {I: "3x12/leg, rest 60s", A: "3x15/leg holding a weight, rest 60s"},
                   ("fingertips on a wall for balance", "knee straight, ankle doesn't roll out"), "rushing the reps"),
    "heel_drop": _ex("Eccentric heel drop", "step", {I: "3x15: up on two, down on one", A: "3x15/leg with a backpack load"},
                     ("heels off a step edge", "3s down below step level"), "dropping fast into the stretch"),
    "seated_calf": _ex("Bent-knee calf raise (soleus)", "none",
                       {B: "3x15, rest 45s", I: "3x20, rest 45s", A: "3x15 heavy dumbbell on knee, rest 60s"},
                       ("knees bent ~45°", "slow up and down"), "straightening the knees"),
    "tib_raise": _ex("Tibialis raise", "none", {B: "2x15", I: "3x20", A: "3x25"},
                     ("back to a wall, heels ~30cm out", "lift toes toward shins"), "using momentum"),
    "pogo": _ex("Pogo hops", "none", {A: "3x20s, rest 60s"},
                ("stiff ankles, quick ground contact", "stay on the balls of the feet"), "doing them when calves are sore"),
    # hip flexors
    "hf_stretch": _ex("Hip flexor lunge stretch", "none",
                      {B: "2x30s/side", I: "2x45s/side", A: "2x60s/side, arm overhead"},
                      ("back knee down, tuck pelvis", "squeeze the back glute, lean slightly forward"),
                      "arching the lower back"),
    "march": _ex("March / A-skip drill", "none",
                 {B: "2x10/leg slow march", I: "3x20m A-skips", A: "3x30m A-skips, quick tempo"},
                 ("knee to hip height", "tall posture, opposite arm drives"), "leaning back"),
    "slr": _ex("Lying straight-leg raise", "none",
               {B: "2x10/leg", I: "3x12/leg, 2s hold", A: "3x15/leg with ankle weight"},
               ("other knee bent, foot flat", "tighten quad, lift to the bent knee's height"), "lower back lifting"),
    "band_knee": _ex("Banded knee drive", "band", {I: "3x12/leg", A: "3x15/leg, heavier band"},
                     ("band around the foot, anchored low", "drive the knee up fast, lower slowly"),
                     "leaning the torso back"),
    "hanging_knee": _ex("Hanging knee raise", "pull-up bar", {A: "3x10, rest 60s"},
                        ("no swinging", "curl the pelvis up"), "kipping with momentum"),
    # adductors
    "add_lift": _ex("Side-lying adductor lift", "none", {B: "2x12/side", I: "3x15/side", A: "3x20/side, ankle weight optional"},
                    ("lie on side, top foot planted in front", "lift the bottom leg slowly"), "rolling backward"),
    "copenhagen": _ex("Copenhagen plank", "bench or chair",
                      {B: "3x10-15s, knee on bench", I: "3x20s, knee on bench", A: "3x20-30s, foot on bench"},
                      ("body in a straight line", "press the top leg into the bench"), "hips sagging"),
    "lateral_lunge": _ex("Lateral lunge", "none", {B: "2x8/side", I: "3x10/side", A: "3x10/side holding a dumbbell"},
                         ("sit back into one hip", "other leg straight, both feet flat"), "knee caving past the toes"),
    "squeeze": _ex("Adductor squeeze", "none", {B: "3x10 x 5s holds", I: "3x10 x 10s holds"},
                   ("pillow or ball between knees", "squeeze hard, breathe out"), "holding your breath"),
    "sumo": _ex("Sumo goblet squat", "dumbbell", {I: "3x10, rest 90s", A: "4x8, rest 90s"},
                ("wide stance, toes out", "knees follow toes"), "knees collapsing in"),
    "cossack": _ex("Cossack squat", "none", {A: "3x6/side, rest 60s"},
                   ("shift side to side low", "straight leg toes up"), "heel lifting on the bent leg"),
    # core
    "dead_bug": _ex("Dead bug", "none", {B: "2x8/side", I: "3x10/side", A: "3x10/side, slow 3s reach"},
                    ("lower back pressed to floor", "extend opposite arm and leg"), "back lifting off the floor"),
    "plank": _ex("Plank", "none", {B: "3x20-30s", I: "3x45s", A: "3x60s"},
                 ("elbows under shoulders", "squeeze glutes, straight line"), "hips sagging or piking"),
    "bird_dog": _ex("Bird dog", "none", {B: "2x8/side", I: "3x10/side, 3s hold"},
                    ("reach long, not high", "hips level"), "rotating the hips"),
    "side_plank": _ex("Side plank", "none", {B: "2x15-20s/side on knees", I: "3x30s/side", A: "3x45s/side with hip dips"},
                      ("elbow under shoulder", "hips high, body straight"), "hips drooping"),
    "pallof": _ex("Pallof press", "band", {I: "3x10/side", A: "3x12/side, heavier band"},
                  ("band anchored at chest height, stand side-on", "press out, resist rotation"), "twisting toward the anchor"),
    "hollow": _ex("Hollow hold", "none", {A: "3x20-30s"},
                  ("lower back glued to floor", "arms and legs low, shoulders up"), "back arching"),
}

GROUPS: dict[str, list[str]] = {
    "quadriceps": ["squat", "split_squat", "bulgarian", "step_up", "wall_sit", "goblet", "jump_squat"],
    "hamstrings": ["bridge", "sl_rdl", "rdl", "slider_curl", "good_morning", "nordic", "sl_bridge"],
    "glutes": ["bridge", "sl_bridge", "hip_thrust", "clamshell", "band_walk", "donkey_kick", "reverse_lunge", "step_up", "sl_rdl"],
    "calves": ["calf_raise", "sl_calf", "heel_drop", "seated_calf", "tib_raise", "pogo"],
    "hip_flexors": ["hf_stretch", "march", "slr", "band_knee", "hanging_knee"],
    "adductors": ["add_lift", "copenhagen", "lateral_lunge", "squeeze", "sumo", "cossack"],
    "core": ["dead_bug", "plank", "bird_dog", "side_plank", "pallof", "hollow"],
}
# Balanced lower-body session: priority order, tagged by muscle group; one per group first, then fill.
LEGS: list[tuple[str, str]] = [
    ("split_squat", "quadriceps"), ("bridge", "glutes"), ("sl_bridge", "glutes"), ("sl_rdl", "hamstrings"),
    ("sl_calf", "calves"), ("calf_raise", "calves"), ("bulgarian", "quadriceps"), ("step_up", "quadriceps"),
    ("squat", "quadriceps"), ("rdl", "hamstrings"), ("copenhagen", "adductors"), ("nordic", "hamstrings"),
]
MUSCLE_GROUPS = (*GROUPS, "legs")

GROUP_ALIASES = {
    "quad": "quadriceps", "quads": "quadriceps", "thigh": "quadriceps", "thighs": "quadriceps", "front thigh": "quadriceps",
    "hamstring": "hamstrings", "hammies": "hamstrings", "hammy": "hamstrings", "back thigh": "hamstrings",
    "glute": "glutes", "gluteus": "glutes", "butt": "glutes", "bum": "glutes", "buttocks": "glutes",
    "calf": "calves", "shin": "calves", "shins": "calves", "ankle": "calves", "ankles": "calves", "achilles": "calves",
    "soleus": "calves", "hip": "hip_flexors", "hips": "hip_flexors", "hip flexor": "hip_flexors", "hip flexors": "hip_flexors",
    "psoas": "hip_flexors", "adductor": "adductors", "groin": "adductors", "inner thigh": "adductors",
    "abs": "core", "ab": "core", "abdominals": "core", "stomach": "core", "trunk": "core",
    "leg": "legs", "lower body": "legs", "lower-body": "legs", "full legs": "legs", "running": "legs", "runner": "legs",
}
LEVEL_ALIASES = {
    "new": B, "novice": B, "starter": B, "easy": B, "low": B, "basic": B,
    "medium": I, "moderate": I, "mid": I, "average": I, "intermediate": I,
    "expert": A, "pro": A, "hard": A, "high": A, "elite": A, "experienced": A,
}
NO_EQUIPMENT = {"none", "no", "nothing", "bodyweight", "body weight", "no equipment", "home"}

SAFETY = (
    "Safety:\n"
    "- Warm up 5-10 min first (easy jog, leg swings).\n"
    "- Progress gradually: add no more than ~10% weekly volume.\n"
    "- Mild soreness for 1-2 days is normal; sharp, joint or worsening pain is not: stop that exercise.\n"
    "- Allow ~48h before training the same muscles hard again; sleep, hydrate and eat enough.\n"
    "- Stop a set when form breaks."
)
NOTES = {
    "quadriceps": "Knees: keep them tracking over toes; front-of-knee pain means reduce depth or load.",
    "hamstrings": "Hamstrings strain easily when sprinting: build eccentric strength slowly, avoid ballistic stretching cold.",
    "glutes": "Strong glutes stabilise knees and hips for runners; keep the pelvis level.",
    "calves": "Runners: calves and Achilles take the most load; build up slowly, and see a professional for Achilles or shin pain.",
    "hip_flexors": "Sitting a lot tightens hip flexors; avoid arching the lower back to fake range.",
    "adductors": "Groin strains come from sudden side-to-side moves: start with short holds.",
    "core": "Keep breathing; stop if you feel lower-back pain.",
    "legs": "Runners: calves/Achilles take the most load; build up slowly and keep hard leg days away from long or fast runs.",
}
DISCLAIMER = (
    "General guidance only, not medical advice. Consult a doctor or physiotherapist for injuries, pain or medical conditions."
)


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().replace("_", " ").split())


def _group(muscle_group: str) -> str:
    key = _norm(muscle_group)
    group = key.replace(" ", "_") if key.replace(" ", "_") in MUSCLE_GROUPS else GROUP_ALIASES.get(key)
    if group is None and key.endswith("s"):
        group = GROUP_ALIASES.get(key[:-1])
    if group is None:
        raise ValueError(f"Unknown muscle group '{muscle_group}'. Choose one of: {', '.join(MUSCLE_GROUPS)}.")
    return group


def _level(fitness_level: str | None) -> str:
    key = _norm(fitness_level)
    if not key:
        return B
    level = key if key in LEVELS else LEVEL_ALIASES.get(key)
    if level is None:
        raise ValueError(f"Unknown fitness level '{fitness_level}'. Choose one of: {', '.join(LEVELS)}.")
    return level


def _fits(ex: Exercise, equipment: str | None) -> bool:
    if equipment is None or ex.equipment == "none":
        return True
    return equipment not in NO_EQUIPMENT and any(word in ex.equipment for word in equipment.split())


def _pick(group: str, level: str, equipment: str | None) -> tuple[list[Exercise], str]:
    """Up to MAX_EXERCISES for the level, preferring equipment matches and (for legs) one per muscle group."""
    pool = LEGS if group == "legs" else [(key, group) for key in GROUPS[group]]
    suited = [(E[key], tag) for key, tag in pool if level in E[key].rx]
    matching = [pair for pair in suited if _fits(pair[0], equipment)]
    chosen: list[tuple[Exercise, str]] = []
    for pair in matching:  # first pass: one exercise per muscle group
        if pair[1] not in {tag for _, tag in chosen}:
            chosen.append(pair)
    chosen += [pair for pair in matching if pair not in chosen][: MAX_EXERCISES - len(chosen)]
    chosen = chosen[:MAX_EXERCISES]
    note = ""
    if len(chosen) < 3:  # too few with that equipment: top up and say what the extras need
        extras = [pair for pair in suited if pair not in chosen][: 3 - len(chosen)]
        chosen += extras
        note = (f"Note: only {len(chosen) - len(extras)} match equipment '{equipment}'; added ones need: "
                f"{', '.join(sorted({ex.equipment for ex, _ in extras}))}.\n")
    return [ex for ex, _ in chosen], note


def _format_exercise(n: int, ex: Exercise, level: str) -> str:
    gear = "bodyweight" if ex.equipment == "none" else ex.equipment
    return f"{n}. {ex.name} ({gear}): {ex.rx[level]}\n   Cues: {'; '.join(ex.cues)}. Avoid: {ex.avoid}."


def _footer(group: str) -> str:
    return f"{SAFETY}\n- {NOTES[group]}\n{DISCLAIMER}"


def exercise_plan(muscle_group: str, fitness_level: str = "beginner", equipment: str | None = None) -> str:
    group, level = _group(muscle_group), _level(fitness_level)
    gear = _norm(equipment) or None
    exercises, note = _pick(group, level, gear)
    header = f"{group.replace('_', ' ').title()} plan, {level}" + (f", equipment: {gear}" if gear else "") + "\n"
    footer = _footer(group)
    lines = [_format_exercise(i, ex, level) for i, ex in enumerate(exercises, 1)]
    while len(lines) > 3 and len(header + note + "\n".join(lines) + footer) + 2 > MAX_CHARS:
        lines.pop()
    return f"{header}{note}" + "\n".join(lines) + f"\n\n{footer}"


def runner_warmup(minutes: int = 10) -> str:
    try:
        total = min(max(int(minutes), 5), 15)
    except (TypeError, ValueError):
        raise ValueError(f"minutes must be a whole number from 5 to 15, got '{minutes}'.") from None
    jog = max(2, round(total * 0.45))
    reps = 8 if total < 10 else 10 if total < 15 else 12
    strides = 2 if total < 10 else 4
    hold = "20-30s" if total < 10 else "30-45s"
    return (
        f"Runner warm-up (~{total} min):\n"
        f"1. Easy jog or brisk walk: {jog} min\n"
        f"2. Leg swings front-back and side-side: {reps}/leg each\n"
        f"3. Walking lunges with a twist: {reps // 2 + 2}/leg\n"
        "4. High knees, butt kicks, A-skips: 2x20m each\n"
        f"5. Ankle hops: 2x15; then {strides} relaxed 20s strides, building to ~80% effort\n\n"
        f"Cool-down (~{max(5, total - 2)} min): walk 3 min, then hold each stretch {hold}, no bouncing:\n"
        "- Calves against a wall (straight and bent knee)\n"
        "- Hamstrings (heel on a low step, hinge forward)\n"
        "- Quads (standing, heel to glute, knees together)\n"
        "- Hip flexor lunge stretch\n"
        "- Glutes (figure-4, lying or seated)\n\n"
        f"{_footer('legs')}"
    )


# name -> (function spec, python fn), the LocalTools format mcp_client.run expects.
TOOLS: dict[str, tuple[dict, Callable[..., str]]] = {
    "exercise_plan": ({
        "name": "exercise_plan",
        "description": "Exercise recommendations for a muscle group: 3-4 exercises with sets/reps or holds, rest, "
        "form cues and mistakes to avoid, plus safety guidelines. Use for any leg, muscle, strength, training or "
        f"workout question. Muscle groups: {', '.join(MUSCLE_GROUPS)} (legs = balanced lower-body session, best "
        "for runners). General guidance from a fixed catalog, not diagnosis or medical advice.",
        "parameters": {
            "type": "object",
            "properties": {
                "muscle_group": {"type": "string", "description": f"One of: {', '.join(MUSCLE_GROUPS)}"},
                "fitness_level": {"type": "string", "enum": list(LEVELS), "description": "default beginner"},
                "equipment": {"type": "string", "description": "Optional, e.g. 'none' (bodyweight only), "
                              "'dumbbells', 'band', 'bench'. Omit to allow anything."},
            },
            "required": ["muscle_group"],
        },
    }, exercise_plan),
    "runner_warmup": ({
        "name": "runner_warmup",
        "description": "Dynamic warm-up before a run and a cool-down stretch routine after it, scaled to 5-15 "
        "minutes, with safety guidelines. General guidance, not medical advice.",
        "parameters": {
            "type": "object",
            "properties": {"minutes": {"type": "integer", "description": "5-15, default 10"}},
        },
    }, runner_warmup),
}


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["plan", "legs"]
    if cmd == "plan" and rest:
        print(exercise_plan(rest[0], rest[1] if len(rest) > 1 else "beginner", " ".join(rest[2:]) or None))
    elif cmd == "warmup":
        print(runner_warmup(int(rest[0]) if rest else 10))
    else:
        sys.exit("usage: python -m backend.integrations.fitness plan <muscle_group> [level] [equipment] | warmup [minutes]")
