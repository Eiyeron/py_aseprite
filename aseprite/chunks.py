from struct import Struct
import zlib
import math

# They're not 0-terminated strings, but they're prefixed with their size
def parse_string(data, string_offset):
    (string_length,) = Struct('<H').unpack_from(data, string_offset)

    (string_name, ) = Struct('<{}s'.format(string_length)).unpack_from(data, string_offset+2)
    return (string_length + 2, string_name.decode('utf-8'))


class Chunk(object):
    chunk_format = '<IH'

    def __init__(self, data, data_offset=0):
        chunk_struct = Struct(Chunk.chunk_format)
        (self.chunk_size, self.chunk_type) = chunk_struct.unpack_from(data, data_offset)

class OldPaleteChunk_0x0004(Chunk):
    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)

        packet_struct = Struct('<BB')
        color_packet_struct = Struct('<BBB')

        (self.num_packets,) = Struct('<H').unpack_from(data, data_offset+6)
        self.packets = []

        packet_offset = data_offset + 8
        for packet_index in range(self.num_packets):
            packet = {'colors':[]}
            (packet['previous_packet_skip'], num_colors) = packet_struct.unpack_from(data, packet_offset)
            packet_offset += 2
            for color in range(0, num_colors):
                (red, blue, green) = color_packet_struct.unpack_from(data, packet_offset)
                packet['colors'].append([red, blue, green])
                packet_offset += 3

            self.packets.append(packet)

class OldPaleteChunk_0x0011(Chunk):
    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)

        packet_struct = Struct('<BB')
        color_packet_struct = Struct('<BBB')
        self.num_packets = Struct('<H').unpack_from(data, data_offset)
        self.packets = []

        packet_offset = data_offset + 6
        for packet_index in range(self.num_packets):
            packet = {'colors':[]}
            (packet.previous_packet_skip, num_colors) = packet_struct.unpack_from(data, packet_offset)
            packet_offset += 2
            for color in range(0, num_colors):
                (red, blue, green) = color_packet_struct.unpack_from(data, packet_offset)
                packet['colors'].append([red, blue, green])
                packet_offset += 3

            self.packets.append(packet)

class LayerChunk(Chunk):
    layer_format = '<HHHHHHB3x'

    def __init__(self, data, layer_index, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        layer_struct = Struct(LayerChunk.layer_format)
        (
            self.flags,
            self.layer_type,
            self.layer_child_level,
            self.default_width,
            self.default_height,
            self.blend_mode,
            self.opacity
        ) = layer_struct.unpack_from(data, data_offset + 6)
        _, self.name = parse_string(data, data_offset + 6 + layer_struct.size)
        self.layer_index = layer_index


class LayerGroupChunk(LayerChunk):
    def __init__(self, base_layer : LayerChunk):
        """Constructed from its base version"""
        self.flags = base_layer.flags
        self.layer_type = base_layer.layer_type
        self.layer_child_level = base_layer.layer_child_level
        self.default_width = base_layer.default_width
        self.default_height = base_layer.default_height
        self.blend_mode = base_layer.blend_mode
        self.opacity = base_layer.opacity
        self.name = base_layer.name
        self.layer_index = base_layer.layer_index
        self.children = []



class CelChunk(Chunk):
    cel_format = '<HhhBH7x'
    cel_type_format = '<HH'

    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        cel_struct = Struct(CelChunk.cel_format)
        (
            self.layer_index,
            self.x_pos,
            self.y_pos,
            self.opacity,
            self.cel_type
        ) = cel_struct.unpack_from(data, data_offset + 6)
        cel_offset = data_offset + cel_struct.size + 6
        cel_struct = Struct(CelChunk.cel_type_format)
        if self.cel_type == 0:
            self.data = {}
            (
                self.data['width'],
                self.data['height']
            ) = cel_struct.unpack_from(data, cel_offset)
            start_range = cel_offset + cel_struct.size
            end_range = data_offset + self.chunk_size
            self.data['data'] = data[start_range:end_range]
        elif self.cel_type == 1:
            self.data = {'link': Struct('<H').unpack_from(data, cel_offset)}
        elif self.cel_type == 2:
            self.data = {}
            (
                self.data['width'],
                self.data['height']
            ) = cel_struct.unpack_from(data, cel_offset)
            start_range = cel_offset + cel_struct.size
            end_range = data_offset + self.chunk_size
            self.data['data'] = zlib.decompress(data[start_range:end_range])

class CelExtraChunk(Chunk):
    celextra_format = '<HLLLL16x'
    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        cel_struct = Struct(CelExtraChunk.celextra_format)
        (
            self.flags,
            self.precise_x_pos,
            self.precise_y_pos,
            self.cel_width,
            self.cel_height
        ) = cel_struct.unpack_from(data, data_offset + 6)

class MaskChunk(Chunk):
    mask_format = '<hhHH8x'

    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        mask_struct = Struct(MaskChunk.mask_format)
        (
            self.x_pos,
            self.y_pos,
            self.width,
            self.height
        ) = mask_struct.unpack_from(data, data_offset + 6)

        name_offset = data_offset + 6 + mask_struct.size
        string_size, self.name = parse_string(data, name_offset)

        start_range = name_offset + string_size
        end_range = start_range + math.ceil(self.height*((self.width+7)/8))
        self.bitmap = data[start_range:start_range:end_range]

class PathChunk(Chunk):
    pass

class FrameTagsChunk(Chunk):
    frametag_head_format = '<H8x'
    frametag_format = '<HHB8x3Bx'

    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        palette_struct = Struct(FrameTagsChunk.frametag_head_format)
        (num_tags,) = palette_struct.unpack_from(data, data_offset + 6)


        self.tags = []
        tag_offset = data_offset + palette_struct.size + 6

        palette_tag_struct = Struct(FrameTagsChunk.frametag_format)
        for index in range(num_tags):
            tag = {'color':{}}
            (
                tag['from'],
                tag['to'],
                tag['loop'],
                tag['color']['red'],
                tag['color']['green'],
                tag['color']['blue']
            ) = palette_tag_struct.unpack_from(data, tag_offset)
            self.tags.append(tag)
            tag_offset += palette_tag_struct.size
            string_size, tag['name'] = parse_string(data, tag_offset)
            tag_offset += string_size

class PaletteChunk(Chunk):
    palette_format = '<III8x'

    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        palette_struct = Struct(PaletteChunk.palette_format)
        (
            self.palette_size,
            self.first_color_index,
            self.last_color_index
        ) = palette_struct.unpack_from(data, data_offset + 6)
        color_struct = Struct('<HBBBB')
        self.colors = []

        color_offset = data_offset + 6 + palette_struct.size
        for index in range(self.first_color_index, self.last_color_index+1):
            color = {'name':None}
            (
                color['flags'],
                color['red'],
                color['blue'],
                color['green'],
                color['alpha']
            ) = color_struct.unpack_from(data, color_offset)
            color_offset += color_struct.size
            if color['flags'] & 1 != 0:
                string_size, color['name'] = parse_string(data, color_offset)
                color_offset += string_size

            self.colors.append(color)

class UserDataChunk(Chunk):
    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        userdata_offset = data_offset + 6
        (self.flags,) = Struct('<I').unpack_from(data, userdata_offset)
        userdata_offset += 4
        if self.flags & 1 != 0:
            string_size, self.string = parse_string(data, userdata_offset)
            userdata_offset += string_size
        if self.flags & 2 != 0:
            (
                self.red,
                self.green,
                self.blue,
                self.alpha
            ) = Struct('<BBBB').unpack_from(data, userdata_offset)

class SliceChunk(Chunk):
    slice_chunk_format = '<III'
    slice_format = '<IiiII'
    slice_key_format = '<IiiII'
    slice_bit_1_format = '<iiII'
    slice_bit_2_format = '<ii'


    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        slice_offset  = data_offset + 6

        slice_chunk_struct = Struct(SliceChunk.slice_chunk_format)
        num_slices, self.flags, self.reserved = slice_chunk_struct.unpack_from(data, slice_offset)
        slice_offset += slice_chunk_struct.size

        string_size, self.name = parse_string(data, slice_offset)
        slice_offset += string_size

        self.slices = []

        for i in range(num_slices):
            slice_struct = Struct(SliceChunk.slice_format)
            slice = {}
            (
                slice['start_frame'],
                slice['x'],
                slice['y'],
                slice['width'],
                slice['height']
            ) = slice_struct.unpack_from(data, slice_offset)
            slice_offset += slice_struct.size
            if self.flags & 1 != 0:
                slice_bit_1_struct = Struct(SliceChunk.slice_bit_1_format)
                slice['center'] = {}
                (
                    slice['center']['x'],
                    slice['center']['y'],
                    slice['center']['width'],
                    slice['center']['height']
                ) = slice_bit_1_struct.unpack_from(data, slice_offset)
                slice_offset += slice_bit_1_struct.size
            if self.flags & 2 != 0:
                slice_bit_2_struct = Struct(SliceChunk.slice_bit_2_format)
                slice['pivot'] = {}
                (
                    slice['pivot']['x'],
                    slice['pivot']['y'],
                ) = slice_bit_2_struct.unpack_from(data, slice_offset)
                slice_offset += slice_bit_2_struct.size
            self.slices.append(slice)