"""Phone-photo realism pass: python realism.py <in.png> <out.jpg> [--strength 1.0]
Adds fine luminance grain, a touch of chroma noise, slight sharpening, subtle vignette and phone-JPEG compression.
Keeps 1080x1350 for feed photos. Safe to run on any PNG from fal."""
import sys, numpy as np
from PIL import Image, ImageFilter, ImageEnhance
src, dst = sys.argv[1], sys.argv[2]; k = float(sys.argv[sys.argv.index("--strength")+1]) if "--strength" in sys.argv else 1.0
im = Image.open(src).convert("RGB"); im = im.resize((1080, int(1080*im.height/im.width)), Image.LANCZOS)
a = np.asarray(im).astype(np.float32)
rng = np.random.default_rng(7)
a += rng.normal(0, 3.2*k, a.shape[:2])[..., None]          # luminance grain
a += rng.normal(0, 1.2*k, a.shape)                           # chroma noise
h, w = a.shape[:2]; yy, xx = np.mgrid[0:h, 0:w]
r = np.sqrt(((xx-w/2)/(w/2))**2 + ((yy-h/2)/(h/2))**2); a *= (1 - 0.10*k*np.clip(r-0.6, 0, 1))[..., None]   # vignette
im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(45*k), threshold=2))
im = ImageEnhance.Contrast(im).enhance(1.03)
im.save(dst, quality=84, subsampling=2)
