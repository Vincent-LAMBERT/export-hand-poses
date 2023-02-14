# Inkscape Plugin: Export Hand Poses
Inkscape v1.2.0+ plugin to export the hand poses corresponding to your SVG layers.
This plugin was developed using Nikolai Shkurkin's plugin export-layers-combo (https://github.com/nshkurkin/inkscape-export-layer-combos) as a base. 

## How it works

Open the `Layers` and `XML Editor` tabs. In the `XML Editor` select layer objects and add the attribute `export-hand-poses` to them and given them a value of the form `[finger],[status]`. 

* `[finger]` is the name of the finger the layer corresponds to. 
* `[status]` (one of `up, down, add-link, abd-linkd, multi-link`) controls the visibility of the layer and how combinations are formed with each finger. `add-link` and `abd-link` work in pair to create a link between two joined fingers. `multi-link` is used to create a link between multiple joined fingers.

You use the tool by running "**Extensions > Export > Export Hand Poses...**". Once you have configured your settings, you hit `Apply` to generate the combinations.

When you export images, the name of the image is of the form `[finger1]-[status1]-[finger2]-[...].png`.

## Working case
We aim to export hand poses from a single SVG file with multiple layers having the following structure.

```
 layer1
    layer1A   -  thumb, up
    layer1B   -  thumb, down
 layer2
    layer2A   -  index, up
    layer2B   -  index, down
    layer2C   -  index, add-link
    layer2D   -  index, multi-link
 layer3
    layer3A   -  middle, up
    layer3B   -  middle, down
    layer3C   -  middle, add-link
    layer3D   -  middle, abd-link
    layer3E   -  middle, multi-link
 layer4
    layer4A   -  ring, up
    layer4B   -  ring, down
    layer4C   -  ring, add-link
    layer4D   -  ring, abd-link
    layer4E   -  ring, multi-link
 layer5
    layer5A   -  pinky, up
    layer5B   -  pinky, down
    layer5C   -  pinky, abd-link
    layer5D   -  pinky, multi-link
```

When you run the tool, it will generate various hand poses corresponding to your designs. Please make sure your layers overlap correctly as the final results depends on the order of the layers.