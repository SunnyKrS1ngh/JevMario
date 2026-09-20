# JevMario 🍄🎮

An autonomous AI agent playing Super Mario in Python, powered by **Jev** (System One decision model) via the OpenRouter Decisions API.


---

## Features

- **Jev AI Integration**: Uses `typesafe/jev-1.13` via the OpenRouter Decisions API (`/api/alpha/decisions`) to make real-time platforming decisions.
- **Accurate Spatial Observation**: Scans tile maps for obstacles (pipes, solid walls, pits) and enemies (Goombas, Koopas), providing calibrated distance and height context to the AI.
- **Continuous Momentum Executor**: Holds jump arcs and forward speed between asynchronous API calls, preventing mid-air stalling and jerky stops.
- **Low-Latency Pre-fetching**: Pipelines background decision requests so actions transition seamlessly.
- **Rule-Based Fallback**: Built-in deterministic model for offline testing without an API key.
- **Live Debug Overlay**: In-game HUD displaying current AI action, remaining frames, decision latency, and obstacle telemetry.

---

## Quick Start

### 1. Installation

```bash
git clone https://github.com/SunnyKrS1ngh/JevMario.git
cd JevMario

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set your OpenRouter API key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
JEV_MODEL=typesafe/jev-1.13
```

### 3. Run the Game

**With Jev AI Control:**
```bash
python main.py --ai
```

**With Rule-Based AI (no API key needed):**
```bash
python main.py --ai --mode rule
```

**Manual Keyboard Control:**
```bash
python main.py
```

---

## Controls (Manual Mode)

- **Left / Right**: Move left / right
- **Space / Up**: Jump
- **Left Shift**: Boost / Sprint
- **Mouse Clicks**: Spawn entities (debug)
- **Escape**: Pause

---

## Architecture Overview

```
 ┌────────────────┐
 │ Pygame Engine  │
 └───────┬────────┘
         │ (every frame)
 ┌───────▼────────┐      ┌─────────────────────────┐
 │  Observation   │ ───► │ Jev AI (OpenRouter API) │
 │     Layer      │      │ typesafe/jev-1.13       │
 └────────────────┘      └───────────┬─────────────┘
                                     │ (async response)
 ┌────────────────┐                  │
 │  Action Trait  │ ◄────────────────┘
 │    Executor    │  (holds momentum & jump arc)
 └────────────────┘
```

- **`ai/observation.py`**: Extracts normalized player physics, tile map obstacle scanning (pipes, walls, pits), and nearby entities.
- **`ai/jev.py`**: Formats state summaries and typed choice questions for the Jev Decisions endpoint.
- **`ai/executor.py`**: Translates AI choices into directional movement and jump traits with momentum preservation.
- **`ai/controller.py`**: Manages the asynchronous loop, background threading, and decision pre-fetching.
- **`ai/logger.py`**: JSONL structured decision logging for offline evaluation.
