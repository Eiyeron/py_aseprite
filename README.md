# This library

This library intends to offer a quick and low-level read-only access to an
[Aseprite](http://aseprite.org/) file, allowing further operations like
extracting cells, palettes and the other data the file contains.

This is a library designed with read-only operations in mind as it was
originally forked out from an automatic file-to-source-code conversion tool.
There isn't any plans to add conversion from 

Aseprite's [file format][specs]
is quite straightforward. It's mainly composed of chunks that have a type
identifier, allowing parsing them case by case.

## Notice

This is a project that was mostly designed for my own uses, thus support of this library
for other projects isn't guaranteed. I'm slowly preparing the project to make it
releasable but it's not my main objective for now. Here be dragons.


# What could be done 

- Support linked cels. Currently, there is stored info on a cel to determine
    if it's a linked cel and which frame the link goes to. There is nothing to fetch
the data from the cel link origin though.
- Define inner structures instead of using dictionaries
- Assume they'll only be a CelChunk per frame and link it when possible to the FrameChunk.
- Blending modes. I'm using this library with a simple blitting logic to manage
pictures in indexed mode. This allows me to stick to the palette. If the file
isn't in indexed mode, add support to blending modes like Dodge, Overlay and
other.
    + Take a look on how to implement Opacity and alpha blendeing on the top of that
- Provide examples. My current tool is not really the most bugfree/codestyle
compliant/pretty code I ever made. Maybe a smaller example or a better written
one should be added to show how to use the library.
- Unit testing. I haven't found a canoncial set of files to test the whole
extent of features the format offers. Unit testing would be a good way to make
sureeverything is and will stay in place.
- Either wrap the existing classes in an optional class easier to manipulate or rewrite
the parser.


# How to use the library

The minimal way to load a file looks like this

```python
from aseprite import AsepriteFile

with open('my_file.aseprite', 'rb') as f:
    parsed_file = AsepriteFile(f.read())
```

The class does the whole file parsing job, allows you to inspect its header
through `AsepriteFle.header`, frames through `AsepriteFile.frames` orlayers
through `Aseprite.layers` or `Aseprite.layer_tree` if you want to browse the
layers through the layer group hierarchy.

## Accessing pixels

Following the [specs], each layer in a frame owns their own chunks which one of
them may be a CelChunk. This holds the data of a layer at a specific frame. For
the needs of the library, the data is uncompressed on load. `CelChunk.data` is
always a 1D array, so using indices this this form `[y * width + x]` is currently
highly recommanded. Note that in indexed mode the data is not a dict but only an index
relating to the picture's palette.


## Blitting/Merging layers into picture

To explain a the process in a more detailled way than the spec file, let's see how the layer merging process works. If Aseprite has an UI with a layer list
where each layer will be applied from bottom-to-top, they're stored in the reverse position in the file. Note that groups are locally merged before being
merged like a normal image layer one level higher. This means that a structure looking like this in Aseprite:

-   `Layer 3`
-   `Group 1`
    -   `Layer 2`
    -   `Layer 2 Bis`
-   `Layer 1.5`
-   `Layer 1`

Will be processed this way:

1.  Create the target picture
2.  Load `Layer 1` to the target picture
3.  Blit `Layer 1.5` over the target picture
4.  Process `Group 1`
    1.  Load `Layer 2 Bis` into a new temporary canvas
    2.  Blit `Layer 2` into that temporary canvas
    3.  Blit the temporary canvas over the target picture
5.  Blit `Layer 3` over the target picture


### Dirty example of a blitting procedure

I'm linking here an (dirty) example straight from my aseprite->code tool. As it only process indexed-mode sprites, I cut some corners on the blend mode, but a tool
supporting them may derivate from this idea and add support for said feature.

``` python
class BlitFrame(object):
    """A blit frame just holds a frame's data and its dimension."""
    def __init__(self, width, height, default_color):
        self.width = width
        self.height = height
        self.data = [[default_color for col in range(width)] for row in range(height)]

    def basic_blit_cel_on_self(self, cel, mask_index):
        """Take a CelChubk and apply its data over the BlitFrame's. Assumes that the data is in indexed mode."""
        for x in range(cel.data['width']):
            for y in range(cel.data['height']):
                current_index = cel.data["data"][y * cel.data['width'] + x]
                if current_index != mask_index:
                    self.data[y + cel.y_pos][x + cel.x_pos] = current_index

    def basic_blit_on(self, target, mask_index):
        """Blits self's data over another BlitFrame"""
        for y, pixel_slice in enumerate(self.data):
            for x, pixel in enumerate(pixel_slice):
                if pixel != mask_index:
                    target.data[y][x] = pixel

def merge_frame_cels(picture, num_frame, mask_index):
    """Given an AsepriteFile picture and a frame number, this function will return a BlitFrame containing the final result for the current frame.
    Assumes that the picture is in indexed mode.
    """
    def indexed_blit_single_layer(picture, layer, cels, num_frame, frame_output):
        current_cel = cels[layer.layer_index]
        if current_cel:
            frame_output.basic_blit_cel_on_self(current_cel, picture.header.palette_mask)

    def indexed_blit_layer_group(picture, layer, cels, num_frame, frame_output):
        temporary_frame = BlitFrame(frame_output.width, frame_output.height, picture.header.palette_mask)
        for child in layer.children:
            if isinstance(child, LayerGroupChunk):
                indexed_blit_layer_group(picture, child, cels, num_frame, frame_output)
            else:
                indexed_blit_single_layer(picture, child, cels, num_frame, frame_output)

        temporary_frame.basic_blit_on(frame_output, picture.header.palette_mask)

    cel_slice = [None] * len(picture.layers)
    for chunk in picture.frames[num_frame].chunks:
        if isinstance(chunk, CelChunk):
            cel_slice[chunk.layer_index] = chunk
    frame_output = BlitFrame(picture.header.width, picture.header.height, picture.header.palette_mask)
    for layer in picture.layer_tree:
        if isinstance(layer, LayerGroupChunk):
            indexed_blit_layer_group(picture, layer, cel_slice, num_frame, frame_output)
        else:
            indexed_blit_single_layer(picture, layer, cel_slice, num_frame, frame_output)

    return frame_output
```

[specs]: (https://github.com/aseprite/aseprite/blob/master/docs/ase-file-specs.md)