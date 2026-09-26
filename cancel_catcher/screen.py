"""화면 캡처와 색 찾기, 색 글자 해석.

좌표는 모든 모니터를 합친 실제 픽셀 좌표로, 마우스 좌표와 같다.
"""

import re

from PIL import ImageGrab

HEX_COLOR = re.compile(r"#?([0-9a-fA-F]{6})|#([0-9a-fA-F]{3})")


def grab(left, top, right, bottom):
    return ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)


def pixel_color(x, y):
    return grab(x, y, x + 1, y + 1).getpixel((0, 0))


def find_color(image, color):
    """image에서 color인 첫 픽셀의 (x, y). 위 줄부터 왼쪽 → 오른쪽으로 찾고, 없으면 None."""
    # 픽셀이 RGB 3바이트씩 이어져 있어서, 3의 배수 위치에서 찾은 것만 진짜 픽셀이다.
    pixels = image.convert("RGB").tobytes()
    target = bytes(color)
    index = pixels.find(target)
    while index != -1 and index % 3:
        index = pixels.find(target, index + 1)

    if index == -1:
        return None
    return index // 3 % image.width, index // 3 // image.width


def parse_color(text):
    """'#7C68EE', '7c68ee', '#abc', '124, 104, 238', '(124 104 238)' → (124, 104, 238).

    틀리면 ValueError.
    """
    text = text.strip()

    match = HEX_COLOR.fullmatch(text)
    if match:
        digits = match[1] or "".join(c * 2 for c in match[2])
        return tuple(bytes.fromhex(digits))

    r, g, b = (int(part) for part in re.split(r"[\s,]+", text.strip("()").strip()))
    if not all(0 <= value <= 255 for value in (r, g, b)):
        raise ValueError(text)
    return r, g, b


def to_hex(color):
    return "#{:02X}{:02X}{:02X}".format(*color)
