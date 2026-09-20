# JevMario — Architecture & Implementation Plan

## Goal

Modify the existing Mario game source so an AI model named **Jev** controls Mario autonomously.

Core loop:

```text
Mario Game
    ↓
Internal Game State
    ↓
Observation / State Adapter
    ↓
Structured JSON
    ↓
Jev
    ↓
Structured Action
    ↓
Action Executor
    ↓
Mario Game
    ↓
repeat
```

Because the source code is available, use the game's **internal state** instead of computer vision for the first implementation. Vision can be added later as an alternative observation provider.

---

## 1. High-Level Architecture

```text
                         ┌──────────────────┐
                         │    Mario Game    │
                         │                  │
                         │ Physics          │
                         │ Entities         │
                         │ Collision        │
                         │ Rendering        │
                         │ Game Loop        │
                         └────────┬─────────┘
                                  │
                                  │ raw internal state
                                  ▼
                         ┌──────────────────┐
                         │ Observation      │
                         │ Layer            │
                         │                  │
                         │ Game state →     │
                         │ AI observation   │
                         └────────┬─────────┘
                                  │
                                  │ structured JSON
                                  ▼
                         ┌──────────────────┐
                         │       Jev        │
                         │                  │
                         │ Decision Model   │
                         └────────┬─────────┘
                                  │
                                  │ structured action
                                  ▼
                         ┌──────────────────┐
                         │ Action Validator │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Action Executor  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    Mario Game    │
                         └──────────────────┘
                                  │
                                  └────── loop
```

---

## 2. Separate Game Loop and AI Decision Loop

Do **not** call Jev necessarily once per rendered frame.

For example:

```text
Game: 60 FPS
Jev:   ~5–20 decisions/sec
```

The game should continue running between AI decisions.

Example:

```text
Game frames:
F0 F1 F2 F3 F4 F5 F6 F7 F8 F9 ...

Jev:
    J0          J1          J2
    ↓           ↓           ↓
    RIGHT       RIGHT_JUMP  LEFT
```

Actions should preferably have a duration:

```json
{
  "action": "RIGHT",
  "duration_frames": 8
}
```

This gives actions temporal meaning and avoids unnecessary model calls.

Make the decision interval configurable.

---

## 3. Observation Layer

Create a dedicated component that extracts AI-visible state.

Conceptually:

```python
class ObservationProvider:
    def get_state(self) -> dict:
        ...
```

Initial implementation:

```python
class InternalStateProvider(ObservationProvider):
    def get_state(self) -> dict:
        ...
```

Do not tightly couple Jev to the game's internal classes.

Inspect the existing source and identify the actual classes/structures representing:

* Mario/player
* enemies
* platforms
* obstacles
* power-ups
* camera
* level
* physics
* collisions

Then normalize them into a stable AI observation schema.

---

## 4. Suggested Observation Schema

Starting example:

```json
{
  "player": {
    "x": 243,
    "y": 381,
    "vx": 2.4,
    "vy": 0,
    "grounded": true,
    "power": "fire"
  },

  "nearby": {
    "enemies": [
      {
        "type": "goomba",
        "relative_x": 67,
        "relative_y": 0,
        "vx": -1.2
      }
    ],

    "platforms": [
      {
        "relative_x": -63,
        "relative_y": 39,
        "width": 300
      }
    ],

    "powerups": []
  },

  "camera": {
    "x": 120
  },

  "level": {
    "remaining_distance": 4380
  }
}
```

This is a starting point, not a mandatory schema. Adapt it to the actual source.

### Prefer relative coordinates

Where useful, use:

```json
{
  "relative_x": 67
}
```

rather than only absolute world coordinates.

The observation should contain information useful for decision-making, not the entire raw game state.

---

## 5. State History

A single state snapshot may be ambiguous.

For example:

```text
Mario x=200
Mario y=300
```

doesn't reveal whether Mario is moving left/right or ascending/falling.

Expose velocity where available:

```json
{
  "vx": 2.4,
  "vy": -5.2
}
```

If velocity is insufficient, support a short history:

```text
state(t-4)
state(t-3)
state(t-2)
state(t-1)
state(t)
       ↓
      Jev
```

Do not implement history unless testing shows that it is necessary.

---

## 6. Jev Interface

Create a clean abstraction around the Jev API.

Conceptually:

```python
class DecisionModel:
    def decide(self, observation: dict) -> dict:
        ...
```

Then:

```python
class JevDecisionModel(DecisionModel):
    def decide(self, observation: dict) -> dict:
        ...
```

The rest of the game should not depend on Jev API implementation details.

This allows Jev to later be replaced with:

* another model
* a local model
* a rule-based controller
* an RL policy

without changing the game integration.

---

## 7. Jev Output

Jev must return **strict structured output**, not natural-language instructions.

Example:

```json
{
  "action": "RIGHT",
  "duration_frames": 8
}
```

Possible actions:

```text
LEFT
RIGHT
JUMP
FIRE
NEUTRAL
```

If the game supports simultaneous controls, use a schema such as:

```json
{
  "move": "RIGHT",
  "jump": true,
  "fire": false,
  "duration_frames": 5
}
```

Choose the smallest action schema that can fully control the game.

Every model response must be validated before execution.

---

## 8. Action Executor

Create:

```python
class ActionExecutor:
    def execute(self, action: dict) -> None:
        ...
```

It converts Jev's normalized action into the game's existing control mechanism.

Prefer using the game's existing input/controller abstraction rather than directly manipulating Pygame keyboard APIs.

Example:

```text
Jev:
RIGHT + duration=8

        ↓

Action Executor

        ↓

RIGHT held for 8 game frames
```

---

## 9. Main Control Loop

Conceptually:

```python
while game_running:

    update_game()

    if should_request_ai_decision():

        observation = observation_provider.get_state()

        action = decision_model.decide(observation)

        action_executor.execute(action)

    render_game()
```

The exact integration must respect the existing game's architecture.

Before modifying it, identify:

1. Main game loop
2. Physics update
3. Player update
4. Input processing
5. Entity storage
6. Collision system
7. Level representation
8. Game reset/death handling

---

## 10. Recommended Decision Timing

Initial target:

```text
Game FPS:        60
AI decisions:    ~10/sec
Action duration: several frames
```

Example:

```text
Jev #1:
RIGHT, 6 frames

→ execute RIGHT for 6 frames

→ collect new state

Jev #2:
RIGHT_JUMP, 8 frames

→ execute

→ collect new state

...
```

Do not hardcode this permanently. Make it configurable.

Example:

```text
AI_DECISION_INTERVAL_FRAMES=6
```

---

## 11. Implementation Phases

### Phase 1 — Run Original Game

Before modifying gameplay:

* Install dependencies.
* Run the original game.
* Confirm it starts.
* Confirm Mario can be controlled manually.
* Avoid unnecessary changes.

### Phase 2 — Source Reconnaissance

Identify:

* player class
* enemy classes
* level/platform representation
* physics
* collision
* game loop
* input handling
* camera
* power-ups
* fireballs

Document relevant classes/functions.

### Phase 3 — Internal State Extraction

Implement:

```text
InternalStateProvider
```

Initially print normalized JSON.

Do not call Jev yet.

### Phase 4 — Action Injection

Implement:

```text
ActionExecutor
```

Test with manually supplied actions.

Example:

```json
{
  "action": "RIGHT",
  "duration_frames": 30
}
```

Verify Mario responds correctly.

### Phase 5 — Jev Integration

Connect:

```text
ObservationProvider
        ↓
JevDecisionModel
        ↓
ActionExecutor
```

Keep API credentials outside source code.

### Phase 6 — Autonomous Play

Enable:

```text
observe
   ↓
Jev
   ↓
act
   ↓
wait
   ↓
observe
   ↓
...
```

### Phase 7 — Logging

Record:

* timestamp
* observation
* Jev response
* action
* duration
* Mario position
* death/restart
* level progress
* Jev latency

---

## 12. Debug Mode

Add an optional debug mode showing the AI's current state.

Example:

```text
AI STATE

Mario: (243,381)
Velocity: (2.4,0)
Grounded: YES

Nearest enemy:
Goomba +67px

Current action:
RIGHT

Duration:
5/8 frames
```

Debug rendering/logging must not change gameplay behavior.

---

## 13. Failure Handling

The AI loop must not crash the game if Jev fails.

Handle:

* API timeout
* malformed response
* invalid action
* network failure
* rate limiting
* empty response
* unexpected game state

Use a safe fallback such as:

```text
NEUTRAL
```

or a short continuation of the last valid action.

Never execute arbitrary model output as code.

---

## 14. Death / Reset Handling

Recognize game states such as:

```text
PLAYING
   ↓
DEAD
   ↓
RESET
   ↓
PLAYING
```

When Mario dies:

* clear pending actions
* reset observation history
* reset action timing
* restart the game
* resume Jev control

Do not feed stale state from the previous life into the controller.

---

## 15. Logging and Evaluation

Track at minimum:

```text
deaths
restarts
distance/progress
time alive
level completed
actions issued
Jev latency
invalid responses
```

Later, add:

```text
average decision latency
actions/minute
progress per life
distance per death
completion rate
```

---

## 16. Configuration

Keep tunable parameters outside core logic.

Possible settings:

```text
JEV_API_KEY
JEV_MODEL
AI_DECISION_INTERVAL_FRAMES
MAX_ACTION_DURATION_FRAMES
DEBUG_AI_STATE
LOG_AI_DECISIONS
```

Use `.env` or the project's existing configuration mechanism.

Never commit API keys.

---

## 17. Suggested Project Structure

Adapt this to the repository's existing conventions. Do not blindly restructure the project.

```text
super-mario-python/
│
├── game/
│   └── existing game source...
│
├── ai/
│   ├── observation.py
│   ├── actions.py
│   ├── decision_model.py
│   ├── jev.py
│   └── controller.py
│
├── logs/
│   └── ...
│
├── requirements.txt
├── .env
└── README.md
```

---

## 18. Engineering Constraints

### Do not

* Rewrite the whole game.
* Replace existing physics.
* Add computer vision before testing internal state extraction.
* Send the entire raw game object graph to Jev.
* Let Jev execute arbitrary code.
* Couple Jev directly to unrelated game classes.
* Call Jev unnecessarily every rendered frame.
* Hardcode API keys.
* Over-engineer the first version.

### Do

* Reuse the existing game architecture.
* Add small adapter modules.
* Normalize state into a stable schema.
* Validate model output.
* Make AI timing configurable.
* Keep observation and action interfaces independent.
* Add logging.
* Allow manual keyboard control to remain available.

---

## 19. Optional Vision Architecture

Vision is **not part of the first implementation**.

However, make the observation interface replaceable:

```text
                    ┌──────────────────────┐
                    │ ObservationProvider  │
                    └──────────┬───────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
       InternalStateProvider       VisionStateProvider
                  │                         │
                  └────────────┬────────────┘
                               ▼
                              Jev
```

Future vision pipeline:

```text
Game screen
    ↓
Vision model
    ↓
structured observation
    ↓
Jev
```

This allows comparison between:

```text
Ground-truth state → Jev
```

and:

```text
Pixels → Vision → Jev
```

without changing the decision/action architecture.

---

## 20. First Milestone

Do **not** attempt autonomous Jev gameplay immediately.

First milestone:

```text
Run Mario
   ↓
Extract internal state
   ↓
Print normalized JSON
```

Example:

```json
{
  "player": {
    "x": 243,
    "y": 381,
    "vx": 2.4,
    "vy": 0,
    "grounded": true
  },
  "nearby": {
    "enemies": [
      {
        "type": "goomba",
        "relative_x": 67,
        "relative_y": 0
      }
    ]
  }
}
```

Second milestone:

```text
Manual action JSON
        ↓
Action Executor
        ↓
Mario responds
```

Third milestone:

```text
JSON state
    ↓
Jev
    ↓
JSON action
    ↓
Mario
```

Only after those work should we optimize decision frequency, observation schema, Jev configuration, and gameplay performance.

---

## 21. Final Intended System

```text
┌─────────────────────────────────────────────────────────────┐
│                       MARIO PROCESS                         │
│                                                             │
│  ┌─────────────┐      ┌──────────────────┐                 │
│  │ Game Loop   │─────▶│ Internal State   │                 │
│  └─────────────┘      └────────┬─────────┘                 │
│                                │                            │
└────────────────────────────────┼────────────────────────────┘
                                 │
                                 ▼
                     ┌─────────────────────┐
                     │ Observation Layer   │
                     │                     │
                     │ Normalize + filter  │
                     └──────────┬──────────┘
                                │
                                │ JSON
                                ▼
                     ┌─────────────────────┐
                     │        Jev          │
                     │                     │
                     │ Decision generation │
                     └──────────┬──────────┘
                                │
                                │ JSON action
                                ▼
                     ┌─────────────────────┐
                     │  Action Validator   │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Action Executor    │
                     └──────────┬──────────┘
                                │
                                ▼
                         Mario controls
                                │
                                └───────────────┐
                                                │
                                                ▼
                                           next state
```

The prototype should prioritize:

* low latency
* minimal state representation
* strict structured actions
* minimal modification to the existing Mario codebase
* clear separation between game, observation, Jev, and action execution

The core experimental loop is:

**game state → Jev decision → game action → new game state**
