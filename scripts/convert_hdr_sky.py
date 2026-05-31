"""Convierte cielos Radiance HDR a JPG liviano para MuseIQ App.

Uso:
  python3 scripts/convert_hdr_sky.py /ruta/mañana.hdr assets/skies/morning.jpg
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convertir Radiance HDR a JPG.")
    parser.add_argument("input", help="Archivo .hdr en formato Radiance RGBE.")
    parser.add_argument("output", help="Archivo .jpg de salida.")
    parser.add_argument("--quality", type=int, default=88)
    parser.add_argument("--key", type=float, default=0.42)
    return parser.parse_args()


def read_header(data: bytes) -> tuple[int, int, int]:
    offset = 0
    while True:
      line_end = data.find(b"\n", offset)
      if line_end < 0:
          raise RuntimeError("HDR sin cabecera valida.")

      line = data[offset:line_end].decode("ascii", errors="ignore").strip()
      offset = line_end + 1
      if line.startswith("-Y "):
          parts = line.split()
          if len(parts) != 4 or parts[2] != "+X":
              raise RuntimeError(f"Resolucion HDR no soportada: {line}")
          height = int(parts[1])
          width = int(parts[3])
          return width, height, offset


def read_scanline(data: bytes, offset: int, width: int) -> tuple[bytearray, int]:
    if width < 8 or width > 32767:
        raise RuntimeError("Solo se soporta HDR RLE moderno.")

    if data[offset] != 2 or data[offset + 1] != 2:
        raise RuntimeError("HDR sin codificacion RLE moderna.")

    encoded_width = (data[offset + 2] << 8) | data[offset + 3]
    if encoded_width != width:
        raise RuntimeError("Ancho de scanline HDR inconsistente.")

    offset += 4
    channels = [bytearray(width) for _ in range(4)]
    for channel in channels:
        cursor = 0
        while cursor < width:
            count = data[offset]
            offset += 1
            if count > 128:
                repeat_count = count - 128
                value = data[offset]
                offset += 1
                channel[cursor:cursor + repeat_count] = bytes([value]) * repeat_count
                cursor += repeat_count
            else:
                channel[cursor:cursor + count] = data[offset:offset + count]
                offset += count
                cursor += count

    scanline = bytearray(width * 4)
    for index in range(width):
        base = index * 4
        scanline[base] = channels[0][index]
        scanline[base + 1] = channels[1][index]
        scanline[base + 2] = channels[2][index]
        scanline[base + 3] = channels[3][index]
    return scanline, offset


def read_rgbe(path: Path) -> tuple[int, int, bytearray]:
    data = path.read_bytes()
    width, height, offset = read_header(data)
    rgbe = bytearray(width * height * 4)

    for row in range(height):
        scanline, offset = read_scanline(data, offset, width)
        start = row * width * 4
        rgbe[start:start + width * 4] = scanline

    return width, height, rgbe


def rgbe_to_linear(r: int, g: int, b: int, e: int) -> tuple[float, float, float]:
    if e == 0:
        return 0.0, 0.0, 0.0

    scale = math.ldexp(1.0, e - 136)
    return (r + 0.5) * scale, (g + 0.5) * scale, (b + 0.5) * scale


def estimate_exposure(rgbe: bytearray, key: float) -> float:
    log_sum = 0.0
    count = 0
    for offset in range(0, len(rgbe), 4):
        red, green, blue = rgbe_to_linear(
            rgbe[offset],
            rgbe[offset + 1],
            rgbe[offset + 2],
            rgbe[offset + 3],
        )
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        if luminance > 0.000001:
            log_sum += math.log(luminance)
            count += 1

    if count == 0:
        return 1.0

    log_average = math.exp(log_sum / count)
    return key / max(log_average, 0.000001)


def tone_map(value: float, exposure: float) -> int:
    mapped = 1.0 - math.exp(-value * exposure)
    corrected = max(0.0, min(1.0, mapped)) ** (1.0 / 2.2)
    return int(round(corrected * 255))


def convert(input_path: Path, output_path: Path, quality: int, key: float) -> None:
    width, height, rgbe = read_rgbe(input_path)
    exposure = estimate_exposure(rgbe, key)
    pixels = bytearray(width * height * 3)

    for pixel_index, offset in enumerate(range(0, len(rgbe), 4)):
        red, green, blue = rgbe_to_linear(
            rgbe[offset],
            rgbe[offset + 1],
            rgbe[offset + 2],
            rgbe[offset + 3],
        )
        output_offset = pixel_index * 3
        pixels[output_offset] = tone_map(red, exposure)
        pixels[output_offset + 1] = tone_map(green, exposure)
        pixels[output_offset + 2] = tone_map(blue, exposure)

    image = Image.frombytes("RGB", (width, height), bytes(pixels))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "JPEG", quality=quality, optimize=True)
    print(f"[Muse3D] Cielo convertido: {input_path} -> {output_path} ({width}x{height})")


def main() -> None:
    args = parse_args()
    convert(Path(args.input), Path(args.output), args.quality, args.key)


if __name__ == "__main__":
    main()
