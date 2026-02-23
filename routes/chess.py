import json
import os
import random

import chess
import chess.engine
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from database import execute_query


chess_bp = Blueprint("chess", __name__, url_prefix="/chess")


def _normalize_profile_picture(raw_value):
    profile_picture = (raw_value or "").strip()
    if not profile_picture:
        return ""

    profile_picture = profile_picture.replace("\\", "/")
    if profile_picture.startswith(("http://", "https://")):
        return profile_picture

    if "/static/" in profile_picture:
        idx = profile_picture.find("/static/") + len("/static/")
        profile_picture = profile_picture[idx:]
    elif profile_picture.startswith("static/"):
        profile_picture = profile_picture[len("static/"):]
    elif profile_picture.startswith("/static/"):
        profile_picture = profile_picture[len("/static/"):]

    profile_picture = profile_picture.lstrip("/")
    if profile_picture.startswith("profile_pics/"):
        profile_picture = f"uploads/{profile_picture}"
    elif profile_picture and "/" not in profile_picture:
        profile_picture = f"uploads/profile_pics/{profile_picture}"

    return profile_picture


def _parse_moves(raw_moves):
    if not raw_moves:
        return []
    try:
        return json.loads(raw_moves)
    except Exception:
        return []


def _serialize_moves(moves):
    return json.dumps(moves)


def _get_game(game_id):
    return execute_query(
        "SELECT * FROM chess_games WHERE id = %s",
        (game_id,),
        fetch_one=True,
    )


def _user_color(game, user_id):
    if game.get("white_id") == user_id:
        return "white"
    if game.get("black_id") == user_id:
        return "black"
    return None


def _is_user_in_game(game, user_id):
    return user_id in (game.get("white_id"), game.get("black_id"))


def _compute_result(board, game):
    if not board.is_game_over():
        return None, None

    if board.is_checkmate():
        winner_color = "white" if board.turn == chess.BLACK else "black"
        winner_id = None
        if winner_color == "white":
            winner_id = game.get("white_id")
        else:
            winner_id = game.get("black_id")
        return winner_color, winner_id

    return "draw", None


def _emit_game_update(game_id, payload):
    socketio = current_app.extensions.get("socketio")
    if socketio:
        socketio.emit("chess_update", payload, room=f"chess_{game_id}")


def _get_stockfish_path():
    configured = current_app.config.get("STOCKFISH_PATH")
    if not configured:
        return None

    path = configured
    if not os.path.isabs(path):
        path = os.path.abspath(os.path.join(current_app.root_path, path))

    return path if os.path.exists(path) else None


def _stockfish_move(board, level):
    path = _get_stockfish_path()
    if not path:
        return None

    try:
        engine = chess.engine.SimpleEngine.popen_uci(path)
    except Exception:
        return None

    try:
        safe_level = max(1, min(20, int(level)))
        engine.configure({"Skill Level": safe_level})
        result = engine.play(board, chess.engine.Limit(time=0.1))
        return result.move
    except Exception:
        return None
    finally:
        engine.quit()


@chess_bp.route("/", methods=["GET"])
@login_required
def lobby():
    user_id = current_user.id

    contacts = execute_query(
        """
        SELECT u.id, u.display_name, u.username, u.profile_picture
        FROM contacts c
        JOIN users u ON u.id = c.contact_user_id
        WHERE c.user_id = %s
        ORDER BY COALESCE(u.display_name, u.username)
        """,
        (user_id,),
        fetch_all=True,
    ) or []

    for contact in contacts:
        contact["profile_picture"] = _normalize_profile_picture(contact.get("profile_picture"))
        contact["display_name"] = contact.get("display_name") or contact.get("username")

    incoming_invites = execute_query(
        """
        SELECT ci.*, u.display_name, u.username
        FROM chess_invites ci
        JOIN users u ON u.id = ci.from_user_id
        WHERE ci.to_user_id = %s AND ci.status = 'pending'
        ORDER BY ci.created_at DESC
        """,
        (user_id,),
        fetch_all=True,
    ) or []

    outgoing_invites = execute_query(
        """
        SELECT ci.*, u.display_name, u.username
        FROM chess_invites ci
        JOIN users u ON u.id = ci.to_user_id
        WHERE ci.from_user_id = %s AND ci.status = 'pending'
        ORDER BY ci.created_at DESC
        """,
        (user_id,),
        fetch_all=True,
    ) or []

    active_games = execute_query(
        """
        SELECT g.*, 
            uw.display_name AS white_name,
            uw.username AS white_username,
            ub.display_name AS black_name,
            ub.username AS black_username
        FROM chess_games g
        LEFT JOIN users uw ON uw.id = g.white_id
        LEFT JOIN users ub ON ub.id = g.black_id
        WHERE (g.white_id = %s OR g.black_id = %s)
          AND g.status IN ('waiting', 'active')
        ORDER BY g.updated_at DESC
        """,
        (user_id, user_id),
        fetch_all=True,
    ) or []

    return render_template(
        "chess/lobby.html",
        contacts=contacts,
        incoming_invites=incoming_invites,
        outgoing_invites=outgoing_invites,
        active_games=active_games,
    )


@chess_bp.route("/invite", methods=["POST"])
@login_required
def invite_contact():
    user_id = current_user.id
    contact_id = (request.form.get("contact_user_id") or "").strip()

    try:
        contact_id = int(contact_id)
    except Exception:
        flash("Select a valid contact.", "error")
        return redirect(url_for("chess.lobby"))

    if contact_id == user_id:
        flash("You cannot invite yourself.", "error")
        return redirect(url_for("chess.lobby"))

    contact_row = execute_query(
        "SELECT id FROM contacts WHERE user_id = %s AND contact_user_id = %s",
        (user_id, contact_id),
        fetch_one=True,
    )
    if not contact_row:
        flash("That user is not in your contacts.", "error")
        return redirect(url_for("chess.lobby"))

    existing_invite = execute_query(
        """
        SELECT id FROM chess_invites
        WHERE ((from_user_id = %s AND to_user_id = %s)
           OR (from_user_id = %s AND to_user_id = %s))
          AND status = 'pending'
        """,
        (user_id, contact_id, contact_id, user_id),
        fetch_one=True,
    )
    if existing_invite:
        flash("There is already a pending invite between you two.", "error")
        return redirect(url_for("chess.lobby"))

    active_game = execute_query(
        """
        SELECT id FROM chess_games
        WHERE status IN ('waiting', 'active')
          AND ((white_id = %s AND black_id = %s) OR (white_id = %s AND black_id = %s))
        """,
        (user_id, contact_id, contact_id, user_id),
        fetch_one=True,
    )
    if active_game:
        flash("You already have an active game with this contact.", "error")
        return redirect(url_for("chess.lobby"))

    execute_query(
        """
        INSERT INTO chess_invites (from_user_id, to_user_id, status)
        VALUES (%s, %s, 'pending')
        """,
        (user_id, contact_id),
        commit=True,
    )

    flash("Invite sent.", "success")
    return redirect(url_for("chess.lobby"))


@chess_bp.route("/invite/<int:invite_id>/accept", methods=["POST"])
@login_required
def accept_invite(invite_id):
    user_id = current_user.id

    invite = execute_query(
        "SELECT * FROM chess_invites WHERE id = %s AND to_user_id = %s",
        (invite_id, user_id),
        fetch_one=True,
    )
    if not invite or invite.get("status") != "pending":
        flash("Invite not found or already handled.", "error")
        return redirect(url_for("chess.lobby"))

    if random.choice([True, False]):
        white_id, black_id = invite["from_user_id"], user_id
    else:
        white_id, black_id = user_id, invite["from_user_id"]

    board = chess.Board()
    fen = board.fen()
    moves = _serialize_moves([])

    game_id = execute_query(
        """
        INSERT INTO chess_games (white_id, black_id, vs_bot, status, fen, moves)
        VALUES (%s, %s, FALSE, 'active', %s, %s)
        """,
        (white_id, black_id, fen, moves),
        commit=True,
    )

    execute_query(
        "UPDATE chess_invites SET status = 'accepted', game_id = %s WHERE id = %s",
        (game_id, invite_id),
        commit=True,
    )

    socketio = current_app.extensions.get("socketio")
    if socketio:
        socketio.emit(
            "chess_invite_accepted",
            {"game_id": game_id, "invite_id": invite_id},
            room=f"user_{invite['from_user_id']}",
        )

    return redirect(url_for("chess.game", game_id=game_id))


@chess_bp.route("/invite/<int:invite_id>/decline", methods=["POST"])
@login_required
def decline_invite(invite_id):
    user_id = current_user.id

    invite = execute_query(
        "SELECT * FROM chess_invites WHERE id = %s AND to_user_id = %s",
        (invite_id, user_id),
        fetch_one=True,
    )
    if not invite or invite.get("status") != "pending":
        flash("Invite not found or already handled.", "error")
        return redirect(url_for("chess.lobby"))

    execute_query(
        "UPDATE chess_invites SET status = 'declined' WHERE id = %s",
        (invite_id,),
        commit=True,
    )

    flash("Invite declined.", "success")
    return redirect(url_for("chess.lobby"))


@chess_bp.route("/bot", methods=["POST"])
@login_required
def start_bot_game():
    user_id = current_user.id
    side = (request.form.get("side") or "random").strip().lower()
    level_raw = (request.form.get("level") or "5").strip()

    if side not in {"white", "black", "random"}:
        side = "random"

    if side == "random":
        side = random.choice(["white", "black"])

    try:
        bot_level = int(level_raw)
    except Exception:
        bot_level = 5
    bot_level = max(1, min(20, bot_level))

    bot_side = "black" if side == "white" else "white"
    white_id = user_id if side == "white" else None
    black_id = user_id if side == "black" else None

    board = chess.Board()
    moves = []

    if bot_side == "white":
        bot_move = _stockfish_move(board, bot_level) or random.choice(list(board.legal_moves))
        san = board.san(bot_move)
        board.push(bot_move)
        moves.append(san)

    game_id = execute_query(
        """
        INSERT INTO chess_games (white_id, black_id, vs_bot, bot_side, bot_level, status, fen, moves, last_move_at)
        VALUES (%s, %s, TRUE, %s, %s, 'active', %s, %s, NOW())
        """,
        (white_id, black_id, bot_side, bot_level, board.fen(), _serialize_moves(moves)),
        commit=True,
    )

    return redirect(url_for("chess.game", game_id=game_id))


@chess_bp.route("/game/<int:game_id>")
@login_required
def game(game_id):
    user_id = current_user.id
    game_row = _get_game(game_id)

    if not game_row or not _is_user_in_game(game_row, user_id):
        flash("Game not found.", "error")
        return redirect(url_for("chess.lobby"))

    player_color = _user_color(game_row, user_id)
    opponent_name = "Bot" if game_row.get("vs_bot") else "Opponent"

    if game_row.get("vs_bot"):
        opponent_name = "Bot"
    else:
        if player_color == "white":
            opponent_name = execute_query(
                "SELECT display_name, username FROM users WHERE id = %s",
                (game_row.get("black_id"),),
                fetch_one=True,
            )
        else:
            opponent_name = execute_query(
                "SELECT display_name, username FROM users WHERE id = %s",
                (game_row.get("white_id"),),
                fetch_one=True,
            )
        if opponent_name:
            opponent_name = opponent_name.get("display_name") or opponent_name.get("username") or "Opponent"
        else:
            opponent_name = "Opponent"

    moves = _parse_moves(game_row.get("moves"))
    fen_parts = (game_row.get("fen") or "").split(" ")
    turn = "white" if len(fen_parts) > 1 and fen_parts[1] == "w" else "black"

    return render_template(
        "chess/game.html",
        game=game_row,
        player_color=player_color,
        opponent_name=opponent_name,
        moves=moves,
        turn=turn,
    )


@chess_bp.route("/api/legal", methods=["POST"])
@login_required
def api_legal_moves():
    user_id = current_user.id
    data = request.get_json(silent=True) or {}

    try:
        game_id = int(data.get("game_id"))
    except Exception:
        return jsonify({"ok": False, "message": "Invalid game."}), 400

    square = (data.get("square") or "").strip().lower()
    if len(square) != 2:
        return jsonify({"ok": False, "message": "Invalid square."}), 400

    game_row = _get_game(game_id)
    if not game_row or not _is_user_in_game(game_row, user_id):
        return jsonify({"ok": False, "message": "Game not found."}), 404

    if game_row.get("status") != "active":
        return jsonify({"ok": False, "message": "Game is not active."}), 400

    board = chess.Board(game_row.get("fen"))
    player_color = _user_color(game_row, user_id)
    if not player_color:
        return jsonify({"ok": False, "message": "Not a player."}), 403

    if (board.turn == chess.WHITE and player_color != "white") or (
        board.turn == chess.BLACK and player_color != "black"
    ):
        return jsonify({"ok": False, "message": "Not your turn."}), 403

    try:
        from_square = chess.parse_square(square)
    except Exception:
        return jsonify({"ok": False, "message": "Invalid square."}), 400

    targets = []
    for move in board.legal_moves:
        if move.from_square == from_square:
            targets.append(chess.square_name(move.to_square))

    return jsonify({"ok": True, "targets": targets})


@chess_bp.route("/api/move", methods=["POST"])
@login_required
def api_move():
    user_id = current_user.id
    data = request.get_json(silent=True) or {}

    try:
        game_id = int(data.get("game_id"))
    except Exception:
        return jsonify({"ok": False, "message": "Invalid game."}), 400

    from_sq = (data.get("from") or "").strip().lower()
    to_sq = (data.get("to") or "").strip().lower()
    promotion = (data.get("promotion") or "").strip().lower()

    if len(from_sq) != 2 or len(to_sq) != 2:
        return jsonify({"ok": False, "message": "Invalid move."}), 400

    game_row = _get_game(game_id)
    if not game_row or not _is_user_in_game(game_row, user_id):
        return jsonify({"ok": False, "message": "Game not found."}), 404

    if game_row.get("status") != "active":
        return jsonify({"ok": False, "message": "Game is not active."}), 400

    player_color = _user_color(game_row, user_id)
    board = chess.Board(game_row.get("fen"))

    if (board.turn == chess.WHITE and player_color != "white") or (
        board.turn == chess.BLACK and player_color != "black"
    ):
        return jsonify({"ok": False, "message": "Not your turn."}), 403

    uci = from_sq + to_sq + (promotion if promotion in {"q", "r", "b", "n"} else "")
    move = chess.Move.from_uci(uci)

    if move not in board.legal_moves:
        if promotion == "" and len(uci) == 4:
            promo_move = chess.Move.from_uci(uci + "q")
            if promo_move in board.legal_moves:
                move = promo_move
            else:
                return jsonify({"ok": False, "message": "Illegal move."}), 400
        else:
            return jsonify({"ok": False, "message": "Illegal move."}), 400

    moves = _parse_moves(game_row.get("moves"))
    san = board.san(move)
    board.push(move)
    moves.append(san)

    result, winner_id = _compute_result(board, game_row)
    status = "finished" if result else "active"

    if status == "active" and game_row.get("vs_bot"):
        bot_side = game_row.get("bot_side")
        bot_level = game_row.get("bot_level") or 5
        bot_turn = board.turn == chess.WHITE and bot_side == "white"
        bot_turn = bot_turn or (board.turn == chess.BLACK and bot_side == "black")
        if bot_turn:
            bot_move = _stockfish_move(board, bot_level) or random.choice(list(board.legal_moves))
            bot_san = board.san(bot_move)
            board.push(bot_move)
            moves.append(bot_san)
            result, winner_id = _compute_result(board, game_row)
            status = "finished" if result else "active"

    execute_query(
        """
        UPDATE chess_games
        SET fen = %s, moves = %s, status = %s, result = %s, winner_id = %s, last_move_at = NOW()
        WHERE id = %s
        """,
        (board.fen(), _serialize_moves(moves), status, result, winner_id, game_id),
        commit=True,
    )

    payload = {
        "ok": True,
        "game_id": game_id,
        "fen": board.fen(),
        "moves": moves,
        "status": status,
        "result": result,
        "turn": "white" if board.turn == chess.WHITE else "black",
    }

    _emit_game_update(game_id, payload)
    return jsonify(payload)


@chess_bp.route("/forfeit/<int:game_id>", methods=["POST"])
@login_required
def forfeit_game(game_id):
    user_id = current_user.id
    game_row = _get_game(game_id)

    if not game_row or not _is_user_in_game(game_row, user_id):
        flash("Game not found.", "error")
        return redirect(url_for("chess.lobby"))

    if game_row.get("status") == "finished":
        return redirect(url_for("chess.lobby"))

    player_color = _user_color(game_row, user_id)
    if not player_color:
        flash("Game not found.", "error")
        return redirect(url_for("chess.lobby"))

    winner_color = "black" if player_color == "white" else "white"
    winner_id = None
    if winner_color == "white":
        winner_id = game_row.get("white_id")
    else:
        winner_id = game_row.get("black_id")

    execute_query(
        """
        UPDATE chess_games
        SET status = 'finished', result = %s, winner_id = %s, last_move_at = NOW()
        WHERE id = %s
        """,
        (winner_color, winner_id, game_id),
        commit=True,
    )

    board = chess.Board(game_row.get("fen"))
    payload = {
        "ok": True,
        "game_id": game_id,
        "fen": board.fen(),
        "moves": _parse_moves(game_row.get("moves")),
        "status": "finished",
        "result": winner_color,
        "turn": "white" if board.turn == chess.WHITE else "black",
        "message": "Opponent forfeited. You win!",
    }
    _emit_game_update(game_id, payload)

    flash("You forfeited the game.", "warning")
    return redirect(url_for("chess.lobby"))
