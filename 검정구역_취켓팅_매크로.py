import ctypes
import sys
import threading
import time
import traceback

import pyautogui
from pynput.keyboard import Key, Listener
from pynput.mouse import Button as MouseButton, Controller
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from components import (
    Button,
    Caption,
    LinkButton,
    Panel,
    RegionPicker,
    Row,
    SectionTitle,
    SlotRow,
    StatusBar,
    TextInput,
    Title,
    stylesheet,
)


# ============================================================
# 1. 전역 변수 / 상태
# ============================================================

mouse_controller = Controller()

# 마우스 좌표
a_position = None
b_position = None
f_position = None
g_position = None
h_position = None

# 색상
rgb_value = (0, 0, 0)

# 매크로 상태
running = False
run_id = 0  # 시작할 때마다 1씩 늘린다. 번호가 바뀌면 이전 루프는 스스로 끝난다.

# 색상 탐색 영역
rectangle_start = None
rectangle_end = None
region_picker = None  # 드래그 창. 참조를 안 잡아두면 바로 사라진다.

# 리스너
listener = None

# 옵션
click_delay = 3
REFRESH_EVERY = 20 * 60  # 초

# 테마
theme_mode = "light"


# ============================================================
# 2. GUI 안전 업데이트
# ============================================================

# Qt 위젯은 GUI 스레드에서만 건드릴 수 있으므로
# 매크로 / 키보드 스레드에서는 시그널로 GUI 스레드에 넘긴다.
class GuiBridge(QObject):
    call = Signal(object)

    @Slot(object)
    def run(self, fn):
        fn()


def run_on_gui(fn):
    gui_bridge.call.emit(fn)


# state: idle / info / running / error / found
def update_status(text, state="info"):
    def _update():
        status_bar.set_status(text, state)
        panel.set_highlight(state == "found")
    run_on_gui(_update)


def set_slot(key, value):
    run_on_gui(lambda: slots[key].set_value(value))


# ============================================================
# 3. 좌표 저장 함수
# ============================================================

def save_position_a():
    global a_position
    a_position = mouse_controller.position
    set_slot("a", a_position)


def save_position_b():
    global b_position
    b_position = mouse_controller.position
    set_slot("b", b_position)


def save_position_f():
    global f_position
    f_position = mouse_controller.position
    set_slot("f", f_position)


def save_position_g():
    global g_position
    g_position = mouse_controller.position
    set_slot("g", g_position)


def save_position_h():
    global h_position
    h_position = mouse_controller.position
    set_slot("h", h_position)


# ============================================================
# 4. RGB 관련 함수
# ============================================================

def save_rgb_value():
    global rgb_value

    x, y = mouse_controller.position
    screenshot = pyautogui.screenshot()
    rgb_value = screenshot.getpixel((x, y))

    run_on_gui(update_color_display)


def modify_rgb_value():
    global rgb_value

    new_rgb = rgb_entry.text().strip()

    try:
        new_rgb = new_rgb.strip("()")
        r, g, b = map(int, new_rgb.split(","))

        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            raise ValueError

        rgb_value = (r, g, b)

    except ValueError:
        update_status(
            "색은 (255, 0, 0)처럼 입력하세요",
            "error",
        )

    update_color_display()
    rgb_entry.clearFocus()


def update_color_display():
    color_row.cap.set_color(rgb_value)
    rgb_entry.setText(str(rgb_value))


# ============================================================
# 5. 클릭 간격 함수
# ============================================================

def update_click_delay():
    global click_delay

    try:
        new_delay = float(time_entry.text())

        if new_delay <= 0:
            raise ValueError

        click_delay = new_delay

        if running:
            update_status(f"찾는 중 ({click_delay:g}초 간격)", "running")
        else:
            update_status(f"클릭 간격을 {click_delay:g}초로 바꿨어요")

    except ValueError:
        update_status(
            "간격은 0보다 큰 숫자로 입력하세요",
            "error",
        )

    time_entry.setText(f"{click_delay:g}")
    time_entry.clearFocus()


# ============================================================
# 6. 매크로 시작 / 정지
# ============================================================

def start_clicking():
    global running
    global run_id

    if a_position is None or b_position is None:
        update_status(
            "A와 B 위치부터 저장하세요",
            "error",
        )
        return

    running = True
    run_id += 1

    update_status(f"찾는 중 ({click_delay:g}초 간격)", "running")

    start_button.setEnabled(False)
    stop_button.setEnabled(True)

    threading.Thread(
        target=alternate_clicks_and_detect,
        args=(run_id,),
        daemon=True,
    ).start()


def stop_clicking():
    global running

    running = False

    update_status("멈췄어요", "idle")

    def _update():
        start_button.setEnabled(True)
        stop_button.setEnabled(False)

    run_on_gui(_update)


# ============================================================
# 7. A ↔ B 반복 클릭 (+ 20분마다 새로고침)
# ============================================================

def click(position):
    mouse_controller.position = position
    mouse_controller.click(MouseButton.left, 1)


# 마우스를 쓰는 일은 전부 이 스레드 하나에서 차례로 해서 서로 엉키지 않게 한다.
def alternate_clicks_and_detect(my_run):
    def alive():
        return running and run_id == my_run

    last_refresh = time.monotonic()

    try:
        while alive():
            click(a_position)
            time.sleep(click_delay)

            if not alive():
                return

            click(b_position)
            time.sleep(click_delay)

            if not alive():
                return

            if rectangle_start and rectangle_end:
                detect_and_click_color_in_rectangle()

            if alive() and time.monotonic() - last_refresh >= REFRESH_EVERY:
                refresh_page()
                last_refresh = time.monotonic()

    except Exception as error:
        traceback.print_exc()
        # 조용히 죽으면 '찾는 중'으로 남으니 멈추고 알린다.
        if run_id == my_run:
            stop_clicking()
            update_status(f"오류로 멈췄어요: {error}", "error")


# ============================================================
# 8. 20분마다 새로고침
# ============================================================

def refresh_page():
    pyautogui.press("f5")
    time.sleep(0.2)

    for position in (g_position, h_position):
        if position:
            click(position)
            time.sleep(0.2)


# ============================================================
# 9. 색상 탐색 영역 설정
# ============================================================

def pick_region():
    global region_picker

    # 매크로가 마우스를 움직이는 동안에는 드래그가 꼬인다.
    if running:
        update_status("정지한 뒤에 영역을 그리세요", "error")
        return

    region_picker = RegionPicker(save_region)
    region_picker.show()


def save_region(start, end):
    global rectangle_start
    global rectangle_end

    rectangle_start = start
    rectangle_end = end

    set_slot("c", f"{start} ~ {end}")


# ============================================================
# 10. 지정 RGB 색상 탐색
# ============================================================

def detect_and_click_color_in_rectangle():

    if rectangle_start is None or rectangle_end is None:
        update_status(
            "C를 눌러 찾을 영역부터 그리세요",
            "error",
        )
        return

    x1, y1 = rectangle_start
    x2, y2 = rectangle_end

    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)

    width = x2 - x1
    height = y2 - y1

    if width <= 0 or height <= 0:
        update_status(
            "찾을 영역을 다시 그리세요",
            "error",
        )
        return

    screenshot = pyautogui.screenshot(
        region=(x1, y1, width, height)
    )

    # 픽셀이 RGB 3바이트씩 이어져 있어서, 3의 배수 위치에서 찾은 것만 진짜 픽셀이다.
    # 위 줄부터 왼쪽→오른쪽 순서로 찾는다.
    pixels = screenshot.tobytes()
    target = bytes(rgb_value)
    index = pixels.find(target)
    while index != -1 and index % 3:
        index = pixels.find(target, index + 1)

    if index == -1:
        return

    click_x = x1 + index // 3 % screenshot.width
    click_y = y1 + index // 3 // screenshot.width

    click((click_x, click_y))

    # 정지 문구가 발견 문구를 덮지 않도록 먼저 멈춘다.
    stop_clicking()

    update_status(
        f"빈자리를 눌렀어요 ({click_x}, {click_y})",
        "found",
    )

    if f_position:
        time.sleep(0.1)
        click(f_position)

        update_status(
            "좌석지정 완료까지 눌렀어요",
            "found",
        )


# ============================================================
# 11. 키보드 이벤트
# ============================================================

user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = ctypes.c_void_p


def macro_window_active():
    return user32.GetForegroundWindow() == main_hwnd


def on_press(key):
    # 드래그 창이 포커스를 못 받았을 때도 Esc로 취소되게 한다.
    if key == Key.esc and region_picker is not None:
        run_on_gui(region_picker.close)
        return

    try:
        key_char = key.char.lower()
    except AttributeError:
        return

    # 정지는 어디서나 받는다. 매크로가 브라우저를 누르면 이 창이 뒤로 가기 때문.
    if key_char == "i":
        stop_clicking()
        return

    # 나머지는 매크로 창이 맨 앞일 때만 받아서, 다른 곳에서 타자 쳐도 안 켜지게 한다.
    if not macro_window_active():
        return

    if key_char == "a":
        save_position_a()
    elif key_char == "b":
        save_position_b()
    elif key_char == "c":
        run_on_gui(pick_region)
    elif key_char == "e":
        save_rgb_value()
    elif key_char == "f":
        save_position_f()
    elif key_char == "g":
        save_position_g()
    elif key_char == "h":
        save_position_h()


# ============================================================
# 12. 키보드 리스너
# ============================================================

def start_listener():
    global listener

    listener = Listener(on_press=on_press)
    listener.start()


def stop_listener():
    global listener

    if listener:
        listener.stop()
        listener = None


# ============================================================
# 13. 테마 관련
# ============================================================

def apply_theme():
    app.setStyleSheet(stylesheet(theme_mode))


def toggle_theme():
    global theme_mode

    if theme_mode == "light":
        theme_mode = "dark"
        theme_button.setText("라이트 모드")
    else:
        theme_mode = "light"
        theme_button.setText("다크 모드")

    apply_theme()


# ============================================================
# 14. 종료 함수
# ============================================================

def close_program():
    global running

    running = False
    stop_listener()


# ============================================================
# 15. GUI 생성
# ============================================================

app = QApplication(sys.argv)

gui_bridge = GuiBridge()
gui_bridge.call.connect(gui_bridge.run)

window = QWidget()
window.setWindowTitle("검정구역 취켓팅 매크로")
window.setMinimumWidth(420)
main_hwnd = int(window.winId())  # 단축키를 받을지 볼 때 맨 앞 창과 비교한다

main_layout = QVBoxLayout(window)
main_layout.setContentsMargins(16, 16, 16, 12)
main_layout.setSpacing(8)


# ============================================================
# 16. 제목 줄 (제목 / 테마 / 종료)
# ============================================================

theme_button = LinkButton("다크 모드", toggle_theme)
exit_button = LinkButton("종료", app.quit)

header = QHBoxLayout()
header.addWidget(Title("검정구역 취켓팅 매크로"))
header.addStretch()
header.addWidget(theme_button)
header.addSpacing(12)
header.addWidget(exit_button)

main_layout.addLayout(header)


# ============================================================
# 17. 신호등 상자 (상태 / 시작 · 정지)
# ============================================================

status_bar = StatusBar("대기 중")

start_button = Button("시작", "green", start_clicking)
stop_button = Button("정지 (I)", "red", stop_clicking)
stop_button.setEnabled(False)

button_row = QHBoxLayout()
button_row.setSpacing(8)
button_row.addWidget(start_button)
button_row.addWidget(stop_button)

panel = Panel(status_bar, button_row)

main_layout.addWidget(panel)


# ============================================================
# 18. 키 목록 (매크로가 도는 순서대로)
# ============================================================

# A, B, C는 없으면 빈자리를 못 찾으니 필수 (저장 전 노랑)
slots = {
    "a": SlotRow("A", "좌석영역 1", required=True),
    "b": SlotRow("B", "좌석영역 2", required=True),
    "c": SlotRow("C", "찾을 영역", empty="C를 누르고 드래그", required=True),
    "f": SlotRow("F", "좌석지정 완료"),
    "g": SlotRow("G", "새로고침 계속"),
    "h": SlotRow("H", "지정석 펼치기"),
}

time_entry = TextInput(f"{click_delay:g}", 48, update_click_delay)
rgb_entry = TextInput("", 110, modify_rgb_value)
color_row = Row("E", "찾을 색", rgb_entry)

for widget in [
    Caption("이 창을 한 번 클릭해 두고, 브라우저 위에 마우스만 올린 채 키를 누르면 그 위치가 저장돼요."),
    SectionTitle("번갈아 클릭"),
    slots["a"],
    slots["b"],
    Row("", "클릭 간격", time_entry, QLabel("초")),
    SectionTitle("빈자리 찾기"),
    slots["c"],
    color_row,
    SectionTitle("찾은 뒤"),
    slots["f"],
    SectionTitle("20분마다 새로고침한 뒤"),
    slots["g"],
    slots["h"],
]:
    main_layout.addWidget(widget)

main_layout.addStretch()


# ============================================================
# 19. 초기화 / 실행
# ============================================================

apply_theme()
update_color_display()
start_listener()

# 종료 버튼 / 창 닫기 모두 여기로 모인다.
app.aboutToQuit.connect(close_program)

window.show()
sys.exit(app.exec())
