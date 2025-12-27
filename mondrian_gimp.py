#!/usr/bin/env python3
"""
Procedural Mondrian Generator for GIMP 3.0
With watercolor effect faithfully replicated from p5.brush
Based on Tyler Hobbs' watercolor algorithm
"""

import random
import math
import sys
import os
import traceback
import json

LOG_FILE = os.path.expanduser("~/mondrian.log")
def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(str(msg) + "\n")

log("=== Plugin file loaded ===")

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject
from gi.repository import GLib
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

# Path to JSON state file exported from gen2.html
STATE_JSON_PATH = os.path.expanduser("~/mondrian_state.json")

def load_state_from_json(path):
    """Load pre-computed state from JSON file exported by gen2.html."""
    if not os.path.exists(path):
        log("No state JSON found at {}".format(path))
        return None
    try:
        with open(path, 'r') as f:
            state = json.load(f)
        log("Loaded state from JSON: {} blocks, {} lines".format(
            len(state.get('blocks', [])), len(state.get('lines', []))))
        return state
    except Exception as e:
        log("Error loading state JSON: {}".format(e))
        return None

def hex_to_rgb(hex_color):
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


# =============================================================================
# Randomness utilities (matching p5.brush R object)
# =============================================================================

def gaussian(mean=0.0, stdev=1.0):
    """Generate random gaussian (normal distribution)."""
    u = 1 - random.random()
    v = random.random()
    z = math.sqrt(-2.0 * math.log(u)) * math.cos(2.0 * math.pi * v)
    return z * stdev + mean

def constrain(n, low, high):
    """Constrain a value to a range."""
    return max(min(n, high), low)

def rmap(value, a, b, c, d, within_bounds=False):
    """Remap a value from one range to another."""
    r = c + ((value - a) / (b - a)) * (d - c)
    if not within_bounds:
        return r
    if c < d:
        return constrain(r, c, d)
    else:
        return constrain(r, d, c)

def dist(x1, y1, x2, y2):
    """Calculate distance between two points."""
    return math.hypot(x2 - x1, y2 - y1)


# =============================================================================
# Polygon utilities for watercolor effect
# =============================================================================

def rotate_point(cx, cy, x, y, angle_deg):
    """Rotate point (x,y) around (cx,cy) by angle in degrees.

    Matches p5.brush Q() function which uses clockwise rotation:
    x' = cos(θ)*(x-cx) + sin(θ)*(y-cy) + cx
    y' = cos(θ)*(y-cy) - sin(θ)*(x-cx) + cy
    """
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    # p5.brush uses clockwise rotation (opposite of standard CCW)
    nx = cos_a * (x - cx) + sin_a * (y - cy) + cx
    ny = cos_a * (y - cy) - sin_a * (x - cx) + cy
    return (nx, ny)


def rect_to_polygon(x, y, w, h):
    """Convert a rectangle to polygon vertices."""
    return [
        {'x': x, 'y': y},
        {'x': x + w, 'y': y},
        {'x': x + w, 'y': y + h},
        {'x': x, 'y': y + h}
    ]


def calc_polygon_center(vertices):
    """Calculate centroid of polygon."""
    if not vertices:
        return {'x': 0, 'y': 0}
    midx = sum(v['x'] for v in vertices) / len(vertices)
    midy = sum(v['y'] for v in vertices) / len(vertices)
    return {'x': midx, 'y': midy}


def calc_polygon_size(vertices, center):
    """Calculate max distance from center to any vertex."""
    size = 0
    for v in vertices:
        d = dist(center['x'], center['y'], v['x'], v['y'])
        if d > size:
            size = d
    return size


class WatercolorPolygon:
    """
    Implements the watercolor polygon growth algorithm from p5.brush.
    Based on Tyler Hobbs' watercolor simulation technique.
    """

    def __init__(self, vertices, multipliers, center, directions, bleed_strength, direction="out"):
        self.v = vertices[:]  # Copy vertices
        self.m = multipliers[:]  # Bleed multipliers per vertex
        self.dir = directions[:]  # Bleed direction per edge
        self.midP = center
        self.size = calc_polygon_size(vertices, center)
        self.bleed_strength = bleed_strength
        self.direction = direction

        # If no directions provided, calculate them
        if not self.dir or len(self.dir) < len(self.v):
            self._calc_directions()

    def _calc_directions(self):
        """Calculate bleed direction for each edge (outward from center)."""
        self.dir = []
        for i in range(len(self.v)):
            v1 = self.v[i]
            v2 = self.v[(i + 1) % len(self.v)]
            # Midpoint of edge
            mid = {'x': (v1['x'] + v2['x']) / 2, 'y': (v1['y'] + v2['y']) / 2}
            # Direction from center to edge midpoint determines outward direction
            # Use cross product to determine which side of edge the center is on
            edge_dx = v2['x'] - v1['x']
            edge_dy = v2['y'] - v1['y']
            to_center_dx = self.midP['x'] - v1['x']
            to_center_dy = self.midP['y'] - v1['y']
            cross = edge_dx * to_center_dy - edge_dy * to_center_dx
            # In Y-down coordinates: cross > 0 means center is CW from edge direction
            # For "outward" bleed, we need to push CCW from edge, which requires dir=False
            # (dir=False -> use +90° rotation -> CCW perpendicular -> outward)
            self.dir.append(cross < 0)

    def grow(self, growth_factor=1.0, degrow=False):
        """
        Grows the polygon's vertices outwards to simulate watercolor spread.
        This is the core algorithm from p5.brush FillPolygon.grow()
        """
        new_verts = []
        new_mods = []
        new_dirs = []

        # Trim vertices for small growth factors (matching p5.brush)
        v = self.v
        m = self.m
        dirs = self.dir

        if len(v) > 10 and growth_factor >= 0.2:
            num_trim = int((1 - growth_factor) * len(v))
            sp = len(v) // 2 - num_trim // 2
            if num_trim > 0:
                v = v[:sp] + v[sp + num_trim:]
                m = m[:sp] + m[sp + num_trim:]
                dirs = dirs[:sp] + dirs[sp + num_trim:]

        mod_adjustment = -0.5 if degrow else 1.0

        def change_modifier(modifier):
            gaussian_variation = gaussian(0.5, 0.1)
            return modifier + (gaussian_variation - 0.5) * 0.1

        for i in range(len(v)):
            current_vertex = v[i]
            next_vertex = v[(i + 1) % len(v)]

            # Determine growth modifier
            if growth_factor == 0.1:
                mod = 0.25 if self.bleed_strength <= 0.1 else 0.75
            else:
                mod = m[i] if i < len(m) else self.bleed_strength
            mod *= mod_adjustment

            # Add current vertex
            new_verts.append(current_vertex)
            new_mods.append(change_modifier(mod))

            # Calculate side vector
            side_x = next_vertex['x'] - current_vertex['x']
            side_y = next_vertex['y'] - current_vertex['y']

            # Determine bleed direction
            dir_val = dirs[i] if i < len(dirs) else True
            bleed_angle = -90 if self.direction == "out" else 90
            rotation_degrees = (bleed_angle if dir_val else -bleed_angle) + gaussian(0, 0.4) * 45

            # Calculate midpoint position (gaussian around 0.5)
            lerp = constrain(gaussian(0.5, 0.2), 0.1, 0.9)
            new_vertex = {
                'x': current_vertex['x'] + side_x * lerp,
                'y': current_vertex['y'] + side_y * lerp
            }

            # Calculate displacement - matches p5.brush exactly
            # Direction is the side vector rotated by ~90 degrees (perpendicular)
            # Magnitude is gaussian(0.5,0.2) * random(0.6,1.4) * modifier
            # The displacement IS proportional to edge length - this is correct behavior
            mult = gaussian(0.5, 0.2) * random.uniform(0.6, 1.4) * mod
            direction = rotate_point(0, 0, side_x, side_y, rotation_degrees)
            new_vertex['x'] += direction[0] * mult
            new_vertex['y'] += direction[1] * mult

            # Add new vertex
            new_verts.append(new_vertex)
            new_mods.append(change_modifier(mod))
            new_dirs.append(dir_val)
            new_dirs.append(dir_val)

        return WatercolorPolygon(new_verts, new_mods, self.midP, new_dirs,
                                  self.bleed_strength, self.direction)


def create_initial_watercolor_polygon(vertices, bleed_strength, direction="out"):
    """Create initial watercolor polygon with bleed multipliers."""
    center = calc_polygon_center(vertices)

    # Calculate fluid vertices (some get stronger bleed)
    fluid = int(len(vertices) * random.uniform(0, 0.4))

    multipliers = []
    for i in range(len(vertices)):
        mult = random.uniform(0.8, 1.2) * bleed_strength
        if i < fluid:
            mult = constrain(mult * 2, 0, 0.9)
        multipliers.append(mult)

    # Random shift of vertices for natural edge
    shift = random.randint(0, len(vertices) - 1) if len(vertices) > 0 else 0
    shifted_verts = vertices[shift:] + vertices[:shift]
    shifted_mults = multipliers[shift:] + multipliers[:shift]

    return WatercolorPolygon(shifted_verts, shifted_mults, center, [], bleed_strength, direction)


# =============================================================================
# Color palettes and configuration
# =============================================================================

COLORS = {
    'red': [(227, 28, 37), (255, 23, 68), (255, 0, 51)],
    'yellow': [(255, 235, 0), (255, 214, 0), (255, 255, 0)],
    'blue': [(0, 85, 255), (41, 121, 255), (0, 102, 255)],
    'black': [(26, 26, 26), (33, 33, 33)],
    'lightBlue': [(64, 196, 255), (0, 176, 255), (0, 229, 255)],
    'white': [(255, 255, 255), (250, 250, 250), (245, 245, 245)],
    'green': [(0, 200, 83), (0, 230, 118), (0, 255, 85)],
    'orange': [(255, 109, 0), (255, 145, 0), (255, 85, 0)],
}

BACKGROUND_COLOR = (248, 245, 239)  # #f8f5ef

COLOR_PROPS_AT_0 = {
    'white': 10, 'red': 3, 'yellow': 3, 'blue': 3,
    'black': 2, 'lightBlue': 2, 'green': 0, 'orange': 0
}
COLOR_PROPS_AT_1 = {
    'white': 0, 'red': 3, 'yellow': 3, 'blue': 3,
    'black': 0, 'lightBlue': 2, 'green': 3, 'orange': 3
}


def pick(arr):
    """Pick a random element from an array."""
    return arr[int(random.random() * len(arr))]


def calc_edgeness(x, y, canvas_width, canvas_height):
    """Calculate edgeness: 0 at center, 1 at edges."""
    center_x = canvas_width / 2.0
    center_y = canvas_height / 2.0
    dx = x - center_x
    dy = y - center_y
    return max(abs(dx) / center_x, abs(dy) / center_y)


def sample_color(painterliness):
    """Sample a color based on painterliness (0=edge, 1=center)."""
    props = {}
    for col in COLOR_PROPS_AT_0:
        props[col] = (COLOR_PROPS_AT_0[col] * (1 - painterliness) +
                      COLOR_PROPS_AT_1[col] * painterliness)
    total = sum(props.values())
    r = random.random() * total
    for col in props:
        r -= props[col]
        if r <= 0:
            return col
    return 'white'


def subdivide(x, y, w, h, blocks, potential_lines):
    """Recursively subdivide a rectangle into quadrants."""
    x, y, w, h = int(x), int(y), int(w), int(h)
    min_side = min(w, h)

    if min_side >= 200:
        prob = 1.0
    elif min_side <= 20:
        prob = 0.0
    else:
        prob = (min_side - 20) / (200.0 - 20.0)

    if 2 * random.random() < prob:
        half_w = w // 2
        half_h = h // 2
        mid_x = x + half_w
        mid_y = y + half_h
        rem_w = w - half_w
        rem_h = h - half_h

        potential_lines.append({'x1': mid_x, 'y1': y, 'x2': mid_x, 'y2': y + h})
        potential_lines.append({'x1': x, 'y1': mid_y, 'x2': x + w, 'y2': mid_y})
        subdivide(x, y, half_w, half_h, blocks, potential_lines)
        subdivide(mid_x, y, rem_w, half_h, blocks, potential_lines)
        subdivide(x, mid_y, half_w, rem_h, blocks, potential_lines)
        subdivide(mid_x, mid_y, rem_w, rem_h, blocks, potential_lines)
    else:
        blocks.append({'x': x, 'y': y, 'w': w, 'h': h})


def select_lines(potential_lines, canvas_width, canvas_height):
    """Select lines based on edgeness."""
    lines = []
    for pl in potential_lines:
        line_center_x = (pl['x1'] + pl['x2']) / 2.0
        line_center_y = (pl['y1'] + pl['y2']) / 2.0
        edgeness = calc_edgeness(line_center_x, line_center_y, canvas_width, canvas_height)
        prob = 0.05 + edgeness * edgeness * 0.9

        if random.random() < prob:
            line_painterliness = 1 - edgeness
            shorten_prob = line_painterliness * 0.5
            shorten_amt = line_painterliness * 0.4
            shorten_start = random.random() * shorten_amt if random.random() < shorten_prob else 0
            shorten_end = random.random() * shorten_amt if random.random() < shorten_prob else 0

            dx = pl['x2'] - pl['x1']
            dy = pl['y2'] - pl['y1']

            lines.append({
                'x1': pl['x1'] + dx * shorten_start,
                'y1': pl['y1'] + dy * shorten_start,
                'x2': pl['x2'] - dx * shorten_end,
                'y2': pl['y2'] - dy * shorten_end,
                'thickness': 0.6 + random.random() * 0.4 + line_painterliness * random.random() * 0.4
            })
    return lines


def set_foreground_rgb(r, g, b):
    """Set foreground color from RGB (0-255) in sRGB color space."""
    # Use CSS hex format which GEGL interprets as sRGB
    hex_color = "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))
    color = Gegl.Color.new(hex_color)
    Gimp.context_set_foreground(color)


def polygon_to_array(vertices):
    """Convert polygon vertices to flat array for GIMP."""
    result = []
    for v in vertices:
        result.append(v['x'])
        result.append(v['y'])
    return result


def draw_polygon_layer(image, wc_layer, polygon, alpha, has_stroke, stroke_alpha, stroke_weight, color_rgb):
    """
    Draw a single polygon layer with fill and optional stroke.
    Exactly matches p5.brush FillPolygon.layer() method.

    Key: In p5.brush, all polygons are drawn to the SAME buffer with alpha blending.
    Canvas alpha compositing: out_α = src_α + dst_α × (1 - src_α)

    We replicate this by drawing directly to wc_layer using GIMP's paint opacity,
    NOT by creating separate layers with layer opacity.
    """
    if len(polygon.v) < 3:
        return wc_layer

    # Clamp alpha to valid range (0-255 in p5, 0-100 for GIMP opacity)
    alpha = constrain(alpha, 0, 255)
    if alpha < 1:
        return wc_layer  # Skip if nearly invisible

    coords = polygon_to_array(polygon.v)

    # Set the paint opacity (this affects how the fill blends with existing content)
    # In GIMP, opacity is 0-100, not 0-255
    paint_opacity = (alpha / 255.0) * 100.0
    Gimp.context_set_opacity(paint_opacity)

    # Set foreground color
    set_foreground_rgb(*color_rgb)

    # Select and fill the polygon directly on wc_layer
    # With paint opacity set, this will blend with existing content just like p5.js canvas
    image.select_polygon(Gimp.ChannelOps.REPLACE, coords)
    wc_layer.edit_fill(Gimp.FillType.FOREGROUND)

    Gimp.Selection.none(image)

    # Reset opacity to full for other operations
    Gimp.context_set_opacity(100.0)

    return wc_layer


def erase_circles(image, wc_layer, polygon, texture, intensity):
    """
    Erase random circles to create watercolor paper texture.
    Exactly matches p5.brush FillPolygon.erase() method.

    In p5.brush, erase(strength, 0) does PARTIAL erasing:
    - strength is typically 3-10 out of 255 (very subtle)
    - This slightly reduces alpha, creating texture variation

    We use GIMP's ERASE layer mode at low opacity to simulate this.
    """
    center = polygon.midP
    size = polygon.size
    half_size = size / 2
    min_size_factor = 0.025 * size
    max_size_factor = 0.19 * size

    # Erase strength in p5: 3.5*texture - map(intensity, 80, 120, 0.3, 1, true)
    # This is in 0-255 range, typically very low (3-10)
    erase_strength = 3.5 * texture - rmap(intensity, 80, 120, 0.3, 1, True)
    if erase_strength <= 0:
        return wc_layer

    # Convert from 0-255 to 0-100 for GIMP layer opacity
    # p5.brush erase() takes strength in 0-255 range, we convert to GIMP's 0-100
    erase_opacity = constrain((erase_strength / 255.0) * 100.0, 0, 100)

    num_circles = random.randint(130, 200)

    # Build selection of all circles
    first_circle = True
    for _ in range(num_circles):
        cx = center['x'] + gaussian(0, half_size)
        cy = center['y'] + gaussian(0, half_size)
        circle_size = random.uniform(min_size_factor, max_size_factor)

        op = Gimp.ChannelOps.REPLACE if first_circle else Gimp.ChannelOps.ADD
        first_circle = False

        image.select_ellipse(
            op,
            int(cx - circle_size / 2), int(cy - circle_size / 2),
            int(circle_size), int(circle_size)
        )

    if not first_circle:
        # Find the position of wc_layer
        layers = image.get_layers()
        wc_position = 0
        for idx, lyr in enumerate(layers):
            if lyr == wc_layer:
                wc_position = idx
                break

        # Create an ERASE mode layer at LOW opacity
        # This partially reduces alpha of underlying pixels, just like p5's erase()
        erase_layer = Gimp.Layer.new(image, "erase_temp",
                                     image.get_width(), image.get_height(),
                                     Gimp.ImageType.RGBA_IMAGE, erase_opacity,
                                     Gimp.LayerMode.ERASE)
        image.insert_layer(erase_layer, None, wc_position)
        erase_layer.fill(Gimp.FillType.TRANSPARENT)

        # Fill the selected circles (color doesn't matter in ERASE mode, only alpha)
        set_foreground_rgb(255, 255, 255)
        erase_layer.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(image)

        # Merge the erase layer - this partially reduces alpha in circle areas
        wc_layer = image.merge_down(erase_layer, Gimp.MergeType.EXPAND_AS_NECESSARY)

    Gimp.Selection.none(image)
    return wc_layer


def draw_watercolor_fill(image, base_layer, vertices, color_rgb, bleed_strength,
                         texture_strength, border_strength, opacity_base):
    """
    Draw a watercolor fill using the Tyler Hobbs / p5.brush algorithm.

    This is an EXACT replication of FillPolygon.fill() from p5.brush:
    - 24 * bleed layers
    - 4 polygon variants per layer (pol, pol2, pol3, pol4)
    - Progressive growth at 1/4, 1/2, 3/4 intervals
    - Circle erasing after each layer iteration
    """
    if len(vertices) < 3:
        return None

    log("draw_watercolor_fill: bleed={}, texture={}, border={}, opacity={}".format(
        bleed_strength, texture_strength, border_strength, opacity_base))

    # Calculate bleed factor: map(bleed_strength, 0, 0.15, 0.6, 1, true)
    bleed = rmap(bleed_strength, 0, 0.15, 0.6, 1, True)
    num_layers = int(24 * bleed)

    log("  bleed factor={}, num_layers={}".format(bleed, num_layers))

    # Calculate intensity: map(opacity_base, 0, 155, 0, 20, true)
    intensity = rmap(opacity_base, 0, 155, 0, 20, True)
    tex = texture_strength

    # Intensity values for different polygon variants (exactly from p5.brush)
    intensity_half = intensity / 5  # For pol (main shape)
    intensity_fifth = intensity / 7 + (tex * intensity) / 3  # For pol4 (degrow)
    intensity_quarter = intensity / 4 + (tex * intensity) / 3  # For pol2
    intensity_third = intensity / 5 + (tex * intensity) / 6  # For pol3

    texture = tex * 3

    # Stroke alpha: 0.5 + 1.5 * border_strength (in p5 this is 0-255 scale, but very low)
    stroke_alpha_base = (0.5 + 1.5 * border_strength)  # Keep in 0-2 range, scale when using

    log("  intensities: half={}, fifth={}, quarter={}, third={}".format(
        intensity_half, intensity_fifth, intensity_quarter, intensity_third))

    # Create a base watercolor layer that will accumulate all the polygon layers
    # All polygons are drawn to this SAME layer with paint opacity, just like p5.brush
    # draws to Mix.masks[0]. Alpha accumulates via standard compositing.
    wc_layer = Gimp.Layer.new(image, "watercolor_base",
                               image.get_width(), image.get_height(),
                               Gimp.ImageType.RGBA_IMAGE, 100.0,
                               Gimp.LayerMode.NORMAL)
    image.insert_layer(wc_layer, None, 0)
    wc_layer.fill(Gimp.FillType.TRANSPARENT)

    # Create initial polygon with bleed multipliers
    initial_pol = create_initial_watercolor_polygon(vertices, bleed_strength, "out")

    # Set up the 4 polygon variants (exactly as in p5.brush)
    pol = initial_pol.grow()
    pol2 = pol.grow().grow(0.9)
    pol3 = pol2.grow(0.75)
    pol4 = initial_pol.grow(0.6)

    log("  Starting {} layer iterations...".format(num_layers))

    # Main layer loop (exactly as in p5.brush)
    for i in range(num_layers):
        # Grow polygons at 1/4, 1/2, 3/4 intervals
        if i == num_layers // 4 or i == num_layers // 2 or i == (3 * num_layers) // 4:
            pol = pol.grow()
            # Grow texture polygons if bleed==1 or at halfway point
            if bleed >= 0.99 or i == num_layers // 2:
                pol2 = pol2.grow(0.75)
                pol3 = pol3.grow(0.75)
                pol4 = pol4.grow(0.1, True)  # degrow

        # Calculate stroke weight: map(i, 0, 24, 6, 0.5)
        stroke_weight = rmap(i, 0, 24, 6, 0.5, False)

        # Alpha scaling: intensity values are 0-20, but we want very subtle layering
        # With 24 layers × 4 polygons = 96 fills, each needs to be very transparent
        # to build up gradually. Use intensity directly as alpha (0-20 out of 255)
        # This gives α ≈ 0.02-0.08 per layer, building to ~50-70% final opacity
        alpha_scale = 1.0  # Use intensity values directly as alpha (0-20)

        # Draw pol layer (main shape with stroke)
        pol_grown = pol.grow()
        wc_layer = draw_polygon_layer(image, wc_layer, pol_grown,
                          intensity_half * alpha_scale,
                          True, stroke_alpha_base * 128, stroke_weight, color_rgb)

        # Draw pol4 layer (degrow variant, no stroke)
        pol4_grown = pol4.grow(0.1, True).grow(0.1)
        wc_layer = draw_polygon_layer(image, wc_layer, pol4_grown,
                          intensity_fifth * alpha_scale,
                          False, 0, 0, color_rgb)

        # Draw pol2 layer (medium growth, no stroke)
        pol2_grown = pol2.grow(0.1).grow(0.1)
        wc_layer = draw_polygon_layer(image, wc_layer, pol2_grown,
                          intensity_quarter * alpha_scale,
                          False, 0, 0, color_rgb)

        # Draw pol3 layer (most growth, no stroke)
        pol3_grown = pol3.grow(0.8).grow(0.1)
        wc_layer = draw_polygon_layer(image, wc_layer, pol3_grown,
                          intensity_third * alpha_scale,
                          False, 0, 0, color_rgb)

        # Erase circles for texture (after each layer iteration)
        if texture > 0:
            wc_layer = erase_circles(image, wc_layer, pol_grown, texture, intensity)

    Gimp.Selection.none(image)

    return wc_layer


def generate_state(seed, canvas_width, canvas_height):
    """Generate the mondrian state (blocks and lines) from scratch."""
    random.seed(seed)

    # Quadtree subdivision
    raw_blocks = []
    potential_lines = []
    half_height = canvas_height
    subdivide(0, 0, half_height, half_height, raw_blocks, potential_lines)
    if canvas_width > half_height:
        subdivide(half_height, 0, min(half_height, canvas_width - half_height),
                  half_height, raw_blocks, potential_lines)

    # Convert raw blocks to drawable blocks with all computed properties
    drawable_blocks = []
    for block in raw_blocks:
        rect_center_x = block['x'] + block['w'] / 2.0
        rect_center_y = block['y'] + block['h'] / 2.0
        painterliness = max(0, 1 - calc_edgeness(rect_center_x, rect_center_y, canvas_width, canvas_height))
        color_key = sample_color(math.sqrt(painterliness))

        # Skip white blocks
        if color_key == 'white':
            continue

        base_color = pick(COLORS[color_key])
        touches_border = (block['x'] <= 0 or block['y'] <= 0 or
                          block['x'] + block['w'] >= canvas_width or
                          block['y'] + block['h'] >= canvas_height)

        drawable_blocks.append({
            'x': block['x'],
            'y': block['y'],
            'w': block['w'],
            'h': block['h'],
            'color': base_color,  # RGB tuple
            'painterliness': painterliness,
            'touchesBorder': touches_border,
            'jitterX': random.uniform(-1, 1) * painterliness,
            'jitterY': random.uniform(-1, 1) * painterliness,
            'jitterW': random.uniform(-2, 2) * painterliness,
            'jitterH': random.uniform(-2, 2) * painterliness,
        })

    lines = select_lines(potential_lines, canvas_width, canvas_height)

    return drawable_blocks, lines


def state_from_json(json_state):
    """Convert JSON state to internal format."""
    drawable_blocks = []
    for block in json_state['blocks']:
        drawable_blocks.append({
            'x': block['x'],
            'y': block['y'],
            'w': block['w'],
            'h': block['h'],
            'color': hex_to_rgb(block['color']),  # Convert hex to RGB tuple
            'painterliness': block['painterliness'],
            'touchesBorder': block['touchesBorder'],
            'jitterX': block['jitterX'],
            'jitterY': block['jitterY'],
            'jitterW': block['jitterW'],
            'jitterH': block['jitterH'],
        })

    # Lines use 't' in JSON, normalize to 'thickness'
    lines = []
    for line in json_state['lines']:
        lines.append({
            'x1': line['x1'],
            'y1': line['y1'],
            'x2': line['x2'],
            'y2': line['y2'],
            'thickness': line.get('t', line.get('thickness', 1.0)),
        })

    return drawable_blocks, lines


def generate_mondrian(procedure, seed, line_thickness, size_multiplier):
    """Core generation logic."""
    log("generate_mondrian started")

    # ===== PHASE 1: Get state (either from JSON or generate) =====
    json_state = load_state_from_json(STATE_JSON_PATH)

    if json_state is not None:
        canvas_width = json_state['width']
        canvas_height = json_state['height']
        drawable_blocks, lines = state_from_json(json_state)
        log("Using JSON state: {}x{}, seed={}, {} blocks, {} lines".format(
            canvas_width, canvas_height, json_state.get('seed'),
            len(drawable_blocks), len(lines)))
    else:
        canvas_height = int(600 * size_multiplier)
        canvas_width = int(1200 * size_multiplier)
        drawable_blocks, lines = generate_state(seed, canvas_width, canvas_height)
        log(f"Generated state: {canvas_width}x{canvas_height},"
            f"{len(drawable_blocks)} blocks, {len(lines)} lines")

    # ===== PHASE 2: Render =====
    image = Gimp.Image.new(canvas_width, canvas_height, Gimp.ImageBaseType.RGB)
    log(f"Image created: {image}")
    Gimp.progress_init("Generating Mondrian...")

    try:
        # Create background layer
        bg_layer = Gimp.Layer.new(image, "Background",
                                  canvas_width, canvas_height,
                                  Gimp.ImageType.RGB_IMAGE, 100.0,
                                  Gimp.LayerMode.NORMAL)
        image.insert_layer(bg_layer, None, 0)
        set_foreground_rgb(*BACKGROUND_COLOR)
        bg_layer.fill(Gimp.FillType.FOREGROUND)

        # Create blocks layer
        blocks_layer = Gimp.Layer.new(image, "Mondrian Blocks",
                                      canvas_width, canvas_height,
                                      Gimp.ImageType.RGBA_IMAGE, 100.0,
                                      Gimp.LayerMode.NORMAL)
        image.insert_layer(blocks_layer, None, 0)
        blocks_layer.fill(Gimp.FillType.TRANSPARENT)

        # Draw blocks (single unified loop)
        for i, block in enumerate(drawable_blocks):
            log(f"Block {i+1}/{len(drawable_blocks)}")
            if block['touchesBorder']:
                # Standard solid fill for border blocks
                set_foreground_rgb(*block['color'])
                image.select_rectangle(Gimp.ChannelOps.REPLACE,
                                       int(block['x']), int(block['y']),
                                       int(block['w']), int(block['h']))
                blocks_layer.edit_fill(Gimp.FillType.FOREGROUND)
                Gimp.Selection.none(image)
            else:
                # Watercolor fill
                jittered_x = block['x'] + block['jitterX']
                jittered_y = block['y'] + block['jitterY']
                jittered_w = block['w'] + block['jitterW']
                jittered_h = block['h'] + block['jitterH']
                vertices = [
                    {'x': jittered_x, 'y': jittered_y},
                    {'x': jittered_x + jittered_w, 'y': jittered_y},
                    {'x': jittered_x + jittered_w, 'y': jittered_y + jittered_h},
                    {'x': jittered_x, 'y': jittered_y + jittered_h}
                ]

                painterliness = block['painterliness']
                bleed_strength = pow(painterliness, 1) * 0.5
                texture_strength = painterliness * 0.8
                border_strength = painterliness * 0.25
                opacity = 150

                wc_layer = draw_watercolor_fill(
                    image, blocks_layer, vertices, block['color'],
                    bleed_strength, texture_strength, border_strength, opacity
                )

                if wc_layer:
                    blocks_layer = image.merge_down(wc_layer, Gimp.MergeType.EXPAND_AS_NECESSARY)

            # Progress update
            progress = float(i + 1) / len(drawable_blocks) * 0.9
            Gimp.progress_init("Generating Mondrian... ({}/{} blocks)".format(i + 1, len(drawable_blocks)))
            Gimp.progress_update(progress)

        Gimp.Selection.none(image)
        log(f"Drawing {len(lines)} lines")

        # Create lines layer
        lines_layer = Gimp.Layer.new(image, "Mondrian Lines",
                                     canvas_width, canvas_height,
                                     Gimp.ImageType.RGBA_IMAGE, 100.0,
                                     Gimp.LayerMode.NORMAL)
        image.insert_layer(lines_layer, None, 0)
        lines_layer.fill(Gimp.FillType.TRANSPARENT)

        # Draw lines
        set_foreground_rgb(0, 0, 0)

        for i, line in enumerate(lines):
            brush_size = line_thickness * line['thickness']
            Gimp.context_set_brush_size(brush_size)

            strokes = [line['x1'], line['y1'], line['x2'], line['y2']]
            Gimp.pencil(lines_layer, strokes)

            # Second pass for paint buildup (matching p5.brush)
            set_foreground_rgb(10, 10, 10)
            Gimp.context_set_brush_size(brush_size * 0.7)
            strokes2 = [
                line['x1'] + random.uniform(-0.3, 0.3),
                line['y1'] + random.uniform(-0.3, 0.3),
                line['x2'] + random.uniform(-0.3, 0.3),
                line['y2'] + random.uniform(-0.3, 0.3)
            ]
            Gimp.pencil(lines_layer, strokes2)
            set_foreground_rgb(0, 0, 0)

            Gimp.progress_update(0.9 + float(i) / max(len(lines), 1) * 0.1)

        # Display the new image
        Gimp.progress_end()
        display = Gimp.Display.new(image)
        Gimp.displays_flush()
        log("Image displayed")

    except Exception as e:
        log("ERROR in generate: " + str(e))
        log(traceback.format_exc())
        raise

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def run(procedure, config, data):
    """Main run function."""
    log("=== run() called ===")
    try:
        run_mode = config.get_property("run-mode")
        if run_mode == Gimp.RunMode.INTERACTIVE:
            log("Interactive mode")
            GimpUi.init("python-fu-procedural-mondrian")
            dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Procedural Mondrian"))
            dialog.fill(None)
            if not dialog.run():
                log("Dialog cancelled")
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

        seed = config.get_property("seed")
        line_thickness = config.get_property("line-thickness")
        size_multiplier = config.get_property("size-multiplier")
        log(f"seed={seed}, thickness={line_thickness}, size={size_multiplier}")

        result = generate_mondrian(procedure, seed, line_thickness, size_multiplier)
        log("generate_mondrian completed")
        return result
    except Exception as e:
        log("ERROR: " + str(e))
        log(traceback.format_exc())
        raise


class ProceduralMondrian(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_set_i18n(self, procname):
        log("do_set_i18n called")
        return True, 'gimp30-python', None

    def do_query_procedures(self):
        log("do_query_procedures called")
        return ['python-fu-procedural-mondrian']

    def do_create_procedure(self, name):
        log("do_create_procedure called: " + name)
        procedure = Gimp.Procedure.new(self, name,
                                       Gimp.PDBProcType.PLUGIN,
                                       run, None)

        procedure.set_documentation(
            _("Generate a procedural Mondrian-style painting"),
            _("Creates a new image with Mondrian-inspired artwork using quadtree subdivision and watercolor effects"),
            name)
        procedure.set_menu_label(_("Procedural Mondrian..."))
        procedure.set_attribution("Translated from gen2.html", "", "2024")
        procedure.add_menu_path("<Image>/File/Create/")

        procedure.add_enum_argument("run-mode", _("Run mode"),
                                    _("The run mode"), Gimp.RunMode,
                                    Gimp.RunMode.INTERACTIVE,
                                    GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("seed", _("_Seed"), _("Random seed"),
                                   0, 999999, 42, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("line-thickness", _("Line _Thickness"), _("Base line thickness"),
                                      1.0, 50.0, 8.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("size-multiplier", _("Size _Multiplier"), _("Size multiplier (base 1200x600)"),
                                      0.5, 10.0, 2.0, GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(ProceduralMondrian.__gtype__, sys.argv)
