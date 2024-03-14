from struct import Struct
from enum import IntFlag

class HeaderFlags(IntFlag):
    ValidLayerOpacity = 1

# Spec version : commit 10dda30a15a58d09e561a59594f348b4db3a4405
class Header(object):
    header_format = (
        "<I" # File size
        + "H" # Magic Number (0xA5E0)
        + "H" # Frames
        + "H" # Width in pixels
        + "H" # Height in pixels
        + "H" # Color depth/bits per pixel
        + "I" # Flags (1: layer opacity is valid)
        + "H" # Speed (deprecated)
        + "4x" # Set as 0
        + "4x" # set as 0
        + "B" # Palette mask/alpha
        + "3x" # "Ignore these bytes"
        + "H" # Number of colors (0 == 256 for older files)
        + "B" #  Pixel width (for pixel ratio)
        + "B" # Pixel height (for pixel ratio)
        + "h" # grid's x position
        + "h" # grid's y position
        + "H" # Grid width (0: no grid)
        + "H" # Grid height (0: no grid)
        + "84x" # Future proofing
    )
    # Note I'm not sure if the combinations of all bitmasks must fill all the bits counted in the tile ID.
    header_size = 128

    def __init__(self, data, data_offset = 0):
        header_struct = Struct(Header.header_format)

        (
            self.filesize,
            self.magic_number,
            self.num_frames,
            self.width,
            self.height,
            self.color_depth,
            self.flags,
            self.speed_deprecated,
            self.palette_mask,
            self.num_colors,
            self.pixel_width,
            self.pixel_height,
            self.grid_x_position,
            self.grid_y_position,
            self.grid_width,
            self.grid_height
        ) = header_struct.unpack_from(data, data_offset)

        if self.magic_number != 0xA5E0:
            raise ValueError('Incorrect magic number, expected {:x}, got {:x}'.format(0xA5E0, self.magic_number))

class Frame(object):
    frame_format = '<IHHH6x'
    frame_size = 16

    def __init__(self, data, data_offset = 0):
        frame_struct = Struct(Frame.frame_format)
        (
            self.size,
            self.magic_number,
            self.num_chunks,
            self.frame_duration
        ) = frame_struct.unpack_from(data, data_offset)

        if self.magic_number != 0xF1FA:
            raise ValueError('Incorrect magic number, expected {:x}, got {:x}'.format(0xF1FA, self.magic_number))
