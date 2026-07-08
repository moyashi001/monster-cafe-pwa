# -*- coding: utf-8 -*-
"""
download_images.py

Downloads every image used by index.html from Pollinations.ai
(a free, no-API-key image generation service) and saves them into an
`images/` folder next to this script, using the exact filenames the
HTML app expects.

Usage:
    python download_images.py

Notes:
- Safe to re-run: files that already exist (and are non-empty) are skipped,
  so if the free service rate-limits you partway through, just run the
  script again later and it will pick up where it left off.
- Pollinations.ai is a free community service with no guaranteed uptime
  or rate limit, so this script retries each image several times with an
  increasing wait between attempts.
- If you add/change images here, service-worker.js's PRECACHE_ASSETS list
  (and CACHE_NAME, to force already-installed copies to refresh) needs to be
  updated to match, or the installed PWA won't pick up the new files.
"""

import os
import sys
import time
import urllib.parse
import urllib.request

STYLE_SUFFIX = ", lowbrow art, pop art, vibrant colors, retro cartoon style, flat vector illustration"
IMG_SIZE = "width=512&height=512&nologo=true"
BASE_URL = "https://image.pollinations.ai/prompt/{prompt}?" + IMG_SIZE

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "images")

RETRIES = 6
RETRY_BASE_DELAY = 6      # seconds, multiplied by attempt number
BETWEEN_REQUEST_DELAY = 3 # seconds, polite delay between successful downloads


def build_image_manifest():
    """Returns an ordered dict: {filename: prompt_without_style_suffix}"""
    images = {}

    # 1) menu background
    images["bg_menu.png"] = "spooky and fun monster cafe background"

    # 2) monster, 6 expressions
    monster_base = "cute scary blue furry monster character with horns, character design, white background"
    images["monster_normal.png"] = monster_base + ", standing, neutral friendly expression"
    images["monster_eat.png"] = monster_base + ", eating happily with big open mouth"
    images["monster_happy.png"] = monster_base + ", extremely happy and excited expression, sparkles"
    images["monster_angry.png"] = monster_base + ", angry roaring expression"
    images["monster_weird.png"] = monster_base + ", confused silly weird expression"
    images["monster_sad.png"] = monster_base + ", sad pouting expression, looking away"

    # 3) abura-soba (used as the falling/conveyor food in game 1)
    images["food_aburasoba.png"] = "a delicious bowl of Japanese Abura-soba noodle"

    # 3b) bomb hazard item for the conveyor belt (game 1) - touching it fails the round
    images["food_bomb.png"] = (
        "a cute round black cartoon bomb character with a lit orange fuse spark on top, "
        "googly eyes, comically nervous sweating expression, simple flat design, isolated"
    )

    # (Game 2 "Topping Master" - base dishes + topping ingredients - was retired.
    # Its prompts and generated images are preserved under
    # archived_topping_master/ in case it comes back later.)

    # 4) sticker-book backgrounds, 2 variants (boy / girl)
    images["bg_seal_boy.png"] = (
        "cute pastel blue and silver background pattern with stars, rockets and robots doodles, "
        "for a boy's sticker album"
    )
    images["bg_seal_girl.png"] = (
        "cute pastel pink and lavender background pattern with flowers, hearts and ribbons doodles, "
        "for a girl's sticker album"
    )

    # 5) 50 reward stickers: Pokemon-style 3-stage evolution lines. Each line has
    # an elemental type + a cute animal/plant motif, drawn through 3 evolution
    # stages (stage 1 cute/small -> stage 2 energetic/medium -> stage 3 powerful/
    # cool), following the "diverse creature characters ... different evolutionary
    # stages" brief. 16 lines x 3 stages = 48, plus one 2-stage bonus "legendary"
    # line = 50. Character name/catchphrase text is rendered separately in the
    # app's own CSS/HTML, so these prompts focus purely on the character art.
    STICKER_STYLE = (
        ", cartoon style, thick clear black outlines, vibrant flat colors, "
        "simple cel shading, cheerful appealing character design, distinct silhouette, "
        "centered composition filling the frame, plain white background, no text, no watermark"
    )

    STAGE_DESC = {
        1: "cute and small, chibi proportions, big round sparkling eyes, playful pose",
        2: "energetic and medium-sized, active dynamic pose, confident expression",
        3: "powerful and cool, larger and more detailed, majestic heroic pose",
    }

    def stage_prompt(type_label, motif, aura, stage_num, stage_desc):
        return "Design stage {} of a {}-type monster based on a {}. {}, {}".format(
            stage_num, type_label, motif, stage_desc, aura
        )

    # (type_label, motif, aura/texture description)
    evolution_lines = [
        ("fire", "kitten", "warm orange and red glowing ember aura"),
        ("water", "turtle", "cool blue water droplet aura, glossy wet sheen"),
        ("grass", "seedling plant creature", "fresh green leaf and vine motifs"),
        ("electric", "chick", "yellow lightning spark aura"),
        ("rock", "armadillo with a shell", "rugged grey stone texture with small pebbles"),
        ("flying", "hawk", "soft cloud and wind swirl motifs"),
        ("ice", "penguin", "pale blue frost crystal aura"),
        ("ground", "mole", "brown earthy soil texture"),
        ("bug", "caterpillar", "shiny iridescent shell texture"),
        ("fairy", "rabbit", "soft pastel glowing light sparkles"),
        ("dark", "fox", "deep purple shadowy wisps"),
        ("dragon", "little lizard", "shimmering scale texture with small flame wisps"),
        ("steel", "hedgehog", "metallic shiny silver texture"),
        ("psychic", "owl", "swirling pastel psychic energy rings"),
        ("poison", "frog", "playful bubbly purple and teal bubble motifs"),
        ("wind", "squirrel", "swirling pale green breeze ribbons"),
    ]
    assert len(evolution_lines) == 16

    i = 1
    for type_label, motif, aura in evolution_lines:
        for stage in (1, 2, 3):
            images["seal_{:02d}.png".format(i)] = (
                stage_prompt(type_label, motif, aura, stage, STAGE_DESC[stage]) + STICKER_STYLE
            )
            i += 1

    # Bonus 2-stage "legendary" line (cute pup -> starry legendary wolf) to
    # round the total out to exactly 50 stickers.
    images["seal_{:02d}.png".format(i)] = (
        stage_prompt("star", "wolf pup", "twinkling starry night sky sparkle", 1, STAGE_DESC[1])
        + STICKER_STYLE
    )
    i += 1
    images["seal_{:02d}.png".format(i)] = (
        stage_prompt(
            "star", "wolf pup", "twinkling starry night sky sparkle, glowing cosmic aura", 2,
            "powerful and cool, majestic legendary appearance, larger and more detailed, heroic confident pose",
        )
        + STICKER_STYLE
    )
    i += 1
    assert i - 1 == 50

    # 6) 10 cars for the shape-matching game (game 3). Side view / profile is
    # required so the silhouette shape is clean and recognizable, and a plain
    # white background is required so make_car_shadows() below can cleanly
    # cut the car shape out to build the "shadow" puzzle piece.
    car_subjects = [
        ("car_01", "a red sedan car"),
        ("car_02", "a yellow sports car, low and sleek"),
        ("car_03", "a blue pickup truck with an open cargo bed"),
        ("car_04", "a yellow school bus, long and boxy"),
        ("car_05", "an orange race car, very low with a big rear spoiler"),
        ("car_06", "a black and white police car with a light bar on the roof"),
        ("car_07", "a red fire engine truck with a ladder on top"),
        ("car_08", "a white ambulance van with a red cross"),
        ("car_09", "a green off-road jeep SUV with big tires"),
        ("car_10", "a vintage 1950s classic car with round fenders"),
        ("car_11", "a green garbage collection truck with a compactor body"),
        ("car_12", "a yellow taxi cab with a roof light sign"),
        ("car_13", "a pink convertible sports car with the top down"),
        ("car_14", "a blue family minivan"),
        ("car_15", "an orange tow truck with a crane and hook on the back"),
        ("car_16", "a purple limousine, very long and sleek"),
        ("car_17", "a white cement mixer truck with a rotating drum"),
        ("car_18", "a red double-decker bus"),
        ("car_19", "a silver monster truck with huge oversized wheels"),
        ("car_20", "a light blue round compact beetle-style car"),
    ]
    for filename, prompt in car_subjects:
        images[filename + ".png"] = prompt + ", side view, profile view, isolated on plain white background, no shadow, no scenery, no background objects"

    # 7) maze game (game 5) assets. The two tile textures (road/grass) are used
    # as opaque per-cell background images; the rest are isolated icons that
    # make_maze_icons_transparent() below cuts out to transparent PNGs so they
    # can sit on top of the tiles and the town/grass scene background.
    #
    # ICON_STYLE keeps every maze icon dead simple and unambiguous for a
    # 4-year-old: one bold, instantly-readable silhouette per icon, no fussy
    # detail that gets lost at small board-cell sizes.
    ICON_STYLE = (
        ", extremely simple flat icon, single bold clearly recognizable shape, "
        "minimal detail, very thick black outline, bright saturated colors, "
        "picture-book illustration style for a young child, centered composition, "
        "isolated on plain white background, no shadow, no scenery, no text"
    )
    images["maze_bg.png"] = (
        "a cheerful pop art bird's-eye view of a small town with green grassy fields, "
        "a few colorful houses and trees scattered around, simple flat shapes, no grid, no road, no characters"
    )
    images["maze_road_tile.png"] = (
        "a single top-down square asphalt road tile texture with a white dashed center line, "
        "flat simple design, seamless, no cars, no scenery"
    )
    images["maze_grass_tile.png"] = (
        "a single top-down square grassy meadow tile texture with a few small flowers and leaf details, "
        "flat simple design, seamless, no cars, no scenery"
    )
    images["maze_car.png"] = "a simple red fire truck, top-down view" + ICON_STYLE
    images["maze_goal.png"] = "a small house with big bright orange flames on the roof" + ICON_STYLE
    images["maze_obstacle_barricade.png"] = "an orange and white striped road barricade" + ICON_STYLE
    images["maze_obstacle_puddle.png"] = "a round blue water puddle with a few small droplets" + ICON_STYLE
    images["maze_start_station.png"] = "a red fire station building with one big garage door" + ICON_STYLE
    images["maze_goal_safe.png"] = "a small tidy house, safe and bright, no fire, no smoke" + ICON_STYLE

    # 8) maze game intermediate tier (police theme, 5x5 grid)
    images["maze_bg_intermediate.png"] = (
        "A 2D children's maze game, 5x5 grid, police car start, police station goal, pastel town background, "
        "playful style, no grid lines, no characters"
    )
    images["maze_car_police.png"] = "a simple black and white police car with one roof light bar, top-down view" + ICON_STYLE
    images["maze_start_police.png"] = "a police station building with one blue lamp sign" + ICON_STYLE
    images["maze_goal_thief.png"] = "a sneaky thief character in a striped shirt and eye mask, holding a round money bag" + ICON_STYLE
    images["maze_goal_thief_caught.png"] = "a thief character wearing handcuffs, sitting down, striped shirt and eye mask" + ICON_STYLE
    images["maze_warp.png"] = "a round colorful spiral swirl portal" + ICON_STYLE

    # 9) maze game advanced tier ("machi no hero" - fire truck, 7x7 grid, finger-trace controls)
    images["maze_bg_advanced.png"] = (
        "A 2D children's advanced maze game screen, top-down view, winding roads through a pastel town, "
        "small obstacles like cones and fallen trees along the streets, bright and playful style, "
        "no grid lines, no characters, no text"
    )
    images["maze_obstacle_cone.png"] = "one single orange and white traffic safety cone" + ICON_STYLE
    images["maze_obstacle_fallen_tree.png"] = "one fallen brown tree log lying down, with a couple of green leaves" + ICON_STYLE
    images["maze_obstacle_trafficjam.png"] = "two small cars bumper to bumper, stuck in traffic" + ICON_STYLE
    images["maze_gimmick_light.png"] = "a simple traffic light pole with one red circle and one green circle" + ICON_STYLE
    images["maze_gimmick_switch.png"] = "a round yellow button switch on the ground" + ICON_STYLE
    images["maze_gimmick_gate.png"] = "a red and white striped road gate barrier arm, straight bar shape" + ICON_STYLE
    images["maze_badge_hero.png"] = "a round gold medal with a single star" + ICON_STYLE

    return images


def make_car_shadows():
    """Builds a car_XX_shadow.png (transparent-background silhouette) next to
    every car_XX.png: a single solid-filled shape showing only the car's outer
    outline (no window/detail holes, no drop shadow under the wheels).

    Pollinations renders these as product photos with a soft grey drop-shadow
    ellipse under the car. A plain "distance from background color" threshold
    can't tell that shadow apart from the car (both are far enough from the
    white background), but the shadow is always low-saturation (grey) while
    car paint is much more saturated - even black/white trim on the car itself
    is protected because it gets absorbed into the solid shape once it's
    enclosed by higher-saturation edges (fill-holes + keep-largest-component
    below). So: pixels are only "car" if they're both far from the background
    color AND reasonably saturated; everything else (background + the grey
    shadow blob) becomes transparent.

    Needs numpy + Pillow + scipy (all common; the script still works without
    them, it just skips this step and prints a note)."""
    try:
        import numpy as np
        from PIL import Image
        from scipy.ndimage import binary_closing, binary_fill_holes, label
    except ImportError:
        print("\n(numpy/Pillow/scipy not installed - skipping car shadow generation.")
        print(" Run: pip install numpy pillow scipy   then re-run this script.)")
        return

    fill = (35, 35, 55, 235)   # dark navy-grey, slightly translucent shadow color
    tolerance = 42             # how far from the background color counts as "not background"
    sat_threshold = 0.08       # how saturated a pixel must be to count as car paint (not a grey shadow)

    for i in range(1, 21):
        src = os.path.join(OUT_DIR, "car_{:02d}.png".format(i))
        dst = os.path.join(OUT_DIR, "car_{:02d}_shadow.png".format(i))
        if not os.path.exists(src):
            continue
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            print("  skip (already exists): {}".format(os.path.basename(dst)))
            continue
        try:
            img = Image.open(src).convert("RGB")
            rgb = np.array(img).astype(np.float64)
            h, w = rgb.shape[0], rgb.shape[1]
            corners = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
            bg = corners.mean(axis=0)
            dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))

            norm = rgb / 255.0
            maxc = norm.max(axis=2)
            minc = norm.min(axis=2)
            sat = np.where(maxc > 0, (maxc - minc) / np.where(maxc == 0, 1, maxc), 0)

            is_car = (dist >= tolerance) & (sat > sat_threshold)
            is_car = binary_closing(is_car, structure=np.ones((9, 9)), iterations=2)
            is_car = binary_fill_holes(is_car)
            labeled, n = label(is_car)
            if n > 1:
                sizes = np.bincount(labeled.ravel())
                sizes[0] = 0
                is_car = labeled == sizes.argmax()

            out = np.zeros((h, w, 4), dtype=np.uint8)
            out[:, :, 0] = fill[0]
            out[:, :, 1] = fill[1]
            out[:, :, 2] = fill[2]
            out[:, :, 3] = np.where(is_car, fill[3], 0).astype(np.uint8)
            Image.fromarray(out, "RGBA").save(dst)
            print("  OK: {} (silhouette built from {})".format(os.path.basename(dst), os.path.basename(src)))
        except Exception as e:
            print("  FAILED to build shadow for {}: {}".format(src, e))


MAZE_ICON_FILES = [
    "maze_car.png",
    "maze_goal.png",
    "maze_goal_safe.png",
    "maze_obstacle_barricade.png",
    "maze_obstacle_puddle.png",
    "maze_start_station.png",
    "maze_car_police.png",
    "maze_start_police.png",
    "maze_goal_thief.png",
    "maze_goal_thief_caught.png",
    "maze_warp.png",
    "maze_obstacle_cone.png",
    "maze_obstacle_fallen_tree.png",
    "maze_obstacle_trafficjam.png",
    "maze_gimmick_light.png",
    "maze_gimmick_switch.png",
    "maze_gimmick_gate.png",
    "maze_badge_hero.png",
]


def make_maze_icons_transparent():
    """Cuts the plain white background out of each file in MAZE_ICON_FILES,
    turning it into a transparent-background icon in place. Unlike
    make_car_shadows() above, this keeps the original colors/detail (it's not
    building a solid silhouette) - it just erases pixels close to the
    background corner color, with a soft-edged alpha falloff so the cut edge
    isn't jagged."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        print("\n(numpy/Pillow not installed - skipping maze icon transparency cutout.")
        print(" Run: pip install numpy pillow   then re-run this script.)")
        return

    inner_tol = 30   # below this distance from bg color: fully transparent
    outer_tol = 70   # above this distance: fully opaque; between is a soft edge

    for filename in MAZE_ICON_FILES:
        path = os.path.join(OUT_DIR, filename)
        if not os.path.exists(path):
            continue
        try:
            img = Image.open(path).convert("RGB")
            rgb = np.array(img).astype(np.float64)
            h, w = rgb.shape[0], rgb.shape[1]
            corners = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
            bg = corners.mean(axis=0)
            dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))

            alpha = np.clip((dist - inner_tol) / (outer_tol - inner_tol), 0, 1) * 255

            out = np.dstack([rgb, alpha]).astype(np.uint8)
            Image.fromarray(out, "RGBA").save(path)
            print("  OK: {} (background cut to transparent)".format(filename))
        except Exception as e:
            print("  FAILED to cut background for {}: {}".format(filename, e))


def download_one(filename, prompt, retries=RETRIES, base_delay=RETRY_BASE_DELAY):
    out_path = os.path.join(OUT_DIR, filename)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print("  skip (already exists): {}".format(filename))
        return True

    full_prompt = prompt + STYLE_SUFFIX
    url = BASE_URL.format(prompt=urllib.parse.quote(full_prompt))

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 500:
                raise ValueError("response too small ({} bytes), likely an error page".format(len(data)))
            with open(out_path, "wb") as f:
                f.write(data)
            print("  OK: {} ({} bytes, attempt {})".format(filename, len(data), attempt))
            return True
        except Exception as e:
            if attempt < retries:
                wait = base_delay * attempt
                print("  attempt {}/{} failed for {}: {} -> retrying in {}s".format(
                    attempt, retries, filename, e, wait))
                time.sleep(wait)
            else:
                print("  attempt {}/{} failed for {}: {}".format(attempt, retries, filename, e))

    print("  FAILED: {} (giving up after {} attempts)".format(filename, retries))
    return False


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    images = build_image_manifest()
    total = len(images)
    print("Found {} images to prepare. Saving into: {}".format(total, OUT_DIR))
    print("(existing files are skipped automatically, so this script is safe to re-run)\n")

    ok_count = 0
    failed = []
    for i, (filename, prompt) in enumerate(images.items(), start=1):
        print("[{}/{}] {}".format(i, total, filename))
        if download_one(filename, prompt):
            ok_count += 1
        else:
            failed.append(filename)
        time.sleep(BETWEEN_REQUEST_DELAY)

    print("\nDone: {}/{} succeeded.".format(ok_count, total))
    if failed:
        print("The following {} file(s) failed - just run this script again to retry them:".format(len(failed)))
        for f in failed:
            print("  -", f)

    print("\nBuilding car shadow silhouettes (game 3)...")
    make_car_shadows()

    print("\nCutting maze icons (game 5) to transparent...")
    make_maze_icons_transparent()

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
