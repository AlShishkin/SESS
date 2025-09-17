# -*- coding: utf-8 -*-
ROUND_Q = 2
FT_TO_M = 0.3048

def r2(x):
    try:
        return round(float(x), ROUND_Q)
    except Exception:
        return x

def centroid_xy(poly):
    a = 0.0; cx = 0.0; cy = 0.0; n = len(poly)
    for i in range(n):
        x1,y1 = poly[i]; x2,y2 = poly[(i+1)%n]
        cross = x1*y2 - x2*y1
        a += cross; cx += (x1+x2)*cross; cy += (y1+y2)*cross
    a *= 0.5
    if abs(a) < 1e-12:
        return sum(p[0] for p in poly)/n, sum(p[1] for p in poly)/n
    return cx/(6.0*a), cy/(6.0*a)

def bounds(items):
    xs, ys = [], []
    for it in items:
        for x, y in it["outer_xy_m"]:
            xs.append(x); ys.append(y)
        for h in it.get("inner_loops_xy_m", []):
            for x, y in h:
                xs.append(x); ys.append(y)
    if not xs:
        return (0,0,1,1)
    return (min(xs), min(ys), max(xs), max(ys))
