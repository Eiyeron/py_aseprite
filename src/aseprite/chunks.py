import struct
from struct import Struct
import zlib
import math

# They're not 0-terminated strings, but they're prefixed with their size
def parse_string(data, string_offset):
    (string_length,) = Struct('<H').unpack_from(data, string_offset)

    (string_name, ) = Struct('<{}s'.format(string_length)).unpack_from(data, string_offset+2)
    return (string_length + 2, string_name.decode('utf-8'))


class Chunk(object):
    """Base class for all chunks."""
    chunk_format = '<IH'

    def __init__(self, data, data_offset=0):
        chunk_struct = Struct(Chunk.chunk_format)
        (self.chunk_size, self.chunk_type) = chunk_struct.unpack_from(data, data_offset)


class OldPaleteChunk_0x0004(Chunk):
    chunk_id = 0x0004

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
    chunk_id = 0x0011

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
    chunk_id = 0x2004
    layer_format = (
        '<H' # Flags
        + 'H' # Layer type
        + 'H' # Layer child level
        + 'H' # Default layer width (ignored)
        + 'H' # Default layer height (ignored)
        + 'H' # Blend mode
        + 'B' # Opacity (only valid if the header's flag is set)
        + '3x' # Padding
    )
    layer_tileset_index_format = '<I'

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
        name_data_length, self.name = parse_string(data, data_offset + 6 + layer_struct.size)
        self.layer_index = layer_index

        if self.layer_type == 2:
            layer_tileset_data_offset =  data_offset + 6 + layer_struct.size + name_data_length
            layer_tileset_struct = Struct(LayerChunk.layer_tileset_index_format)
            (self.tileset_index, ) = layer_tileset_struct.unpack_from(data, layer_tileset_data_offset)


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
    chunk_id = 0x2005
    cel_format = '<HhhBH7x'
    cel_type_format = '<HH'
    cel_tilemap_format = (
        '<H' # Width in tiles
        'H' # height in tiles
        'H' # Bits per tile (hardcoded as 32 bits per tile for now)
        'I' # Bitmask for tile ID (harcoded as 0x1fffffff for now)
        'I' # Bitmask for X flip
        'I' # Bitmask for Y flip
        'I' # Bitmask for diagonal flip ("swap X/y axis")
        '10x' # Reserved
    )

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
        cel_end_offset = data_offset + cel_struct.size + 6
        self.data = {}
        if self.cel_type == 0:
            cel_type_struct = Struct(CelChunk.cel_type_format)
            (
                self.data['width'],
                self.data['height']
            ) = cel_type_struct.unpack_from(data, cel_end_offset)
            start_range = cel_end_offset + cel_struct.size
            end_range = data_offset + self.chunk_size
            self.data['data'] = data[start_range:end_range]
        elif self.cel_type == 1:
            self.data = {'link': Struct('<H').unpack_from(data, cel_end_offset)}
        elif self.cel_type == 2:
            (
                self.data['width'],
                self.data['height']
            ) = cel_struct.unpack_from(data, cel_end_offset)
            start_range = cel_end_offset + cel_struct.size
            end_range = data_offset + self.chunk_size
            self.data['data'] = zlib.decompress(data[start_range:end_range])
        elif self.cel_type == 3:
            cel_tilemap_struct = Struct(CelChunk.cel_tilemap_format)
            cel_tilemap_offset = cel_end_offset
            (
                self.data['width'],
                self.data['height'],
                self.data['bits_per_tile'],
                self.data['tile_id_bitmask'],
                self.data['flip_x_bitmask'],
                self.data['flip_y_bitmask'],
                self.data['flip_diagonal_bitmask'],
            ) = cel_tilemap_struct.unpack_from(data, cel_tilemap_offset)
            start_range = cel_tilemap_offset + cel_tilemap_struct.size
            end_range = data_offset + self.chunk_size
            self.data['data'] = zlib.decompress(data[start_range:end_range])
            # Is there always width * height tiles or can the tile array be smaller than that.
        else:
            print("Unsupported Cel chunk type {:04x}. Skipping.".format(self.cel_type))

    def unpack_tiles(self):
        """Basic helper to conver the raw data to an array containing tile ids for common tile id bit sizes."""
        # I might move that in a wrapper class to split the raw data loading from parsing.
        if self.cel_type != 2:
            return None
        tiles = []
        # Not really DRY, but it's not really at a good enough version.
        if self.data['bits_per_tile'] == 32:
            num_loaded_tiles = len(self.data['data']) // 4
            return struct.unpack('<' + num_loaded_tiles * 'I', self.data['data'])
        if self.data['bits_per_tile'] == 16:
            num_loaded_tiles = len(self.data['data']) // 2
            return struct.unpack('<' + num_loaded_tiles * 'H', self.data['data'])
        if self.data['bits_per_tile'] == 8:
            num_loaded_tiles = len(self.data['data']) // 1
            return struct.unpack('<' + num_loaded_tiles * 'B', self.data['data'])
        return None

class CelExtraChunk(Chunk):
    chunk_id = 0x2006
    celextra_format = '<LLLLL16x'

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


class ColorProfileChunk(Chunk):
    chunk_id = 0x2007
    color_profile_format = "<HHH8x"
    icc_profile_format = "<I"

    def __init__(self, data, data_offset=0):
        Chunk.__init__(self, data, data_offset)
        color_profile_struct = Struct(ColorProfileChunk.color_profile_format)
        color_profile_offset = data_offset + 6

        icc_profile_length_struct = Struct(ColorProfileChunk.icc_profile_format)
        icc_profile_offset = color_profile_offset + color_profile_struct.size
        icc_data_offset = icc_profile_offset + icc_profile_length_struct.size
        (
            self.use_color_profile,
            self.use_fixed_gamma,
            self.fixed_gamma
        ) = color_profile_struct.unpack_from(data, color_profile_offset)

        # Read ICC data
        if self.color_profile_format == 2:
            icc_data_length = icc_profile_length_struct.unpack_from(data, icc_profile_offset)
            self.icc_profile_data = data[icc_data_offset:icc_data_offset + icc_data_length]
        else:
            self.icc_profile_data = []


# TODO External File Chunk (0x2008)

class MaskChunk(Chunk):
    """According to the specs, this chunk is deprecated."""
    chunk_id = 0x2016
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
    """According to the specs, this chunk is never used."""
    chunk_id = 0x2017
    pass

# TODO Update the chunk format, it's currently missing data.
class FrameTagsChunk(Chunk):
    chunk_id = 0x2018
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
    chunk_id = 0x2019
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
                color['green'],
                color['blue'],
                color['alpha']
            ) = color_struct.unpack_from(data, color_offset)
            color_offset += color_struct.size
            if color['flags'] & 1 != 0:
                string_size, color['name'] = parse_string(data, color_offset)
                color_offset += string_size

            self.colors.append(color)

# TODO Update this chunk, it's missing properties and the property map.
class UserDataChunk(Chunk):
    chunk_id = 0x2020
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
        if self.flags & 4 != 0:
            print("Property map not yet supported, skipped.")

class SliceChunk(Chunk):
    chunk_id = 0x2022
    slice_chunk_format = '<III'
    slice_format = '<IiiII'
    slice_key_format = '<IiiII'
    slice_center_format = '<iiII'
    slice_pivot_format = '<ii'


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
                slice_center_struct = Struct(SliceChunk.slice_center_format)
                slice['center'] = {}
                (
                    slice['center']['x'],
                    slice['center']['y'],
                    slice['center']['width'],
                    slice['center']['height']
                ) = slice_center_struct.unpack_from(data, slice_offset)
                slice_offset += slice_center_struct.size
            if self.flags & 2 != 0:
                slice_pivot_struct = Struct(SliceChunk.slice_pivot_format)
                slice['pivot'] = {}
                (
                    slice['pivot']['x'],
                    slice['pivot']['y'],
                ) = slice_pivot_struct.unpack_from(data, slice_offset)
                slice_offset += slice_pivot_struct.size
            self.slices.append(slice)


class TilesetChunk(Chunk):
    chunk_id = 0x2023
    tileset_chunk_format = (
        '<I' # Tileset ID
        + 'I' # Tileset flags
        + 'I' # Number of tiles
        + 'H' # Tile width
        + 'H' # Tile height
        + 'h' # Base index (index of the first tile to show in the UI)
        + '14x'
    )
    tileset_chunk_external_id_format = (
        '<I' # External file ID (see External Files chunk)
        + 'I' # Tileset ID "in the external file"
    )
    tileset_chunk_compressed_tiles_format = (
        '<I' # Data length
    )

    def __init__(self, data, data_offset=0):
        slice_offset = data_offset + 6
        tileset_chunk_struct = Struct(TilesetChunk.tileset_chunk_format)
        tileset_name_offset = slice_offset + tileset_chunk_struct.size
        tileset_external_id_struct = Struct(TilesetChunk.tileset_chunk_external_id_format)
        tileset_compressed_data_struct = Struct(TilesetChunk.tileset_chunk_compressed_tiles_format)
        (
            self.tileset_id,
            self.tileset_flags,
            num_tiles,
            self.tile_width,
            self.tile_height,
            self.base_index
        ) = tileset_chunk_struct.unpack_from(data, slice_offset)
        string_data_length, self.layer_name = parse_string(data, tileset_name_offset)

        additional_data_offset = tileset_name_offset + string_data_length

        if self.tileset_flags & 1 != 0:
            (
                self.external_file_id,
                self.external_tileset_id
            ) = tileset_external_id_struct.unpack_from(data, additional_data_offset)
            additional_data_offset += tileset_external_id_struct.size

        if self.tileset_flags & 2 != 0:
            (compressed_data_length,) = tileset_compressed_data_struct.unpack_from(data, additional_data_offset)
            compressed_data_start = additional_data_offset + tileset_compressed_data_struct.size
            compressed_data_end = compressed_data_start + compressed_data_length
            compressed_data = data[compressed_data_start:compressed_data_end]
            self.tileset_image = zlib.decompress(compressed_data)