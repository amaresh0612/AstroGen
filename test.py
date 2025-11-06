# test.py
"""
Standalone test for house assignment + Pillow rendering of East-Indian chart.
Run: python test.py
Output: test_chart.png and printed planet -> degree -> house mapping.
"""

from PIL import Image, ImageDraw, ImageFont
import io, os

# -----------------------------
# Helpers (same logic as app)
# -----------------------------
def get_house_number_from_degree(degree, house_cusps):
    """
    Determine house number (1..12) for a planet at `degree` (0..360),
    given `house_cusps` list of 12 cusp degrees.
    """
    d = degree % 360
    cusps = [c % 360 for c in house_cusps]
    for i in range(12):
        current = cusps[i]
        nxt = cusps[(i + 1) % 12]
        if current < nxt:
            if current <= d < nxt:
                return i + 1
        else:
            # wrap case
            if d >= current or d < nxt:
                return i + 1
    return 1

def _planet_abbr(name: str) -> str:
    mapping = {
        'Sun': 'SUN', 'Moon': 'MOO', 'Mars': 'MAR', 'Mercury': 'MER',
        'Jupiter': 'JUP', 'Venus': 'VEN', 'Saturn': 'SAT',
        'Rahu': 'RAH', 'Ketu': 'KET'
    }
    return mapping.get(name, name[:3].upper())

# -----------------------------
# Sample data (adjust as needed)
# -----------------------------
# sample house cusps in degrees (12 values). You can replace with your real cusps.
sample_house_cusps = [
    15.0, 45.0, 75.0, 105.0, 135.0, 165.0,
    195.0, 225.0, 255.0, 285.0, 315.0, 345.0
]

# sample planet positions (full_degree 0..360)
sample_planets = {
    "Sun": 14.2,     # near house 1 cusp example
    "Moon": 182.5,
    "Mars": 300.0,
    "Mercury": 46.3,
    "Jupiter": 120.7,
    "Venus": 250.4,
    "Saturn": 330.6,
    "Rahu": 195.0,
    "Ketu": 15.0
}

# -----------------------------
# Print assignments (verification)
# -----------------------------
print("Planet -> degree -> house assignment")
for pname, pdata in sample_planets.items():
    h = get_house_number_from_degree(pdata, sample_house_cusps)
    print(f"{pname:8} -> {pdata:7.3f}° -> House {h}")

print("\nHouse cusps (for reference):")
for i, c in enumerate(sample_house_cusps, start=1):
    print(f"House {i:2}: {c:.6f}°")

# -----------------------------
# Pillow renderer (simpler, but robust)
# -----------------------------
def render_chart_png_bytes_pil(planet_data, house_cusps_degrees, size=900, out_path="test_chart.png"):
    pad = int(size * 0.05)
    inner = size - 2 * pad
    cell = inner / 3.0
    ox, oy = pad, pad
    bg = (255, 255, 255)
    line_color = (0, 0, 0)
    planet_color = (2, 48, 99)

    im = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(im)

    # outer/inner frames
    draw.rectangle([pad // 4, pad // 4, size - pad // 4, size - pad // 4], outline=line_color, width=max(2, int(size*0.01)))
    draw.rectangle([ox, oy, ox + inner, oy + inner], outline=line_color, width=max(1, int(size*0.003)))

    # grid
    for i in range(1, 3):
        x = ox + i * cell; y = oy + i * cell
        draw.line([(x, oy), (x, oy + inner)], fill=line_color, width= max(1, int(size*0.003)))
        draw.line([(ox, y), (ox + inner, y)], fill=line_color, width= max(1, int(size*0.003)))

    # corners coords
    x0, x1, x2, x3 = ox, ox + cell, ox + 2 * cell, ox + 3 * cell
    y0, y1, y2, y3 = oy, oy + cell, oy + 2 * cell, oy + 3 * cell

    # diagonals (all black)
    draw.line([(x0, y3), (x1, y2)], fill=line_color, width=max(1, int(size*0.003)))
    draw.line([(x3, y3), (x2, y2)], fill=line_color, width=max(1, int(size*0.003)))
    draw.line([(x0, y0), (x1, y1)], fill=line_color, width=max(1, int(size*0.003)))
    draw.line([(x3, y0), (x2, y1)], fill=line_color, width=max(1, int(size*0.003)))

    # positions mapping (x,y,anchor)
    positions = {
        1:  (ox + 1.50 * cell, oy + 2.68 * cell, 'middle'),
        2:  (ox + 2.73 * cell, oy + 2.18 * cell, 'end'),
        3:  (ox + 2.73 * cell, oy + 1.50 * cell, 'end'),
        4:  (ox + 2.73 * cell, oy + 0.32 * cell, 'end'),
        5:  (ox + 1.50 * cell, oy + 0.32 * cell, 'middle'),
        6:  (ox + 1.50 * cell, oy + 1.50 * cell, 'middle'),
        7:  (ox + 0.27 * cell, oy + 1.50 * cell, 'start'),
        8:  (ox + 0.27 * cell, oy + 2.18 * cell, 'start'),
        9:  (ox + 1.50 * cell, oy + 2.18 * cell, 'middle'),
        10: (ox + 0.27 * cell, oy + 0.32 * cell, 'start'),
        11: (ox + 0.27 * cell, oy + 1.82 * cell, 'start'),
        12: (ox + 0.80 * cell, oy + 2.80 * cell, 'middle'),
    }

    # build houses -> planets
    houses = {i: [] for i in range(1, 13)}
    for pname, pdata in planet_data.items():
        hnum = get_house_number_from_degree(pdata, house_cusps_degrees)
        houses[hnum].append(_planet_abbr(pname))

    # font pick
    try:
        font = ImageFont.truetype("arial.ttf", size=max(12, int(size * 0.03)))
    except Exception:
        font = ImageFont.load_default()

    # measure function
    def measure_text(txt, fnt):
        try:
            bbox = draw.textbbox((0,0), txt, font=fnt)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except AttributeError:
            w, h = draw.textsize(txt, font=fnt)
        return w, h

    max_cell_width = cell * 1.9

    for h in range(1, 13):
        items = houses[h]
        if not items:
            continue
        x, y, anchor = positions[h]
        text = ", ".join(items)

        # reduce font size if too wide (only works for truetype)
        if isinstance(font, ImageFont.FreeTypeFont):
            fsize = font.size
            chosen_font = font
            w, ht = measure_text(text, chosen_font)
            while w > max_cell_width and fsize > 8:
                fsize -= 1
                chosen_font = ImageFont.truetype("arial.ttf", size=fsize)
                w, ht = measure_text(text, chosen_font)
        else:
            chosen_font = font
            w, ht = measure_text(text, chosen_font)

        # anchors
        if anchor == 'start':
            tx = x
        elif anchor == 'end':
            tx = x - w
        else:
            tx = x - (w / 2.0)
        ty = y - (ht / 2.0)
        draw.text((tx, ty), text, fill=planet_color, font=chosen_font)

    # save file
    out_path = out_path
    im.save(out_path, format="PNG")
    return out_path

# Render and save test_chart.png
out_file = render_chart_png_bytes_pil(sample_planets, sample_house_cusps, size=900, out_path="test_chart.png")
print(f"\nRendered image saved to: {os.path.abspath(out_file)}")
