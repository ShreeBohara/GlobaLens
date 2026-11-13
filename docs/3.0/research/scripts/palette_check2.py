import importlib.util, sys
spec = importlib.util.spec_from_file_location("pc", "palette_check.py")
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
tok = pc.tok
for name, L in [("border-control", 0.50), ("border-control", 0.52), ("border-control", 0.54)]:
    hx = pc.oklch_to_hex(L, 0.020, 255)[0]
    print(name, L, hx, "on canvas %.2f surface-1 %.2f surface-2 %.2f surface-3 %.2f" % tuple(pc.contrast(hx, tok[b]) for b in ["canvas","surface-1","surface-2","surface-3"]))
# 5-class tone variant with wider lightness span
NEG_H, POS_H = 38, 236
five = {}
for i, t in [(-2,1.0),(-1,0.5),(0,0.0),(1,0.5),(2,1.0)]:
    L = 0.58 + 0.20*t; C = 0.012 + 0.165*t
    h = NEG_H if i<0 else (POS_H if i>0 else 255)
    five[i] = pc.oklch_to_hex(L, C, h)[0]
print("5-class tone:", "  ".join(f"{k:+d}:{v}" for k,v in sorted(five.items())))
ks = sorted(five)
for a,b in zip(ks, ks[1:]):
    print(f"{a:+d}->{b:+d}", "  ".join(f"{s or 'normal'}:{pc.dE(five[a],five[b],s):.3f}" for s in (None,'protan','deutan','tritan')))
land = pc.scene['land']
for k,v in sorted(five.items()):
    print(f"{k:+d} {v} vs land {pc.contrast(v, land):.2f}")
print("lens-500 vs warning:", "  ".join(f"{s or 'normal'}:{pc.dE(tok['lens-500'], tok['warning'], s):.3f}" for s in (None,'protan','deutan','tritan')))
print("lens-500 vs danger:", "  ".join(f"{s or 'normal'}:{pc.dE(tok['lens-500'], tok['danger'], s):.3f}" for s in (None,'protan','deutan','tritan')))
# Dark-adapted Okabe-Ito check vs surface-1 / land
oi = {"orange":"#E69F00","sky":"#56B4E9","bluish-green":"#2BC79A","yellow":"#F0E442","blue":"#3D9BE0","vermillion":"#E8743B","purple":"#E08DC0"}
for k,v in oi.items():
    print(f"OI {k:13s} {v} land {pc.contrast(v, land):.2f}")
names=list(oi)
worst=[]
for s in (None,'protan','deutan','tritan'):
    m=min(((pc.dE(oi[a],oi[b],s),a,b) for i,a in enumerate(names) for b in names[i+1:]))
    worst.append((s or 'normal',)+m)
for w in worst: print("closest OI pair", w[0], f"{w[1]:.3f}", w[2], w[3])
