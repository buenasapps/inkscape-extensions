#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 3D Revolve - Inkscape extension
# Copyright (C) 2026 tebicap
#
# This program is free software; you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version. It is distributed WITHOUT ANY WARRANTY; see the
# LICENSE file for details.
# SPDX-License-Identifier: GPL-2.0-or-later
"""
3D Revolve for Inkscape (Python extension, inkex >= 1.2; tested with inkex 1.4.1).

WHAT IT DOES
    Takes a path (the "profile"), revolves it around a vertical axis and draws it as a solid of
    revolution in pure vectors: one band for each segment of the profile, one linear gradient per band
    for the shading, caps on the open ends and cut faces if the sweep is partial. No raster and no 3D
    libraries: the math is our own (see below).

"LIVE" MODEL (the state is stored in the SVG itself)
    The result is a <g> that contains:
      * the original profile, hidden (display:none) and marked with data-revolve3d-role="profile";
      * a local <defs> with the gradients (ids "<group_id>-g1", "-g2"...);
      * the faces (<path>), already sorted from back to front.
    The group carries data-revolve3d = JSON {"version", "params"} with the parameters that were applied.
    Running the extension again on the group (or on any of its children) deletes everything except
    the profile and regenerates. Ungrouping breaks the link (on purpose).

ACTIONS  (internal .inx value -> dialog text; the internal names are confusing!)
    "apply"   -> "Apply/update": uses the values in the dialog.
    "reapply" -> "Restore effect": applies again with the SAVED values (in the group, or in the path
                 whose effect was removed, see ATTR_SAVED). The saved values take precedence; the dialog
                 only fills in keys that are missing (groups created with old versions).
    "restore" -> "Remove effect": gives back the original path (visible, with its transform) and
                 leaves the parameters on it (attribute data-revolve3d-saved).

FLOW
    Revolve3D.effect -> apply() / restore()
    apply -> RevolveEngine(params, path, color).build(group_id)
          -> list of faces (z, d, style) + gradients -> written inside the group.

GEOMETRIC CONVENTIONS (important if you touch the engine)
    * The profile arrives in SVG coordinates (x to the right, y DOWNWARD). The engine converts it to (r, h):
      r = distance to the axis (>= 0, outward), h = height (positive upward), centered on pivot_y.
    * World: (±r·cosθ, h, r·sinθ). The sign is the side of the axis; θ is the sweep angle.
    * View: v = M · world, with M = Rz·Rx·Ry (see view_matrix). +z points toward the viewer.
    * Screen: (axis_x + x, pivot_y − y); with perspective, x and y are multiplied by d / (d − z).
    * The object stays anchored to its axis: axis_x and pivot_y do not change when the view is rotated.
    * Drawing order: painter's algorithm (mean z of the face, from lowest to highest). It is an
      approximation: surfaces that intersect each other may be drawn in the wrong order.
    * Flat faces (caps, and the cut faces of a partial sweep) are placed with their PLANE, not with
      their mean z (see _place_plane): what lies behind their plane is drawn before them, what lies
      on the viewer's side after. Bands are split at the angle opposite to each cut so every piece
      falls entirely on one side of the cut plane.
    * Unit of the seam stroke (seam_width): document pixels (user units).

WHY IT IS THE WAY IT IS (decisions that should not be undone without a reason)
    * The seam stroke uses the SAME paint (the same gradient) as the fill. With a flat color it does
      not match the gradient and a line shows between bands (see face_style).
    * The bands are NOT enlarged or overlapped: this was tried and the joins looked bad (they did not
      line up). The ONLY way to hide the seams is that thin stroke; with seam_width = 0 (or seam_fix
      disabled) thin lines may be visible between bands.
    * The gradients are simplified (simplify_stops) and there are 3 levels (GRAD_QUALITY): before, each
      band carried ~17 stops for no reason.
    * The gradients live in a <defs> INSIDE the group: duplicating or deleting the group leaves no
      dangling references. If Inkscape moves them to the root, purge_orphan_gradients cleans them up.
    * The .inx dialog cannot be preloaded with the group's values nor disable controls depending on
      another value: these are limitations of the INX format, not of this code.

More context, parameters and how to test without Inkscape: README_EN.md / README_ES.md.
"""
import gettext
import json
import math
import os

import inkex
from inkex import Color, Group, LinearGradient, PathElement, Stop

# Translatable messages: domain "revolve3d", catalogs in locale/<language>/LC_MESSAGES/revolve3d.mo
# (next to this script). If there is no catalog for the language, English is kept.
_ = gettext.translation(
    "revolve3d", os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale"), fallback=True
).gettext

__version__ = "1.0"
__author__ = "tebicap"
__license__ = "GPL-2.0-or-later"

TAU = 2.0 * math.pi
ATTR_PARAMS = "data-revolve3d"
ATTR_ROLE = "data-revolve3d-role"
ROLE_PROFILE = "profile"
ATTR_SAVED = "data-revolve3d-saved"  # parameters left on the path when the effect is removed
FORMAT_VERSION = 1  # version of the JSON stored in data-revolve3d
# gradient quality: (samples per band, simplification tolerance in color levels)
GRAD_QUALITY = {"low": (7, 6.0), "normal": (11, 1.6), "high": (17, 0.7)}
# Perspective at 100 %: the camera is placed so that the nearest point it could possibly see (the object
# fits in a sphere of radius R around its center) is magnified by this factor. Lower = gentler maximum.
PERSPECTIVE_MAX_MAGNIFICATION = 5.0

# Parameters stored in the group (name -> default value). The names match the
# <param name="..."> entries of the .inx and the --arguments of add_arguments. If you change a default
# value, change it in the .inx too (value and "Default: ..." tooltip).
DEFAULTS = {
    "axis_side": "left",
    "axis_offset": 0.0,
    "sweep": 360.0,
    "start_angle": 0.0,
    "rot_x": 20.0,
    "rot_y": 0.0,
    "rot_z": 0.0,
    "perspective": 0.0,
    "shading": "smooth",
    "light_az": -40.0,
    "light_el": 40.0,
    "ambient": 35.0,
    "highlight": 25.0,
    "cap": True,
    "sides": "auto",
    "profile_detail": 24,
    "band_step": 5.0,
    "angular_segments": 28,
    "seam_fix": True,
    "seam_width": 0.2,
    "grad_quality": "normal",
    "force_color": False,
    "fallback_fill": "#4f9da6",
}


# --------------------------------------------------------------------------
# Minimal 3D algebra
# --------------------------------------------------------------------------
def mat_mul(a, b):
    """Product of two 3×3 matrices (lists of lists)."""
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mat_vec(m, v):
    """3×3 matrix times 3D vector (tuple)."""
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def dot(a, b):
    """Dot product of two 3D vectors."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def normalize(v):
    """Unit vector (returns the zero vector if the length is ~0)."""
    n = math.sqrt(dot(v, v))
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def view_matrix(rx, ry, rz):
    """World -> view matrix; the angles are in degrees.

    It is composed as Rz·Rx·Ry: first rotate about the solid's axis (Y), then tilt
    forward/backward (X) and finally roll (Z). With rot_y on a 360° sweep it is barely noticeable."""
    a, b, g = math.radians(rx), math.radians(ry), math.radians(rz)
    ca, sa = math.cos(a), math.sin(a)
    cb, sb = math.cos(b), math.sin(b)
    cg, sg = math.cos(g), math.sin(g)
    rx_m = [[1, 0, 0], [0, ca, -sa], [0, sa, ca]]
    ry_m = [[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]]
    rz_m = [[cg, -sg, 0], [sg, cg, 0], [0, 0, 1]]
    return mat_mul(rz_m, mat_mul(rx_m, ry_m))


def fmt(v):
    """Number -> compact text for SVG: 2 decimals, no trailing zeros and no "-0"."""
    s = "%.2f" % v
    if s in ("-0.00", "0.00"):
        return "0"
    return s.rstrip("0").rstrip(".")


# --------------------------------------------------------------------------
# Profile: curve flattening
# --------------------------------------------------------------------------
def _is_straight(p0, p1, p2, p3, tol=1e-6):
    """True if the cubic p0..p3 is (almost) a straight segment: its control points lie on the
    chord. Straight segments are not subdivided (a single band)."""

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    d = (p3[0] - p0[0], p3[1] - p0[1])
    length = math.hypot(*d)
    if length < 1e-12:
        return math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < tol and math.hypot(p2[0] - p0[0], p2[1] - p0[1]) < tol
    d1 = (p1[0] - p0[0], p1[1] - p0[1])
    d2 = (p2[0] - p0[0], p2[1] - p0[1])
    return abs(cross(d, d1)) / length < tol * 10 and abs(cross(d, d2)) / length < tol * 10


def _cubic(p0, p1, p2, p3, t):
    """Point of the cubic Bézier p0..p3 at parameter t (0..1)."""
    u = 1.0 - t
    return (
        u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
    )


def _turning_deg(p0, p1, p2, p3):
    """Total turning (degrees) of a cubic's control polygon: measures how much it curves."""
    pts = [p0, p1, p2, p3]
    vecs = []
    for a, b in zip(pts, pts[1:]):
        v = (b[0] - a[0], b[1] - a[1])
        if math.hypot(*v) > 1e-9:
            vecs.append(v)
    total = 0.0
    for u, v in zip(vecs, vecs[1:]):
        ang = math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])
        total += abs(ang)
    return math.degrees(total)


def flatten_profile(path, detail, step_deg=5.0):
    """Flattens the profile into polylines: returns [(points, closed), ...], one per subpath, in
    SVG coordinates. Each segment between two consecutive points will end up being ONE band of the solid.

    path:     inkex Path of the profile (with its transform already applied).
    detail:   cap on the number of bands per curve (parameter profile_detail).
    step_deg: maximum angle the curve's direction may turn between one band and the next
              (parameter band_step). Each curve uses as many bands as needed to meet it
              (capped at `detail`, minimum 2): gentle curves produce few bands and strongly
              curved ones more, instead of a fixed number for all of them.
    A subpath is "closed" if its last point coincides with the first (the duplicate is removed)."""
    result = []
    for sub in path.to_superpath():
        if len(sub) < 2:
            continue
        pts = [tuple(sub[0][1])]
        for k in range(len(sub) - 1):
            p0, p1 = tuple(sub[k][1]), tuple(sub[k][2])
            p2, p3 = tuple(sub[k + 1][0]), tuple(sub[k + 1][1])
            if _is_straight(p0, p1, p2, p3):
                pts.append(p3)
            else:
                n = int(math.ceil(_turning_deg(p0, p1, p2, p3) / max(0.5, step_deg)))
                n = max(2, min(detail, n))
                for i in range(1, n + 1):
                    pts.append(_cubic(p0, p1, p2, p3, i / float(n)))
        # remove consecutive duplicates
        clean = [pts[0]]
        for p in pts[1:]:
            if math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-9:
                clean.append(p)
        closed = False
        if len(clean) > 2 and math.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) < 1e-6:
            clean.pop()
            closed = True
        if len(clean) >= 2:
            result.append((clean, closed))
    return result


# --------------------------------------------------------------------------
# Smooth curves (Catmull-Rom -> cubic Bézier)
# --------------------------------------------------------------------------
def spline_cmds(pts, closed=False):
    """'C ...' commands that run through pts[0] -> pts[-1] (or the whole loop if closed).

    Converts a polyline into a smooth curve (Catmull-Rom -> cubic Bézier; the control points
    are at 1/6 of the chord between neighbors). This way a ring of few points looks round without
    having to sample hundreds. It does not include the initial 'M'; the caller writes it."""
    n = len(pts)
    out = []
    if n < 2:
        return out
    count = n if closed else n - 1
    for i in range(count):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        if closed:
            p0 = pts[(i - 1) % n]
            p3 = pts[(i + 2) % n]
        else:
            p0 = pts[i - 1] if i > 0 else p1
            p3 = pts[i + 2] if i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        out.append("C %s %s %s %s %s %s" % (fmt(c1[0]), fmt(c1[1]), fmt(c2[0]), fmt(c2[1]), fmt(p2[0]), fmt(p2[1])))
    return out


def pt(p):
    """Point (x, y) as the text "x y" for a path command."""
    return "%s %s" % (fmt(p[0]), fmt(p[1]))


# --------------------------------------------------------------------------
# Revolve engine
# --------------------------------------------------------------------------
class RevolveEngine(object):
    """Converts a profile (SVG coordinates) into a list of vector faces.

    Usage: engine = RevolveEngine(params, path, rgb); items, gradients = engine.build(group_id).
    It does not touch the document: it only computes. Writing the result into the SVG is up to Revolve3D.apply.

    Pieces of the drawing:
      * band -> one segment of the revolved profile (cylinder/cone/ring); this is what carries a gradient;
      * cap  -> flat disc or sector at an open end of the profile (parameter cap);
      * cut  -> flat face at each end of a partial sweep (sweep < 360°).
    """

    def __init__(self, params, profile_path, base_rgb):
        """params: dict with the keys of DEFAULTS. profile_path: inkex Path of the profile with its
        transform already applied. base_rgb: base color (r, g, b) 0-255 of the solid."""
        self.p = params
        self.base = base_rgb
        self.M = view_matrix(params["rot_x"], params["rot_y"], params["rot_z"])  # world -> view
        self.persp = max(0.0, min(1.0, params["perspective"] / 100.0))  # 0 = orthographic, 1 = maximum
        self.sgn = 1.0 if params["axis_side"] == "left" else -1.0  # +1: axis at the left edge of the profile
        self.sweep = math.radians(max(0.5, min(360.0, params["sweep"])))
        self.full = params["sweep"] >= 359.999  # full turn: the bands form closed rings
        self.theta0 = math.radians(params["start_angle"])
        self.seg = max(6, int(params["angular_segments"]))
        self.shade_on = params["shading"] != "none"

        self.subpaths = flatten_profile(
            profile_path, max(2, int(params["profile_detail"])), float(params["band_step"])
        )
        if not self.subpaths:
            raise inkex.AbortExtension(_("The profile does not have enough segments."))

        xs = [q[0] for sp, _ in self.subpaths for q in sp]
        ys = [q[1] for sp, _ in self.subpaths for q in sp]
        left, right = min(xs), max(xs)
        offset = params["axis_offset"]
        if self.sgn > 0:
            self.axis_x = left - offset
        else:
            self.axis_x = right + offset
        self.pivot_y = 0.5 * (min(ys) + max(ys))
        max_r = max(abs(self.sgn * (x - self.axis_x)) for x in xs)
        half_h = 0.5 * (max(ys) - min(ys))
        self.model_size = max(2.0 * max_r, 2.0 * half_h, 1.0)
        # Camera distance to the center; None = orthographic projection. The object always fits in a sphere
        # of radius `bound` around its center (the pivot on the axis), so a camera at distance D = bound·M/(M−1)
        # magnifies the very nearest possible point by exactly M (D/(D−bound) = M) and never gets inside the
        # object. That distance is the 100 % setting; other values scale it as 1/perspective, so the
        # perceived strength grows linearly with the slider.
        bound = max(math.hypot(max_r, half_h), 0.5)
        m = PERSPECTIVE_MAX_MAGNIFICATION
        self.cam_dist = bound * m / (m - 1.0) / self.persp if self.persp > 1e-6 else None

        az, el = math.radians(params["light_az"]), math.radians(params["light_el"])
        # UNIT direction toward the light, in view space (azimuth 0 = frontal light)
        self.light = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
        # Blinn-Phong half vector (light + direction to the camera, which in orthographic is +z)
        half = normalize((self.light[0], self.light[1], self.light[2] + 1.0))
        self.half = half
        self.ambient = max(0.0, min(1.0, params["ambient"] / 100.0))
        self.spec_k = max(0.0, min(1.0, params["highlight"] / 100.0))

        # profile in (r, h): h upward, centered on the pivot
        self.profiles = []
        for pts, closed in self.subpaths:
            q = [(self.sgn * (x - self.axis_x), -(y - self.pivot_y)) for x, y in pts]
            self.profiles.append((q, closed))

        # Are back faces discarded? Only in "Solid" mode and when something closes the
        # volume (closed profile or caps); with an open surface without caps the interior must be visible.
        closed_any = any(c for _, c in self.profiles)
        self.cull = params["sides"] == "auto" and (closed_any or params["cap"])

        self.items = []  # faces: (mean_z, d attribute, style, heights|None, angles|None); build() sorts them by z
        self.planes = []  # flat faces (caps, cuts): (kind, face, value, sign, front_facing); build() repositions them
        self._split_at = []  # extra angles at which to split the bands (antipodes of the cuts)
        self.gradients = []  # LinearGradient elements used by the faces
        self._gid = 0  # counter for the gradient ids

    # -- transformations ------------------------------------------------
    def world(self, r, h, theta):
        """Profile point (distance to the axis r, height h) rotated by an angle theta -> world coordinates."""
        return (self.sgn * r * math.cos(theta), h, r * math.sin(theta))

    def to_view(self, w):
        """World -> view (the dialog's rotations)."""
        return mat_vec(self.M, w)

    def screen(self, v):
        """Point in view space -> SVG coordinates (x, y). With perspective it scales x and y by d/(d − z);
        the denominator is clamped so as not to divide by ~0 if something ended up behind the camera."""
        x, y, z = v
        if self.cam_dist:
            k = self.cam_dist / max(self.cam_dist - z, self.cam_dist * 0.05)
            x, y = x * k, y * k
        return (self.axis_x + x, self.pivot_y - y)

    def ring_point(self, r, h, theta):
        """Point (r, h, theta) already projected: returns (screen (x, y), view z)."""
        v = self.to_view(self.world(r, h, theta))
        return self.screen(v), v[2]

    def view_vec(self, v):
        """Vector toward the camera from a point in view space."""
        if self.cam_dist:
            return (-v[0], -v[1], self.cam_dist - v[2])
        return (0.0, 0.0, 1.0)

    # -- lighting -------------------------------------------------------
    def shade(self, nview):
        """Color (r, g, b) 0-255 of a surface whose normal `nview` is in view space.

        Model: ambient + diffuse (Lambert) + specular (Blinn-Phong, exponent 24). With shading
        disabled it returns the base color as is."""
        n = normalize(nview)
        if not self.shade_on:
            return tuple(int(round(c)) for c in self.base)
        diff = max(0.0, dot(n, self.light))
        inten = self.ambient + (1.0 - self.ambient) * diff
        col = [c * inten for c in self.base]
        if self.spec_k > 0:
            s = max(0.0, dot(n, self.half)) ** 24 * self.spec_k
            col = [c + (255.0 - c) * s for c in col]
        return tuple(max(0, min(255, int(round(c)))) for c in col)

    @staticmethod
    def hexcol(c):
        """(r, g, b) 0-255 -> "#rrggbb"."""
        return "#%02x%02x%02x" % c

    # -- gradients --------------------------------------------------------
    def add_gradient(self, stops, p1, p2):
        """Creates a LinearGradient (userSpaceOnUse) between points p1 and p2 with the stops
        [(offset 0..1, (r, g, b)), ...] and registers it in self.gradients. Returns its id, which is the
        group id + "-g<n>" (that prefix is what allows cleaning up orphans later)."""
        self._gid += 1
        gid = "%s-g%d" % (self.prefix, self._gid)
        grad = LinearGradient()
        grad.set("id", gid)
        grad.set("gradientUnits", "userSpaceOnUse")
        grad.set("x1", fmt(p1[0]))
        grad.set("y1", fmt(p1[1]))
        grad.set("x2", fmt(p2[0]))
        grad.set("y2", fmt(p2[1]))
        last = 0.0
        for off, col in stops:
            off = max(last, min(1.0, off))
            last = off
            st = Stop()
            st.set("offset", fmt(off) if off not in (0.0, 1.0) else str(int(off)))
            st.set("style", "stop-color:%s;stop-opacity:1" % self.hexcol(col))
            grad.append(st)
        self.gradients.append(grad)
        return gid

    def face_style(self, paint, evenodd=False):
        """Style of a face. The thin seam stroke uses EXACTLY the same paint as the
        fill (the same gradient), so its color matches the band's at every point and it is
        not noticeable. A flat color does not match the gradient and leaves a visible line.
        The width (seam_width) is in document pixels; 0 disables the stroke."""
        stroke = ";stroke:none"
        width = float(self.p["seam_width"])
        if self.p["seam_fix"] and width > 0:
            stroke = ";stroke:%s;stroke-width:%s;stroke-linejoin:round" % (paint, fmt(width))
        return "fill:%s;fill-rule:%s%s" % (paint, "evenodd" if evenodd else "nonzero", stroke)

    @staticmethod
    def simplify_stops(stops, tol=1.6):
        """Removes the stops that a linear gradient already reproduces by interpolation (error <= tol levels)."""
        keep = list(stops)
        changed = True
        while changed and len(keep) > 2:
            changed = False
            for i in range(1, len(keep) - 1):
                (o0, c0), (o1, c1), (o2, c2) = keep[i - 1], keep[i], keep[i + 1]
                span = o2 - o0
                k = 0.0 if span < 1e-9 else (o1 - o0) / span
                err = max(abs(c1[j] - (c0[j] + (c2[j] - c0[j]) * k)) for j in range(3))
                if err <= tol:
                    del keep[i]
                    changed = True
                    break
        return keep

    # -- visibility ---------------------------------------------------------
    def _facing(self, rm, hm, nr, nh, theta):
        """Product (normal · vector toward the camera) at the point (rm, hm, theta) of a band whose
        normal in the profile is (nr, nh). Positive = that part of the surface faces the viewer."""
        w = self.world(rm, hm, theta)
        v = self.to_view(w)
        n3 = (self.sgn * nr * math.cos(theta), nh, nr * math.sin(theta))
        nv = mat_vec(self.M, n3)
        return dot(nv, self.view_vec(v))

    def _runs(self, rm, hm, nr, nh):
        """Splits the sweep of a band into front / back arcs.

        Looks for the sign changes of _facing and refines each cut by bisection. Returns
        [(theta_a, theta_b, front_facing, is_full_ring)]. "Full ring" = a 360° turn with
        no visibility change: it is drawn as a closed loop (with a hole if there is an inner radius)."""
        th0, sw = self.theta0, self.sweep
        n = max(self.seg * 4, 96)

        def f(t):
            return self._facing(rm, hm, nr, nh, t) > 0.0

        def refine(a, b):
            fa = f(a)
            for _ in range(28):
                m = 0.5 * (a + b)
                if f(m) == fa:
                    a = m
                else:
                    b = m
            return 0.5 * (a + b)

        step = sw / n
        thetas = [th0 + step * j for j in range(n + 1)]
        vals = [f(t) for t in thetas]
        runs = []
        if self.full:
            cuts = []
            for j in range(n):
                if vals[j] != vals[(j + 1) % n]:
                    cuts.append(refine(thetas[j], thetas[j] + step))
            if not cuts:
                runs.append((th0, th0 + TAU, vals[0], True))
            else:
                for i in range(len(cuts)):
                    a = cuts[i]
                    b = cuts[i + 1] if i + 1 < len(cuts) else cuts[0] + TAU
                    runs.append((a, b, f(0.5 * (a + b)), False))
        else:
            cuts = []
            for j in range(n):
                if vals[j] != vals[j + 1]:
                    cuts.append(refine(thetas[j], thetas[j + 1]))
            edges = [th0] + cuts + [th0 + sw]
            for i in range(len(edges) - 1):
                a, b = edges[i], edges[i + 1]
                if b - a > 1e-6:
                    runs.append((a, b, f(0.5 * (a + b)), False))
        return runs

    # -- face generation -------------------------------------------------
    def build(self, prefix):
        """Generates all faces and gradients. `prefix` is the group id (it names the gradients).
        Returns (items, gradients) with items = [(z, d, style)] sorted from back to front
        (lowest z first = painter's algorithm)."""
        self.prefix = prefix
        for q, closed in self.profiles:
            self._build_profile(q, closed)
        self.items.sort(key=lambda it: it[0])
        for plane in self.planes:
            self._place_plane(plane)
        return [(z, d, style) for z, d, style, _hr, _ar in self.items], self.gradients

    def _place_plane(self, plane):
        """Repositions a flat face (cap or cut face) relative to the others using ITS PLANE, not the mean z:
        a large disc or sector has a mean z that says little. Whatever lies on the opposite side of the
        plane from the viewer is hidden by the flat face (goes BEFORE it); whatever lies on the
        viewer's side hides it (goes AFTER it). Whatever crosses the plane, is coplanar or has no data
        keeps its z order.

        Each face carries `hr` = (h_min, h_max) and `ar` = (angle_a, angle_b) (None if not applicable).
        Faces of revolution have the same height over the whole sweep, so comparing with the
        horizontal plane y = h (caps) is exact; for the vertical plane of a cut at angle θc the side of a
        point at angle t is the sign of sin(t − θc), so classifying the angular range is enough."""
        kind, item, value, sign, front = plane
        eps = 1e-6

        if kind == "y":
            h = value
            viewer = sign if front else -sign  # +1: the viewer is upward (larger y)

            def far_side(it):
                hr = it[3]
                if hr is None:
                    return None
                below = hr[1] <= h + eps  # the whole face is below the plane
                above = hr[0] >= h - eps
                if below == above:  # crosses the plane, or is coplanar with it
                    return None
                return below if viewer > 0 else above

        else:
            theta_c = value
            viewer = sign if front else -sign  # sign of sin(t − θc) on the viewer's side

            def far_side(it):
                ar = it[4]
                if ar is None:
                    return None
                u = (ar[0] - theta_c) % TAU
                if u > TAU - eps:
                    u = 0.0
                w = ar[1] - ar[0]
                if w < eps:  # face at a single angle (another cut): u = 0 or π is coplanar
                    if u < eps or abs(u - math.pi) < eps:
                        return None
                    s_item = 1.0 if u < math.pi else -1.0
                elif u + w <= math.pi + eps:
                    s_item = 1.0
                elif u >= math.pi - eps and u + w <= TAU + eps:
                    s_item = -1.0
                else:  # crosses the plane
                    return None
                return s_item != viewer

        rest = [it for it in self.items if it is not item]
        side = [far_side(it) for it in rest]
        last_far = max([i for i, v in enumerate(side) if v is True], default=-1)
        head = [it for i, it in enumerate(rest[: last_far + 1]) if side[i] is not False]
        moved = [it for i, it in enumerate(rest[: last_far + 1]) if side[i] is False]
        self.items = head + [item] + moved + rest[last_far + 1 :]

    def _orientation(self, q, closed):
        """+1 / −1 depending on the winding direction of the profile polygon (if open, it is closed against
        the axis). Decides which side the band normals point to (outward from the solid)."""
        poly = list(q)
        if not closed:
            poly = poly + [(0.0, q[-1][1]), (0.0, q[0][1])]
        area = 0.0
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            area += x1 * y2 - x2 * y1
        return 1.0 if area >= 0 else -1.0

    def _build_profile(self, q, closed):
        """All the faces of a subpath: one band per segment, plus caps at the open ends
        (if cap) and cut faces when the sweep is partial."""
        s = self._orientation(q, closed)
        n = len(q)
        count = n if closed else n - 1
        # With cut faces and a sweep of more than half a turn, the bands are split at the angles
        # opposite to each cut (θ0 + π and θend − π): this way each piece falls entirely on one side of the
        # cut's plane and _place_plane can order it exactly. With a sweep <= 180° it is not needed.
        self._split_at = []
        if (not self.full) and (closed or self.p["cap"]) and self.sweep > math.pi + 1e-6:
            self._split_at = [self.theta0 + math.pi, self.theta0 + self.sweep - math.pi]
        for k in range(count):
            r0, h0 = q[k]
            r1, h1 = q[(k + 1) % n]
            tr, th = r1 - r0, h1 - h0
            tl = math.hypot(tr, th)
            if tl < 1e-9:
                continue
            tr, th = tr / tl, th / tl
            nr, nh = (th, -tr) if s > 0 else (-th, tr)
            self._build_band(r0, h0, r1, h1, nr, nh)

        if self.p["cap"] and not closed:
            for end, (r, h), nh in ((0, q[0], -s), (1, q[-1], s)):
                if r > 1e-6:
                    self._build_cap(r, h, nh)
        if (not self.full) and (closed or self.p["cap"]):
            self._build_cuts(q, closed)

    def _build_band(self, r0, h0, r1, h1, nr, nh):
        """A band = the segment (r0,h0)->(r1,h1) of the revolved profile. (nr, nh) is its normal in the profile.
        The sweep is split into visible arcs
        (_runs) and, with shading, into arcs where the gradient is monotonic (_split_monotonic).
        Back-facing arcs are discarded if self.cull."""
        rm, hm = 0.5 * (r0 + r1), 0.5 * (h0 + h1)
        runs = self._runs(rm, hm, nr, nh)
        if self.shade_on:
            runs = self._split_monotonic(runs, rm, hm)
        if self._split_at:
            runs = self._split_runs(runs, self._split_at)
        for a, b, front, ring in runs:
            if self.cull and not front:
                continue
            self._emit_band_run(r0, h0, r1, h1, rm, hm, nr, nh, a, b, front, ring)

    @staticmethod
    def _split_runs(runs, angles):
        """Splits the arcs (a, b, front, ring) at the given angles (only those that fall inside each arc)."""
        out = []
        for a, b, front, ring in runs:
            inner = sorted(a + (c - a) % TAU for c in angles if 1e-6 < (c - a) % TAU < (b - a) - 1e-6)
            edges = [a] + inner + [b]
            for i in range(len(edges) - 1):
                if edges[i + 1] - edges[i] > 1e-6:
                    out.append((edges[i], edges[i + 1], front, ring))
        return out

    def _arc_points(self, r, h, a, b, ring):
        """Projected points of the circle of radius r at height h between theta=a and theta=b.
        Returns (screen_points, view_z). With ring=True it is a closed loop and does NOT repeat the
        first point at the end."""
        span = b - a
        k = max(3, int(math.ceil(span / TAU * self.seg)) + 1)
        if ring:
            k = max(k, self.seg)
        pts, zs = [], []
        count = k if ring else k + 1
        for i in range(count):
            t = a + span * i / float(k)
            p, z = self.ring_point(r, h, t)
            pts.append(p)
            zs.append(z)
        return pts, zs

    def _emit_band_run(self, r0, h0, r1, h1, rm, hm, nr, nh, a, b, front, ring):
        """Creates the face for ONE arc of a band and adds it to self.items as (mean_z, d, style, (h_min, h_max), (a, b)).

        Outline: upper arc going out + lower arc coming back, both with smooth curves. A full
        ring is two loops with fill-rule evenodd (leaves the central hole). Fill: the band's
        own gradient, or flat color if shading is disabled."""
        top, z_top = self._arc_points(r0, h0, a, b, ring)
        bot, z_bot = self._arc_points(r1, h1, a, b, ring)
        depth = (sum(z_top) + sum(z_bot)) / float(len(z_top) + len(z_bot))

        if ring:
            d = "M %s %s Z" % (pt(top[0]), " ".join(spline_cmds(top, True)))
            rev = list(reversed(bot))
            if max(abs(p[0] - bot[0][0]) + abs(p[1] - bot[0][1]) for p in bot) > 1e-6:
                d += " M %s %s Z" % (pt(rev[0]), " ".join(spline_cmds(rev, True)))
        else:
            rev = list(reversed(bot))
            d = "M %s %s L %s %s Z" % (
                pt(top[0]),
                " ".join(spline_cmds(top)),
                pt(rev[0]),
                " ".join(spline_cmds(rev)),
            )

        # --- fill ---
        allpts = top + bot
        if not self.shade_on:
            paint = self.hexcol(tuple(int(round(c)) for c in self.base))
        else:
            paint = "url(#%s)" % self._band_gradient(rm, hm, nr, nh, a, b, front, allpts, ring)
        self.items.append((depth, d, self.face_style(paint, evenodd=ring), (min(h0, h1), max(h0, h1)), (a, b)))

    def _grad_frame(self, hm):
        """Gradient direction (perpendicular to the projected axis) and center of the ring."""
        ax = self.to_view((0.0, 1.0, 0.0))
        ax2 = (ax[0], -ax[1])  # to SVG coordinates
        if math.hypot(*ax2) < 1e-4:
            d = (1.0, 0.0)
        else:
            L = math.hypot(*ax2)
            d = (-ax2[1] / L, ax2[0] / L)
        cc = self.screen(self.to_view((0.0, hm, 0.0)))
        return d, cc

    def _split_monotonic(self, runs, rm, hm):
        """Splits each arc where the position along the gradient changes direction,
        so that a linear gradient represents the lighting well (especially on full rings)."""
        d, cc = self._grad_frame(hm)

        def t(theta):
            p, _ = self.ring_point(rm, hm, theta)
            return d[0] * (p[0] - cc[0]) + d[1] * (p[1] - cc[1])

        n = 180
        samples = [(t(TAU * i / n), TAU * i / n) for i in range(n)]
        cuts = [max(samples)[1], min(samples)[1]]
        out = []
        for a, b, front, ring in runs:
            span = b - a
            inner = []
            for c in cuts:
                x = (c - a) % TAU
                if 1e-6 < x < span - 1e-6:
                    inner.append(a + x)
            edges = [a] + sorted(inner) + [b]
            for i in range(len(edges) - 1):
                if edges[i + 1] - edges[i] > 1e-6:
                    out.append((edges[i], edges[i + 1], front, False))
        return out

    def _band_gradient(self, rm, hm, nr, nh, a, b, front, allpts, ring):
        """Linear gradient for the face of one arc; returns its id.

        The gradient axis is perpendicular to the solid's projected axis (_grad_frame). The normal is
        sampled along the arc, the color is computed with shade(), sorted by position along
        the gradient axis, normalized to offsets 0..1 and simplified (simplify_stops). The number
        of samples and the tolerance come from GRAD_QUALITY. If the arc is back-facing (not front) the
        normal is flipped: what is seen is the interior of the surface."""
        d, cc = self._grad_frame(hm)
        ts = [d[0] * (p[0] - cc[0]) + d[1] * (p[1] - cc[1]) for p in allpts]
        tmin, tmax = min(ts), max(ts)
        if tmax - tmin < 1e-6:
            tmax = tmin + 1e-6
        samples = GRAD_QUALITY.get(self.p["grad_quality"], GRAD_QUALITY["normal"])[0]
        raw = []
        for i in range(samples):
            t = a + (b - a) * i / float(samples - 1)
            if ring:
                t = a + (b - a) * i / float(samples)
            p, _ = self.ring_point(rm, hm, t)
            tt = d[0] * (p[0] - cc[0]) + d[1] * (p[1] - cc[1])
            n3 = (self.sgn * nr * math.cos(t), nh, nr * math.sin(t))
            nv = mat_vec(self.M, n3)
            if not front:
                nv = (-nv[0], -nv[1], -nv[2])
            raw.append((tt, self.shade(nv)))
        raw.sort(key=lambda x: x[0])
        stops = [((tt - tmin) / (tmax - tmin), col) for tt, col in raw]
        if stops[0][0] > 0.0:
            stops.insert(0, (0.0, stops[0][1]))
        if stops[-1][0] < 1.0:
            stops.append((1.0, stops[-1][1]))
        stops = self.simplify_stops(stops, GRAD_QUALITY.get(self.p["grad_quality"], GRAD_QUALITY["normal"])[1])
        p1 = (cc[0] + d[0] * tmin, cc[1] + d[1] * tmin)
        p2 = (cc[0] + d[0] * tmax, cc[1] + d[1] * tmax)
        return self.add_gradient(stops, p1, p2)

    def _build_cap(self, r, h, nh):
        """Flat cap (disc, or sector if the sweep is partial) of radius r at height h, with a flat color
        based on its normal. nh = +1 / −1: facing up or down."""
        center_v = self.to_view((0.0, h, 0.0))
        n3 = (0.0, nh, 0.0)
        nv = mat_vec(self.M, n3)
        front = dot(nv, self.view_vec(center_v)) > 0
        if self.cull and not front:
            return
        if not front:
            nv = (-nv[0], -nv[1], -nv[2])
        col = self.shade(nv)
        a, b = self.theta0, self.theta0 + self.sweep
        pts, _ = self._arc_points(r, h, a, b, self.full)
        if self.full:
            d = "M %s %s Z" % (pt(pts[0]), " ".join(spline_cmds(pts, True)))
        else:
            c = self.screen(center_v)
            d = "M %s L %s %s L %s Z" % (pt(c), pt(pts[0]), " ".join(spline_cmds(pts)), pt(c))
        paint = self.hexcol(col)
        item = (center_v[2], d, self.face_style(paint), (h, h), None if self.full else (a, b))
        self.items.append(item)
        self.planes.append(("y", item, h, nh, front))

    def _build_cuts(self, q, closed):
        """Flat faces at both ends of a partial sweep: the profile section (closed against
        the axis if the profile is open) at theta = start_angle and at start_angle + sweep."""
        poly = list(q)
        if not closed:
            poly = poly + [(0.0, q[-1][1]), (0.0, q[0][1])]
        for theta, sign in ((self.theta0, -1.0), (self.theta0 + self.sweep, 1.0)):
            tang = (-self.sgn * math.sin(theta), 0.0, math.cos(theta))
            n3 = (sign * tang[0], 0.0, sign * tang[2])
            nv = mat_vec(self.M, n3)
            pts, zs = [], []
            for r, h in poly:
                p, z = self.ring_point(r, h, theta)
                pts.append(p)
                zs.append(z)
            center_v = self.to_view(self.world(sum(r for r, _ in poly) / len(poly), sum(h for _, h in poly) / len(poly), theta))
            front = dot(nv, self.view_vec(center_v)) > 0
            if self.cull and not front:
                continue
            if not front:
                nv = (-nv[0], -nv[1], -nv[2])
            d = "M %s %s Z" % (pt(pts[0]), " ".join("L " + pt(p) for p in pts[1:]))
            item = (
                sum(zs) / len(zs),
                d,
                self.face_style(self.hexcol(self.shade(nv))),
                (min(h for _, h in poly), max(h for _, h in poly)),
                (theta, theta),
            )
            self.items.append(item)
            self.planes.append(("t", item, theta, sign, front))


# --------------------------------------------------------------------------
# Extension
# --------------------------------------------------------------------------
class Revolve3D(inkex.EffectExtension):
    """The inkex part: handles selection, group, stored parameters and writing to the SVG.
    The geometry lives in RevolveEngine."""

    def add_arguments(self, pars):
        """One argument per <param> of the .inx (same name). The default values come from DEFAULTS.
        --tab is sent by the .inx notebook and is not used."""
        pars.add_argument("--tab", type=str, default="")
        pars.add_argument("--action", type=str, default="apply")
        pars.add_argument("--axis_side", type=str, default=DEFAULTS["axis_side"])
        pars.add_argument("--axis_offset", type=float, default=DEFAULTS["axis_offset"])
        pars.add_argument("--sweep", type=float, default=DEFAULTS["sweep"])
        pars.add_argument("--start_angle", type=float, default=DEFAULTS["start_angle"])
        pars.add_argument("--rot_x", type=float, default=DEFAULTS["rot_x"])
        pars.add_argument("--rot_y", type=float, default=DEFAULTS["rot_y"])
        pars.add_argument("--rot_z", type=float, default=DEFAULTS["rot_z"])
        pars.add_argument("--perspective", type=float, default=DEFAULTS["perspective"])
        pars.add_argument("--shading", type=str, default=DEFAULTS["shading"])
        pars.add_argument("--light_az", type=float, default=DEFAULTS["light_az"])
        pars.add_argument("--light_el", type=float, default=DEFAULTS["light_el"])
        pars.add_argument("--ambient", type=float, default=DEFAULTS["ambient"])
        pars.add_argument("--highlight", type=float, default=DEFAULTS["highlight"])
        pars.add_argument("--cap", type=inkex.utils.Boolean, default=DEFAULTS["cap"])
        pars.add_argument("--sides", type=str, default=DEFAULTS["sides"])
        pars.add_argument("--profile_detail", type=int, default=DEFAULTS["profile_detail"])
        pars.add_argument("--band_step", type=float, default=DEFAULTS["band_step"])
        pars.add_argument("--angular_segments", type=int, default=DEFAULTS["angular_segments"])
        pars.add_argument("--seam_fix", type=inkex.utils.Boolean, default=DEFAULTS["seam_fix"])
        pars.add_argument("--seam_width", type=float, default=DEFAULTS["seam_width"])
        pars.add_argument("--grad_quality", type=str, default=DEFAULTS["grad_quality"])
        pars.add_argument("--force_color", type=inkex.utils.Boolean, default=DEFAULTS["force_color"])
        pars.add_argument("--fallback_fill", type=Color, default=Color(DEFAULTS["fallback_fill"]))

    # -- utilities ----------------------------------------------------------
    def dialog_params(self):
        """Current dialog values as a dict with the keys of DEFAULTS (the color as "#rrggbb")."""
        p = {}
        for key, default in DEFAULTS.items():
            val = getattr(self.options, key)
            if key == "fallback_fill":
                val = str(Color(val).to_rgb())
            p[key] = val
        return p

    @staticmethod
    def revolve_group_of(node):
        """Walks up the ancestors looking for a revolve group."""
        cur = node
        while cur is not None and isinstance(cur, inkex.BaseElement):
            if cur.get(ATTR_PARAMS) is not None:
                return cur
            cur = cur.getparent()
        return None

    @staticmethod
    def profile_of(group):
        """Child of the group marked as the original profile (or None if absent)."""
        for child in group:
            if child.get(ATTR_ROLE) == ROLE_PROFILE:
                return child
        return None

    @staticmethod
    def saved_params(node):
        """Parameters left by "Remove effect" on a path (None if it has none)."""
        raw = node.get(ATTR_SAVED)
        if raw is None:
            return None
        try:
            return dict(json.loads(raw).get("params", {}))
        except (ValueError, TypeError, AttributeError):
            return None

    @staticmethod
    def stored_params(group):
        """Parameters stored in a revolve group (empty dict if the JSON is not valid)."""
        try:
            data = json.loads(group.get(ATTR_PARAMS))
            return dict(data.get("params", {}))
        except (ValueError, TypeError):
            return {}

    @staticmethod
    def base_rgb(profile, fallback, force=False):
        """Base color of the solid: the profile's fill, or the dialog's color if the profile
        has no usable fill or if forcing it was requested."""
        if not force:
            try:
                fill = profile.style.get("fill")
                if fill and fill != "none" and not fill.startswith("url"):
                    return tuple(int(c) for c in list(Color(fill).to_rgb()))
            except Exception:
                pass
        try:
            return tuple(int(c) for c in list(Color(fallback).to_rgb()))
        except Exception:
            return (79, 157, 166)

    # -- main flow ------------------------------------------------------
    def effect(self):
        """Entry point. Resolves each selected object to its revolve group (if any;
        a child counts as its group) without repeating groups, and runs the chosen action on each one."""
        action = self.options.action
        if action == "show":  # read-only: prints the stored values, changes nothing
            self.show_values()
            return
        if action in ("transfer_first", "transfer_last"):  # overrides everything else and is silent
            self.transfer(action)
            return
        targets = []
        seen = set()
        for node in self.svg.selection:
            grp = self.revolve_group_of(node)
            key = grp if grp is not None else node
            if id(key) in seen:
                continue
            seen.add(id(key))
            targets.append((grp, node))
        if not targets:
            raise inkex.AbortExtension(_("Select a path (the profile) or a revolve group."))

        done = 0
        for grp, node in targets:
            if action == "restore":  # "Remove effect": only makes sense on a group
                if grp is None:
                    continue
                self.restore(grp)
                done += 1
            elif action == "reapply":  # "Restore effect": the saved parameters take precedence over the dialog
                params = dict(self.dialog_params())
                if grp is None:
                    saved = self.saved_params(node)
                    if saved is None:
                        inkex.errormsg(
                            _("\"Restore effect\" needs a revolve group or a path whose effect was removed.")
                        )
                        continue
                    params.update(saved)
                else:
                    params.update(self.stored_params(grp))
                self.apply(grp, node, params)
                done += 1
            else:  # "Apply/update": creates the group if needed and uses the dialog values
                self.apply(grp, node, self.dialog_params())
                done += 1
        if done == 0:
            raise inkex.AbortExtension(_("There was nothing to process with the chosen action."))

    def show_values(self):
        """"Show values": prints, as one clear message (translated like the dialog), the parameters stored
        in each selected revolve group or in each path whose effect was removed. Never modifies anything
        (inkex emits no document, so Inkscape keeps it as is)."""
        on, off = _("on"), _("off")
        names = {
            "left": _("Left of profile"), "right": _("Right of profile"),
            "auto": _("Solid (hide back faces)"), "both": _("Both sides (for open surfaces)"),
            "smooth": _("Smooth (gradients)"), "none": _("No shading"),
            "low": _("Few"), "normal": _("Normal"), "high": _("Many"),
        }
        # (section, [(label, key, kind)]); kind: n = number, b = on/off, o = option, c = color
        sections = [
            (_("Geometry"), [(_("Axis at profile edge:"), "axis_side", "o"), (_("Axis offset (px):"), "axis_offset", "n"),
                             (_("Revolve angle (°):"), "sweep", "n"), (_("Start angle (°):"), "start_angle", "n"),
                             (_("Caps on open ends"), "cap", "b"), (_("Surface:"), "sides", "o")]),
            (_("View"), [(_("Rotation X (°):"), "rot_x", "n"), (_("Rotation Y (°):"), "rot_y", "n"),
                         (_("Rotation Z (°):"), "rot_z", "n"), (_("Perspective (%):"), "perspective", "n")]),
            (_("Shading"), [(_("Shading:"), "shading", "o"), (_("Light: azimuth (°):"), "light_az", "n"),
                            (_("Light: elevation (°):"), "light_el", "n"), (_("Ambient light (%):"), "ambient", "n"),
                            (_("Specular highlight (%):"), "highlight", "n"), (_("Color:"), "fallback_fill", "c"),
                            (_("Force"), "force_color", "b")]),
            (_("Quality"), [(_("Max bands per curve:"), "profile_detail", "n"), (_("Angle between bands (°):"), "band_step", "n"),
                            (_("Segments per turn:"), "angular_segments", "n"), (_("Gradient stops:"), "grad_quality", "o"),
                            (_("Hide seams (stroke)"), "seam_fix", "b"), (_("Seam width (px):"), "seam_width", "n")]),
        ]
        blocks, seen = [], set()
        for node in self.svg.selection:
            grp = self.revolve_group_of(node)
            key = grp if grp is not None else node
            if id(key) in seen:
                continue
            seen.add(id(key))
            if grp is not None:
                stored, state = self.stored_params(grp), _("effect active (group)")
            else:
                stored, state = self.saved_params(node), _("effect removed (values saved on the path)")
            if not stored:
                continue
            params = dict(DEFAULTS, **stored)
            lines = [_("Object: %s") % key.get_id() + "  [" + state + "]"]
            for title, rows in sections:
                lines.append("")
                lines.append("  " + title.upper())
                for label, k, kind in rows:
                    v = params[k]
                    if kind == "b":
                        txt = on if v else off
                    elif kind == "o":
                        txt = names.get(v, str(v))
                    elif kind == "c":
                        txt = str(v)
                    else:
                        try:
                            txt = "%g" % v
                        except (TypeError, ValueError):
                            txt = str(v)
                    lines.append("    %s %s" % (label.rstrip(":").strip() + ":", txt))
            blocks.append("\n".join(lines))
        if not blocks:
            inkex.errormsg(_("No saved values found. Select a 3D Revolve group, or a path whose effect was removed."))
            return
        rule = "=" * 44
        inkex.errormsg(
            rule + "\n" + _("3D Revolve — saved values") + "\n" + rule + "\n\n" + ("\n\n" + "-" * 44 + "\n\n").join(blocks)
        )

    def transfer(self, action):
        """Transfer from first/last selected: copies the effect parameters of the first/last selected
        object to all the other selected objects (the source stays the same). It is SILENT: no
        messages or errors, and it touches nothing if there are fewer than two objects, if the source
        has no effect or if a target is not usable as a profile (that one is skipped). It ignores the
        remaining dialog parameters. The order is that of self.svg.selection (as delivered by Inkscape)."""
        nodes = list(self.svg.selection)
        if len(nodes) < 2:
            return
        source = self.revolve_group_of(nodes[0] if action == "transfer_first" else nodes[-1])
        if source is None:
            return
        stored = self.stored_params(source)
        if not stored:
            return
        params = dict(DEFAULTS)
        params.update(stored)
        seen = {id(source)}
        for node in nodes:
            grp = self.revolve_group_of(node)
            key = grp if grp is not None else node
            if id(key) in seen:
                continue
            seen.add(id(key))
            try:
                self.apply(grp, node, dict(params))  # validates before touching the document
            except inkex.AbortExtension:
                continue

    def apply(self, group, node, params):
        """Creates (if `group` is None, wrapping `node`) or updates the revolve group: deletes
        everything except the profile, regenerates defs + faces and stores `params` in data-revolve3d.
        Everything that can fail (invalid profile) is checked BEFORE modifying the document."""
        if group is None:
            if not hasattr(node, "path"):
                raise inkex.AbortExtension(_("The selected object is neither a path nor a basic shape."))
            profile = node
        else:
            profile = self.profile_of(group)
            if profile is None:
                raise inkex.AbortExtension(_("The group does not contain the original profile; it cannot be updated."))

        try:
            path = profile.path.transform(profile.transform)
        except Exception:
            raise inkex.AbortExtension(_("The profile must be a path or a shape (rectangle, ellipse, polygon…)."))

        engine = RevolveEngine(params, path, self.base_rgb(profile, params["fallback_fill"], params.get("force_color", False)))
        if group is None:
            group = self.wrap_profile(node)
        gid = group.get_id()
        items, gradients = engine.build(gid)

        # delete the old content (everything except the profile) and regenerate
        for child in list(group):
            if child is not profile:
                group.remove(child)
        self.purge_orphan_gradients(gid)

        if gradients:
            defs = inkex.Defs()
            for g in gradients:
                defs.append(g)
            group.append(defs)
        for _unused, d, style in items:
            el = PathElement()
            el.set("d", d)
            el.set("style", style)
            group.append(el)

        group.set(ATTR_PARAMS, json.dumps({"version": FORMAT_VERSION, "params": params}, separators=(",", ":")))
        group.set(inkex.addNS("label", "inkscape"), _("3D Revolve"))

    def _is_referenced(self, ident):
        """True if any attribute in the document points to #ident (direct href or url(#ident))."""
        token = "#" + ident
        for el in self.svg.iter():
            for val in el.attrib.values():
                if token in val and (val.strip() == token or "url(" + token in val):
                    return True
        return False

    def purge_orphan_gradients(self, gid):
        """If Inkscape moved gradients of this group to the root <defs> (e.g. when editing them),
        they end up outside the group and are not deleted on their own: they are removed here, together
        with the stop vectors they pointed to if nobody else uses them."""
        prefix = gid + "-g"
        removed_hrefs = []
        for el in list(self.svg.iter("{http://www.w3.org/2000/svg}linearGradient")):
            ident = el.get("id") or ""
            if ident.startswith(prefix):
                href = el.get(inkex.addNS("href", "xlink")) or el.get("href")
                if href:
                    removed_hrefs.append(href.lstrip("#"))
                el.getparent().remove(el)
        for ident in removed_hrefs:
            target = self.svg.getElementById(ident)
            if target is not None and not self._is_referenced(ident):
                target.getparent().remove(target)

    def wrap_profile(self, node):
        """Puts `node` in a new group (at the same position in the Z order), marks it as the profile and
        hides it. If it came from "Remove effect", it discards its saved parameters (they move to the group)."""
        if not hasattr(node, "path"):
            raise inkex.AbortExtension(_("The selected object is neither a path nor a basic shape."))
        parent = node.getparent()
        index = list(parent).index(node)
        group = Group()
        parent.insert(index, group)
        group.get_id()
        profile = node  # it is moved into the group
        group.append(profile)
        profile.set(ATTR_ROLE, ROLE_PROFILE)
        if profile.get(ATTR_SAVED) is not None:  # the parameters now live in the group
            del profile.attrib[ATTR_SAVED]
        style = profile.style
        style["display"] = "none"
        profile.style = style
        return group

    def restore(self, group):
        """Implements "Remove effect": replaces the group with its original profile (visible, with the
        group's transform merged in) and leaves the parameters on it in data-revolve3d-saved."""
        profile = self.profile_of(group)
        if profile is None:
            raise inkex.AbortExtension(_("The group does not contain the original profile."))
        gid = group.get_id()
        parent = group.getparent()
        index = list(parent).index(group)
        style = profile.style
        if "display" in style:
            del style["display"]
        profile.style = style
        if profile.get(ATTR_ROLE) is not None:
            del profile.attrib[ATTR_ROLE]
        # the parameters are saved on the original path so they can be applied again
        if group.get(ATTR_PARAMS) is not None:
            profile.set(ATTR_SAVED, group.get(ATTR_PARAMS))
        profile.transform = group.transform @ profile.transform
        parent.remove(group)
        parent.insert(index, profile)
        self.purge_orphan_gradients(gid)


if __name__ == "__main__":
    Revolve3D().run()
