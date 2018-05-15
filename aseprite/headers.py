from struct import Struct


class Header(object):
    header_format = '<IHHHHHI2x8xB3xHBB92x'
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
            self.palette_mask,
            self.num_colors,
            self.pixel_width,
            self.pixel_height
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
