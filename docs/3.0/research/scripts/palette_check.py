"""Generate and verify the GlobaLens 3.0 'Deep Field' palette.

- Builds tokens in OKLCH (Ottosson OKLab), converts to sRGB hex (chroma-reduced into gamut).
- Computes WCAG 2.x contrast ratios for text/UI tokens against surfaces.
- Simulates colour-vision deficiency (Machado et al. 2009, severity 1.0, linear RGB)
  and reports OKLab distances between adjacent steps of the tone (sentiment) scale.
"""
import math

import numpy as np


def srgb_to_linear(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)


def oklab_to_linear_rgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return np.array([r, g, bb])


def linear_rgb_to_oklab(rgb):
    r, g, b = rgb
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return np.array([
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    ])


def oklch_to_hex(L, C, h):
    """Convert OKLCH to hex, reducing chroma until in sRGB gamut."""
    c = C
    while c >= 0:
        a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
        lin = oklab_to_linear_rgb(L, a, b)
        if np.all(lin >= -1e-6) and np.all(lin <= 1 + 1e-6):
            srgb = linear_to_srgb(np.clip(lin, 0, 1))
            return "#" + "".join(f"{int(round(v * 255)):02X}" for v in srgb), c
        c -= 0.002
    raise ValueError("out of gamut")


def hex_to_linear(hx):
    hx = hx.lstrip("#")
    rgb = np.array([int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return srgb_to_linear(rgb)


def rel_lum(hx):
    r, g, b = hex_to_linear(hx)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


MACHADO = {
    "protan": np.array([[0.152286, 1.052583, -0.204868],
                        [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    "deutan": np.array([[0.367322, 0.860646, -0.227968],
                        [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
    "tritan": np.array([[1.255528, -0.076749, -0.178779],
                        [-0.078411, 0.930809, 0.147602],
                        [0.004733, 0.691367, 0.303900]]),
}


def oklab_of(hx, sim=None):
    lin = hex_to_linear(hx)
    if sim:
        lin = np.clip(MACHADO[sim] @ lin, 0, 1)
    return linear_rgb_to_oklab(lin)


def dE(h1, h2, sim=None):
    return float(np.linalg.norm(oklab_of(h1, sim) - oklab_of(h2, sim)))


# ---------------------------------------------------------------- tokens
HUE_N = 255  # cool neutral hue
neutrals = {
    "void": (0.115, 0.012),
    "canvas": (0.145, 0.014),
    "surface-1": (0.180, 0.016),
    "surface-2": (0.215, 0.018),
    "surface-3": (0.255, 0.020),
    "border-subtle": (0.300, 0.020),
    "border-strong": (0.370, 0.022),
    "text-disabled": (0.470, 0.020),
    "text-tertiary": (0.660, 0.020),
    "text-secondary": (0.790, 0.016),
    "text-primary": (0.950, 0.008),
}
tok = {}
for k, (L, C) in neutrals.items():
    tok[k] = oklch_to_hex(L, C, HUE_N)[0]

accent = {
    "lens-300": (0.950, 0.150, 122),
    "lens-500": (0.900, 0.200, 124),
    "lens-700": (0.640, 0.150, 126),
    "lens-900": (0.300, 0.070, 128),
}
for k, (L, C, h) in accent.items():
    tok[k] = oklch_to_hex(L, C, h)[0]

status = {
    "danger": (0.680, 0.200, 22),
    "warning": (0.820, 0.150, 75),
}
for k, (L, C, h) in status.items():
    tok[k] = oklch_to_hex(L, C, h)[0]

# Tone (sentiment) diverging scale: neutral is dim slate, extremes luminous.
NEG_H, POS_H = 42, 236
tone = {}
for i, t in [(-3, 1.0), (-2, 2 / 3), (-1, 1 / 3), (0, 0.0), (1, 1 / 3), (2, 2 / 3), (3, 1.0)]:
    L = 0.60 + 0.17 * t
    C = 0.012 + 0.160 * t
    h = NEG_H if i < 0 else (POS_H if i > 0 else HUE_N)
    tone[i] = oklch_to_hex(L, C, h)[0]

# Globe scene colours
scene = {
    "ocean": oklch_to_hex(0.135, 0.020, 250)[0],
    "land": oklch_to_hex(0.205, 0.018, 250)[0],
    "coast": oklch_to_hex(0.330, 0.025, 250)[0],
    "graticule": oklch_to_hex(0.250, 0.020, 250)[0],
    "atmosphere": oklch_to_hex(0.620, 0.110, 245)[0],
    "city-lights": oklch_to_hex(0.840, 0.110, 70)[0],
}

print("== Neutral + accent + status tokens ==")
for k, v in tok.items():
    print(f"{k:16s} {v}")
print("\n== Scene ==")
for k, v in scene.items():
    print(f"{k:16s} {v}")
print("\n== Tone scale (neg -> pos) ==")
print("  ".join(f"{i:+d}:{tone[i]}" for i in sorted(tone)))

print("\n== WCAG contrast: text tokens on surfaces (need >= 4.5 for body text) ==")
for txt in ["text-primary", "text-secondary", "text-tertiary", "text-disabled", "lens-500", "lens-300", "danger", "warning"]:
    row = []
    for bg in ["void", "canvas", "surface-1", "surface-2", "surface-3"]:
        row.append(f"{bg}:{contrast(tok[txt], tok[bg]):5.2f}")
    print(f"{txt:15s} " + "  ".join(row))

print("\n== Non-text contrast (need >= 3.0): UI strokes on surfaces ==")
for ui in ["border-strong", "border-subtle", "lens-500", "lens-700"]:
    row = [f"{bg}:{contrast(tok[ui], tok[bg]):5.2f}" for bg in ["canvas", "surface-1", "surface-2"]]
    print(f"{ui:15s} " + "  ".join(row))

print("\n== Text on accent fill (dark text on lens-500 button) ==")
print("void on lens-500:", round(contrast(tok["void"], tok["lens-500"]), 2))

print("\n== Tone marks vs land/ocean (non-text contrast, aim >= 3 for extremes) ==")
for i in sorted(tone):
    print(f"{i:+d} {tone[i]}  land:{contrast(tone[i], scene['land']):5.2f}  ocean:{contrast(tone[i], scene['ocean']):5.2f}")

print("\n== Tone scale distinguishability: OKLab dE between steps (normal / protan / deutan / tritan) ==")
keys = sorted(tone)
for a, b in zip(keys, keys[1:]):
    vals = [dE(tone[a], tone[b], s) for s in (None, "protan", "deutan", "tritan")]
    print(f"{a:+d}->{b:+d}: " + "  ".join(f"{v:.3f}" for v in vals))
print("extremes -3 vs +3: " + "  ".join(f"{dE(tone[-3], tone[3], s):.3f}" for s in (None, 'protan', 'deutan', 'tritan')))
print("lens-500 vs tone+3 / tone-3 (accent must not read as data): " +
      "  ".join(f"{s or 'normal'}:{dE(tok['lens-500'], tone[3], s):.3f}/{dE(tok['lens-500'], tone[-3], s):.3f}" for s in (None, 'protan', 'deutan', 'tritan')))
