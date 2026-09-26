"""전역 단축키 (pynput).

keys는 매크로 창이 맨 앞이고 입력칸에서 타자 중이 아닐 때만 받는다. 다른 곳에서 타자 쳐도 안 켜지게.
always는 어디서나 받는다 (정지, 드래그 취소). 매크로가 돌면 브라우저를 눌러 창이 뒤로 가기 때문.
"""

import ctypes
import traceback

from pynput.keyboard import Listener

user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = ctypes.c_void_p


def foreground_window():
    return user32.GetForegroundWindow()


class Hotkeys:
    def __init__(self, window_id, keys, always, on_error):
        self.window_id = window_id
        self.keys = keys  # {"1": fn, "c": fn, ...}
        self.always = always  # {"i": fn, Key.esc: fn}
        self.on_error = on_error
        self.typing = False  # 매크로 창 입력칸에 포커스가 있으면 True (GUI 스레드가 바꾼다)
        self.listener = Listener(on_press=self.on_press)

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()

    def on_press(self, key):
        # 예외가 밖으로 나가면 pynput이 감지를 꺼 버려서 정지 키까지 먹통이 된다.
        try:
            char = getattr(key, "char", None)
            name = char.lower() if char else key

            if name in self.always:
                self.always[name]()
            elif name in self.keys and not self.typing and foreground_window() == self.window_id:
                self.keys[name]()

        except Exception as error:
            traceback.print_exc()
            self.on_error(error)
