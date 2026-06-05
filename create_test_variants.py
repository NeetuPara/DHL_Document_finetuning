"""
Create synthetic scan/photo/multi-image variants of test PDFs for robustness testing.

Reads from:  test_documents/  (digital PDFs — kept untouched)

Writes to:
  test_documents_variants/
    scanned/      — PDF pages rendered as grayscale with scan artifacts
    photos/       — JPG pages with perspective, noise, lighting, JPEG compression
    multi_images/ — Each PDF page as a separate JPG (tests multi-image upload)

Run:
    python create_test_variants.py [--count N]  (default: 20 packets, 10 singles)
"""
import argparse, random, shutil, math
from pathlib import Path

import fitz                        # PyMuPDF — PDF → image
from PIL import (Image, ImageFilter, ImageEnhance,
                 ImageDraw, ImageChops, ImageOps)
import numpy as np

BASE  = Path(__file__).parent
SRC   = BASE / "test_documents"
OUT   = BASE / "test_documents_variants"

random.seed(42)
np.random.seed(42)


# ── Image degradation helpers ─────────────────────────────────────────────────

def add_gaussian_noise(img: Image.Image, sigma: float = 8.0) -> Image.Image:
    arr  = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, sigma, arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def random_rotation(img: Image.Image, max_deg: float = 1.5) -> Image.Image:
    angle = random.uniform(-max_deg, max_deg)
    return img.rotate(angle, expand=False, fillcolor=(255, 255, 255), resample=Image.BICUBIC)


def perspective_warp(img: Image.Image, strength: float = 0.04) -> Image.Image:
    """Simulate slight trapezoidal distortion from off-angle photo."""
    w, h = img.size
    d = int(min(w, h) * strength)
    # Randomise which corners shift
    dx = [random.randint(-d, d) for _ in range(4)]
    dy = [random.randint(-d, d) for _ in range(4)]
    # Source corners: TL, TR, BR, BL
    src = [(0,0),(w,0),(w,h),(0,h)]
    dst = [(dx[0],dy[0]),(w+dx[1],dy[1]),(w+dx[2],h+dy[2]),(dx[3],h+dy[3])]
    # Compute perspective coefficients
    coeffs = _perspective_coeffs(src, dst)
    return img.transform(img.size, Image.PERSPECTIVE, coeffs, Image.BICUBIC,
                         fillcolor=(240, 240, 235))


def _perspective_coeffs(src, dst):
    """Solve 8-parameter perspective transform from 4 point pairs."""
    import numpy as np
    A = []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u*x, -u*y],
              [0, 0, 0, x, y, 1, -v*x, -v*y]]
    A = np.array(A, dtype=float)
    b = np.array([u for (u,v) in src for _ in range(2)]
                 if False else
                 sum([[u, v] for (u,v) in src], []), dtype=float)
    coeffs, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    return tuple(coeffs)


def gradient_lighting(img: Image.Image) -> Image.Image:
    """Simulate uneven lighting — one corner is brighter."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    # Random bright corner
    cx = random.choice([0, w])
    cy = random.choice([0, h])
    radius = int(max(w, h) * 1.2)
    # Draw radial gradient — bright at corner, dim toward opposite
    for r in range(radius, 0, -max(1, radius//80)):
        alpha = int(30 * (1 - r / radius))
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=alpha)
    overlay = Image.new("RGB", (w, h), (255, 245, 230))  # warm light
    img = Image.composite(overlay, img, mask)
    return img


def jpeg_compress(img: Image.Image, quality: int = None) -> Image.Image:
    """Round-trip through JPEG to add compression artifacts."""
    q = quality or random.randint(60, 82)
    buf = __import__("io").BytesIO()
    img.save(buf, format="JPEG", quality=q)
    buf.seek(0)
    return Image.open(buf).copy()


def make_scan(img: Image.Image) -> Image.Image:
    """Simulate a flatbed or office scanner output."""
    # 50% chance of grayscale (many office scanners default to B&W/gray)
    if random.random() < 0.5:
        img = ImageOps.grayscale(img).convert("RGB")
    else:
        # Slight desaturation for colour scanners
        img = ImageEnhance.Color(img).enhance(random.uniform(0.7, 0.9))

    img = random_rotation(img, max_deg=1.2)
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.9, 1.15))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.92, 1.05))
    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 0.8)))
    img = add_gaussian_noise(img, sigma=random.uniform(3.0, 7.0))
    return img


def make_photo(img: Image.Image) -> Image.Image:
    """Simulate a phone camera photo of a printed document."""
    img = img.convert("RGB")
    img = perspective_warp(img, strength=random.uniform(0.025, 0.055))
    img = random_rotation(img, max_deg=random.uniform(2.0, 5.0))
    img = gradient_lighting(img)
    # Colour temperature shift — slightly warmer (phone cameras run warm)
    r, g, b = img.split()
    r = ImageEnhance.Brightness(r).enhance(random.uniform(1.02, 1.08))
    b = ImageEnhance.Brightness(b).enhance(random.uniform(0.90, 0.97))
    img = Image.merge("RGB", (r, g, b))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.7, 0.9))  # phone softening
    img = add_gaussian_noise(img, sigma=random.uniform(6.0, 14.0))
    img = jpeg_compress(img, quality=random.randint(55, 78))
    return img


# ── PDF rendering ─────────────────────────────────────────────────────────────

def pdf_to_images(pdf_path: Path, dpi: int = 150) -> list[Image.Image]:
    mat  = fitz.Matrix(dpi / 72, dpi / 72)
    pdf  = fitz.open(str(pdf_path))
    imgs = []
    for page in pdf:
        buf = page.get_pixmap(matrix=mat).tobytes("png")
        imgs.append(Image.open(__import__("io").BytesIO(buf)).copy())
    pdf.close()
    return imgs


def images_to_pdf(images: list[Image.Image], out_path: Path):
    """Save list of PIL images as a single PDF."""
    if not images:
        return
    rgb_imgs = [img.convert("RGB") for img in images]
    rgb_imgs[0].save(str(out_path), save_all=True, append_images=rgb_imgs[1:])


# ── Main ───────────────────────────────────────────────────────────────────────

def main(n_packets: int = 20, n_singles: int = 10, n_multi: int = 10):
    # Output dirs
    for sub in ["scanned/splitting_packets", "scanned/single_docs",
                "photos/splitting_packets",  "photos/single_docs",
                "multi_images"]:
        (OUT / sub).mkdir(parents=True, exist_ok=True)

    # ── Collect source PDFs ───────────────────────────────────────────────────
    packet_pdfs = sorted((SRC / "splitting_packets").glob("*.pdf"))
    single_pdfs = []
    for cls_dir in sorted((SRC / "single_docs").iterdir()):
        single_pdfs.extend(sorted(cls_dir.glob("*.pdf")))

    random.shuffle(packet_pdfs)
    random.shuffle(single_pdfs)

    packet_pdfs = packet_pdfs[:n_packets]
    single_pdfs = single_pdfs[:n_singles]

    total = len(packet_pdfs) * 2 + len(single_pdfs) * 2 + min(n_multi, len(packet_pdfs))
    done  = 0

    print(f"Generating {total} variant files ...")
    print(f"  {len(packet_pdfs)} packets × 2 variants + "
          f"{len(single_pdfs)} singles × 2 variants + "
          f"{min(n_multi, len(packet_pdfs))} multi-image sets")

    def progress(label):
        nonlocal done
        done += 1
        print(f"  [{done:>3}/{total}] {label}")

    # ── Scanned + Photo variants ───────────────────────────────────────────────
    for src_list, out_sub, label in [
        (packet_pdfs, "splitting_packets", "pkt"),
        (single_pdfs, "single_docs",       "sgl"),
    ]:
        for pdf_path in src_list:
            imgs = pdf_to_images(pdf_path)

            # Scanned
            scan_imgs = [make_scan(img) for img in imgs]
            images_to_pdf(scan_imgs, OUT / "scanned" / out_sub / pdf_path.name)
            progress(f"scanned/{out_sub}/{pdf_path.name}")

            # Photo
            photo_imgs = [make_photo(img) for img in imgs]
            images_to_pdf(photo_imgs, OUT / "photos" / out_sub / pdf_path.name)
            progress(f"photos/{out_sub}/{pdf_path.name}")

    # ── Multi-image sets (each page → separate JPG) ────────────────────────────
    for pdf_path in packet_pdfs[:n_multi]:
        imgs    = pdf_to_images(pdf_path)
        out_dir = OUT / "multi_images" / pdf_path.stem
        out_dir.mkdir(exist_ok=True)
        for i, img in enumerate(imgs, 1):
            # Light photo simulation — keeps it realistic but not too degraded
            img_out = make_photo(img)
            img_out.save(str(out_dir / f"page_{i:02d}.jpg"), quality=80)
        progress(f"multi_images/{pdf_path.stem}/ ({len(imgs)} pages)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\nDone. Output: {OUT}")
    print(f"\nFolder structure:")
    print(f"  scanned/splitting_packets/  {len(packet_pdfs)} PDFs  (flatbed scan simulation)")
    print(f"  scanned/single_docs/        {len(single_pdfs)} PDFs")
    print(f"  photos/splitting_packets/   {len(packet_pdfs)} PDFs  (phone camera simulation)")
    print(f"  photos/single_docs/         {len(single_pdfs)} PDFs")
    print(f"  multi_images/               {min(n_multi, len(packet_pdfs))} folders, "
          f"each containing individual page JPGs")
    print(f"\nHow to test:")
    print(f"  Scans   : upload any PDF from scanned/")
    print(f"  Photos  : upload any PDF from photos/")
    print(f"  Multi   : in the app, select ALL JPGs inside one multi_images/<folder>/")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--packets", type=int, default=20,
                   help="Number of splitting-packet PDFs to convert (default 20)")
    p.add_argument("--singles", type=int, default=10,
                   help="Number of single-doc PDFs to convert (default 10)")
    p.add_argument("--multi",   type=int, default=10,
                   help="Number of packets to split into individual page JPGs (default 10)")
    a = p.parse_args()
    main(a.packets, a.singles, a.multi)
