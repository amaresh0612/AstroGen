from reportlab.graphics.shapes import Drawing, Rect, Line
from reportlab.graphics import renderPM
from reportlab.lib import colors

def test_east_indian_diagonals():
    size = 440
    margin = 24
    inner = size - 2 * margin
    cell = inner / 3.0

    ox, oy = margin, margin
    d = Drawing(size, size)

    # Outer + inner frames
    d.add(Rect(6, 6, size-12, size-12, strokeColor=colors.HexColor('#8B4513'), fillColor=None, strokeWidth=6))
    d.add(Rect(ox, oy, inner, inner, strokeColor=colors.black, fillColor=None, strokeWidth=2))

    # Grid lines
    for i in range(1, 3):
        d.add(Line(ox + i*cell, oy, ox + i*cell, oy + inner, strokeColor=colors.black, strokeWidth=1.5))
        d.add(Line(ox, oy + i*cell, ox + inner, oy + i*cell, strokeColor=colors.black, strokeWidth=1.5))

    # Coordinates
    x0, x1, x2, x3 = ox, ox + cell, ox + 2*cell, ox + 3*cell
    y0, y1, y2, y3 = oy, oy + cell, oy + 2*cell, oy + 3*cell

    # NEW: Top-left diagonal from TOP-LEFT -> BOTTOM-RIGHT (↘) — **per your request**
    d.add(Line(x0, y3, x1, y2, strokeColor=colors.red, strokeWidth=2))    # top-left (red) ↘

    # Mirror pattern for other corners (keeps alternating look)
    d.add(Line(x3, y3, x2, y2, strokeColor=colors.blue, strokeWidth=2))    # top-right (blue) ↙
    d.add(Line(x0, y0, x1, y1, strokeColor=colors.green, strokeWidth=2))   # bottom-left (green) ↗
    d.add(Line(x3, y0, x2, y1, strokeColor=colors.purple, strokeWidth=2))  # bottom-right (purple) ↖

    png_bytes = renderPM.drawToString(d, fmt="PNG")
    with open("test_diagonals_updated.png", "wb") as f:
        f.write(png_bytes)

    print("Saved test_diagonals_updated.png — check that RED diagonal (top-left) runs top-left → bottom-right (↘).")

if __name__ == "__main__":
    test_east_indian_diagonals()
