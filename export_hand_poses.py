#! /usr/bin/env python3
#######################################################################################################################
#  Copyright (c) 2023 Vincent LAMBERT
#  License: MIT
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
# 
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
# 
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
#
#######################################################################################################################
# NOTES
#
# Developing extensions:
#   SEE: https://inkscape.org/develop/extensions/
#   SEE: https://wiki.inkscape.org/wiki/Python_modules_for_extensions
#   SEE: https://wiki.inkscape.org/wiki/Using_the_Command_Line
#
# Implementation References:
#   SEE: https://github.com/nshkurkin/inkscape-export-layer-combos

import sys
sys.path.append('/usr/share/inkscape/extensions')
import inkex
import os
import subprocess
import tempfile
import shutil
import copy
from lxml import etree
import logging
import itertools

######################################################################################################################

NONE="None"
THUMB="thumb"
INDEX="index"
MIDDLE="middle"
RING="ring"
PINKY="pinky"
UP="up"
DOWN="down"
ADD_LINK="add-link"
ABD_LINK="abd-link"
MULTI_LINK="multi-link"

FINGERS= [THUMB, INDEX, MIDDLE, RING, PINKY]
STATUS = [UP, DOWN, ADD_LINK, ABD_LINK, MULTI_LINK]

ACCEPTED_STATUSES = { THUMB : [INDEX, MIDDLE, RING, PINKY],
                      INDEX : [UP, DOWN, ADD_LINK, MULTI_LINK],
                      MIDDLE : [UP, DOWN, ADD_LINK, ABD_LINK, MULTI_LINK],
                      RING: [UP, DOWN, ADD_LINK, ABD_LINK, MULTI_LINK],
                      PINKY: [UP, DOWN, ABD_LINK, MULTI_LINK]}

PROXIMATE_FINGERS = { THUMB : [],
                 INDEX : [MIDDLE],
                 MIDDLE : [INDEX, RING],
                 RING : [MIDDLE, PINKY],
                 PINKY : [RING]}

ACCEPTED_S_LINKS = [{ADD_LINK : INDEX, ABD_LINK : MIDDLE},
                    {ADD_LINK : MIDDLE, ABD_LINK : RING},
                    {ADD_LINK : RING, ABD_LINK : PINKY}]


def has_multi_joints(combination) :
    return any([status == MULTI_LINK for finger,status in combination])

def has_add_or_abd_joints(combination) :
    return any([status == ADD_LINK for finger,status in combination]) or any([status == ABD_LINK for finger,status in combination])

def has_valid_multi_joints(combination) :
    # If the thumb is a multi-link, return False
    if any([finger == THUMB and status == MULTI_LINK for finger,status in combination]) :
        return False
    # If there is less than 3 multi-links, return False
    if len([status for finger,status in combination if status == MULTI_LINK]) < 3 :
        return False
    # If both the middle and the ring are multi-links, its true, otherwise return False
    if any([finger == MIDDLE and status == MULTI_LINK for finger,status in combination]) and any([finger == RING and status == MULTI_LINK for finger,status in combination]) :
        return True
    return False

def has_valid_add_and_abd_joints(combination) :
    # Check if there is an equal number of add-links and abd-links
    if len([status for finger,status in combination if status == ADD_LINK]) != len([status for finger,status in combination if status == ABD_LINK]) :
        return False
    # At this state there is a abd-link for each add-link
    # Fetch all add-links and abd-links as a list of couples
    add_fingers = [finger for finger,status in combination if status == ADD_LINK]
    abd_fingers = [finger for finger,status in combination if status == ABD_LINK]    
    
    for add_finger in add_fingers :
        # Check if one of the proximate fingers of the add_finger has a abd-link
        proximate_fingers_with_abd_link = intersect(PROXIMATE_FINGERS[add_finger], abd_fingers)
        if proximate_fingers_with_abd_link==[] :
            return False
        # If its the case, still check if the link is accepted
        # Get the adb-link with the add-link being the add_finger in the accepted links
        i = 0
        while ACCEPTED_S_LINKS[i][ADD_LINK] != add_finger :
            i+=1
        # Check if the abd-link is the one accepted
        if ACCEPTED_S_LINKS[i][ABD_LINK] not in proximate_fingers_with_abd_link :
            return False
    return True

def intersect(list1, list2):
    set1 = set(list1)
    set2 = set(list2)

    set3 = set1 & set2
    return list(set3)
    
def compute_accepted_combinations(multi_link_combo, simple_link_combo) :
    # Compute all possible combinations of finger other than the thumb and status
    print("\n\nCompute all possible combinations\n")
    fingers = [x for x in FINGERS if x != THUMB]
    finger_status_combinations = itertools.product(STATUS, repeat=len(fingers))
    finger_accepted_combinations = [[(finger, status) for finger,status in zip(fingers,statuses)] for statuses in finger_status_combinations]
    
    # # Remove unaccepted finger combinations
    finger_accepted_combinations = [combination for combination in finger_accepted_combinations if all([status in ACCEPTED_STATUSES[finger] for finger,status in combination])]
    
    # Handle multi-links combinations if not three side fingers have the same multi-link status
    new_finger_accepted_combinations = []
    for combination in finger_accepted_combinations :
        if has_multi_joints(combination) :
            if multi_link_combo and has_valid_multi_joints(combination) :
                new_finger_accepted_combinations.append(combination)
        else :
            new_finger_accepted_combinations.append(combination)
    finger_accepted_combinations = new_finger_accepted_combinations
    
    # Handle add-link and abd-link combinations
    # If a finger is a add-link, then the last side finger must be a abd-link
    new_finger_accepted_combinations = []
    for combination in finger_accepted_combinations :
        if has_add_or_abd_joints(combination) :
            if simple_link_combo and has_valid_add_and_abd_joints(combination) :
                new_finger_accepted_combinations.append(combination)
        else :
            new_finger_accepted_combinations.append(combination)
    finger_accepted_combinations = new_finger_accepted_combinations
    
    # Combine with the thumb states as one of the fingers
    # We would combine the thumb with the finger combinations with every thumb hover or touch
    # context if we needed to with the following line
    # accepted_combinations = [[x[0], x[1][0],x[1][1],x[1][2],x[1][3]]  for x in itertools.product(*[thumb_accepted_combinations, finger_accepted_combinations])]
    # However, we only want the thumb to be in the opened state except for the case where every finger is down
    # That is why we compure the following lines
    at_least_one_up = [[x[0], x[1][0],x[1][1],x[1][2],x[1][3]]  for x in itertools.product(*[[(THUMB, UP)], finger_accepted_combinations]) if not all([status == DOWN for finger,status in x[1]])]
    all_closed = [[x[0], x[1][0],x[1][1],x[1][2],x[1][3]]  for x in itertools.product(*[[(THUMB, DOWN)], finger_accepted_combinations]) if all([status == DOWN for finger,status in x[1]])]
    accepted_combinations = at_least_one_up + all_closed
    
    return accepted_combinations

######################################################################################################################

class LayerRef(object):
    """A wrapper around an Inkscape XML layer object plus some helper data for doing combination exports."""

    def __init__(self, source: etree.Element, logit):
        self.source = source
        self.id = source.attrib["id"]
        label_attrib_name = LayerRef.get_layer_attrib_name(source)
        self.label = source.attrib[label_attrib_name]
        self.children = list()
        self.parent = None

        self.export_specs = list()
        self.request_hidden_state = False
        self.requested_hidden = False
        self.sibling_ids = list()

        self.export_specs = ExportSpec.create_specs(self, logit)

    @staticmethod
    def get_layer_attrib_name(layer: etree.Element) -> str:
        return "{%s}label" % layer.nsmap['inkscape']
    
    def has_valid_export_spec(self):
        return len(self.export_specs) > 0

class ComboExport(inkex.Effect):
    """The core logic of exporting combinations of layers as images."""

    def __init__(self):
        super().__init__()
        self.arg_parser.add_argument("--path", type=str, dest="path", default="~/", help="The directory to export into")
        self.arg_parser.add_argument('-f', '--filetype', type=str, dest='filetype', default='jpeg', 
                                     help='Exported file type. One of [png|jpeg]')
        self.arg_parser.add_argument("--dpi", type=float, dest="dpi", default=90.0, help="DPI of exported image")
        self.arg_parser.add_argument("--ascii", type=inkex.Boolean, dest="ascii", default=False, 
                                     help="If true, removes non-ascii characters from layer names during export")
        self.arg_parser.add_argument("--lower", type=inkex.Boolean, dest="lower", default=False, 
                                     help="If true, foces the final file name to be lowercase")
        self.arg_parser.add_argument("--multi", type=inkex.Boolean, dest="multi", default=False, 
                                     help="Includes hand poses with 3 or more fingers linked")
        self.arg_parser.add_argument("--simple", type=inkex.Boolean, dest="simple", default=False, 
                                     help="Includes hand poses with 2 fingers linked")
        self.arg_parser.add_argument("--debug", type=inkex.Boolean, dest="debug", default=False, help="Print debug messages as warnings")
        self.arg_parser.add_argument("--five", type=inkex.Boolean, dest="five", default=False, help='Stop after processing five combination')
        self.arg_parser.add_argument("--dry", type=inkex.Boolean, dest="dry", default=False, help="Don't actually do all of the exports")

    def get_exported_layers(self, logit) :
        layers = self.get_layers()
        exported_layers=dict()
        # Figure out the groups of permutations.
        for layer in layers:
            if not layer.has_valid_export_spec():
                continue
            
            logit(f"Found valid layer '{layer.label}' with '{len(layer.export_specs)}' exports, it has {len(layer.children)} children.")
            for export in layer.export_specs:
                if export.finger not in exported_layers:
                    exported_layers[export.finger] = list()
                exported_layers[export.finger].append(export)

        logit(f"Found valid layers : {exported_layers}")
        return exported_layers
    
    def get_label_from_hand_pose(self, hand_pose):
        # Has as input a hand pose of the form [(finger, status), (finger, status), ...]
        # Returns a string of the form "finger1_status1_finger2_status2_..."
        label = ""
        for finger, status in hand_pose:
            label = label+"_"+finger.capitalize()+"_"+status.capitalize()
        return label[1:]

    def effect(self):
        logit = logging.warning if self.options.debug else logging.info
        logit(f"Options: {str(self.options)}")
    
        layers = self.get_exported_layers(logit)
        hand_poses = compute_accepted_combinations(self.options.multi, self.options.simple)
        
        count=1  # ounter to break on 5 first outputs
        for hand_pose in hand_poses:
            show, hide = [], []
            for finger, status in hand_pose :
                new_show, new_hide = self.update_show_hide(finger, status, layers, logit)
                show.extend(new_show)
                hide.extend(new_hide)
            if self.options.dry:
                logit(f"Skipping because --dry was specified")
                continue
            label = self.get_label_from_hand_pose(hand_pose)
            self.export_shown_layers(label, show, hide, logit)
            # Break on 5 first outputs for debug purposes
            if self.options.five and count==5:
                break
            count+=1
    
    def update_show_hide(self, finger, status, layers, logit) :
        logit(f"Update show hide (finger, status) : ({finger}, {status})")
        show = list()
        hide = list()
        
        # Get layer corresponding to finger and status in layers
        finger_layer = layers[finger]
        for finger_with_status in finger_layer :
            if finger_with_status.status == status :
                show.append(finger_with_status.layer.id)
            else :
                hide.append(finger_with_status.layer.id)
        return show, hide
    
    def export_shown_layers(self, label, show, hide, logit):
        label = f"{label}"
        if self.options.ascii:
            label = label.encode("ascii", "ignore").decode()
        if self.options.lower:
            label = label.lower()
            
        # Actually do the export into the destination path.
        output_path = os.path.expanduser(self.options.path)
        # Remove trailing slash for unix and windows
        if os.name == "nt":
            output_path = output_path.rstrip("\\")
        else :
            output_path = output_path.rstrip("/")
        if not os.path.exists(os.path.join(output_path)):
            logit(f"Creating directory path {output_path} because it does not exist")
            os.makedirs(os.path.join(output_path))

        # If OS is Windows, use a the CustomNamedTemporaryFile.
        if os.name == "nt":
            with CustomNamedTemporaryFile(suffix=".svg") as fp_svg:
                layer_dest_svg_path = fp_svg.name
                logit(f"Writing SVG to temporary location {layer_dest_svg_path}")
                self.export_layers(layer_dest_svg_path, show, hide)

                if self.options.filetype == "jpeg":
                    with CustomNamedTemporaryFile(suffix=".png") as fp_png:
                        logit(f"Writing PNG to temporary location {fp_png.name}")
                        self.export_to_png(layer_dest_svg_path, fp_png.name)
                        layer_dest_jpg_path = os.path.join(output_path, f"{label}.jpg")
                        logit(f"Writing JPEG to final location {layer_dest_jpg_path}")
                        self.convert_png_to_jpeg(fp_png.name, layer_dest_jpg_path)
                else:
                    layer_dest_png_path = os.path.join(output_path, f"{label}.png")
                    logit(f"Writing PNG to final location {layer_dest_png_path}")
                    self.export_to_png(layer_dest_svg_path, layer_dest_png_path)
        else : # Otherwise, use the standard NamedTemporaryFile.
            with tempfile.NamedTemporaryFile(suffix=".svg") as fp_svg:
                layer_dest_svg_path = fp_svg.name
                logit(f"Writing SVG to temporary location {layer_dest_svg_path}")
                self.export_layers(layer_dest_svg_path, show, hide)

                if self.options.filetype == "jpeg":
                    with tempfile.NamedTemporaryFile(suffix=".png") as fp_png:
                        logit(f"Writing PNG to temporary location {fp_png.name}")
                        self.export_to_png(layer_dest_svg_path, fp_png.name)
                        layer_dest_jpg_path = os.path.join(output_path, f"{label}.jpg")
                        logit(f"Writing JPEG to final location {layer_dest_jpg_path}")
                        self.convert_png_to_jpeg(fp_png.name, layer_dest_jpg_path)
                else:
                    layer_dest_png_path = os.path.join(output_path, f"{label}.png")
                    logit(f"Writing PNG to final location {layer_dest_png_path}")
                    self.export_to_png(layer_dest_svg_path, layer_dest_png_path)
                    
    def get_layers(self) -> list:
        svg_layers = self.document.xpath('//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS)
        layers = []

        # Find all of our "valid" layers.
        for layer in svg_layers:
            label_attrib_name = LayerRef.get_layer_attrib_name(layer)
            if label_attrib_name not in layer.attrib:
                continue
            layers.append(LayerRef(layer, logit))

        # Create the layer hierarchy (children and parents).
        for layer in layers:
            for other in layers:
                for child in layer.source.getchildren():
                    if child is other.source:
                        layer.children.append(other)
                if layer.source.getparent() is other.source:
                    layer.parent = other 

        return layers

    def export_layers(self, dest: str, show: list, hide: list):
        logit = logging.warning if self.options.debug else logging.info
        doc = copy.deepcopy(self.document)
        for layer in doc.xpath('//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS):
            id = layer.attrib["id"]
            label_attrib_name = LayerRef.get_layer_attrib_name(layer)
            label = layer.attrib[label_attrib_name]

            if id in show:
                layer.attrib['style'] = 'display:inline'
                # logit(f" ... showing layer '{label}'")
            if id in hide:
                layer.attrib['style'] = 'display:none'
                # logit(f" ... hiding layer '{label}'")
        doc.write(dest)

    def export_to_png(self, svg_path: str, output_path: str):
        logit = logging.warning if self.options.debug else logging.info
        command = f"inkscape --export-type=\"png\" -d {self.options.dpi} --export-filename=\"{output_path}\" \"{svg_path}\""
        # logit(f"Running command '{command}'")
       
        if os.name == "nt":
            p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else :
            p = subprocess.Popen(command.encode("utf-8"), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        output, err = p.communicate()
        logit(f"stdout:\n{output}")
        logit(f"stderr:\n{err}")

    def convert_png_to_jpeg(self, png_path: str, output_path: str):
        logit = logging.warning if self.options.debug else logging.info
        command = f"convert \"{png_path}\" \"{output_path}\""
        # logit(f"Running command '{command}'")

        p = subprocess.Popen(command.encode("utf-8"), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        output, err = p.communicate()
        logit(f"stdout:\n{output}")
        logit(f"stderr:\n{err}")

#######################################################################################################################

class CustomNamedTemporaryFile: 
    """
    MODIFIED FROM : https://stackoverflow.com/questions/23212435/permission-denied-to-write-to-my-temporary-file
    This custom implementation is needed because of the following limitation of tempfile.NamedTemporaryFile:

    > Whether the name can be used to open the file a second time, while the named temporary file is still open,
    > varies across platforms (it can be so used on Unix; it cannot on Windows NT or later).
    """
    def __init__(self, mode='wb', suffix="", delete=True):
        self._mode = mode
        self._delete = delete
        self.suffix = suffix

    def __enter__(self):
        # Generate a random temporary file name
        file_name = os.path.join(tempfile.gettempdir(), os.urandom(24).hex())+self.suffix
        # Ensure the file is created
        open(file_name, "x").close()
        # Open the file in the given mode
        self._tempFile = open(file_name, self._mode)
        return self._tempFile

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._tempFile.close()
        if self._delete:
            os.remove(self._tempFile.name)

######################################################################################################################

class ExportSpec(object):
    """A description of how to export a layer."""

    ATTR_ID = "export-hand-poses"

    def __init__(self, spec: str, layer: object, finger: str, status: str):
        self.layer = layer
        self.spec = spec
        self.finger = finger
        self.status = status

    @staticmethod
    def create_specs(layer, logit) -> list:
        """Extracts '[finger],[status]' pairs from the layer's ATTR_ID attribute and returns them as a 
           list of ExportSpec. A RuntimeError is raised if any are incorrectly formatted. 
        """
        result = list()
        if ExportSpec.ATTR_ID not in layer.source.attrib:
            return result
        
        spec = layer.source.attrib[ExportSpec.ATTR_ID]
        for finger_selector in spec.split(";"):
            gs_split = finger_selector.split(",")
            if len(gs_split) != 2:
                raise RuntimeError(f"layer '{layer.label}'(#{layer.id}) has an invalid form '{gs_split}'. " +
                                   f"Expected format is '[finger],[status]'")

            finger = gs_split[0]
            status = gs_split[1]
            if finger not in FINGERS:
                raise RuntimeError(f"layer '{layer.label}'(#{layer.id}) has an invalid finger '{finger}'. " +
                                   f"Only the following are valid: {str(FINGERS)}")
            if status not in STATUS:
                raise RuntimeError(f"layer '{layer.label}'(#{layer.id}) has an invalid status '{status}'. " +
                                   f"Only the following are valid: {str(STATUS)}")

            result.append(ExportSpec(spec, layer, finger, status))

        return result

######################################################################################################################

def _main():
    effect = ComboExport()
    effect.run()
    exit()

if __name__ == "__main__":
    _main()

#######################################################################################################################
