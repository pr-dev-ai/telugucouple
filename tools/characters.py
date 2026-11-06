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
    # Pradeep 5 Nov: shirts and pants for Satyam (no more vest and lungi)
    "satyam": ("a plain half-sleeve or full-sleeve cotton shirt (light blue, white, beige, light checks or thin stripes) tucked into loose formal trousers with a plain belt sitting above his belly, like a middle-aged government officer; bathroom chappals or plain sandals at home, a black thread on the right wrist, a basic steel watch. Neat but never stylish, never fashionable, zero glamour next to her."),
    "padma":  ("a bright saree draped low on the hips so her waist and midriff show, fitted blouse with a deep sweetheart neckline, "
               "elbow sleeves or sleeveless, glossy lips, light everyday makeup, toe rings, anklets."),
}
# per-reel glam text for Padma (same register as Siri's GLAM, which Instagram has been rewarding). Full-body dance framing only.
GLAM = {
    "padma": ("Glamorous home-made reel styling: saree or half-saree draped low so her waist and midriff show, fitted blouse with a deep "
              "sweetheart or V neckline, kajal, glossy rose lips, a small jasmine string pinned at the back of her hair (never hanging over the shoulder or chest), bangles. The styling must not change her face shape, "
              "eyes, nose or jawline at all."),
    "satyam": ("He is NOT styled: a plain cotton shirt tucked into loose formal trousers with the belt above his belly, bald head shining under the light, moustache, "
               "a slight paunch, dancing with full enthusiasm but stiff awkward steps, the total opposite of her glamour."),
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
    """Real photo of their house first (sets/real/plates, shot by Pradeep 4 Nov), AI plate only as a fallback."""
    real = ROOT / "sets" / "real" / "plates" / f"{name}.jpg"
    if real.exists():
        return real
    p = ROOT / "sets" / f"{name}.png"
    if not p.exists():
        raise SystemExit(f"set plate missing: {p}  (python make_sets.py {name})")
    return p


# ---- close-range room plates (3 Nov fix for "background does not blend") ----
# The wide plates show the whole room; a half-body or close dance shot needs the room as a phone sees it from ~1.5-2 m:
# a smaller part of the room, larger in frame, naturally a little soft. Made by editing the wide plate so the room stays the same.
CLOSE_OF = {f"{k}_close": k for k in ("hall_a", "hall_b", "bedroom_a", "bedroom_b", "kitchen_a", "balcony_a", "dining_a")}
CLOSE_PROMPT = ("The same room as the image, same walls, furniture, colours and light, but photographed with a phone main camera held at "
                "chest height by someone standing about 2 metres from the far wall/furniture, so only the middle part of the room fills the frame "
                "and everything looks larger and closer; the background is naturally a little soft like a phone photo focused on someone standing "
                "in front of it. Empty room, no people, no text. Real phone photo, slight sensor noise, 9:16 vertical.")

# How the person must be lit so she sits IN the room (pasted into every still prompt)
LIGHT_MATCH = ("She is lit ONLY by this room's own light, exactly like the room: same white balance, same exposure, same softness. "
               "If a bright window or balcony door is behind her she is softly backlit: a rim of light on her hair and shoulders, her front a "
               "little darker than the window, never front-lit by a flash or ring light. Her skin and clothes are never brighter, warmer or more "
               "saturated than the room around her. Shadows fall the same way as the room's shadows, her feet cast a soft contact shadow on the floor.")
CAMERA_MATCH = ("Re-photograph the room from where the phone stands in the LAST image: the same camera height, the same distance to the dancer "
                "and the same lens, so the room appears at the scale it really would behind a person at that distance (closer framing = less "
                "room, larger, slightly soft). Never paste her in front of a far-away wide room view.")


# ---- Padma's wardrobe by time of day (Pradeep, 4 Nov: "why same costume daily, morning she might be in night dresses") ----
# Every reel picks its outfit from the slot it is set in; out/wardrobe_log.json keeps the last picks so a garment+colour is not
# repeated within 7 reels, and the two nightwear styles alternate. Nightwear stays bold but recommendable: fitted, never lingerie, never western.
# Pradeep, 5 Nov: jasmine strands hanging at her side flicker/vanish in Kling video (Nadakallo reel deleted): pin it at the back only.
# Pradeep, 5 Nov: NO WESTERN DRESSES for Padma (the satin night suit did not suit her). Nightwear = deep-neck nighty only;
# otherwise sarees (cleavage / deep-neck blouse), half-sarees, churidars. No jeans, kurti-jeans, night suits, gowns or tops.
WARDROBE = {
    "morning": [   # coffee, kitchen, waking ayana up: a slightly deep-neck nighty, two cuts so it is not the same daily
        ("nighty", "a fitted full-length printed cotton nighty with short sleeves and a slightly deep V neckline (front button placket, top button open), a thin dupatta loosely over one shoulder, hair loose or in a quick messy bun, small bindi, mangalsutra and glass bangles"),
        ("nighty yoke", "a soft fitted full-length cotton nighty with a lace-trimmed deep round yoke neckline and puff sleeves, shaped at the waist, hair in a loose messy bun with a few strands on her face, small bindi, mangalsutra and glass bangles"),
    ],
    "late_morning": [  # housework, tailoring
        ("cotton saree", "a simple cotton saree draped practically with the pallu tucked at the waist so the waist shows, deep-neck elbow-sleeve cotton blouse, hair tied in a plait"),
        ("churidar", "a fitted cotton churidar kurta with a deep round neck and churidar pants, dupatta around the neck, hair in a plait"),
    ],
    "evening": [   # getting ready, functions, dance reels: the bold glam look
        ("silk saree", "a silk saree draped low on the hips with the waist showing, sleeveless deep-V blouse with natural cleavage, a small jasmine string pinned at the back of her hair (never hanging over the shoulder or chest), gold jhumkas"),
        ("chiffon saree", "a light chiffon saree draped low on the hips with the waist showing, deep sweetheart-neck blouse with natural cleavage, a small jasmine string pinned at the back of her hair (never hanging over the shoulder or chest), bangles"),
        ("half saree", "a silk half-saree (langa voni) with the bare waist showing between blouse and skirt, deep-neck blouse, a small jasmine string pinned at the back of her hair (never hanging over the shoulder or chest)"),
    ],
    "out": [       # shopping, market, outings (Indian wear only)
        ("printed saree", "a printed georgette saree draped neatly with the waist showing, deep-neck blouse, small earrings, handbag, hair in a plait"),
        ("anarkali", "a fitted anarkali churidar with a deep neck and a light dupatta, jhumkas, hair open"),
    ],
    "night": [     # bed-time chit-chat
        ("nighty", "a soft printed cotton nighty with a slightly deep neckline and short sleeves, hair open, mangalsutra only"),
        ("nighty yoke", "a fitted cotton nighty with a lace-trimmed deep yoke neckline, hair open, mangalsutra only"),
    ],
}
COLOURS = ["peach", "sky blue", "maroon", "mint green", "lavender", "mustard yellow", "rani pink", "navy blue", "emerald green",
           "cream", "red", "teal", "wine", "orange", "lilac", "black", "white with small flowers", "royal blue"]
WARDROBE_LOG = ROOT / "out" / "wardrobe_log.json"


def choose_look(slot, note=""):
    """Pick an outfit for this slot that was not worn in the last 7 reels (garment+colour), alternating styles; logs the pick."""
    log = json.load(open(WARDROBE_LOG)) if WARDROBE_LOG.exists() else []
    recent = log[-7:]
    used = {(e["garment"], e["colour"]) for e in recent}
    last_style = next((e["garment"] for e in reversed(log) if e["slot"] == slot), None)
    options = WARDROBE[slot]
    order = [o for o in options if o[0] != last_style] + [o for o in options if o[0] == last_style]
    recent_colours = [e["colour"] for e in recent]
    for garment, desc in order:
        for colour in sorted(COLOURS, key=lambda c: (c in recent_colours, COLOURS.index(c))):
            if (garment, colour) not in used:
                look = f"{colour} {desc}"
                log.append({"date": __import__("time").strftime("%Y-%m-%d %H:%M"), "slot": slot, "garment": garment, "colour": colour, "note": note})
                WARDROBE_LOG.parent.mkdir(parents=True, exist_ok=True); json.dump(log, open(WARDROBE_LOG, "w"), indent=1)
                return look
    return f"{COLOURS[0]} {options[0][1]}"


# ---- REAL backgrounds (Pradeep 4 Nov: AI rooms "look purely AI"; he shot their actual house into sets/real) ----
# Rooms now: hall_a hall_b hall_tv hall_sofa hall_window kitchen_a kitchen_b kitchen_c bedroom_a bedroom_b bedroom_c balcony_a balcony_b door_a door_b
# (+ <name>_close). It is a house in a gated villa community; all photos are daytime.
ROOM_REAL = ("is a REAL phone photo of their house, with no people in it. Keep that photo exactly as it is: the same room, furniture, "
             "floor, curtains, light, perspective, lens distortion and grain (only small loose items may change, as described); do not redraw, tidy, beautify, recolour or re-light it. "
             "Only add the person into it, standing on that floor at the right size for their distance from the camera, so it looks like the same "
             "phone photographed them in that room")
CAMERA_MATCH = ("The camera is the phone that took the room photo: keep its height, lens and perspective. The person is inside the room, "
                "behind or beside the furniture where natural, at a believable scale, never pasted flat in front of the photo.")
LIGHT = {k: "lit by the room photo's own daylight exactly as captured (window direction, softness, colour), nothing added" for k in LIGHT}


def is_real(plate):
    return "/real/" in str(plate).replace("\\", "/")


# ---- Variety inside the real rooms (Pradeep 4 Nov: "kitchen photo has cut vegetables; if every kitchen reel shows them people will doubt") ----
# Fixed: walls, cabinets, stove, furniture, windows, floor. Variable per reel: small loose items, chosen by scene; views rotate.
VIEWS = {"kitchen": ["kitchen_a", "kitchen_b", "kitchen_c"], "hall": ["hall_a", "hall_b", "hall_tv", "hall_sofa", "hall_window"],
         "bedroom": ["bedroom_a", "bedroom_b", "bedroom_c"], "balcony": ["balcony_a", "balcony_b"], "door": ["door_a", "door_b"]}
LOOSE = {
    "kitchen": {"morning": ["a milk packet, a steel davara-tumbler set and a small sugar tin on a clean counter",
                            "a steel kettle, two tea cups and a plate of rusk biscuits, the counter otherwise clear",
                            "a filter-coffee filter, a steel tumbler and the morning newspaper folded on the counter"],
                "late_morning": ["a pressure cooker, a bowl of washed rice and a few curry leaves on the counter",
                                 "a cutting board with green beans and a knife, a steel bowl of potatoes",
                                 "steel containers of dal and spices with a ladle, the counter wiped clean"],
                "evening": ["a plate of hot mirchi bajji and two cups of tea", "a steel plate of upma and a water bottle",
                            "a clean empty counter with just a fruit basket"],
                "night": ["washed vessels drying in a steel rack, the counter wiped and empty", "a covered casserole and two plates"]},
    "hall": {"*": ["a folded newspaper and the TV remote on the sofa", "a couple of cushions out of place and a phone charger cable",
                   "a steel tumbler and a plate on the side table", "nothing extra, the hall tidy"]},
    "bedroom": {"*": ["a folded saree and a blouse laid on the bed", "a few clothes on the bed waiting to be folded",
                      "the bedsheet neatly made, a phone and charger on the pillow", "a handbag and a jewellery box on the bed"]},
    "balcony": {"*": ["a few clothes drying on a stand", "a tulasi pot and a watering can", "nothing extra"]},
    "door": {"*": ["a pair of chappals and an office bag by the door", "a milk packet and a newspaper at the door", "nothing extra"]},
}
ROOM_LOG = ROOT / "out" / "room_log.json"


def room_kind(view):
    return view.split("_")[0]


def choose_room(kind, slot, note=""):
    """Pick a view of this room not used recently, and a set of loose items for the scene. Returns (view, loose_text) and logs it."""
    import time as _t
    log = json.load(open(ROOM_LOG)) if ROOM_LOG.exists() else []
    recent = [e["view"] for e in log[-6:]]
    views = sorted(VIEWS[kind], key=lambda v: (v in recent, recent[::-1].index(v) if v in recent else 0))
    view = views[0]
    pool = LOOSE[kind].get(slot) or LOOSE[kind].get("*") or LOOSE[kind][next(iter(LOOSE[kind]))]
    used = [e["loose"] for e in log[-8:]]
    loose = next((x for x in pool if x not in used), pool[0])
    log.append({"date": _t.strftime("%Y-%m-%d %H:%M"), "view": view, "slot": slot, "loose": loose, "note": note})
    ROOM_LOG.parent.mkdir(parents=True, exist_ok=True); json.dump(log, open(ROOM_LOG, "w"), indent=1)
    return view, loose


def loose_txt(loose):
    return (f"Small loose everyday items on the counters, tables or bed are NOT fixed: remove whatever loose items are in the room photo "
            f"(cut vegetables, vessels, bottles, packets, clothes) and show instead: {loose}. Everything fixed (walls, cabinets, stove, "
            f"furniture, windows, floor, curtains) stays exactly as in the photo.")
