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

    # (Game 2 "Topping Master" - base dishes + topping ingredients - was retired.
    # Its prompts and generated images are preserved under
    # archived_topping_master/ in case it comes back later.)

    # 4) sticker-book backgrounds, 3 variants
    images["bg_seal_01.png"] = "cute pastel rainbow and stars pattern background"
    images["bg_seal_02.png"] = "cute pastel colored animal doodle pattern background"
    images["bg_seal_03.png"] = "cute pastel candy and sweets pattern background"

    # 5) 50 reward stickers
    sticker_subjects = [
        "cat", "dog", "rabbit", "bear", "panda", "fox", "lion", "elephant", "penguin", "owl",
        "unicorn", "dinosaur", "dragon", "whale", "dolphin", "octopus", "turtle", "frog", "ladybug", "butterfly",
        "bee", "star", "rainbow", "sun", "moon", "cloud", "rocket", "car", "train", "airplane",
        "boat", "balloon", "ice cream", "cupcake", "donut", "cookie", "candy", "apple", "strawberry", "banana",
        "watermelon", "pizza slice", "heart", "crown", "diamond", "flower", "tree", "mushroom", "snowman", "robot",
    ]
    assert len(sticker_subjects) == 50
    for i, subject in enumerate(sticker_subjects, start=1):
        filename = "seal_{:02d}.png".format(i)
        images[filename] = "cute cartoon {} sticker".format(subject)

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
    ]
    for filename, prompt in car_subjects:
        images[filename + ".png"] = prompt + ", side view, profile view, isolated on plain white background, no shadow, no scenery, no background objects"

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

    for i in range(1, 11):
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

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
