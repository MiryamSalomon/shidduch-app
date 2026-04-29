"""
Seed Candidates Script
=======================
Populates the ``candidates`` collection with 25 male and 25 female realistic
fake candidates for development and demos. Each candidate has plausible
Hebrew/Jewish names, communities, yeshivas/seminaries, character traits,
and partner preferences in Hebrew.

After insertion the script also generates OpenAI embeddings for every
seeded candidate so they are immediately ready for AI-driven matching.

Usage
-----
    cd backend
    python scripts/seed_candidates.py

Idempotent
----------
On second run, the script detects existing candidates inserted by a previous
seeding pass (recognised by the ``seed_marker`` field) and exits without
inserting duplicates. Pass ``--force`` to delete the previous seed batch and
re-insert fresh records.

Cost estimate
-------------
Embeddings: ~50 candidates × 2 texts × ~$0.0002 = a few US cents per run.
"""

import argparse
import asyncio
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Make the backend package importable when running from project root or backend/.
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.services import embeddings


# ---------------------------------------------------------------------------
# Constants — used across all the seed-data pools below.
# ---------------------------------------------------------------------------

SEED_MARKER = "seed_v1"  # Tag attached to every record this script inserts.
TARGET_PER_GENDER = 25
RANDOM_SEED = 42  # Fixed for reproducible output across runs.


# ---------------------------------------------------------------------------
# Data pools (Hebrew / Jewish realistic)
# ---------------------------------------------------------------------------

MALE_FIRST_NAMES = [
    "אברהם", "יצחק", "יעקב", "משה", "אהרן", "יוסף", "דוד", "שלמה", "אליהו",
    "מרדכי", "שמואל", "חיים", "מנחם", "נתן", "יהודה", "בנימין", "יהושע",
    "אריה", "דניאל", "אלעזר", "פנחס", "ראובן", "שמעון", "צבי", "נחמן",
]

FEMALE_FIRST_NAMES = [
    "שרה", "רבקה", "רחל", "לאה", "מרים", "חנה", "אסתר", "תמר", "דבורה",
    "יעל", "רות", "נעמי", "חוה", "ביילה", "פרידה", "חיה", "מלכה", "ברכה",
    "שיינדל", "פרומה", "טובה", "מאירה", "אהובה", "ציפורה", "בתיה",
]

LAST_NAMES = [
    "כהן", "לוי", "פרידמן", "גולדברג", "רוזנברג", "שטיינברג", "ויינברג",
    "פינקל", "ליכטנשטיין", "האלפרין", "ברוורמן", "הירשפלד", "שפירא",
    "מלמד", "טייטלבוים", "פיינשטיין", "סלובייצ'יק", "ברנשטיין",
    "כץ", "אדלשטיין", "וייס", "גרוס", "פרנקל", "לנדאו", "אזולאי",
]

CITIES = [
    "ירושלים", "בני ברק", "מודיעין עילית", "ביתר עילית", "בית שמש",
    "אלעד", "אשדוד", "נתיבות", "צפת", "טבריה", "פתח תקווה", "רחובות",
]

# Major yeshivas — used for males.
YESHIVAS = [
    "ישיבת מיר", "ישיבת בריסק", "ישיבת חברון", "ישיבת פוניבז'",
    "ישיבת סלבודקא", "ישיבת קמניץ", "ישיבת אור ישראל", "ישיבת גרודנא",
    "ישיבת בית מתתיהו", "ישיבת תורה ודעת",
]

# Seminaries — used for females.
SEMINARIES = [
    "סמינר בית יעקב הישן", "סמינר בנות שרה", "סמינר מיכלל",
    "סמינר אופקים", "סמינר בית רבקה", "סמינר וולף",
    "סמינר בנות חיה", "סמינר בית יעקב הירושלמי",
]

PROFESSIONS_MALE = [
    "אברך כולל", "מלמד", "ר\"מ בישיבה קטנה", "סופר סת\"ם",
    "מהנדס תוכנה", "רואה חשבון", "עובד הוראה", "סוחר", "טכנאי מחשבים",
]

PROFESSIONS_FEMALE = [
    "מורה", "גננת", "מטפלת", "מזכירה", "אחות", "פיזיותרפיסטית",
    "מעצבת גרפית", "אחראית הוראה", "עוזרת אישית",
]

FATHER_PROFESSIONS = [
    "אברך כולל", "ראש כולל", "ר\"מ בישיבה", "סוחר", "רואה חשבון",
    "עורך דין", "רב קהילה", "מנהל בית ספר",
]

MOTHER_PROFESSIONS = [
    "מורה", "גננת", "אם בית", "מנהלת סמינר", "אחות", "פסיכולוגית",
    "מטפלת רגשית", "מורה לספרות",
]

CHARACTER_TRAITS_POOL = [
    "אדם רציני, שקוע בלימוד, בעל מידות טובות ויחס חם לזולת. שואף לגדול בתורה ולבנות בית של תורה ויראת שמים.",
    "בחור מתמיד וחרוץ, שמח ובעל אופי נעים. אוהב לעזור לאחרים ובעל יכולת ביטוי גבוהה.",
    "אישיות שקטה, צנועה ועדינה. בעלת לב טוב, רגישה לזולת, מסודרת ובעלת שמחת חיים.",
    "אוהבת תורה ומשפחה, רגישה ואחראית. בעלת תכונות של נתינה, סבלנות וביטחון פנימי.",
    "בחור שאפתן ומסור, בעל יראת שמים אמיתית ושאיפות לימוד גבוהות. רגיש ואכפתי כלפי הסביבה.",
    "אישה צעירה רצינית, אוהבת ילדים, מאורגנת ובעלת אופי מאוזן. שואפת לבנות בית עם אווירה רוחנית חמה.",
    "אדם פתוח, נעים הליכות, אוהב חברה ובעל יכולת לימוד טובה. שואף להיות חיוני בקהילה.",
    "בחורה שמחה, יצירתית, חכמה ובעלת תושייה. מעריכה כנות, אמת ופשטות.",
    "מתמיד גדול בלימודו, ירא שמים, נעים הליכות ובעל מידות מתוקנות. אוהב משפחה ושלום בית.",
    "אישיות מאוזנת, חכמה ובעלת יכולת הקשבה. אוהבת בית, ילדים ולימוד בעיון.",
]

PREFERENCES_POOL = [
    "מחפש/ת בן/בת זוג רציני/ת, בעל/ת מידות טובות, יראת שמים אמיתית ושאיפה לבית של תורה. חשובה התאמה אישית, אווירה חמה ושותפות אמיתית.",
    "מחפש/ת אדם שקט, ישר ונעים הליכות. בעל/ת מטרות ברורות בחיים, אהבת תורה ויחס חם למשפחה ולזולת.",
    "מחפש/ת בן/בת זוג שמח/ה, אופטימי/ת, בעל/ת ביטחון עצמי בריא ויכולת לבנות בית של אהבה והבנה.",
    "מעדיף/ה אדם בעל מידות טובות, צנוע, אכפתי ובעל לב חם. חשובה לי קרבה למשפחה ויחסים בריאים.",
    "מחפש/ת מישהו/י עם רוחב לב, יציבות רגשית, רצון להתפתח רוחנית ובית בעל אווירה תורנית מאוזנת.",
    "מחפש/ת בן/בת זוג שמבין/ה את חשיבות הלימוד, מעריך/ה זמן ביחד, ובעל/ת חשיבה מסודרת ובוגרת.",
    "מעוניין/ת באדם בעל יראת שמים, מידות מתוקנות, נעימות ויכולת לבנות בית שלום ואושר.",
    "מחפש/ת חבר/ה לחיים — אדם רגיש, אוהב/ת אמת, בעל/ת תושייה ושאיפה אמיתית לגדול ביחד.",
]

HAIR_COLORS = ["שחור", "חום", "בלונד", "אדמוני", "כהה"]

LANGUAGES_POOL = [
    ["עברית"],
    ["עברית", "אידיש"],
    ["עברית", "אנגלית"],
    ["עברית", "אנגלית", "אידיש"],
    ["עברית", "צרפתית"],
    ["עברית", "ספרדית"],
]

COMMUNITIES = ["litvish", "chassidish", "dati-leumi", "sephardi", "mixed"]

CLOTHING_STYLES = ["חליפה ומגבעת", "חליפה וכובע", "מסורתי", "אלגנטי", "צנוע"]

KOVA_SUIT_TYPES = ["מגבעת רחבה", "מגבעת צרה", "כובע מהודר", "מגבעת אטומה"]

SUB_SECTORS = [
    "ליטאי ירושלמי", "ליטאי בני-ברקי", "אמריקאי", "ספרדי-ליטאי",
    "חסידי-ספרדי", "תורני מודרני", "מסורתי",
]

HALAKHA_VIEWPOINTS = [
    "פסקי הרב אלישיב זצ\"ל", "פסקי הרב שטיינמן זצ\"ל",
    "פסקי הרב עובדיה יוסף זצ\"ל", "פסקי הראי\"ה זצ\"ל",
    "פסקי הרב פיינשטיין זצ\"ל",
]

OPENNESS_LEVELS = [
    "פתיחות לרעיונות חדשים", "סגור יותר, מסורתי", "מאוזן",
    "פתוח לדיון", "שמרני",
]


# ---------------------------------------------------------------------------
# Generators — small helpers that produce random but plausible field values.
# ---------------------------------------------------------------------------

def _random_dob(min_age: int, max_age: int) -> date:
    """Generate a random date of birth that produces an age in the given range."""
    today = date.today()
    age = random.randint(min_age, max_age)
    # Random offset within the year to avoid identical birthdays.
    days_offset = random.randint(0, 364)
    birth_year = today.year - age
    return date(birth_year, 1, 1) + timedelta(days=days_offset)


def _build_siblings() -> tuple[list[dict], int, int]:
    """Build a small list of sibling sub-documents and the brother/sister counts."""
    n_siblings = random.randint(2, 8)
    siblings: list[dict] = []
    n_brothers = 0
    n_sisters = 0

    for _ in range(n_siblings):
        relation = random.choice(["brother", "sister"])
        if relation == "brother":
            n_brothers += 1
        else:
            n_sisters += 1

        is_married = random.random() < 0.45
        sibling: dict = {
            "relation": relation,
            "age": random.randint(15, 45),
            "institution": random.choice(YESHIVAS + SEMINARIES),
            "marital_status": "married" if is_married else "single",
            "spouse_lastname": None,
            "support_location": None,
            "spouse_study": None,
            "spouse_occupation": None,
        }
        if is_married:
            sibling["spouse_lastname"] = random.choice(LAST_NAMES)
            sibling["support_location"] = random.choice(CITIES)
            sibling["spouse_study"] = random.choice(YESHIVAS + SEMINARIES)
            sibling["spouse_occupation"] = random.choice(
                FATHER_PROFESSIONS + MOTHER_PROFESSIONS,
            )
        siblings.append(sibling)

    return siblings, n_brothers, n_sisters


def _build_candidate(gender: str, idx: int) -> dict:
    """
    Build one full candidate document ready to be inserted into MongoDB.

    Args:
        gender: "male" or "female".
        idx: Sequence number used to vary deterministic-ish defaults.
    """
    is_male = gender == "male"

    first = random.choice(MALE_FIRST_NAMES if is_male else FEMALE_FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    dob = _random_dob(20, 32) if is_male else _random_dob(19, 30)
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    institution = random.choice(YESHIVAS if is_male else SEMINARIES)
    profession = random.choice(PROFESSIONS_MALE if is_male else PROFESSIONS_FEMALE)
    siblings, n_brothers, n_sisters = _build_siblings()

    # Combine two phrases so the strings are richer and embeddings have more signal.
    char_traits = (
        random.choice(CHARACTER_TRAITS_POOL)
        + " "
        + random.choice(CHARACTER_TRAITS_POOL)
    )
    prefs = (
        random.choice(PREFERENCES_POOL)
        + " "
        + random.choice(PREFERENCES_POOL)
    )

    now = datetime.utcnow()

    candidate: dict = {
        "first_name": first,
        "last_name": last,
        "gender": gender,
        "date_of_birth": datetime.combine(dob, datetime.min.time()),
        "age": age,
        "city": random.choice(CITIES),
        "community": random.choice(COMMUNITIES),
        "education": {
            "current_institution": institution,
            "current_study": random.choice(
                ["חבורת גמרא", "סדר עיון", "סדר בקיאות", "תכנית הוראה", "לימודי הלכה"],
            ),
            "previous_institutions": random.sample(
                YESHIVAS if is_male else SEMINARIES,
                k=random.randint(1, 2),
            ),
            "is_primary_study": True,
            "study_type": "ישיבה גדולה" if is_male else "סמינר",
            "profession": profession,
            "jobs": [
                {
                    "title": profession,
                    "employer": random.choice(
                        ["מוסד פרטי", "ארגון ציבורי", "עצמאי/ת", "מוסד חינוכי"],
                    ),
                    "description": "משרה חלקית" if random.random() < 0.5 else "משרה מלאה",
                },
            ],
        },
        "family": {
            "father_profession": random.choice(FATHER_PROFESSIONS),
            "mother_profession": random.choice(MOTHER_PROFESSIONS),
            "siblings": siblings,
            "num_brothers": n_brothers,
            "num_sisters": n_sisters,
            "father_name": random.choice(MALE_FIRST_NAMES),
            "father_is_cohen": random.random() < 0.15,
            "father_origin": random.choice(["אשכנזי", "ספרדי", "תימני", "מרוקאי"]),
            "father_occupation_details": "פרטים נוספים על העיסוק",
            "father_youth_study": random.choice(YESHIVAS),
            "father_phone": f"05{random.randint(0, 9)}-{random.randint(1000000, 9999999)}",
            "mother_name": random.choice(FEMALE_FIRST_NAMES),
            "mother_origin": random.choice(["אשכנזיה", "ספרדיה", "תימנית", "מרוקאית"]),
            "mother_youth_study": random.choice(SEMINARIES),
            "mother_parents_names": f"{random.choice(MALE_FIRST_NAMES)} ו{random.choice(FEMALE_FIRST_NAMES)}",
            "mother_phone": f"05{random.randint(0, 9)}-{random.randint(1000000, 9999999)}",
            "family_style": random.choice(["חמה ופתוחה", "תורנית מסורתית", "מאוזנת"]),
            "parents_marital_status": "married",
            "family_openness": random.choice(["גבוהה", "בינונית", "שמרנית"]),
            "address": f"רחוב {random.randint(1, 99)}, {random.choice(CITIES)}",
            "family_notes": None,
            "contact_phones": [
                {
                    "number": f"05{random.randint(0, 9)}-{random.randint(1000000, 9999999)}",
                    "name": "אבא",
                    "relation": "אב",
                },
                {
                    "number": f"05{random.randint(0, 9)}-{random.randint(1000000, 9999999)}",
                    "name": "אמא",
                    "relation": "אם",
                },
            ],
        },
        "character_traits": char_traits,
        "preferences": prefs,
        "status": "active",
        "notes": None,
        # Extended personal fields
        "personal_status": "single",
        "sub_sector": random.choice(SUB_SECTORS),
        "halakha_viewpoint": random.choice(HALAKHA_VIEWPOINTS),
        "languages": random.choice(LANGUAGES_POOL),
        "residence": random.choice(["עם ההורים", "שכירות", "דירה משותפת"]),
        "financial_info": random.choice(
            ["משפחה תומכת", "תומכים בשנות הלימוד", "עצמאי/ת כלכלית"],
        ),
        "phone_type": random.choice(["smartphone", "kosher", "basic"]),
        "openness": random.choice(OPENNESS_LEVELS),
        "clothing_style": random.choice(CLOTHING_STYLES) if is_male else "צנועה ואלגנטית",
        "kova_suit_type": random.choice(KOVA_SUIT_TYPES) if is_male else None,
        "has_headshot": random.random() < 0.5,
        "has_license": random.random() < 0.6,
        "is_cohen": random.random() < 0.12,
        "height": random.randint(165, 188) if is_male else random.randint(150, 175),
        "hair_color": random.choice(HAIR_COLORS),
        "hobbies_aspirations": random.choice([
            "אוהב/ת ללמוד, לטייל, ולהתפתח אישית.",
            "תחביבים: קריאה, מוזיקה, התנדבות בקהילה.",
            "שאיפה לבנות בית של תורה וחסד.",
            "מעוניין/ת לפתח קריירה מקצועית בתחום ההוראה.",
        ]),
        # AI / embedding fields — start empty, embedding job will fill them.
        "profile_embedding": [],
        "preferences_embedding": [],
        "profile_text_hash": "",
        "preferences_text_hash": "",
        "embedding_model": "",
        "embedding_updated_at": None,
        # Audit
        "created_by": None,
        "updated_by": None,
        "created_at": now,
        "updated_at": now,
        # Marker for idempotency
        "seed_marker": SEED_MARKER,
    }

    return candidate


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

async def already_seeded(db) -> int:
    """Return how many seed-marked candidates already exist."""
    return await db["candidates"].count_documents({"seed_marker": SEED_MARKER})


async def clear_seed(db) -> int:
    """Remove all candidates inserted by previous seed runs. Returns count deleted."""
    result = await db["candidates"].delete_many({"seed_marker": SEED_MARKER})
    return result.deleted_count


async def insert_candidates(db) -> list[dict]:
    """Insert 25 male + 25 female candidates and return their inserted documents."""
    candidates: list[dict] = []
    for i in range(TARGET_PER_GENDER):
        candidates.append(_build_candidate("male", i))
    for i in range(TARGET_PER_GENDER):
        candidates.append(_build_candidate("female", i))

    result = await db["candidates"].insert_many(candidates)
    print(f"  [OK] Inserted {len(result.inserted_ids)} candidates "
          f"({TARGET_PER_GENDER} male + {TARGET_PER_GENDER} female).")
    return candidates


async def generate_embeddings(db) -> None:
    """Generate OpenAI embeddings for every seed candidate that lacks them."""
    print("\nGenerating embeddings (this may take ~30–60 seconds)…")
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        print("  [WARN] OPENAI_API_KEY is not configured — skipping embedding generation.")
        print("         The candidates were seeded but cannot be matched until embeddings exist.")
        return

    # Use the existing bulk helper. Force is False so it only processes missing ones.
    updated = await embeddings.embed_candidates_bulk(db, force=False)
    print(f"  [OK] Embeddings generated for {updated} candidate(s).")


async def main(force: bool) -> None:
    settings = get_settings()
    print(f"Connecting to MongoDB at {settings.mongodb_uri[:60]}…")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    try:
        await client.admin.command("ping")
        print("  [OK] Connected.")
    except Exception as exc:  # noqa: BLE001 — we want the message
        print(f"  [FAIL] Could not connect: {exc}")
        client.close()
        sys.exit(1)

    db = client[settings.mongodb_db_name]

    existing = await already_seeded(db)
    if existing > 0:
        if force:
            removed = await clear_seed(db)
            print(f"  --force: removed {removed} existing seed candidates.")
        else:
            print(
                f"\n{existing} seed candidate(s) already exist — skipping insertion.\n"
                "  Re-run with --force to wipe the previous seed batch and reseed."
            )
            client.close()
            return

    random.seed(RANDOM_SEED)
    await insert_candidates(db)
    await generate_embeddings(db)

    client.close()
    print("\n[DONE] Seeding complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed 25 male + 25 female candidates.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete previously-seeded candidates and reseed.",
    )
    args = parser.parse_args()
    asyncio.run(main(force=args.force))
