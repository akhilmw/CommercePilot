from datetime import UTC, datetime

from commercepilot.db.session import SessionLocal
from commercepilot.models.review import ReviewCreate
from commercepilot.services.review_ingestion import ingest_reviews

PRODUCT_SKU = "NOVA-AUDIO-001"


def make_review(
    prefix: str,
    number: int,
    rating: int,
    title: str,
    body: str,
) -> ReviewCreate:
    return ReviewCreate(
        source_review_id=f"synthetic-{prefix}-{number:03d}",
        source="synthetic-novacart",
        rating=rating,
        title=title,
        body=body,
        verified_purchase=number % 6 != 0,
        reviewed_at=datetime(2026, 11, number, 12, tzinfo=UTC),
    )


def review(
    number: int,
    rating: int,
    title: str,
    body: str,
) -> ReviewCreate:
    return make_review("ns", number, rating, title, body)


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

NOVA_FIT_REVIEWS = (
    make_review(
        "nf",
        1,
        5,
        "Battery easily lasts the week",
        "I track workouts and sleep every day and still get almost a full "
        "week between charges.",
    ),
    make_review(
        "nf",
        2,
        5,
        "Bright display outdoors",
        "The AMOLED screen stays clear in direct sunlight and workout stats "
        "are easy to read while running.",
    ),
    make_review(
        "nf",
        3,
        4,
        "Accurate heart-rate tracking",
        "Heart-rate readings closely match the chest strap I use at the gym, "
        "and the activity summaries are useful.",
    ),
    make_review(
        "nf",
        4,
        2,
        "GPS takes too long to lock",
        "Outdoor runs sometimes begin before GPS connects, leaving the first "
        "part of my route and distance inaccurate.",
    ),
    make_review(
        "nf",
        5,
        2,
        "Sleep tracking misses wake-ups",
        "The watch reports solid sleep even when I wake several times during "
        "the night, so the sleep score is not reliable.",
    ),
    make_review(
        "nf",
        6,
        3,
        "Comfortable watch, irritating strap",
        "The watch body is light, but the included silicone strap irritates "
        "my skin after long workouts.",
    ),
    make_review(
        "nf",
        7,
        4,
        "Great fitness dashboard",
        "Workout trends, recovery summaries, and heart-rate zones are "
        "presented clearly without overwhelming me.",
    ),
    make_review(
        "nf",
        8,
        2,
        "Notifications arrive late",
        "Messages occasionally appear several minutes late when the watch is "
        "connected to my Android phone.",
    ),
    make_review(
        "nf",
        9,
        4,
        "Excellent for swimming",
        "Pool workouts and lap counts have been dependable, and the watch "
        "has handled regular swimming without issues.",
    ),
    make_review(
        "nf",
        10,
        3,
        "Good hardware, confusing app",
        "The watch itself is responsive, but finding historical health data "
        "inside the phone app takes too many taps.",
    ),
    make_review(
        "nf",
        11,
        5,
        "Useful without daily charging",
        "Long battery life, clear exercise metrics, and a sharp screen make "
        "this easy to wear every day.",
    ),
    make_review(
        "nf",
        12,
        2,
        "GPS distance drifts under trees",
        "Distance and pace become inconsistent on wooded trails even after "
        "the watch confirms a GPS connection.",
    ),
)

NOVA_BREW_REVIEWS = (
    make_review(
        "nb",
        1,
        5,
        "Rich espresso from a compact machine",
        "Shots have a thick crema and balanced flavor, while the machine "
        "takes very little counter space.",
    ),
    make_review(
        "nb",
        2,
        4,
        "Ready before I grind the beans",
        "The thermoblock heats quickly and produces consistent espresso on "
        "busy mornings.",
    ),
    make_review(
        "nb",
        3,
        2,
        "Steam wand lacks power",
        "The steam wand takes too long to texture milk and struggles to make "
        "fine foam for lattes.",
    ),
    make_review(
        "nb",
        4,
        2,
        "Drip tray overflows easily",
        "The shallow drip tray fills after only a few drinks and spills when "
        "I carry it to the sink.",
    ),
    make_review(
        "nb",
        5,
        4,
        "Consistent pressure and crema",
        "Once the grind is dialed in, the machine pulls repeatable shots with "
        "good crema and temperature.",
    ),
    make_review(
        "nb",
        6,
        3,
        "Cleaning instructions are unclear",
        "The machine works well, but the manual does not clearly explain the "
        "descaling cycle or when each part should be cleaned.",
    ),
    make_review(
        "nb",
        7,
        5,
        "Ideal for a small apartment",
        "It heats fast, fits beneath my cabinets, and makes much better coffee "
        "than my old pod machine.",
    ),
    make_review(
        "nb",
        8,
        2,
        "Portafilter drips after brewing",
        "Water continues dripping from the group head and leaves a mess after "
        "the shot finishes.",
    ),
    make_review(
        "nb",
        9,
        4,
        "Simple controls for beginners",
        "The buttons are straightforward and I learned to pull a good double "
        "shot within a few attempts.",
    ),
    make_review(
        "nb",
        10,
        3,
        "Good espresso, weak milk drinks",
        "Espresso quality is impressive for the price, but steaming enough "
        "milk for two cappuccinos is slow.",
    ),
    make_review(
        "nb",
        11,
        5,
        "Fast and dependable every morning",
        "Heat-up is quick and shot temperature has stayed consistent through "
        "several weeks of daily use.",
    ),
    make_review(
        "nb",
        12,
        2,
        "Water tank is awkward to remove",
        "The rear tank catches beneath my cabinets and is difficult to refill "
        "without moving the whole machine.",
    ),
)

REVIEW_DATASETS = {
    PRODUCT_SKU: SYNTHETIC_REVIEWS,
    "NOVA-WEAR-001": NOVA_FIT_REVIEWS,
    "NOVA-HOME-001": NOVA_BREW_REVIEWS,
}


def seed_reviews() -> None:
    with SessionLocal() as session:
        results = [
            ingest_reviews(session, product_sku, reviews)
            for product_sku, reviews in REVIEW_DATASETS.items()
        ]
        session.commit()

    for result in results:
        print(result)


if __name__ == "__main__":
    seed_reviews()
