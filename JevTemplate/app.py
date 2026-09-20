"""
app.py
------
Flask server for the Jev Tic-Tac-Toe game.

Routes
------
GET  /          Serve the game UI (templates/index.html)
POST /api/move  Receive current board, ask Jev for O's next move,
                return the chosen cell + Jev's full probability distribution.

The frontend handles:
  - rendering the board
  - win / draw detection
  - showing Jev's probabilities per cell after each AI move
"""

from flask import Flask, jsonify, render_template, request
from jev_client import ask_jev

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WIN_LINES = [
    # rows
    [(0, 0), (0, 1), (0, 2)],
    [(1, 0), (1, 1), (1, 2)],
    [(2, 0), (2, 1), (2, 2)],
    # cols
    [(0, 0), (1, 0), (2, 0)],
    [(0, 1), (1, 1), (2, 1)],
    [(0, 2), (1, 2), (2, 2)],
    # diagonals
    [(0, 0), (1, 1), (2, 2)],
    [(0, 2), (1, 1), (2, 0)],
]


def check_winner(board: list[list[str]]) -> str | None:
    """Return "X", "O", "draw", or None (game still going)."""
    for line in WIN_LINES:
        values = [board[r][c] for r, c in line]
        if values[0] != "_" and len(set(values)) == 1:
            return values[0]

    if all(board[r][c] != "_" for r in range(3) for c in range(3)):
        return "draw"

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/move", methods=["POST"])
def make_move():
    """
    Receive the current board, ask Jev for O's move, return the result.

    Request JSON:
        { "board": [["X","_","_"], ["_","_","_"], ["_","_","_"]] }

    Response JSON (success):
        {
            "cell": "r1c1",
            "row": 1,
            "col": 1,
            "probabilities": { "r0c1": 0.05, "r1c1": 0.88, ... },
            "confidence": 0.91,
            "winner": null          // "X", "O", "draw", or null
        }

    Response JSON (error):
        { "error": "..." }
    """
    data = request.get_json(silent=True)
    if not data or "board" not in data:
        return jsonify({"error": "Missing 'board' in request body."}), 400

    board = data["board"]

    # Basic validation
    if (
        not isinstance(board, list)
        or len(board) != 3
        or any(len(row) != 3 for row in board)
    ):
        return jsonify({"error": "Board must be a 3x3 list."}), 400

    # Check if the game is already over before asking Jev
    winner = check_winner(board)
    if winner:
        return jsonify({"winner": winner})

    try:
        result = ask_jev(board)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Apply Jev's move to the board and check for a winner
    r, c = result["row"], result["col"]
    board[r][c] = "O"
    winner = check_winner(board)

    return jsonify(
        {
            "cell": result["cell"],
            "row": r,
            "col": c,
            "probabilities": result["probabilities"],
            "confidence": result["confidence"],
            "winner": winner,
            "board": board,   # send back the updated board for state sync
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting Jev Tic-Tac-Toe at http://localhost:5000")
    app.run(debug=True, port=5000)
