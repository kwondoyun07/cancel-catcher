"""매크로 엔진. Qt를 모르고, 상태가 바뀌면 on_status(문구, 상태)만 부른다.

구역들을 차례로 누르고, 누를 때마다 찾을 영역에서 빈자리 색을 찾는다.
찾으면 그 자리와 좌석지정 완료(F)를 누르고 멈춘다.
20분마다 새로고침(F5 → 새로고침 계속 G → 지정석 펼치기 H)한다.
"""

import threading
import time
import traceback

from pynput.keyboard import Controller as Keyboard, Key
from pynput.mouse import Button, Controller as Mouse

from cancel_catcher import screen

MAX_AREAS = 10
REFRESH_EVERY = 20 * 60  # 초


class Macro:
    def __init__(self, on_status):
        # on_status(text, state)는 매크로 스레드에서도 불린다.
        # state: idle / info / running / error / found
        self.on_status = on_status
        self.mouse = Mouse()
        self.keyboard = Keyboard()

        self.areas = [None] * MAX_AREAS  # 구역 1~10 좌표
        self.area_count = 2
        self.region = None  # 찾을 영역 (left, top, right, bottom)
        self.color = None  # 찾을 색 (r, g, b)
        self.buttons = {"f": None, "g": None, "h": None}  # 좌석지정 완료 / 새로고침 계속 / 지정석 펼치기
        self.click_delay = 3

        self.running = False
        self.run_id = 0  # 시작할 때마다 1씩 늘린다. 번호가 바뀌면 이전 루프는 스스로 끝난다.

    def missing(self):
        """시작하려면 더 정해야 하는 것들"""
        areas = [str(n + 1) for n in range(self.area_count) if self.areas[n] is None]
        names = [f"구역 {', '.join(areas)}"] if areas else []
        if self.region is None:
            names.append("찾을 영역")
        if self.color is None:
            names.append("찾을 색")
        return names

    def start(self):
        missing = self.missing()
        if missing:
            self.on_status(f"{', '.join(missing)}부터 정하세요", "error")
            return

        self.running = True
        self.run_id += 1
        self.on_status(f"찾는 중 ({self.click_delay:g}초 간격)", "running")
        threading.Thread(target=self._loop, args=(self.run_id,), daemon=True).start()

    def stop(self):
        self.running = False
        self.on_status("멈췄어요", "idle")

    def click(self, position):
        self.mouse.position = position
        self.mouse.click(Button.left, 1)

    # 마우스를 쓰는 일은 전부 이 스레드 하나에서 차례로 해서 서로 엉키지 않게 한다.
    def _loop(self, my_run):
        def alive():
            return self.running and self.run_id == my_run

        last_refresh = time.monotonic()

        try:
            while alive():
                for position in self.areas[:self.area_count]:
                    if position is None:  # 도는 중에 구역 수를 늘린 경우
                        continue

                    self.click(position)
                    time.sleep(self.click_delay)

                    if not alive() or self._found():
                        return

                if time.monotonic() - last_refresh >= REFRESH_EVERY:
                    self._refresh()
                    last_refresh = time.monotonic()

        except Exception as error:
            traceback.print_exc()
            # 조용히 죽으면 '찾는 중'으로 남으니 멈추고 알린다.
            if self.run_id == my_run:
                self.running = False
                self.on_status(f"오류로 멈췄어요: {error}", "error")

    def _found(self):
        left, top, right, bottom = self.region
        spot = screen.find_color(screen.grab(left, top, right, bottom), self.color)
        if spot is None:
            return False

        x, y = left + spot[0], top + spot[1]
        self.click((x, y))
        self.running = False
        self.on_status(f"빈자리를 눌렀어요 ({x}, {y})", "found")

        if self.buttons["f"]:
            time.sleep(0.1)
            self.click(self.buttons["f"])
            self.on_status("좌석지정 완료까지 눌렀어요", "found")

        return True

    def _refresh(self):
        self.keyboard.tap(Key.f5)
        time.sleep(0.2)

        for key in ("g", "h"):
            if self.buttons[key]:
                self.click(self.buttons[key])
                time.sleep(0.2)
