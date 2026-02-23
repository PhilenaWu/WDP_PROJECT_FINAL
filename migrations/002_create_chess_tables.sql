CREATE TABLE IF NOT EXISTS chess_games (
    id INT AUTO_INCREMENT PRIMARY KEY,
    white_id INT NULL,
    black_id INT NULL,
    vs_bot BOOLEAN NOT NULL DEFAULT FALSE,
    bot_side ENUM('white','black') DEFAULT NULL,
    status ENUM('waiting','active','finished','aborted') NOT NULL DEFAULT 'waiting',
    fen VARCHAR(120) NOT NULL,
    moves TEXT,
    result VARCHAR(32),
    winner_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_move_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS chess_invites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    from_user_id INT NOT NULL,
    to_user_id INT NOT NULL,
    status ENUM('pending','accepted','declined','canceled') NOT NULL DEFAULT 'pending',
    game_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chess_invites_to_status ON chess_invites (to_user_id, status);
CREATE INDEX idx_chess_invites_from_status ON chess_invites (from_user_id, status);
CREATE INDEX idx_chess_games_players ON chess_games (white_id, black_id);
