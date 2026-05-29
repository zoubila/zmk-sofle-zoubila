#!/usr/bin/env python3
import argparse
import re
import sys
import struct
import zlib
from pathlib import Path


TARGET_WIDTH = 160
TARGET_HEIGHT = 68


def read_chunks(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")

    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        yield chunk_type, chunk_data
        offset += 12 + length


def paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def unpack_png(path):
    width = height = bit_depth = color_type = interlace = None
    palette = []
    transparency = b""
    idat = bytearray()

    for chunk_type, chunk_data in read_chunks(path.read_bytes()):
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
        elif chunk_type == b"PLTE":
            palette = [tuple(chunk_data[i : i + 3]) for i in range(0, len(chunk_data), 3)]
        elif chunk_type == b"tRNS":
            transparency = chunk_data
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)

    if interlace != 0:
        raise ValueError(f"{path}: interlaced PNGs are not supported")

    channel_count = {
        0: 1,
        2: 3,
        3: 1,
        4: 2,
        6: 4,
    }.get(color_type)
    if channel_count is None:
        raise ValueError(f"{path}: unsupported PNG color type {color_type}")

    if color_type != 3 and bit_depth != 8:
        raise ValueError(f"{path}: only 8-bit non-paletted PNGs are supported")

    bits_per_pixel = channel_count * bit_depth
    scanline_len = (width * bits_per_pixel + 7) // 8
    filter_bpp = max(1, (bits_per_pixel + 7) // 8)
    raw = zlib.decompress(bytes(idat))

    rows = []
    offset = 0
    prev = [0] * scanline_len
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        current = list(raw[offset : offset + scanline_len])
        offset += scanline_len

        for i, value in enumerate(current):
            left = current[i - filter_bpp] if i >= filter_bpp else 0
            up = prev[i]
            upper_left = prev[i - filter_bpp] if i >= filter_bpp else 0
            if filter_type == 1:
                current[i] = (value + left) & 0xFF
            elif filter_type == 2:
                current[i] = (value + up) & 0xFF
            elif filter_type == 3:
                current[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                current[i] = (value + paeth(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"{path}: unsupported PNG filter {filter_type}")

        rows.append(current)
        prev = current

    return width, height, color_type, bit_depth, palette, transparency, rows


def palette_index(row, x, bit_depth):
    if bit_depth == 8:
        return row[x]
    bit_offset = x * bit_depth
    byte = row[bit_offset // 8]
    shift = 8 - bit_depth - (bit_offset % 8)
    mask = (1 << bit_depth) - 1
    return (byte >> shift) & mask


def png_to_luma(path):
    width, height, color_type, bit_depth, palette, transparency, rows = unpack_png(path)
    pixels = []

    for row in rows:
        out = []
        for x in range(width):
            if color_type == 0:
                r = g = b = row[x]
                a = 255
            elif color_type == 2:
                base = x * 3
                r, g, b = row[base : base + 3]
                a = 255
            elif color_type == 3:
                index = palette_index(row, x, bit_depth)
                r, g, b = palette[index]
                a = transparency[index] if index < len(transparency) else 255
            elif color_type == 4:
                base = x * 2
                r = g = b = row[base]
                a = row[base + 1]
            else:
                base = x * 4
                r, g, b, a = row[base : base + 4]

            if a < 255:
                r = (r * a + 255 * (255 - a)) // 255
                g = (g * a + 255 * (255 - a)) // 255
                b = (b * a + 255 * (255 - a)) // 255
            out.append((299 * r + 587 * g + 114 * b) // 1000)
        pixels.append(out)

    return pixels


def rotate_clockwise(pixels):
    height = len(pixels)
    width = len(pixels[0])
    return [[pixels[height - 1 - y][x] for y in range(height)] for x in range(width)]


def resize_cover_nearest(pixels, target_width, target_height):
    source_height = len(pixels)
    source_width = len(pixels[0])
    scale = max(target_width / source_width, target_height / source_height)
    crop_width = target_width / scale
    crop_height = target_height / scale
    crop_x = (source_width - crop_width) / 2
    crop_y = (source_height - crop_height) / 2

    out = []
    for y in range(target_height):
        source_y = min(source_height - 1, max(0, int(crop_y + (y + 0.5) / scale)))
        row = []
        for x in range(target_width):
            source_x = min(source_width - 1, max(0, int(crop_x + (x + 0.5) / scale)))
            row.append(pixels[source_y][source_x])
        out.append(row)
    return out


def pack_i1(pixels):
    data = []
    for row in pixels:
        for start in range(0, len(row), 8):
            byte = 0
            for bit, value in enumerate(row[start : start + 8]):
                if value >= 128:
                    byte |= 1 << (7 - bit)
            data.append(byte)
    return data


def symbol_name(path):
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", path.stem).strip("_").lower()
    if not stem or stem[0].isdigit():
        stem = f"img_{stem}"
    return f"nice_view_custom_{stem}"


def c_array(values, indent="        "):
    lines = []
    for offset in range(0, len(values), 16):
        chunk = values[offset : offset + 16]
        lines.append(indent + ", ".join(f"0x{value:02x}" for value in chunk) + ",")
    return "\n".join(lines)


def convert_image(path):
    pixels = png_to_luma(path)
    source_height = len(pixels)
    source_width = len(pixels[0])
    if (source_width, source_height) not in (
        (TARGET_WIDTH, TARGET_HEIGHT),
        (TARGET_HEIGHT, TARGET_WIDTH),
    ):
        print(
            f"warning: {path} is {source_width}x{source_height}; best results need "
            f"{TARGET_HEIGHT}x{TARGET_WIDTH} portrait or {TARGET_WIDTH}x{TARGET_HEIGHT} landscape",
            file=sys.stderr,
        )

    if len(pixels) > len(pixels[0]):
        pixels = rotate_clockwise(pixels)
    pixels = resize_cover_nearest(pixels, TARGET_WIDTH, TARGET_HEIGHT)
    return pack_i1(pixels)


def write_outputs(images, output_path, header_path):
    image_entries = []
    source = [
        "/* Generated by scripts/generate_art.py. Do not edit by hand. */",
        "",
        "#include <lvgl.h>",
        "#include <stddef.h>",
        '#include "nice_view_custom_art.h"',
        "",
        "#ifndef LV_ATTRIBUTE_MEM_ALIGN",
        "#define LV_ATTRIBUTE_MEM_ALIGN",
        "#endif",
        "",
    ]

    if not images:
        raise ValueError("at least one PNG image is required in nice_view_custom/images")

    for image_path in images:
        name = symbol_name(image_path)
        image_data = convert_image(image_path)
        map_name = f"{name}_map"
        image_entries.append(name)

        source.extend(
            [
                f"#ifndef LV_ATTRIBUTE_IMG_{name.upper()}",
                f"#define LV_ATTRIBUTE_IMG_{name.upper()}",
                "#endif",
                "",
                f"const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST "
                f"LV_ATTRIBUTE_IMG_{name.upper()} uint8_t {map_name}[] = {{",
                "#if CONFIG_NICE_VIEW_WIDGET_INVERTED",
                "        0xff, 0xff, 0xff, 0xff, /* Color of index 0 */",
                "        0x00, 0x00, 0x00, 0xff, /* Color of index 1 */",
                "#else",
                "        0x00, 0x00, 0x00, 0xff, /* Color of index 0 */",
                "        0xff, 0xff, 0xff, 0xff, /* Color of index 1 */",
                "#endif",
                "",
                c_array(image_data),
                "};",
                "",
                f"const lv_image_dsc_t {name} = {{",
                "    .header.cf = LV_COLOR_FORMAT_I1,",
                f"    .header.w = {TARGET_WIDTH},",
                f"    .header.h = {TARGET_HEIGHT},",
                f"    .data_size = sizeof({map_name}),",
                f"    .data = {map_name},",
                "};",
                "",
            ]
        )

    source.extend(
        [
            "const lv_image_dsc_t *const nice_view_custom_images[] = {",
            *[f"    &{name}," for name in image_entries],
            "};",
            "",
            f"const size_t nice_view_custom_image_count = {len(image_entries)};",
            "",
        ]
    )

    header = [
        "/* Generated by scripts/generate_art.py. Do not edit by hand. */",
        "",
        "#pragma once",
        "",
        "#include <lvgl.h>",
        "#include <stddef.h>",
        "",
        "extern const lv_image_dsc_t *const nice_view_custom_images[];",
        "extern const size_t nice_view_custom_image_count;",
        "",
    ]

    output_path.write_text("\n".join(source), encoding="ascii")
    header_path.write_text("\n".join(header), encoding="ascii")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--header", required=True, type=Path)
    parser.add_argument("--images", nargs="*", type=Path, default=[])
    args = parser.parse_args()

    images = sorted(args.images)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.header.parent.mkdir(parents=True, exist_ok=True)
    write_outputs(images, args.output, args.header)


if __name__ == "__main__":
    main()
