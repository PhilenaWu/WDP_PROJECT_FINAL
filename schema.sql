-- =====================================================================
-- Genlink — full database schema
-- =====================================================================
-- Reconstructed from every query in the application code after the
-- original Railway database became unreachable.
--
-- This file is COMPLETE and already includes migrations 001–003.
-- Run this on an empty database and do NOT also run migrations/*.sql,
-- or the ALTER statements there will fail on columns that already exist.
--
--   mysql -h <host> -P <port> -u <user> -p <database> < schema.sql
--
-- Then seed demo content with:
--   python scripts/seed_demo.py
-- =====================================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- Identity
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    email             VARCHAR(255) NOT NULL,
    username          VARCHAR(80)  NOT NULL,
    password_hash     VARCHAR(255) NOT NULL,
    user_type         ENUM('user','admin') NOT NULL DEFAULT 'user',

    first_name        VARCHAR(80)  DEFAULT NULL,
    last_name         VARCHAR(80)  DEFAULT NULL,
    display_name      VARCHAR(80)  DEFAULT NULL,
    date_of_birth     DATE         DEFAULT NULL,
    phone_number      VARCHAR(20)  DEFAULT NULL,
    profile_picture   VARCHAR(255) DEFAULT NULL,

    age_group         ENUM('youth','adult','elderly') DEFAULT NULL,
    location_enabled  BOOLEAN      NOT NULL DEFAULT FALSE,
    latitude          DECIMAL(10,8) DEFAULT NULL,
    longitude         DECIMAL(11,8) DEFAULT NULL,

    profile_completed BOOLEAN      NOT NULL DEFAULT FALSE,
    language          VARCHAR(10)  NOT NULL DEFAULT 'en',
    -- Comma-separated topic slugs chosen at signup step 3.
    interests         TEXT         DEFAULT NULL,

    created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_users_email (email),
    UNIQUE KEY uq_users_username (username),
    KEY idx_users_age_group (age_group)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS appearance (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    theme       ENUM('lightmode','darkmode') NOT NULL DEFAULT 'lightmode',
    text_size   INT         NOT NULL DEFAULT 16,
    font_style  VARCHAR(50) NOT NULL DEFAULT 'Poppins',
    boldness    VARCHAR(20) NOT NULL DEFAULT 'medium',

    UNIQUE KEY uq_appearance_user (user_id),
    CONSTRAINT fk_appearance_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS interests (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    UNIQUE KEY uq_interests_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_interests (
    user_id     INT NOT NULL,
    interest_id INT NOT NULL,
    PRIMARY KEY (user_id, interest_id),
    CONSTRAINT fk_ui_user     FOREIGN KEY (user_id)     REFERENCES users (id)     ON DELETE CASCADE,
    CONSTRAINT fk_ui_interest FOREIGN KEY (interest_id) REFERENCES interests (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS feedback (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    full_name     VARCHAR(120) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    feedback_type ENUM('Positive','Negative') NOT NULL,
    feedback_text TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_feedback_user (user_id),
    CONSTRAINT fk_feedback_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Social graph
-- ---------------------------------------------------------------------

-- requester_id / receiver_id preserve who initiated the request.
-- user_low / user_high are the same pair stored order-independently,
-- so the unique key can prevent duplicate connections in either direction.
CREATE TABLE IF NOT EXISTS connections (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    requester_id INT NOT NULL,
    receiver_id  INT NOT NULL,
    user_low     INT NOT NULL,
    user_high    INT NOT NULL,
    status       ENUM('pending','accepted','rejected') NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_connection_pair (user_low, user_high),
    KEY idx_connections_receiver (receiver_id, status),
    KEY idx_connections_requester (requester_id, status),
    CONSTRAINT fk_conn_requester FOREIGN KEY (requester_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_conn_receiver  FOREIGN KEY (receiver_id)  REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contacts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    contact_user_id INT NOT NULL,
    nickname        VARCHAR(50) DEFAULT NULL,
    is_favorite     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_contact_pair (user_id, contact_user_id),
    CONSTRAINT fk_contact_owner FOREIGN KEY (user_id)         REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_contact_target FOREIGN KEY (contact_user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Storyboard
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS topics (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(120) NOT NULL,
    slug        VARCHAR(120) NOT NULL,
    image       VARCHAR(255) DEFAULT NULL,
    category    VARCHAR(100) DEFAULT NULL,
    is_featured TINYINT(1)   NOT NULL DEFAULT 0,

    UNIQUE KEY uq_topics_slug (slug),
    KEY idx_topics_featured (is_featured)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stories (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL,
    topic_id   INT NOT NULL,
    title      VARCHAR(200) NOT NULL,
    body       TEXT         DEFAULT NULL,
    audio_path VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_stories_topic (topic_id, created_at),
    KEY idx_stories_user (user_id),
    CONSTRAINT fk_stories_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE,
    CONSTRAINT fk_stories_topic FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS story_media (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    story_id   INT NOT NULL,
    media_type ENUM('image','video') NOT NULL,
    file_path  VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_story_media_story (story_id, created_at),
    CONSTRAINT fk_media_story FOREIGN KEY (story_id)
        REFERENCES stories (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS story_likes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    story_id   INT NOT NULL,
    user_id    INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_story_like (story_id, user_id),
    CONSTRAINT fk_slike_story FOREIGN KEY (story_id) REFERENCES stories (id) ON DELETE CASCADE,
    CONSTRAINT fk_slike_user  FOREIGN KEY (user_id)  REFERENCES users (id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comments (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    story_id   INT NOT NULL,
    user_id    INT NOT NULL,
    body       TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_comments_story (story_id, created_at),
    CONSTRAINT fk_comments_story FOREIGN KEY (story_id) REFERENCES stories (id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user  FOREIGN KEY (user_id)  REFERENCES users (id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comment_likes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    comment_id INT NOT NULL,
    user_id    INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_comment_like (comment_id, user_id),
    CONSTRAINT fk_clike_comment FOREIGN KEY (comment_id) REFERENCES comments (id) ON DELETE CASCADE,
    CONSTRAINT fk_clike_user    FOREIGN KEY (user_id)    REFERENCES users (id)    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Events
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS events (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    title                VARCHAR(200) NOT NULL,
    description          TEXT         DEFAULT NULL,
    event_date           DATE         NOT NULL,
    start_time           TIME         DEFAULT NULL,
    end_time             TIME         DEFAULT NULL,
    location             VARCHAR(255) DEFAULT NULL,
    location_address     VARCHAR(255) DEFAULT NULL,
    latitude             DECIMAL(10,8) DEFAULT NULL,
    longitude            DECIMAL(11,8) DEFAULT NULL,
    image_url            VARCHAR(255) DEFAULT NULL,
    max_participants     INT          DEFAULT NULL,
    -- Denormalised counter read directly by the home page; the events
    -- pages recompute the live count from event_registrations instead.
    current_participants INT          NOT NULL DEFAULT 0,
    event_type           VARCHAR(50)  DEFAULT NULL,
    age_group            VARCHAR(20)  DEFAULT NULL,
    created_by           INT          DEFAULT NULL,
    status               ENUM('upcoming','ongoing','completed','cancelled')
                             NOT NULL DEFAULT 'upcoming',
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_events_date_status (event_date, status),
    CONSTRAINT fk_events_creator FOREIGN KEY (created_by)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS event_registrations (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    event_id      INT NOT NULL,
    user_id       INT NOT NULL,
    full_name     VARCHAR(120) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    phone_number  VARCHAR(20)  NOT NULL,
    confirmed     BOOLEAN      NOT NULL DEFAULT TRUE,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_registration (event_id, user_id),
    KEY idx_reg_user (user_id),
    CONSTRAINT fk_reg_event FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
    CONSTRAINT fk_reg_user  FOREIGN KEY (user_id)  REFERENCES users (id)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS event_submissions (
    id                           INT AUTO_INCREMENT PRIMARY KEY,
    user_id                      INT NOT NULL,

    organizer_name               VARCHAR(120) NOT NULL,
    organizer_dob                DATE         DEFAULT NULL,
    organizer_age_group          VARCHAR(20)  DEFAULT NULL,
    organizer_email              VARCHAR(255) NOT NULL,
    organizer_phone              VARCHAR(20)  NOT NULL,
    organizer_location           VARCHAR(255) DEFAULT NULL,

    event_title                  VARCHAR(200) NOT NULL,
    event_summary                VARCHAR(255) NOT NULL,
    event_type                   VARCHAR(50)  NOT NULL,
    image_url                    VARCHAR(255) DEFAULT NULL,
    preferred_date               DATE         NOT NULL,
    expected_participants        INT          NOT NULL,

    why_meaningful               TEXT         NOT NULL,
    previous_experience          TEXT         DEFAULT NULL,
    accessibility_considerations TEXT         NOT NULL,

    status                       ENUM('pending','approved','rejected')
                                     NOT NULL DEFAULT 'pending',
    reviewed_by                  INT       DEFAULT NULL,
    reviewed_at                  DATETIME  DEFAULT NULL,
    admin_notes                  TEXT      DEFAULT NULL,
    created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_submissions_status (status, created_at),
    KEY idx_submissions_user (user_id),
    CONSTRAINT fk_sub_user     FOREIGN KEY (user_id)     REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_sub_reviewer FOREIGN KEY (reviewed_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Messaging
-- ---------------------------------------------------------------------

-- `groups` is a reserved word in MySQL 8 and must always be backticked.
CREATE TABLE IF NOT EXISTS `groups` (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    description TEXT         DEFAULT NULL,
    created_by  INT          NOT NULL,
    -- Groups are soft-deleted: routes set is_active = FALSE and every
    -- read filters on it.
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_groups_creator (created_by),
    CONSTRAINT fk_groups_creator FOREIGN KEY (created_by)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS group_members (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    group_id  INT NOT NULL,
    user_id   INT NOT NULL,
    is_admin  BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_group_member (group_id, user_id),
    KEY idx_gm_user (user_id),
    CONSTRAINT fk_gm_group FOREIGN KEY (group_id) REFERENCES `groups` (id) ON DELETE CASCADE,
    CONSTRAINT fk_gm_user  FOREIGN KEY (user_id)  REFERENCES users (id)    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS messages (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    sender_id    INT NOT NULL,
    -- Exactly one of receiver_id / group_id is set.
    receiver_id  INT DEFAULT NULL,
    group_id     INT DEFAULT NULL,
    message_type ENUM('text','image','voice','video','story_share')
                     NOT NULL DEFAULT 'text',
    content      TEXT         DEFAULT NULL,
    file_path    VARCHAR(255) DEFAULT NULL,
    is_read      BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NULL DEFAULT NULL,

    KEY idx_messages_direct (sender_id, receiver_id, created_at),
    KEY idx_messages_group (group_id, created_at),
    KEY idx_messages_unread (receiver_id, is_read),
    CONSTRAINT fk_msg_sender   FOREIGN KEY (sender_id)   REFERENCES users (id)    ON DELETE CASCADE,
    CONSTRAINT fk_msg_receiver FOREIGN KEY (receiver_id) REFERENCES users (id)    ON DELETE CASCADE,
    CONSTRAINT fk_msg_group    FOREIGN KEY (group_id)    REFERENCES `groups` (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Chess  (migrations 002 + 003, merged)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chess_games (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    white_id     INT NULL,
    black_id     INT NULL,
    vs_bot       BOOLEAN NOT NULL DEFAULT FALSE,
    bot_side     ENUM('white','black') DEFAULT NULL,
    bot_level    TINYINT DEFAULT 5,
    status       ENUM('waiting','active','finished','aborted') NOT NULL DEFAULT 'waiting',
    -- Full board state; a game is reconstructible from this row alone.
    fen          VARCHAR(120) NOT NULL,
    moves        TEXT,
    result       VARCHAR(32),
    winner_id    INT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_move_at TIMESTAMP NULL,

    KEY idx_chess_games_players (white_id, black_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chess_invites (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    from_user_id INT NOT NULL,
    to_user_id   INT NOT NULL,
    status       ENUM('pending','accepted','declined','canceled') NOT NULL DEFAULT 'pending',
    game_id      INT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    KEY idx_chess_invites_to_status (to_user_id, status),
    KEY idx_chess_invites_from_status (from_user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
