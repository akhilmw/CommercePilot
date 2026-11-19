from datetime import UTC, datetime

from commercepilot.db.session import SessionLocal
from commercepilot.models.review import ReviewCreate
from commercepilot.services.review_ingestion import ingest_reviews

PRODUCT_SKU = "NOVA-AUDIO-001"


def review(
    number: int,
    rating: int,
    title: str,
    body: str,
) -> ReviewCreate:
    return ReviewCreate(
        source_review_id=f"synthetic-ns-{number:03d}",
        source="synthetic-novacart",
        rating=rating,
        title=title,
        body=body,
        verified_purchase=number % 6 != 0,
        reviewed_at=datetime(2026, 11, number, 12, tzinfo=UTC),
    )


SYNTHETIC_REVIEWS = (
    review(
        1,
        5,
        "Excellent sound and battery",
        "Music sounds detailed and balanced, and the battery easily lasts "
        "through several workdays.",
    ),
    review(
        2,
        5,
        "Noise cancellation is impressive",
        "The active noise cancellation blocks most train noise and makes my "
        "daily commute much calmer.",
    ),
    review(
        3,
        3,
        "Good audio but a tight fit",
        "The sound quality is strong, but the earcups become uncomfortable "
        "after about an hour.",
    ),
    review(
        4,
        2,
        "Microphone needs work",
        "People on work calls say my voice sounds distant and muffled even "
        "in a quiet room.",
    ),
    review(
        5,
        2,
        "Bluetooth disconnects randomly",
        "The headphones sometimes disconnect from my laptop and need to be "
        "paired again.",
    ),
    review(
        6,
        5,
        "Battery lasts forever",
        "I used these throughout a three-day trip without charging and still "
        "had battery remaining.",
    ),
    review(
        7,
        4,
        "Fantastic sound with firm earcups",
        "Bass is controlled and vocals are clear, although the earcups feel "
        "tight during long sessions.",
    ),
    review(
        8,
        2,
        "Not suitable for conference calls",
        "The microphone makes my voice sound compressed, so I switch to my "
        "laptop mic for meetings.",
    ),
    review(
        9,
        4,
        "Great for commuting",
        "Noise cancellation handles buses and trains very well while "
        "preserving clear, enjoyable audio.",
    ),
    review(
        10,
        3,
        "A little too heavy",
        "They sound good, but the weight and headband pressure become "
        "noticeable after extended use.",
    ),
    review(
        11,
        5,
        "Reliable everyday headphones",
        "Pairing with my phone was fast, the connection stayed stable, and "
        "the sound is excellent.",
    ),
    review(
        12,
        2,
        "Connection drops on my laptop",
        "Bluetooth audio occasionally cuts out for a few seconds when "
        "connected to my laptop.",
    ),
    review(
        13,
        4,
        "Very dependable battery",
        "Battery life is excellent and I only need to charge the headphones "
        "once every few days.",
    ),
    review(
        14,
        3,
        "Headband pressure is tiring",
        "The sound is enjoyable, but the clamping pressure causes discomfort "
        "during long listening sessions.",
    ),
    review(
        15,
        5,
        "Detailed and balanced audio",
        "Instruments are easy to separate, voices sound natural, and the bass "
        "never overwhelms the mix.",
    ),
    review(
        16,
        3,
        "Good ANC except outdoors",
        "Noise cancellation works indoors, but wind creates distracting "
        "noise when I walk outside.",
    ),
    review(
        17,
        3,
        "Earcups get warm",
        "The cushioning feels soft initially, but the earcups become hot and "
        "uncomfortable after two hours.",
    ),
    review(
        18,
        3,
        "Microphone struggles in noisy places",
        "Calls are acceptable at home, but the microphone picks up too much "
        "background noise in cafes.",
    ),
    review(
        19,
        4,
        "Strong value for the price",
        "Sound, battery life, and noise cancellation make these a very "
        "competitive everyday option.",
    ),
    review(
        20,
        4,
        "Clean sound for podcasts and music",
        "Speech is crisp, music has good detail, and the battery comfortably "
        "handles daily use.",
    ),
    review(
        21,
        4,
        "Controls are easy to use",
        "The physical controls are intuitive and the headphones paired "
        "quickly with my phone.",
    ),
    review(
        22,
        2,
        "Frequent Bluetooth interruptions",
        "The connection briefly drops several times per day even when my "
        "phone is nearby.",
    ),
    review(
        23,
        3,
        "Excellent ANC, uncomfortable flight",
        "Cabin noise nearly disappeared, but the tight fit became painful "
        "during a long flight.",
    ),
    review(
        24,
        4,
        "Solid build and premium sound",
        "The headphones feel durable, sound refined, and deliver dependable "
        "battery performance.",
    ),
    review(
        25,
        3,
        "Promising but needs refinement",
        "A lighter design and a clearer microphone would make these much "
        "better for all-day work.",
    ),
)


def seed_reviews() -> None:
    with SessionLocal() as session:
        result = ingest_reviews(session, PRODUCT_SKU, SYNTHETIC_REVIEWS)
        session.commit()

    print(result)


if __name__ == "__main__":
    seed_reviews()
