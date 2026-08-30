# Genlink

**An intergenerational social platform — where youth, adults and seniors meet through shared stories, shared interests, and things worth doing together.**

Built for the **NYP Web Development Project (WDP)** module. Flask + MySQL + Socket.IO, deployed against a Railway-hosted database.

---

## The problem

Singapore's youth and seniors live in the same estates and rarely talk. The gap is not hostility — it is that there is no *shared surface*. Youth socialise on platforms seniors do not use; seniors gather at events youth never hear about. Interest-based communities exist for both groups, separately, on either side of the divide.

Generic social networks do not close that gap, because they optimise for people who are already alike: same age, same feed, same friends-of-friends.

## Our answer

Genlink is built around the one thing that genuinely crosses generations — **a shared interest** — and gives it four different places to live:

| Surface | What crosses the gap |
| --- | --- |
| **Storyboard** | Topic-scoped stories with text, photos, video **and voice recordings** — so a senior who would rather talk than type can still post |
| **Events** | Community events anyone can *attend*, and anyone can *propose*; an admin approval queue keeps the calendar real |
| **Connections** | Discovery filtered by age group (`youth` / `adult` / `elderly`) — the filter exists so you can deliberately connect *across* it, not within it |
| **Games** | A real chess board, playable against a connection or against Stockfish — the classic intergenerational excuse to sit down together |

Three cross-cutting decisions make it usable by both ends of the age range:

- **Appearance is a first-class setting.** Theme, text size (12–48px), font family and font weight, persisted per user and applied server-side on first paint — not a toggle buried in a menu.
- **Auto-translation on input.** Text submitted in Chinese (and, for events, any non-ASCII script) is translated to English on the way into the database, so a bilingual household posts once and everyone reads it.
- **Profanity is blocked, not just flagged.** A leetspeak-normalising filter — including Singapore-context terms — rejects the message before it is stored, on both the HTTP and Socket.IO paths.

---

## What it does

### Accounts and onboarding

| Capability | Detail |
| --- | --- |
| **Three-step signup** | Step 1 credentials → Step 2 profile (name, username, display name, phone, birthday) → Step 3 pick interests from the storyboard topic list. The draft lives in the session, so a refresh does not lose it |
| **Google OAuth** | Sign up or log in with Google; the callback pre-fills the signup draft and drops the user into Step 2 |
| **Strict validation** | Gmail-only addresses, Unicode-aware name patterns (`\p{L}`), passwords requiring upper + lower + digit + symbol at 8+ chars, and a hard **minimum age of 13** derived from date of birth |
| **Age groups** | Computed from DOB, not self-declared: `youth` (13–20), `adult` (21–59), `elderly` (60+). This drives discovery filtering |
| **Password reset** | Time-limited `itsdangerous` token emailed over Gmail SMTP, default 30-minute expiry |
| **Profile management** | Edit every field, upload a profile picture (auto-thumbnailed to 400×400 by Pillow), change password, delete account |

### Storyboard

| Capability | Detail |
| --- | --- |
| **Topics** | A curated topic catalogue with featured topics, plus search and A–Z / Z–A sort over the rest |
| **Three feeds per topic** | `For You` (everything), `Connections` (only people you are connected to), `Mine` |
| **Rich stories** | Title + body, multiple image/video attachments, and an optional **audio recording** |
| **Social layer** | Like and comment on stories, like comments, delete your own; counts and "did I like this" resolved in the same query |
| **Share to chat** | Send a story straight into a direct message as a linked `story_share` message |
| **Interest-aware home** | The home page surfaces the topics you chose at signup, plus a preview of recent stories from your connections |

### Events

| Capability | Detail |
| --- | --- |
| **Browse and register** | Carousel of upcoming events, participant counts, one-click signup with a validated form (Singapore `[89]xxxxxxx` phone format), and opt-out |
| **My Events calendar** | Registered events on a calendar with `all` / `week` / `month` filters, refreshable without a page load via `/api/calendar` |
| **Google Maps directions** | Route to any registered event with driving / walking / cycling / transit modes |
| **Propose an event** | A three-section proposal form — who you are, your event idea, and *why it matters* (meaningfulness, prior experience, **accessibility considerations**). Proposed dates must be at least 7 days out |
| **Submission lifecycle** | Pending → approved / rejected, with admin notes. Authors can edit and delete while pending; revoking an approval also deletes the published event and its registrations |
| **AI event posters** | Admins generate an event image with **Gemini 2.5 Flash Image** from the event's own title, type, date, time and location — no separate prompt to write |

Full feature-by-feature walkthrough, including the admin flows: [`EVENTS_SETUP.md`](EVENTS_SETUP.md).

### Connections and messaging

| Capability | Detail |
| --- | --- |
| **Connection requests** | Send, accept, reject, cancel, remove — all as JSON endpoints, so the UI updates without reloading |
| **Discovery** | Search by name with an age-group filter; admins are excluded from suggestions |
| **Notifications** | A navbar bell fed by `/api/notifications/summary` — pending incoming requests plus events starting within 3 days |
| **Direct and group chat** | Real-time over Socket.IO with per-user rooms (`user_<id>`), typing indicators, online/offline presence, and read receipts |
| **Group management** | Create groups, edit them, manage membership, delete |
| **Media messages** | Images, video and voice notes uploaded over HTTP, then broadcast to the same rooms so both paths land in one live thread |
| **Message editing** | Edit and delete your own messages |
| **Contacts CRUD** | A contact list separate from connections, with custom nicknames (2–50 chars). This is also the list the chess lobby invites from |

### Games

| Capability | Detail |
| --- | --- |
| **Chess vs. a person** | Invite a contact, accept or decline; live board sync over the `chess_<game_id>` Socket.IO room |
| **Chess vs. Stockfish** | Skill levels 1–20, choose white / black / random. If the engine binary is missing the bot falls back to a legal random move rather than erroring |
| **Server-authoritative rules** | Legal moves, move validation, checkmate/draw detection and results are all computed by `python-chess` on the server — the browser never decides what is legal |
| **Lobby** | Active games, incoming and outgoing invites, and forfeit |

### Settings and feedback

- **Appearance** — theme, text size, font family, font weight; stored in the `appearance` table, mirrored to `localStorage`, and injected into every template by a context processor so there is no flash of the wrong theme.
- **Language** — a full Google Translate language list (100+ codes) with alias normalisation.
- **Feedback** — submit positive/negative feedback, then view, edit and delete your own history.

---

## Architecture

```
                    Browser
   Jinja2 templates · Bootstrap 5 · vanilla JS · Socket.IO client
                       │
            HTTP       │      WebSocket
                       ▼
        ┌──────────────────────────────┐
        │   Flask app  (app.py)        │
        │   create_app() factory       │
        ├──────────────────────────────┤
        │  Flask-Login   session auth  │
        │  Flask-Session filesystem    │
        │  Flask-SocketIO  rooms:      │
        │    user_<id>                 │
        │    chess_<game_id>           │
        │    chess_lobby_<user_id>     │
        └──────────────┬───────────────┘
                       │
        ┌──────────────┴───────────────┐
        │        Blueprints            │
        │  auth · profile · main       │
        │  storyboard · topics         │
        │  events · connections        │
        │  messaging · chess · games   │
        └──────────────┬───────────────┘
                       │
     ┌─────────────────┼─────────────────────┐
     ▼                 ▼                     ▼
┌──────────┐   ┌────────────────┐   ┌──────────────────┐
│  MySQL   │   │ static/uploads │   │ External services│
│ (Railway)│   │ images · video │   ├──────────────────┤
│          │   │ audio · posters│   │ Gemini 2.5 Flash │
│ mysql-   │   └────────────────┘   │ Google Maps      │
│ connector│                        │ Google OAuth     │
│ + g-     │   ┌────────────────┐   │ Google Translate │
│ scoped   │   │ Stockfish UCI  │   │ Gmail SMTP       │
│ conns    │   │ subprocess     │   └──────────────────┘
└──────────┘   └────────────────┘
```

**Notable structural choices:**

- **No ORM.** Every query is hand-written parameterised SQL through a single `execute_query()` helper in [database.py](database.py). Connections are request-scoped on Flask's `g` and torn down by `teardown_appcontext`.
- **Async mode is platform-dependent.** `eventlet` with `monkey_patch()` on Linux; `threading` on Windows, where eventlet's patching is unreliable. The check happens in [app.py](app.py) *before* any other import.
- **The chess engine is a subprocess, not a service.** `python-chess` opens Stockfish over UCI per move with a 0.1s limit and quits it in a `finally`, so a hung engine cannot leak into the next request.
- **Two write paths, one broadcast shape.** Text messages go through Socket.IO; media messages go through an HTTP upload. Both emit the identical `new_message` payload to the same rooms, so the client renders one consistent thread.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Web framework | Flask 3.0 (blueprints + app factory) |
| Templating | Jinja2, Bootstrap 5.3, Bootstrap Icons |
| Real-time | Flask-SocketIO 5.6 / python-socketio — eventlet (Linux) or threading (Windows) |
| Auth | Flask-Login, Google OAuth 2.0, `itsdangerous` reset tokens |
| Sessions | Flask-Session, filesystem backend |
| Database | MySQL 8 via `mysql-connector-python`, hosted on **Railway** |
| Images | Pillow (profile thumbnails) |
| AI images | `google-genai` → `models/gemini-2.5-flash-image` |
| Maps | Google Maps JavaScript / Places / Directions / Geocoding APIs |
| Translation | `deep-translator` (Google Translate) |
| Chess | `python-chess` + Stockfish UCI engine |
| Email | Gmail SMTP via `smtplib` |
| Deployment | Vercel config present ([vercel.json](vercel.json)); Railway `PORT` honoured in [app.py](app.py) |

---

## Repository layout

```
├── app.py                     ← app factory, Socket.IO init, template filters,
│                                 appearance + translation context processors
├── config.py                  ← every setting, read from environment
├── database.py                ← get_db / execute_query, g-scoped connections
├── models.py                  ← User, Interest, Event, EventRegistration, EventSubmission
├── utils.py                   ← profile picture resize, age + age-group calculation
├── topics.py                  ← featured / searchable topic queries
├── story_service.py           ← story, media and comment queries
├── connections_service.py     ← accepted-connection id lookup
├── swearwords_filter.py       ← leetspeak-normalising profanity filter
│
├── routes/
│   ├── auth/__init__.py       ← signup (3 steps), login, Google OAuth, password
│   │                             reset, language, appearance, feedback, delete account
│   ├── main.py                ← home, notifications, calendar API
│   ├── profile.py             ← profile view + update
│   ├── storyboard.py          ← topics, stories, media, comments, likes
│   ├── topics_routes.py       ← standalone topic browser
│   ├── events.py              ← browse, register, propose, admin review, AI posters
│   ├── connections.py         ← request / accept / reject / cancel / remove
│   ├── messaging.py           ← contacts, groups, chat, message CRUD, uploads
│   ├── chess.py               ← lobby, invites, bot games, move validation
│   ├── games.py               ← games hub
│   └── socketio_events.py     ← connect, messaging, typing, presence, chess rooms
│
├── templates/                 ← Jinja2, one folder per blueprint, all extend base.html
├── static/
│   ├── css/                   ← style.css · events.css · chess.css
│   ├── js/                    ← chess.js · chess_lobby.js
│   └── uploads/               ← profile_pics · events · story_media · story_audio
│
├── migrations/                ← incremental SQL, run in order
├── stockfish/                 ← chess engine binary (Git LFS)
├── EVENTS_SETUP.md            ← events subsystem: setup, flows, troubleshooting
└── requirements.txt
```

---

## Getting started

### Prerequisites

- **Python 3.11+** (developed on 3.13)
- **MySQL 8** — local, or a hosted instance such as Railway
- **Git LFS** — the Stockfish binary is stored via LFS (see [.gitattributes](.gitattributes))
- Optional, each gating one feature: a Google Maps key, a Gemini key, Google OAuth credentials, and Gmail SMTP credentials. Leave any unset and only that feature degrades; the app still boots.

### 1. Clone and install

```bash
git clone https://github.com/mahdiyaa/WDP_PROJECT_FINAL.git
cd WDP_PROJECT_FINAL
```

```bash
python -m venv venv
```

```bash
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

### 2. Configure the environment

Create a `.env` file in the project root. **It is git-ignored — never commit it.**

```env
SECRET_KEY=change-this-to-a-long-random-string

MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=genlink
MYSQL_PORT=3306

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-address@gmail.com
MAIL_APP_PASSWORD=your-16-char-app-password
RESET_TOKEN_MAX_AGE_SECONDS=1800

GOOGLE_MAPS_API_KEY=
GOOGLE_GENAI_API_KEY=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:5000/auth/signup/google/callback

STOCKFISH_PATH=stockfish/stockfish.exe
```

### 3. Set up the database

Create the schema, then apply the migrations in order:

```bash
mysql -u root -p genlink < migrations/001_add_image_url_event_submissions.sql
mysql -u root -p genlink < migrations/002_create_chess_tables.sql
mysql -u root -p genlink < migrations/003_add_chess_bot_level.sql
```

Seed the `topics` table before first use — signup Step 3 and the whole Storyboard read from it. Sample event inserts are in [`EVENTS_SETUP.md`](EVENTS_SETUP.md#sample-data).

### 4. Run

```bash
python app.py
```

The app serves on `http://localhost:5000` (or `$PORT`, which is how Railway starts it).

### 5. Create an admin

Admin-only surfaces — the submission review queue, event creation and AI poster generation — are gated on `user_type`:

```sql
UPDATE users SET user_type = 'admin' WHERE email = 'you@gmail.com';
```

---

## Environment variables

| Variable | Purpose | Unset behaviour |
| --- | --- | --- |
| `SECRET_KEY` | Flask session signing and reset tokens | Falls back to an insecure default — **always set in production** |
| `MYSQL_HOST` / `USER` / `PASSWORD` / `DATABASE` / `PORT` | Database connection | App cannot start |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USE_TLS` | SMTP transport | Defaults to Gmail on 587 with TLS |
| `MAIL_USERNAME` / `MAIL_APP_PASSWORD` | Gmail account and app password | Password reset emails fail |
| `RESET_TOKEN_MAX_AGE_SECONDS` | Reset link lifetime | 1800 (30 minutes) |
| `GOOGLE_MAPS_API_KEY` | Maps JavaScript, Places, Directions, Geocoding | Event directions unavailable |
| `GOOGLE_GENAI_API_KEY` | Gemini 2.5 Flash Image | AI poster generation returns an error; manual upload still works |
| `GOOGLE_OAUTH_CLIENT_ID` / `CLIENT_SECRET` / `REDIRECT_URI` | Google sign-in | Google buttons fail; email signup unaffected |
| `STOCKFISH_PATH` | Engine binary, absolute or relative to the app root | Bot plays random legal moves instead of engine moves |

`MAX_CONTENT_LENGTH` caps uploads at 5 MB and `ALLOWED_EXTENSIONS` restricts profile pictures to `png/jpg/jpeg/gif`; both are set in [config.py](config.py).

---

## Data model

MySQL, 21 tables, no ORM:

| Group | Tables |
| --- | --- |
| **Identity** | `users` · `appearance` · `interests` · `user_interests` · `feedback` |
| **Social graph** | `connections` (requester / receiver + status) · `contacts` |
| **Storyboard** | `topics` · `stories` · `story_media` · `story_likes` · `comments` · `comment_likes` |
| **Events** | `events` · `event_registrations` · `event_submissions` |
| **Messaging** | `messages` · `groups` · `group_members` |
| **Chess** | `chess_games` (FEN + SAN move list + result) · `chess_invites` |

`chess_games` stores the board as a **FEN string** plus a JSON array of SAN moves, so a game is fully reconstructible from one row and a reconnecting player resumes exactly where they left off.

---

## Roles

| Role (`users.user_type`) | Can do |
| --- | --- |
| `user` | Everything above: stories, events, connections, messaging, chess, settings, feedback |
| `admin` | All of the above, plus review and approve/reject event submissions, create events directly, and generate AI event posters. Admins are hidden from connection suggestions |

---

## Security notes

- **Every** query is parameterised — no string-interpolated user input reaches SQL.
- Uploads are run through `secure_filename()`, extension-allowlisted, size-capped at 5 MB, and stored under `static/uploads/` with UUID filenames for story media.
- Profanity filtering runs on both the HTTP and Socket.IO message paths, so neither can be used to bypass the other.
- Socket.IO handlers re-check `current_user.is_authenticated` on every event, and chess room joins verify the user is actually a player in that game.
- Admin routes check `current_user.user_type` server-side, not just in the template.
- Secrets live only in `.env`, which is git-ignored; `config.py` contains names and defaults, never values.

> **Known limitation:** passwords are currently compared as stored strings rather than hashes (`User.check_password`). Moving to `werkzeug.security.generate_password_hash` / `check_password_hash` is the single highest-value hardening change to this codebase.

---

## Team

Five members. Primary ownership, by the files each person actually authored:

| Member | Primary area |
| --- | --- |
| **Hasini** | Authentication — 3-step signup, login, Google OAuth, password reset, appearance and language settings, feedback; plus the base template |
| **Philena** | Events and the events admin queue, including AI poster generation; chess and the games hub; home and topic browsing |
| **Mahdiya** | Storyboard — topics, stories, media, comments and likes |
| **Ridzwan** | Messaging — contacts, groups, chat, uploads and message CRUD |
| **Zoe** | Connections and the home page |

Work is shared across the codebase; the table reflects where each member did most of it.

---

## Further reading

- [`EVENTS_SETUP.md`](EVENTS_SETUP.md) — the events subsystem end to end: setup, admin flows, Google Maps configuration, sample data, and troubleshooting.
