#!/usr/bin/env python3
"""
Procedural Mondrian Generator for GIMP 3.0
Translated from gen2.html p5.js implementation
"""

import random
import math
import sys
import os
import traceback

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


# Color palettes (RGB tuples, 0-255)
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

# Color proportions at painterliness 0 (edges) and 1 (center)
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
    # Use integers throughout to avoid off-by-one errors
    x, y, w, h = int(x), int(y), int(w), int(h)
    min_side = min(w, h)

    if min_side >= 200:
        prob = 1.0
    elif min_side <= 20:
        prob = 0.0
    else:
        prob = (min_side - 20) / (200.0 - 20.0)

    if 2 * random.random() < prob:
        # Integer division for clean splits
        half_w = w // 2
        half_h = h // 2
        mid_x = x + half_w
        mid_y = y + half_h
        # Remaining width/height for right/bottom quadrants
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
    """Set foreground color from RGB (0-255)."""
    color = Gegl.Color.new("black")
    color.set_rgba(r / 255.0, g / 255.0, b / 255.0, 1.0)
    Gimp.context_set_foreground(color)


def generate_mondrian(procedure, seed, line_thickness, size_multiplier):
    """Core generation logic."""
    log("generate_mondrian started")
    random.seed(seed)

    # Base size is 1200x600, multiplied by size_multiplier
    # Always 2:1 aspect ratio
    canvas_height = int(600 * size_multiplier)
    canvas_width = int(1200 * size_multiplier)
    log("Canvas: {}x{}".format(canvas_width, canvas_height))

    # Create new image
    image = Gimp.Image.new(canvas_width, canvas_height, Gimp.ImageBaseType.RGB)
    log("Image created: {}".format(image))

    # Initialize progress bar
    Gimp.progress_init("Generating Mondrian...")

    try:
        # Create blocks layer
        log("Creating blocks layer...")
        blocks_layer = Gimp.Layer.new(image, "Mondrian Blocks",
                                      canvas_width, canvas_height,
                                      Gimp.ImageType.RGBA_IMAGE, 100.0,
                                      Gimp.LayerMode.NORMAL)
        log("Layer created: {}".format(blocks_layer))
        image.insert_layer(blocks_layer, None, 0)
        log("Layer inserted")

        # Fill background
        log("Filling background...")
        set_foreground_rgb(*BACKGROUND_COLOR)
        blocks_layer.fill(Gimp.FillType.FOREGROUND)
        log("Background filled")

        # Quadtree subdivision
        blocks = []
        potential_lines = []
        half_height = canvas_height
        subdivide(0, 0, half_height, half_height, blocks, potential_lines)
        if canvas_width > half_height:
            subdivide(half_height, 0, min(half_height, canvas_width - half_height),
                      half_height, blocks, potential_lines)

        # Draw blocks
        for i, block in enumerate(blocks):
            rect_center_x = block['x'] + block['w'] / 2.0
            rect_center_y = block['y'] + block['h'] / 2.0
            painterliness = max(0, 1 - calc_edgeness(rect_center_x, rect_center_y, canvas_width, canvas_height))
            color_key = sample_color(math.sqrt(painterliness))

            if color_key == 'white':
                continue

            base_color = pick(COLORS[color_key])
            set_foreground_rgb(*base_color)

            # Check if block touches outer border
            touches_border = (block['x'] <= 0 or block['y'] <= 0 or
                              block['x'] + block['w'] >= canvas_width or
                              block['y'] + block['h'] >= canvas_height)

            # Add jitter for painterly effect (more jitter toward center)
            jitter_x = (random.random() * 2 - 1) * painterliness * 0
            jitter_y = (random.random() * 2 - 1) * painterliness * 0
            jitter_w = (random.random() * 4 - 2) * painterliness * 0
            jitter_h = (random.random() * 4 - 2) * painterliness * 0

            x = max(0, int(block['x'] + jitter_x))
            y = max(0, int(block['y'] + jitter_y))
            w = max(1, int(block['w'] + jitter_w))
            h = max(1, int(block['h'] + jitter_h))

            if touches_border:
                # Solid fill for border blocks
                image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
                blocks_layer.edit_fill(Gimp.FillType.FOREGROUND)
            else:
                # Watercolor-style fill matching p5.brush approach:
                # - Rounded corners approaching ellipse at painterliness=1
                # - Edge bleeding outward via gaussian blur
                # - Texture via noise

                # Create a temporary layer for this block's watercolor effect
                block_layer = Gimp.Layer.new(image, "block_temp",
                                             canvas_width, canvas_height,
                                             Gimp.ImageType.RGBA_IMAGE, 100.0,
                                             Gimp.LayerMode.NORMAL)
                image.insert_layer(block_layer, None, 0)
                block_layer.fill(Gimp.FillType.TRANSPARENT)

                # Calculate corner radius: 0 at painterliness=0, min(w,h)/2 at painterliness=1
                # This makes the shape transition from rectangle to stadium/ellipse
                min_dim = min(w, h)
                corner_radius = painterliness * min_dim / 2.0

                # Blur radius for soft edges (scales with painterliness and size)
                # Larger blur = softer edges
                blur_radius = painterliness * min_dim * 0.08

                # To bleed OUTWARD, we fill an EXPANDED shape, then blur
                # The blur "eats into" the shape, so expansion compensates
                # Expand by blur_radius so after blur, we still cover original bounds
                expand = blur_radius * 1.5  # slightly more than blur to ensure coverage

                fill_x = x - expand
                fill_y = y - expand
                fill_w = w + expand * 2
                fill_h = h + expand * 2
                fill_corner = corner_radius + expand  # corners expand too

                # Fill expanded rounded rectangle with base color
                set_foreground_rgb(*base_color)
                image.select_round_rectangle(
                    Gimp.ChannelOps.REPLACE,
                    fill_x, fill_y, fill_w, fill_h,
                    fill_corner, fill_corner
                )
                block_layer.edit_fill(Gimp.FillType.FOREGROUND)
                Gimp.Selection.none(image)

                # Apply Gaussian blur for soft bleeding edges
                if blur_radius > 0.5:
                    blur_filter = Gimp.DrawableFilter.new(block_layer, "gegl:gaussian-blur", "")
                    blur_config = blur_filter.get_config()
                    blur_config.set_property("std-dev-x", blur_radius)
                    blur_config.set_property("std-dev-y", blur_radius)
                    block_layer.merge_filter(blur_filter)

                # Add noise for texture (like brush.fillTexture)
                if painterliness > 0.1:
                    noise_pct = painterliness * 0.8 * 15
                    noise_filter = Gimp.DrawableFilter.new(block_layer, "gegl:noise-hsv", "")
                    noise_config = noise_filter.get_config()
                    noise_config.set_property("holdness", 2)
                    noise_config.set_property("hue-distance", 0.0)
                    noise_config.set_property("saturation-distance", noise_pct * 0.3)
                    noise_config.set_property("value-distance", noise_pct * 0.5)
                    block_layer.merge_filter(noise_filter)

                # Layer opacity: semi-transparent for watercolor effect
                block_opacity = 75 - painterliness * 20  # 75% at edges, 55% at center
                block_layer.set_opacity(block_opacity)

                # Merge down to blocks layer and update reference
                blocks_layer = image.merge_down(block_layer, Gimp.MergeType.EXPAND_AS_NECESSARY)

            Gimp.progress_update(float(i) / len(blocks) * 0.9)

        Gimp.Selection.none(image)

        # Select lines
        lines = select_lines(potential_lines, canvas_width, canvas_height)

        # Create lines layer
        lines_layer = Gimp.Layer.new(image, "Mondrian Lines",
                                     canvas_width, canvas_height,
                                     Gimp.ImageType.RGBA_IMAGE, 100.0,
                                     Gimp.LayerMode.NORMAL)
        image.insert_layer(lines_layer, None, 0)
        lines_layer.fill(Gimp.FillType.TRANSPARENT)

        # Draw lines
        log("Drawing {} lines".format(len(lines)))

        # Set black color before drawing lines
        set_foreground_rgb(0, 0, 0)
        log("Set foreground to black")

        for i, line in enumerate(lines):
            brush_size = line_thickness * line['thickness']
            Gimp.context_set_brush_size(brush_size)

            # Draw line using Gimp.pencil with flat coordinate list
            strokes = [line['x1'], line['y1'], line['x2'], line['y2']]
            Gimp.pencil(lines_layer, strokes)

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
        log("seed={}, thickness={}, size={}".format(seed, line_thickness, size_multiplier))

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
            _("Creates a new image with Mondrian-inspired artwork using quadtree subdivision"),
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
