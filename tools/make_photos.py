"""Feed photos from the locked identity: python make_photos.py <set_name> [--dry-run]
Each photo = Nano Banana 2 Edit with hero.png as reference ($0.08), 4:5 for the feed. Then face_gate check.
"""
import json, os, pathlib, sys, time, urllib.request
sys.path.insert(0, "."); import make_candidates as mc, fal_cost
EDIT_EP = "google/nano-banana-2.1/edit"   # Nano Banana 2.1, ~half the price of nano-banana-2/edit; thinking minimal
ROOT = mc.ROOT
PHOTOS = [
 ("p01_gym_mirror",   "mirror selfie in a modern gym at 7 am, holding the phone, plum sports top and black leggings, high ponytail, light sweat, confident half smile, phone photo"),
 ("p02_chai",         "sitting at a roadside Irani chai stall in Secunderabad holding a glass of chai, cotton kurti, hair open, laughing, warm evening light, candid phone photo"),
 ("p03_temple",       "at the steps of Keesaragutta temple in the morning, simple cotton saree, small bindi, plaited hair, calm smile, soft sunlight, phone photo"),
 ("p04_office_night", "at her desk in a dim software office at night, monitor glow on her face, oversized hoodie, hair in a messy bun, tired smile holding a coffee mug, candid"),
 ("p05_lehenga_home", "trying a new teal lehenga in front of a bedroom mirror at home, hair open, excited expression, warm indoor light, phone photo"),
 ("p06_necklace_road","standing at Necklace Road, Hyderabad at dusk with the lake and Buddha statue far behind, jeans and oversized white shirt, sunglasses on head, wind in hair, phone photo"),
 ("p07_biryani",      "at a Kompally dhaba at night under string lights with a plate of biryani in front of her, kurti, hair half tied, mid laugh, candid phone photo"),
 ("p08_scooter",      "sitting on a white Activa scooter on a Kompally street at golden hour, oversized shirt, slight grin, looking at camera, phone photo"),
 ("p09_saree_closeup","close portrait in a maroon silk saree with gold jhumkas, hair open, soft evening light on a balcony, gentle smile, shallow depth of field"),
 ("p10_rooftop",      "golden hour on a Hitec City rooftop cafe, glass towers behind, off-shoulder rust top, hair in soft waves, looking off camera, editorial phone photo"),
]

GLAM = [
 ("g01_saree_glam",     "editorial portrait in a deep maroon silk saree with gold zari border, gold jhumkas and a thin choker, professional makeup with defined eyes and glossy nude lips, hair in soft blow-dried waves over one shoulder, warm evening rim light on a terrace, looking into the lens"),
 ("g02_lehenga_shoot",  "full-length fashion photo in an emerald green embroidered lehenga with dupatta draped over the arm, statement earrings, glam makeup, hair open and styled, standing in a heritage courtyard with warm bokeh lights, confident pose"),
 ("g03_western_night",  "night-out look: black satin slip dress with a blazer over the shoulders, sleek straight hair, smokey eye makeup, small hoops, leaning on a railing at a Hitec City rooftop lounge, city lights behind, three-quarter pose"),
 ("g04_gym_glam",       "athleisure shoot in a matching wine-coloured sports bra and leggings set, sleek high ponytail, light glam makeup, soft studio light in a bright gym, hands on hips, strong confident smile"),
 ("g05_anarkali",       "floor-length pastel pink anarkali with mirror work, soft curls, dewy makeup, chandbali earrings, twirling slightly in a bright haveli corridor, joyful"),
 ("g06_cafe_chic",      "cafe portrait in a cream off-shoulder top and gold layered necklaces, hair in loose waves, glossy makeup, holding an iced coffee, window light, soft smile"),
 ("g07_car_selfie",     "glam car selfie in the passenger seat, sunglasses pushed up, red lips, white shirt, golden hour light through the window, phone photo"),
 ("g08_temple_festive", "festive look at a temple during a festival evening, bright yellow silk saree, jasmine flowers in a loose braid, traditional gold jewellery, light makeup, soft lamp light, serene smile"),
 ("g09_mirror_ootd",    "full-length mirror outfit photo at home in a fitted denim co-ord set and white sneakers, styled hair, light glam makeup, phone held at chest, confident look"),
 ("g10_closeup_beauty", "beauty close-up, flawless glowing skin, winged eyeliner, soft pink lips, hair pulled back with a few strands loose, small diamond studs, soft diffused light, direct gaze"),
]

REAL = [
 ("r01_saree_flash",    "night, pattu silk saree in deep maroon with gold border, jhumkas, hair blow-dried and open, done makeup with glossy lips, phone camera FLASH photo on a terrace with fairy lights, direct flash look, slightly overexposed skin, friends partly visible at the edge"),
 ("r02_lehenga_candid", "at a cousin's wedding, emerald embroidered lehenga, statement earrings, glam makeup, candid shot while adjusting the dupatta, mandap decorations and guests blurred behind, mixed warm hall lighting, slight motion blur"),
 ("r03_rooftop_night",  "rooftop lounge at Hitec City at night, black satin top and blazer, straight sleek hair, smokey eyes, holding a mocktail, photo taken by a friend on a phone, city bokeh behind, slightly tilted framing, some noise"),
 ("r04_gym_phone",      "chest-up gym mirror selfie at 7 am, face large and close to the mirror, wine sports bra, sleek ponytail, light makeup, visible sweat sheen, phone held at chest, gym equipment blurred behind, fluorescent and window light mix"),
 ("r05_car_golden",     "car passenger seat, golden hour sun flare through the window, oversized white shirt, red lipstick, sunglasses pushed up, phone selfie, slight lens flare and grain"),
 ("r06_cafe_window",    "cafe window seat, cream off-shoulder top, layered gold necklaces, loose waves, glossy makeup, iced coffee on the table with napkins and a phone, shot on a phone by a friend across the table, natural window light, slightly busy background"),
 ("r07_festive_lamps",  "temple festival evening, bright yellow silk saree, jasmine in a loose braid, gold jewellery, oil lamps and crowd around, phone photo with warm mixed lighting and a little noise, serene smile"),
 ("r08_street_night",   "Kompally street at night in a short kurti and jeans, hair styled, glam makeup, standing near a parked Activa under a sodium streetlight, phone photo, shop boards in Telugu behind, grainy"),
 ("r09_mirror_ootd",    "bedroom mirror outfit photo, fitted denim co-ord and sneakers, styled hair, light glam, clothes on the bed and a charger cable visible, phone in hand covering part of the face, warm tube light"),
 ("r10_closeup_phone",  "close selfie on a phone front camera, flawless but real skin with visible pores, winged eyeliner, soft pink lips, hair tucked behind one ear, small diamond studs, daylight from a window, slightly off-centre framing"),
]

if len(sys.argv) > 2 and sys.argv[2] == '--glam': PHOTOS = GLAM
if len(sys.argv) > 2 and sys.argv[2] == '--real': PHOTOS = REAL
name = sys.argv[1]; dry = "--dry-run" in sys.argv
out = ROOT / "photos" / name; out.mkdir(parents=True, exist_ok=True)
print(len(PHOTOS), "photos, about $%.2f" % (len(PHOTOS)*0.042))
if dry: sys.exit()
os.environ["FAL_KEY"] = mc.load_key(); import fal_client
hero = fal_client.upload_file(str(ROOT/"identity/v1/hero.png"))
for pid, desc in PHOTOS:
    p = out / f"{pid}.png"
    if p.exists(): continue
    prompt = (f"Same woman as the reference image, identical face, no moles anywhere, clear skin, same small gold nose stud. "
              f"{desc}. {mc.FACE_TXT} Shot on an iPhone, real photo, not a studio shoot, no retouching, natural skin texture with pores, slight grain, true-to-life colours, one person only, no text, no watermark.")
    r = fal_client.subscribe(EDIT_EP, arguments={"prompt": prompt, "image_urls": [hero], "thinking_level": "minimal",
          "aspect_ratio": "4:5", "resolution": "1K", "num_images": 1, "output_format": "png"})
    fal_cost.spend(EDIT_EP, 1, pid)
    urllib.request.urlretrieve(r["images"][0]["url"], p); print("ok", pid)
json.dump(dict(PHOTOS), open(out/"prompts.json","w"), indent=1)
