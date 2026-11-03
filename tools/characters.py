"""The couple: Satyam (45, bald, plain, a government officer) and Padma (28, beautiful, glamorous), a married Telugu couple in a neat
3BHK in a gated apartment in Kukatpally, Hyderabad. The mismatch between his plainness and her glamour is the account.
Every prompt in this repo takes its face, body, clothes and room text from here, never from an ad-hoc string.
identity/characters.json lists the reference images per character; identity/couple_bible.md is the human-readable version.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent          # D:\telugucouple
CHARS = json.load(open(ROOT / "identity" / "characters.json"))
WHO = list(CHARS)                                                # ["satyam", "padma"]


def ident(who):
    return ROOT / "identity" / who / "v1"


def refs(who):
    """Reference images for the still prompts, in the order the prompt names them."""
    return [ident(who) / n for n in CHARS[who]["refs"]]


# ---- faces (paste into every prompt; the gate checks the result against the frozen sheet) ----
FACE_TXT = {
    "satyam": ("Indian man, 45 years old, Telugu, completely bald shiny crown with short black hair only at the sides and back, "
               "thick black moustache, clean-shaven cheeks with light stubble, medium-dark brown skin, plain round face, small eyes, "
               "slightly chubby cheeks and a small double chin, thick black eyebrows, no glasses, no grey hair, "
               "an ordinary educated middle-class office-going uncle, plain and unstylish, not handsome, fit enough to dance, "
               "real candid phone photo look, not airbrushed."),
    "padma":  ("Indian woman, 28 years old, Telugu, round soft face with a cute smile and dimples, large dark almond eyes with kajal, "
               "neatly arched eyebrows, straight nose with a small gold nose pin, full lips, warm medium-brown skin with natural texture, "
               "long black hair in a loose thick plait with a string of jasmine, round maroon bindi, black-bead mangalsutra, "
               "glass bangles, beautiful and graceful, no moles or marks, real candid phone photo look, not airbrushed."),
}
BODY_TXT = {
    "satyam": "5 ft 7 in, paunch belly, average soft build, not athletic, slightly rounded shoulders, ordinary uncle body.",
    "padma":  "5 ft 4 in, curvy figure, fuller large bust, medium waist (soft, not very thin), wide hips, soft arms, graceful posture.",
}
# signature clothes (default look when a reel's --look does not say otherwise)
CLOTHES = {
    "satyam": ("an old loose cotton lungi with a plain white banian or a faded old round-neck T-shirt at home, or an old-fashioned "
               "ironed half-sleeve checked shirt tucked into loose trousers with the belt above the belly when back from the office, "
               "bathroom chappals, a black thread on the right wrist. Never stylish, never fashionable, zero glamour next to her."),
    "padma":  ("a bright saree draped low on the hips so her waist and midriff show, fitted blouse with a deep sweetheart neckline, "
               "elbow sleeves or sleeveless, glossy lips, light everyday makeup, toe rings, anklets."),
}
# per-reel glam text for Padma (same register as Siri's GLAM, which Instagram has been rewarding). Full-body dance framing only.
GLAM = {
    "padma": ("Glamorous home-made reel styling: saree or half-saree draped low so her waist and midriff show, fitted blouse with a deep "
              "sweetheart or V neckline, kajal, glossy rose lips, jasmine in the plait, bangles. The styling must not change her face shape, "
              "eyes, nose or jawline at all."),
    "satyam": ("He is NOT styled: the same plain banian or faded T-shirt and lungi, bald head shining under the light, moustache, "
               "belly showing, dancing with full enthusiasm but stiff awkward steps, the total opposite of her glamour."),
}
NEG = ("Photograph, not illustration. Realistic skin pores, no airbrushing, no beauty filter, no doll face, no extra fingers, "
       "no text, no captions, no stickers, no logos, no watermark.")

# ---- the flat: neat upper-middle-class 3BHK in a gated apartment, Kukatpally (KPHB), Hyderabad. Plates live in sets/<name>.png ----
FLAT = ("a neat, tidy upper-middle-class 3BHK apartment in a gated community in Kukatpally, Hyderabad, modern Indian interior, "
        "light cream walls, glossy beige vitrified tile floor, false ceiling with warm LED cove lighting, everything clean and arranged, "
        "a real lived-in Telugu family home (a few everyday objects), not a showroom, not a hotel, real phone photo, no people")
SETS = {
    "hall_a":    f"{FLAT}. The living hall: a grey L-shaped fabric sofa with cushions, a wooden TV unit with a large wall-mounted TV, "
                 "a glass centre table, a tall indoor plant, sheer white curtains over a big window with sliding glass, a small brass "
                 "Venkateswara idol on a wall shelf, a ceiling fan and LED cove light. Straight-on view with open floor space in the middle, "
                 "phone held at chest height, 9:16 vertical.",
    "hall_b":    f"{FLAT}. The same living hall seen from the dining side: sofa on the left, TV unit on the right, big window at the back with "
                 "daylight through sheer curtains, open tile floor in the middle, 9:16 vertical.",
    "dining_a":  f"{FLAT}. The dining area next to the hall: a six-seater wooden dining table with cushioned chairs, a hanging pendant lamp, "
                 "a glass crockery unit, a fruit bowl, a water jug, an arch opening to the kitchen behind, 9:16 vertical.",
    "bedroom_a": f"{FLAT}. The master bedroom: a queen-size upholstered bed with a cream quilt and matching pillows, a full-wall wardrobe "
                 "with a long mirror panel, a split AC above a window with blackout and sheer curtains, bedside lamps, straight-on view "
                 "with floor space in front of the bed, 9:16 vertical.",
    "bedroom_b": f"{FLAT}. The same master bedroom seen from the doorway: the wardrobe mirror on the left, the bed on the right, warm LED "
                 "cove light on, 9:16 vertical.",
    "kitchen_a": f"{FLAT}. The modular kitchen: white and wood laminate cabinets, black granite counter, a chimney over a four-burner hob, "
                 "a steel pressure cooker, a microwave, a wall water purifier, neat jars on a shelf, a window over the sink, 9:16 vertical.",
    "balcony_a": f"{FLAT}. The balcony: a steel and glass railing, a few potted plants and a tulasi pot, a small cane chair, a hanging swing "
                 "chair, a clothes-drying stand with a few folded clothes, neighbouring gated-community towers and trees behind, afternoon light, "
                 "9:16 vertical.",
    "door_a":    f"{FLAT}. Inside the entrance foyer: a polished teak main door with a brass nameplate 'S. Satyam', a shoe cabinet, a small "
                 "wall mirror with a key holder, a rangoli sticker on the floor, a tulasi pot, 9:16 vertical.",
}
LIGHT = {"evening": "evening, the room lit by the warm LED cove light and a lamp, soft shadows, slight sensor noise",
         "morning": "morning, soft daylight through the sheer curtains, no lamps on",
         "night":   "night, dim warm lighting, visible phone-camera grain"}


def set_plate(name):
    p = ROOT / "sets" / f"{name}.png"
    if not p.exists():
        raise SystemExit(f"set plate missing: {p}  (python make_sets.py {name})")
    return p
