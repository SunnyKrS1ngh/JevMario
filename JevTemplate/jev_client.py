"""
jev_client.py
-------------
Thin wrapper around the OpenRouter Decisions API (Jev model).

Endpoint : POST https://openrouter.ai/api/alpha/decisions
Model    : typesafe/jev-1.13
Auth     : Bearer $OPENROUTER_API_KEY

Jev is a System One model — it does not generate text.
It takes a *state* (any JSON) and a map of typed *questions*, and returns
calibrated answers: choice (pick from options), score (position on a rubric),
or noul (yes/no probability 0→1).

For tic-tac-toe we send:
  - state  : the live board + whose turn it is
  - questions : one Choice question whose *criteria* are the empty cells only
                (dynamic — shrinks as cells are claimed)

Jev returns:
  - choice       : the cell key it picked  (e.g. "r1c2")
  - probabilities: distribution over every empty cell  (great for the UI)
  - confidence   : how peaked/certain the distribution is (0–1)
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"

# Cell key → human label (used as Choice criteria descriptions)
CELL_LABELS = {
    "r0c0": "Top-left",
    "r0c1": "Top-center",
    "r0c2": "Top-right",
    "r1c0": "Middle-left",
    "r1c1": "Center",
    "r1c2": "Middle-right",
    "r2c0": "Bottom-left",
    "r2c1": "Bottom-center",
    "r2c2": "Bottom-right",
}


def _board_to_key(row: int, col: int) -> str:
    """Convert (row, col) indices to a Jev-friendly cell key."""
    return f"r{row}c{col}"


def _empty_cells(board: list[list[str]]) -> dict[str, str]:
    """
    Return only the empty cells as a Choice criteria dict.
    Jev's Choice question requires criteria to be non-empty, so we only
    include cells that are still available.

    Returns: { "r0c1": "Top-center", "r1c0": "Middle-left", ... }
    """
    criteria = {}
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            if cell == "_":
                key = _board_to_key(r, c)
                criteria[key] = CELL_LABELS[key]
    return criteria


def _board_to_state(board: list[list[str]]) -> dict:
    """
    Convert the board array to a structured state dict for Jev.

    We represent the board both as a 2-D array (easy for the model to parse
    structure) and as a readable text grid (provides a natural language anchor).
    Including both gives Jev the richest context.
    """
    symbols = {"X": "X", "O": "O", "_": "."}  # "." reads as empty in text

    rows_text = []
    for r, row in enumerate(board):
        cells = " | ".join(symbols[c] for c in row)
        rows_text.append(f"Row {r}: {cells}")

    grid_text = "\n".join(rows_text)

    return {
        "board": board,
        "board_text": grid_text,
        "you_are": "O",
        "opponent": "X",
        "context": (
            "Tic-tac-toe on a 3x3 grid. "
            "Win by placing three O's in a row, column, or diagonal. "
            "Block X from completing three in a row, column, or diagonal. "
            "Empty cells are shown as '_'. "
            "Prefer the center, then corners, then edges when no immediate win or block is needed."
        ),
    }


def ask_jev(board: list[list[str]]) -> dict:
    """
    Ask Jev which empty cell O should play next.

    Args:
        board: 3x3 list of lists. Each cell is "X", "O", or "_".

    Returns:
        {
            "cell": "r1c1",           # the cell key Jev chose
            "row": 1, "col": 1,       # unpacked for convenience
            "probabilities": {        # full distribution over empty cells
                "r0c1": 0.05,
                "r1c1": 0.88,
                ...
            },
            "confidence": 0.91        # how certain Jev is (0–1)
        }

    Raises:
        RuntimeError: if the API key is missing or the request fails.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )

    criteria = _empty_cells(board)
    if not criteria:
        raise ValueError("No empty cells left — the game is already over.")

    state = _board_to_state(board)

    payload = {
        "model": MODEL,
        "state": state,
        "questions": {
            "next_move": {
                "type": "choice",
                "instructions": (
                    "Which empty cell should O play? "
                    "Prioritise: (1) winning move for O, "
                    "(2) blocking X's winning move, "
                    "(3) best strategic position."
                ),
                "criteria": criteria,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-OpenRouter-Title": "Jev Tic-Tac-Toe",
    }

    resp = requests.post(DECISIONS_URL, json=payload, headers=headers, timeout=15)

    if not resp.ok:
        raise RuntimeError(
            f"Jev API error {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    answer = data["answers"]["next_move"]

    cell = answer["choice"]          # e.g. "r1c1"
    row = int(cell[1])               # parse row from key
    col = int(cell[3])               # parse col from key

    return {
        "cell": cell,
        "row": row,
        "col": col,
        "probabilities": answer.get("probabilities", {}),
        "confidence": answer.get("confidence", None),
    }
