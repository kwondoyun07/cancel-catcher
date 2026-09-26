"""매크로 핵심 동작 확인 (Qt 없이, 실제 마우스 · 키보드 안 씀). 실행: uv run python -m tests.test_macro"""

import threading
import time

from PIL import Image
from pynput.keyboard import Key, KeyCode

from cancel_catcher import hotkeys, macro, screen
from cancel_catcher.macro import Macro

SEAT = (10, 20, 30)


def test_parse_color():
    assert screen.parse_color("#7C68EE") == (124, 104, 238)
    assert screen.parse_color("7c68ee") == (124, 104, 238)
    assert screen.parse_color("#abc") == (0xAA, 0xBB, 0xCC)
    assert screen.parse_color("124, 104, 238") == (124, 104, 238)
    assert screen.parse_color(" (124 104 238) ") == (124, 104, 238)
    assert screen.to_hex((124, 104, 238)) == "#7C68EE"

    for bad in ["", "abc", "#12345", "256, 0, 0", "1, 2", "red"]:
        try:
            screen.parse_color(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r}를 받아들이면 안 됨")


def test_find_color():
    image = Image.new("RGB", (50, 40), (200, 200, 200))
    image.putpixel((0, 1), (0, 10, 20))  # 두 픽셀에 걸쳐 10 20 30 바이트가 생긴다 (픽셀 경계 아님)
    image.putpixel((1, 1), (30, 0, 0))
    assert screen.find_color(image, SEAT) is None

    image.putpixel((3, 9), SEAT)  # 더 왼쪽이지만 아래 줄
    image.putpixel((7, 5), SEAT)  # 위 줄이 먼저
    assert screen.find_color(image, SEAT) == (7, 5)


class FakeInput:
    """마우스 · 키보드 대신 누른 것을 기록만 한다."""

    def __init__(self, log):
        self.log = log
        self.position = (0, 0)

    def click(self, button, count):
        self.log.append(self.position)

    def tap(self, key):
        self.log.append(key)


def ready_macro(log, statuses, screen_image):
    m = Macro(on_status=lambda text, state: statuses.append((text, state)))
    m.mouse = m.keyboard = FakeInput(log)
    m.area_count = 2
    m.areas[:2] = [(1, 1), (2, 2)]
    m.region = (100, 200, 150, 240)
    m.color = SEAT
    m.click_delay = 0.02
    screen.grab = lambda *box: screen_image
    return m


def loops(m):
    return [t for t in threading.enumerate() if getattr(t, "_target", None) == m._loop]


def test_start_needs_everything():
    statuses = []
    m = Macro(on_status=lambda text, state: statuses.append((text, state)))
    m.start()
    assert not m.running
    assert statuses[-1] == ("구역 1, 2, 찾을 영역, 찾을 색부터 정하세요", "error")


def test_restart_keeps_one_loop():
    log, statuses = [], []
    m = ready_macro(log, statuses, Image.new("RGB", (50, 40)))
    m.start()
    m.stop()
    m.start()  # 이전 루프가 자는 동안 다시 시작
    time.sleep(0.2)
    assert len(loops(m)) == 1
    m.stop()
    time.sleep(0.1)
    assert not loops(m)


def test_found_clicks_seat_then_done_button():
    log, statuses = [], []
    image = Image.new("RGB", (50, 40))
    image.putpixel((7, 5), SEAT)
    m = ready_macro(log, statuses, image)
    m.buttons["f"] = (9, 9)
    m.start()
    time.sleep(0.3)
    assert log == [(1, 1), (107, 205), (9, 9)], log  # 구역 1을 누른 뒤 바로 찾음
    assert not m.running and statuses[-1] == ("좌석지정 완료까지 눌렀어요", "found")


def test_error_stops_with_message():
    log, statuses = [], []
    m = ready_macro(log, statuses, None)

    def broken(*box):
        raise OSError("screen grab failed")

    screen.grab = broken
    m.start()
    time.sleep(0.2)
    assert not m.running and not loops(m)
    assert statuses[-1] == ("오류로 멈췄어요: screen grab failed", "error")


def test_refresh_runs_in_order():
    log, statuses = [], []
    m = ready_macro(log, statuses, Image.new("RGB", (50, 40)))
    m.buttons["g"], m.buttons["h"] = (7, 7), (8, 8)
    macro.REFRESH_EVERY = 0  # 매 바퀴 새로고침
    try:
        m.start()
        time.sleep(0.6)
        m.stop()
        time.sleep(0.5)
    finally:
        macro.REFRESH_EVERY = 20 * 60
    assert log[:5] == [(1, 1), (2, 2), Key.f5, (7, 7), (8, 8)], log


def test_hotkeys():
    calls = []

    def broken():
        raise RuntimeError("boom")

    keys = hotkeys.Hotkeys(
        123,
        keys={"1": lambda: calls.append("1"), "e": broken},
        always={"i": lambda: calls.append("i")},
        on_error=lambda error: calls.append(f"error: {error}"),
    )

    hotkeys.foreground_window = lambda: 999  # 다른 창이 맨 앞
    keys.on_press(KeyCode.from_char("1"))
    keys.on_press(KeyCode.from_char("i"))  # 정지는 어디서나
    assert calls == ["i"]

    hotkeys.foreground_window = lambda: 123  # 매크로 창이 맨 앞
    keys.on_press(KeyCode.from_char("1"))
    keys.typing = True  # 입력칸에서 타자 중
    keys.on_press(KeyCode.from_char("1"))
    keys.typing = False
    keys.on_press(KeyCode.from_char("e"))  # 예외가 나도 밖으로 안 나가야 감지가 안 꺼진다
    keys.on_press(Key.f1)  # 글자 없는 키는 무시
    assert calls == ["i", "1", "error: boom"], calls


if __name__ == "__main__":
    real_grab = screen.grab
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            screen.grab = real_grab
            print("ok", name)
