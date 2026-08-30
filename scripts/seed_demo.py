"""
Seed a Genlink database with demo content.

Creates a small but complete world: topics, users across all three age
groups, connections, stories with likes and comments, events dated
relative to today, a pending event submission for the admin queue, and
chat history. Every date is computed from `now`, so the demo never goes
stale.

    python scripts/seed_demo.py            # seed, refusing to clobber data
    python scripts/seed_demo.py --reset    # wipe every table first

WARNING: --reset deletes ALL rows in ALL tables. Only ever point this at
a database you created for the demo.

NOTE ON PASSWORDS: this application compares passwords as plain strings
(see User.check_password), so the demo passwords below are stored as
plain text. They are throwaway credentials for a public demo. Never
reuse a real password here.
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector

load_dotenv()

# --------------------------------------------------------------------------
# Demo credentials — these are what you publish
# --------------------------------------------------------------------------

# NOTE: the login form authenticates on USERNAME, not email
# (see User.get_by_username in the login route). The usernames below are
# what you publish; the emails are only used for password reset and the
# event signup forms.

DEMO_USER_EMAIL = "demo@gmail.com"
DEMO_USER_USERNAME = "demo"
DEMO_USER_PASSWORD = "Demo@1234"

DEMO_ADMIN_EMAIL = "admin.demo@gmail.com"
DEMO_ADMIN_USERNAME = "admindemo"
DEMO_ADMIN_PASSWORD = "Admin@1234"

# Every other seeded account shares this password so you can log in as any
# of them to show a second perspective (e.g. the other side of a chat).
COMMUNITY_PASSWORD = "Genlink@1234"


# --------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------

FEATURED_TOPICS = [
    ("Food & Culinary Heritage", "food-and-culinary-heritage", "food-and-culinary-heritage.webp", "Culture"),
    ("Nature & Environment", "nature-and-environment", "nature-and-environment.avif", "Lifestyle"),
    ("Technology & Innovation", "technology-and-innovation", "technology-and-innovation.jpg", "Technology"),
    ("Arts & Entertainment", "arts-and-entertainment", "arts-and-entertainment.png", "Culture"),
]

TOPICS = [
    ("Culture & Tradition", "culture-and-tradition", "culture-and-tradition.jpg", "Culture"),
    ("Family & Traditions", "family-and-traditions", "family-and-traditions.jpeg", "Culture"),
    ("Health & Wellness", "health-and-wellness", "health-and-wellness.jpg", "Lifestyle"),
    ("Travel & Exploration", "travel-and-exploration", "travel-and-exploration.jpg", "Lifestyle"),
    ("Work & Careers", "work-and-careers", "work-and-careers.webp", "Career"),
    ("Education & School Life", "education-and-school-life", "education-and-school-life.jpg", "Education"),
    ("History", "history", "history.jpg", "Culture"),
    ("Festivals", "festivals", "festivals.jpg", "Culture"),
    ("Language", "language", "language.jpg", "Culture"),
    ("Sports", "sports", "sports.avif", "Lifestyle"),
    ("Photography", "photography", "photography.jpg", "Hobbies"),
    ("Writing", "writing", "writing.jpg", "Hobbies"),
    ("Gaming", "gaming", "gaming.jpg", "Hobbies"),
    ("Mindfulness", "mindfulness", "mindfulness.jpg", "Lifestyle"),
    ("Community", "community", "community.jpg", "Community"),
    ("Religion", "religion", "religion.jpg", "Culture"),
]

# (email, username, display_name, first, last, dob, age_group, phone, interests)
COMMUNITY = [
    ("mei.tan.demo@gmail.com", "meitan", "Mei", "Mei", "Tan", date(1952, 3, 14), "elderly", "81234501",
     "food-and-culinary-heritage,history,culture-and-tradition"),
    ("raj.kumar.demo@gmail.com", "rajkumar", "Raj", "Raj", "Kumar", date(1948, 11, 2), "elderly", "81234502",
     "history,language,community"),
    ("aisha.rahman.demo@gmail.com", "aisharahman", "Aisha", "Aisha", "Rahman", date(2007, 6, 21), "youth", "81234503",
     "technology-and-innovation,photography,arts-and-entertainment"),
    ("kai.wong.demo@gmail.com", "kaiwong", "Kai", "Kai", "Wong", date(2006, 1, 9), "youth", "81234504",
     "gaming,sports,technology-and-innovation"),
    ("siti.nur.demo@gmail.com", "sitinur", "Siti", "Siti", "Nur", date(1985, 8, 30), "adult", "81234505",
     "nature-and-environment,health-and-wellness,community"),
    ("david.lim.demo@gmail.com", "davidlim", "David", "David", "Lim", date(1979, 4, 17), "adult", "81234506",
     "work-and-careers,travel-and-exploration,writing"),
]

# (author_username, topic_slug, title, body)
STORIES = [
    ("meitan", "food-and-culinary-heritage",
     "My mother's laksa recipe, written down at last",
     "For sixty years it lived only in her hands — a pinch of this, a handful of that, never a "
     "measurement. Last month my granddaughter sat in the kitchen with a notebook and made me cook it "
     "slowly, stopping to weigh everything. It took four hours. The recipe is now two pages long and I "
     "cried when she read it back to me."),
    ("rajkumar", "history",
     "The kampung that used to stand where the mall is",
     "People walk through that shopping centre every day and have no idea. There was a well right about "
     "where the escalator is now. We used to queue there in the mornings. I still catch myself looking "
     "for it."),
    ("aisharahman", "technology-and-innovation",
     "Teaching my grandfather to video call — what I learned",
     "I thought it would take ten minutes. It took three weeks. Not because he could not learn, but "
     "because I kept explaining it the way I understand phones, not the way he does. Once I stopped "
     "saying 'just tap the icon' and started saying 'press the green picture of a camera', everything "
     "changed. The problem was never him."),
    ("kaiwong", "gaming",
     "I taught my neighbour chess. He has not lost since.",
     "Uncle Chua is 78. I showed him the app on a Tuesday. By Friday he had beaten me nine times in a "
     "row and started explaining what I was doing wrong. He apparently played competitively in the "
     "seventies and did not think to mention it."),
    ("sitinur", "nature-and-environment",
     "Our block's rooftop garden, one year on",
     "We started with four pots and a lot of scepticism. There are now thirty-two planters, a compost "
     "bin, and a rota pinned to the lift lobby. The oldest gardener is 81 and the youngest is 9, and "
     "they argue constantly about tomatoes."),
    ("davidlim", "work-and-careers",
     "Changing careers at 45, with advice from someone who did it at 60",
     "I was terrified. Then I met a man at a Genlink event who retrained as an electrician in his "
     "sixties after thirty years in shipping. He said the only thing that surprised him was how much "
     "of the old job turned out to be useful. He was right."),
]

# (title, description, days_from_today, start, end, location, address, type, max, image)
EVENTS = [
    ("Hawker Heritage Cooking Session",
     "Seniors and youth pair up to cook three classic hawker dishes together. All ingredients provided. "
     "No experience needed — you will be taught by people who have made these dishes for decades.",
     6, "10:00:00", "13:00:00", "Tampines Community Club",
     "1 Tampines Walk, Singapore 528523", "Community", 30,
     "/static/uploads/events/20260222_014244_Xiao_Bai_Cai-H1.jpg"),

    ("Beach Clean-Up & Breakfast",
     "An early morning clean-up at East Coast Park followed by breakfast together. Gloves, bags and "
     "grabbers provided. Family friendly and wheelchair accessible along the main path.",
     13, "07:30:00", "10:30:00", "East Coast Park",
     "East Coast Park Service Rd, Singapore", "Environment", 60,
     "/static/uploads/events/20260214_002931_beach_clean.jpeg"),

    ("Digital Skills Drop-In Clinic",
     "Bring your phone and your questions. Youth volunteers help with video calling, banking apps, "
     "scam awareness and photo sharing. One-to-one, at your own pace, in English or Mandarin.",
     20, "14:00:00", "17:00:00", "Woodlands Regional Library",
     "900 South Woodlands Dr, Singapore 730900", "Workshop", 40,
     "/static/uploads/events/ai_20260223_012100_Mothers_Day.png"),

    ("Intergenerational Cycling Morning",
     "A gentle 8km ride along the park connector, with rest stops. Tandem and tricycle options "
     "available for those who want them. Helmets provided.",
     27, "08:00:00", "11:00:00", "Punggol Waterway Park",
     "Sentul Cres, Singapore 821313", "Sports", 25,
     "/static/uploads/events/20260223_203358_ageless_cyclists_3.png"),

    ("Storytelling Night: Kampung Memories",
     "An evening of shared memories. Four seniors tell stories from Singapore in the 1950s and 60s, "
     "recorded with their permission for the Genlink storyboard archive.",
     34, "19:00:00", "21:00:00", "Kampong Glam Community Centre",
     "37 Beach Rd, Singapore 189678", "Social", 80,
     "/static/uploads/events/20260222_193758_climate.jpg"),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

# Order matters: children before parents.
WIPE_ORDER = [
    "comment_likes", "story_likes", "comments", "story_media", "stories",
    "chess_invites", "chess_games",
    "messages", "group_members", "`groups`",
    "event_registrations", "event_submissions", "events",
    "contacts", "connections",
    "user_interests", "interests", "appearance", "feedback",
    "topics", "users",
]


def connect():
    cfg = dict(
        host=os.environ.get("MYSQL_HOST"),
        user=os.environ.get("MYSQL_USER"),
        password=os.environ.get("MYSQL_PASSWORD"),
        database=os.environ.get("MYSQL_DATABASE"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        connection_timeout=30,
    )
    missing = [k for k in ("host", "user", "database") if not cfg[k]]
    if missing:
        sys.exit(f"Missing environment variables for: {', '.join(missing)}. Check your .env file.")
    print(f"Connecting to {cfg['host']}:{cfg['port']}/{cfg['database']} ...")
    return mysql.connector.connect(**cfg)


def age_group_for(dob, today):
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 13:
        return None
    if age <= 20:
        return "youth"
    if age <= 59:
        return "adult"
    return "elderly"


def wipe(cur):
    print("\nWiping existing rows ...")
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in WIPE_ORDER:
        try:
            cur.execute(f"TRUNCATE TABLE {table}")
            print(f"  cleared {table}")
        except mysql.connector.Error as exc:
            print(f"  skipped {table} ({exc.errno})")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")


def already_seeded(cur):
    cur.execute("SELECT COUNT(*) FROM users")
    return cur.fetchone()[0] > 0


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------

def seed(cur, today):
    # --- topics ---------------------------------------------------------
    topic_ids = {}
    for title, slug, image, category in FEATURED_TOPICS:
        cur.execute(
            "INSERT INTO topics (title, slug, image, category, is_featured) VALUES (%s,%s,%s,%s,1)",
            (title, slug, image, category),
        )
        topic_ids[slug] = cur.lastrowid
    for title, slug, image, category in TOPICS:
        cur.execute(
            "INSERT INTO topics (title, slug, image, category, is_featured) VALUES (%s,%s,%s,%s,0)",
            (title, slug, image, category),
        )
        topic_ids[slug] = cur.lastrowid
    print(f"  topics: {len(topic_ids)}")

    # --- users ----------------------------------------------------------
    def add_user(email, username, display, first, last, dob, phone, interests,
                 password, user_type="user"):
        cur.execute(
            """
            INSERT INTO users
                (email, username, password_hash, user_type, first_name, last_name,
                 display_name, date_of_birth, phone_number, age_group,
                 profile_completed, language, interests)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,'en',%s)
            """,
            (email, username, password, user_type, first, last, display, dob,
             phone, age_group_for(dob, today), interests),
        )
        uid = cur.lastrowid
        cur.execute(
            "INSERT INTO appearance (user_id, theme, text_size, font_style, boldness) "
            "VALUES (%s,'lightmode',16,'Poppins','medium')",
            (uid,),
        )
        return uid

    demo_id = add_user(
        DEMO_USER_EMAIL, DEMO_USER_USERNAME, "Demo User", "Demo", "User",
        date(1996, 5, 12), "81234500",
        "food-and-culinary-heritage,history,technology-and-innovation",
        DEMO_USER_PASSWORD,
    )
    admin_id = add_user(
        DEMO_ADMIN_EMAIL, DEMO_ADMIN_USERNAME, "Genlink Admin", "Genlink", "Admin",
        date(1990, 2, 2), "81234599",
        "community,education-and-school-life",
        DEMO_ADMIN_PASSWORD, user_type="admin",
    )

    user_ids = {"demo": demo_id, "admindemo": admin_id}
    for email, username, display, first, last, dob, _ag, phone, interests in COMMUNITY:
        user_ids[username] = add_user(
            email, username, display, first, last, dob, phone, interests,
            COMMUNITY_PASSWORD,
        )
    print(f"  users: {len(user_ids)}")

    # --- connections ----------------------------------------------------
    # Demo user is connected to four people and has two pending requests
    # waiting, so the notification bell is not empty on first login.
    accepted = ["meitan", "aisharahman", "sitinur", "kaiwong"]
    pending_incoming = ["rajkumar", "davidlim"]

    def add_connection(requester, receiver, status):
        lo, hi = sorted((requester, receiver))
        cur.execute(
            """
            INSERT INTO connections
                (requester_id, receiver_id, user_low, user_high, status, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,NOW(),NOW())
            """,
            (requester, receiver, lo, hi, status),
        )

    for name in accepted:
        add_connection(demo_id, user_ids[name], "accepted")
    for name in pending_incoming:
        add_connection(user_ids[name], demo_id, "pending")

    # A few connections between community members so suggestions look real.
    add_connection(user_ids["meitan"], user_ids["aisharahman"], "accepted")
    add_connection(user_ids["rajkumar"], user_ids["kaiwong"], "accepted")
    print(f"  connections: {len(accepted) + len(pending_incoming) + 2}")

    # --- contacts (the chess lobby invites from this list) ---------------
    for name in accepted:
        cur.execute(
            "INSERT INTO contacts (user_id, contact_user_id, nickname) VALUES (%s,%s,%s)",
            (demo_id, user_ids[name], None),
        )
        cur.execute(
            "INSERT INTO contacts (user_id, contact_user_id, nickname) VALUES (%s,%s,%s)",
            (user_ids[name], demo_id, None),
        )
    print(f"  contacts: {len(accepted) * 2}")

    # --- stories, likes, comments ---------------------------------------
    story_ids = []
    for username, slug, title, body in STORIES:
        cur.execute(
            "INSERT INTO stories (user_id, topic_id, title, body) VALUES (%s,%s,%s,%s)",
            (user_ids[username], topic_ids[slug], title, body),
        )
        story_ids.append(cur.lastrowid)

    likers = ["demo", "meitan", "aisharahman", "sitinur", "kaiwong", "davidlim"]
    like_count = 0
    for i, sid in enumerate(story_ids):
        for username in likers[: 3 + (i % 3)]:
            cur.execute(
                "INSERT IGNORE INTO story_likes (story_id, user_id) VALUES (%s,%s)",
                (sid, user_ids[username]),
            )
            like_count += 1

    COMMENTS = [
        (0, "aisharahman", "Please post the recipe! My grandmother makes hers with more tamarind."),
        (0, "demo", "Four hours well spent. This is exactly what this place is for."),
        (1, "kaiwong", "I walk through there every week. I will never see it the same way again."),
        (2, "meitan", "'Press the green picture of a camera.' You have taught me something today."),
        (3, "demo", "Uncle Chua sounds dangerous. Please arrange a match."),
        (4, "rajkumar", "Which block? I would like to see it — I grew a little in my corridor."),
    ]
    for idx, username, body in COMMENTS:
        cur.execute(
            "INSERT INTO comments (story_id, user_id, body) VALUES (%s,%s,%s)",
            (story_ids[idx], user_ids[username], body),
        )
    print(f"  stories: {len(story_ids)} · likes: {like_count} · comments: {len(COMMENTS)}")

    # --- events ---------------------------------------------------------
    event_ids = []
    for (title, desc, offset, start, end, loc, addr, etype, cap, img) in EVENTS:
        cur.execute(
            """
            INSERT INTO events
                (title, description, event_date, start_time, end_time, location,
                 location_address, image_url, max_participants, current_participants,
                 event_type, created_by, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,'upcoming')
            """,
            (title, desc, today + timedelta(days=offset), start, end, loc, addr,
             img, cap, etype, admin_id),
        )
        event_ids.append(cur.lastrowid)

    # Demo user is registered for the first two, so "My Events" and the
    # calendar are populated and the 3-day reminder can fire.
    for eid in event_ids[:2]:
        cur.execute(
            """
            INSERT INTO event_registrations
                (event_id, user_id, full_name, email, phone_number, confirmed)
            VALUES (%s,%s,%s,%s,%s,TRUE)
            """,
            (eid, demo_id, "Demo User", DEMO_USER_EMAIL, "81234500"),
        )
    for eid in event_ids[:3]:
        for name in ("meitan", "aisharahman", "sitinur"):
            cur.execute(
                """
                INSERT IGNORE INTO event_registrations
                    (event_id, user_id, full_name, email, phone_number, confirmed)
                VALUES (%s,%s,%s,%s,%s,TRUE)
                """,
                (eid, user_ids[name], name.title(), f"{name}.demo@gmail.com", "81234500"),
            )
    cur.execute(
        "UPDATE events e SET current_participants = "
        "(SELECT COUNT(*) FROM event_registrations r WHERE r.event_id = e.id)"
    )
    print(f"  events: {len(event_ids)} (registrations seeded)")

    # --- event submissions (so the admin queue is not empty) ------------
    SUBMISSIONS = [
        (demo_id, "Demo User", DEMO_USER_EMAIL, "81234500", "pending", None,
         "Board Games Afternoon",
         "A relaxed afternoon of board games pairing secondary school students with residents.",
         "Social", 40, 45,
         "Both my grandparents live alone and the highlight of their week is company, not activities. "
         "Board games give people a reason to sit at the same table for two hours.",
         "I helped run a games stall at my school's open house last year.",
         "Step-free venue, large-print rule cards, and a quiet corner for anyone who needs a break."),
        (user_ids["sitinur"], "Siti Nur", "siti.nur.demo@gmail.com", "81234505", "approved", admin_id,
         "Rooftop Garden Open Day",
         "Tours of our block's rooftop garden with seedlings to take home.",
         "Environment", 25, 60,
         "The garden was built by residents aged 9 to 81 and we would like to show other blocks how.",
         "I coordinate the garden rota for 32 planters.",
         "Lift access to the roof, seating throughout, and shade cover over the main beds."),
    ]
    for (uid, name, email, phone, status, reviewer, title, summary, etype,
         participants, offset, why, prev, access) in SUBMISSIONS:
        cur.execute(
            """
            INSERT INTO event_submissions
                (user_id, organizer_name, organizer_age_group, organizer_email,
                 organizer_phone, organizer_location, event_title, event_summary,
                 event_type, preferred_date, expected_participants, why_meaningful,
                 previous_experience, accessibility_considerations, status,
                 reviewed_by, reviewed_at, admin_notes)
            VALUES (%s,%s,'adult',%s,%s,'Singapore',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (uid, name, email, phone, title, summary, etype,
             today + timedelta(days=offset), participants, why, prev, access, status,
             reviewer,
             datetime.now() if reviewer else None,
             "Approved. Great accessibility planning." if reviewer else None),
        )
    print(f"  event submissions: {len(SUBMISSIONS)} (1 pending for the admin queue)")

    # --- messages -------------------------------------------------------
    CHAT = [
        ("meitan", "demo", "Thank you for the kind words on my laksa story!"),
        ("demo", "meitan", "I meant every word. Is the recipe somewhere I can read it?"),
        ("meitan", "demo", "My granddaughter is typing it up. I will send it this week."),
        ("demo", "meitan", "Are you going to the hawker heritage session on Saturday?"),
        ("meitan", "demo", "I am helping to run it. Come and find me at the second station."),
        ("aisharahman", "demo", "Saw you signed up for the beach clean-up. I'll be there too!"),
        ("demo", "aisharahman", "Great. Bring sunscreen, last time I got burnt within an hour."),
    ]
    for sender, receiver, text in CHAT:
        cur.execute(
            """
            INSERT INTO messages (sender_id, receiver_id, message_type, content, is_read)
            VALUES (%s,%s,'text',%s,TRUE)
            """,
            (user_ids[sender], user_ids[receiver], text),
        )

    # A group chat with history.
    cur.execute(
        "INSERT INTO `groups` (name, description, created_by) VALUES (%s,%s,%s)",
        ("Beach Clean-Up Crew", "Planning for the East Coast Park clean-up", demo_id),
    )
    gid = cur.lastrowid
    for username, is_admin in (("demo", True), ("aisharahman", False),
                               ("sitinur", False), ("kaiwong", False)):
        cur.execute(
            "INSERT INTO group_members (group_id, user_id, is_admin) VALUES (%s,%s,%s)",
            (gid, user_ids[username], is_admin),
        )
    for sender, text in (
        ("demo", "Meeting point is the carpark by the food centre, 7.30am sharp."),
        ("sitinur", "I can bring two extra grabbers and a first aid kit."),
        ("kaiwong", "I'll bring my speaker. Music makes the two hours go faster."),
        ("aisharahman", "Breakfast after is on me if we fill more than twenty bags."),
    ):
        cur.execute(
            """
            INSERT INTO messages (sender_id, group_id, message_type, content)
            VALUES (%s,%s,'text',%s)
            """,
            (user_ids[sender], gid, text),
        )
    print(f"  messages: {len(CHAT)} direct + 4 group · 1 group chat")


def main():
    parser = argparse.ArgumentParser(description="Seed the Genlink demo database.")
    parser.add_argument("--reset", action="store_true",
                        help="Delete all existing rows before seeding.")
    args = parser.parse_args()

    today = date.today()
    cn = connect()
    cur = cn.cursor()

    try:
        if args.reset:
            wipe(cur)
        elif already_seeded(cur):
            sys.exit(
                "\nThis database already contains users.\n"
                "Re-run with --reset to wipe it and seed from scratch, but only if\n"
                "you are certain this is your throwaway demo database."
            )

        print("\nSeeding ...")
        seed(cur, today)
        cn.commit()
    except Exception:
        cn.rollback()
        raise
    finally:
        cur.close()
        cn.close()

    print(f"""
Done. Demo credentials — log in with the USERNAME, not the email:

    Regular user   {DEMO_USER_USERNAME} / {DEMO_USER_PASSWORD}
    Admin          {DEMO_ADMIN_USERNAME} / {DEMO_ADMIN_PASSWORD}
    Any community  meitan | rajkumar | aisharahman | kaiwong | sitinur |
                   davidlim  ...  all with {COMMUNITY_PASSWORD}

Log in as the admin to review the pending event submission at
/events/admin/submissions.
""")


if __name__ == "__main__":
    main()
