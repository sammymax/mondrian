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
    min_side = min(w, h)

    if min_side >= 200:
        prob = 1.0
    elif min_side <= 20:
        prob = 0.0
    else:
        prob = (min_side - 20) / (200.0 - 20.0)

    if 2 * random.random() < prob:
        mid_x = x + w / 2.0
        mid_y = y + h / 2.0
        potential_lines.append({'x1': mid_x, 'y1': y, 'x2': mid_x, 'y2': y + h})
        potential_lines.append({'x1': x, 'y1': mid_y, 'x2': x + w, 'y2': mid_y})
        subdivide(x, y, w / 2.0, h / 2.0, blocks, potential_lines)
        subdivide(mid_x, y, w / 2.0, h / 2.0, blocks, potential_lines)
        subdivide(x, mid_y, w / 2.0, h / 2.0, blocks, potential_lines)
        subdivide(mid_x, mid_y, w / 2.0, h / 2.0, blocks, potential_lines)
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


def generate_mondrian(procedure, image, seed, line_thickness):
    """Core generation logic."""
    log("generate_mondrian started")
    random.seed(seed)

    canvas_width = image.get_width()
    canvas_height = image.get_height()
    log("Canvas: {}x{}".format(canvas_width, canvas_height))

    image.undo_group_start()
    log("undo_group_start done")

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

            # Add jitter for painterly effect
            jitter_x = (random.random() * 2 - 1) * painterliness
            jitter_y = (random.random() * 2 - 1) * painterliness
            jitter_w = (random.random() * 4 - 2) * painterliness
            jitter_h = (random.random() * 4 - 2) * painterliness

            x = max(0, int(block['x'] + jitter_x))
            y = max(0, int(block['y'] + jitter_y))
            w = max(1, int(block['w'] + jitter_w))
            h = max(1, int(block['h'] + jitter_h))

            image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
            blocks_layer.edit_fill(Gimp.FillType.FOREGROUND)

            Gimp.progress_update(float(i) / len(blocks) * 0.5)

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

        # Draw lines using PDB
        pdb = Gimp.get_pdb()

        for i, line in enumerate(lines):
            brush_size = line_thickness * line['thickness']

            # Set brush size
            Gimp.context_set_brush_size(brush_size)
            set_foreground_rgb(0, 0, 0)

            # Use gimp-pencil via PDB
            pencil_proc = pdb.lookup_procedure('gimp-pencil')
            if pencil_proc:
                config = pencil_proc.create_config()
                config.set_property('drawable', lines_layer)
                config.set_property('strokes', Gimp.FloatArray.new([
                    line['x1'], line['y1'], line['x2'], line['y2']
                ]))
                pencil_proc.run(config)

            Gimp.progress_update(0.5 + float(i) / max(len(lines), 1) * 0.5)

        Gimp.displays_flush()

    finally:
        image.undo_group_end()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def run(procedure, run_mode, image, layers, config, data):
    """Main run function."""
    log("=== run() called ===")
    try:
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
        log("seed={}, thickness={}".format(seed, line_thickness))

        result = generate_mondrian(procedure, image, seed, line_thickness)
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
        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            run, None)

        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)

        procedure.set_documentation(
            _("Generate a procedural Mondrian-style painting"),
            _("Creates a Mondrian-inspired artwork using quadtree subdivision"),
            name)
        procedure.set_menu_label(_("Procedural Mondrian..."))
        procedure.set_attribution("Translated from gen2.html", "", "2024")
        procedure.add_menu_path("<Image>/Filters/Render/")

        procedure.add_int_argument("seed", _("_Seed"), _("Random seed"),
                                   0, 999999, 42, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("line-thickness", _("Line _Thickness"), _("Base line thickness"),
                                      1.0, 50.0, 8.0, GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(ProceduralMondrian.__gtype__, sys.argv)
