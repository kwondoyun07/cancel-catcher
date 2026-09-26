import sys
import threading
import time

import pyautogui
from pynput.keyboard import Listener
from pynput.mouse import Button, Controller
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
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

# 색상 탐색 영역
rectangle_start = None
rectangle_end = None

# 스레드 / 리스너
listener = None
periodic_thread = None

# 옵션
click_delay = 3

# 테마
theme_mode = "light"


# ============================================================
# 2. 테마 설정
# ============================================================

themes = {
    "light": {
        "bg": "#f5f6f8",
        "surface": "#ffffff",
        "fg": "#222222",
        "sub_fg": "#666666",
        "border": "#dddddd",
        "entry_bg": "#ffffff",
        "entry_fg": "#222222",
        "start": "#2ecc71",
        "stop": "#e74c3c",
        "normal_button": "#e9ecef",
        "normal_button_fg": "#222222",
        "status": "#3478f6",
    },
    "dark": {
        "bg": "#181a1f",
        "surface": "#24272e",
        "fg": "#f1f1f1",
        "sub_fg": "#aaaaaa",
        "border": "#3a3e46",
        "entry_bg": "#30343b",
        "entry_fg": "#ffffff",
        "start": "#2ecc71",
        "stop": "#e74c3c",
        "normal_button": "#343840",
        "normal_button_fg": "#f1f1f1",
        "status": "#5b9cff",
    },
}


# ============================================================
# 3. GUI 안전 업데이트
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


def update_status(text, fg=None):
    def _update():
        status_label.setText(text)
        if fg:
            status_label.setStyleSheet(f"color: {fg};")
    run_on_gui(_update)


def set_label_text(label, text):
    run_on_gui(lambda: label.setText(text))


# ============================================================
# 4. 좌표 저장 함수
# ============================================================

def save_position_a():
    global a_position
    a_position = mouse_controller.position
    set_label_text(label_a, f"좌석영역 1 (A)   {a_position}")


def save_position_b():
    global b_position
    b_position = mouse_controller.position
    set_label_text(label_b, f"좌석영역 2 (B)   {b_position}")


def save_position_f():
    global f_position
    f_position = mouse_controller.position
    set_label_text(label_f, f"좌석지정 완료 (F)   {f_position}")


def save_position_g():
    global g_position
    g_position = mouse_controller.position
    set_label_text(label_g, f"새로고침 계속 (G)   {g_position}")


def save_position_h():
    global h_position
    h_position = mouse_controller.position
    set_label_text(label_h, f"지정석 펼치기 (H)   {h_position}")


# ============================================================
# 5. RGB 관련 함수
# ============================================================

def save_rgb_value():
    global rgb_value

    x, y = mouse_controller.position
    screenshot = pyautogui.screenshot()
    rgb_value = screenshot.getpixel((x, y))

    def _update():
        rgb_entry.setText(str(rgb_value))
        update_color_display()

    run_on_gui(_update)


def modify_rgb_value():
    global rgb_value

    new_rgb = rgb_entry.text().strip()

    try:
        new_rgb = new_rgb.strip("()")
        r, g, b = map(int, new_rgb.split(","))

        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            raise ValueError

        rgb_value = (r, g, b)
        update_color_display()

    except ValueError:
        QMessageBox.critical(
            window,
            "RGB 오류",
            "RGB 형식이 올바르지 않습니다.\n\n예: (255, 0, 0)",
        )

    rgb_entry.setText(str(rgb_value))
    rgb_entry.clearFocus()


def update_color_display():
    r, g, b = rgb_value
    color_hex = f"#{r:02x}{g:02x}{b:02x}"
    color_display.setText(f"RGB {rgb_value}")
    color_display.setStyleSheet(f"background: {color_hex};")


# ============================================================
# 6. 클릭 간격 함수
# ============================================================

def update_click_delay():
    global click_delay

    try:
        new_delay = float(time_entry.text())

        if new_delay <= 0:
            raise ValueError

        click_delay = new_delay

        update_status(
            f"클릭 간격이 {click_delay}초로 설정되었습니다.",
            current_theme()["status"],
        )

    except ValueError:
        QMessageBox.critical(
            window,
            "입력 오류",
            "0보다 큰 숫자를 입력하세요.\n\n예: 3 또는 1.5",
        )

    time_entry.setText(str(click_delay))
    time_entry.clearFocus()


# ============================================================
# 7. 매크로 시작 / 정지
# ============================================================

def start_clicking():
    global running
    global periodic_thread

    if a_position is None or b_position is None:
        update_status(
            "좌석영역 1(A), 2(B)를 먼저 지정하세요.",
            "#e74c3c",
        )
        return

    running = True

    update_status("● 매크로 실행 중", "#2ecc71")

    start_button.setEnabled(False)
    stop_button.setEnabled(True)

    threading.Thread(
        target=alternate_clicks_and_detect,
        daemon=True,
    ).start()

    if not periodic_thread or not periodic_thread.is_alive():
        periodic_thread = threading.Thread(
            target=execute_periodic_tasks,
            daemon=True,
        )
        periodic_thread.start()


def stop_clicking():
    global running

    running = False

    update_status(
        "● 매크로 정지",
        current_theme()["status"],
    )

    def _update():
        start_button.setEnabled(True)
        stop_button.setEnabled(False)

    run_on_gui(_update)


# ============================================================
# 8. A ↔ B 반복 클릭
# ============================================================

def alternate_clicks_and_detect():
    while running:

        if a_position:
            mouse_controller.position = a_position
            mouse_controller.click(Button.left, 1)

        time.sleep(click_delay)

        if not running:
            return

        if b_position:
            mouse_controller.position = b_position
            mouse_controller.click(Button.left, 1)

        time.sleep(click_delay)

        if not running:
            return

        if rectangle_start and rectangle_end:
            detect_and_click_color_in_rectangle()

        if not running:
            return


# ============================================================
# 9. 20분 주기 작업
# ============================================================

def execute_periodic_tasks():
    while running:

        for _ in range(1200):
            if not running:
                return
            time.sleep(1)

        if not running:
            return

        pyautogui.press("f5")
        time.sleep(0.2)

        if g_position:
            mouse_controller.position = g_position
            mouse_controller.click(Button.left, 1)
            time.sleep(0.2)

        if h_position:
            mouse_controller.position = h_position
            mouse_controller.click(Button.left, 1)
            time.sleep(0.2)


# ============================================================
# 10. 색상 탐색 영역 설정
# ============================================================

def start_rectangle():
    global rectangle_start

    rectangle_start = mouse_controller.position

    set_label_text(
        label_rectangle_start,
        f"탐색 시작 (C)   {rectangle_start}",
    )


def end_rectangle():
    global rectangle_end

    rectangle_end = mouse_controller.position

    set_label_text(
        label_rectangle_end,
        f"탐색 끝 (D)   {rectangle_end}",
    )

    if running:
        detect_and_click_color_in_rectangle()


# ============================================================
# 11. 지정 RGB 색상 탐색
# ============================================================

def detect_and_click_color_in_rectangle():

    if rectangle_start is None or rectangle_end is None:
        update_status(
            "탐색 영역(C / D)을 먼저 지정하세요.",
            "#e74c3c",
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
            "탐색 영역의 크기가 올바르지 않습니다.",
            "#e74c3c",
        )
        return

    screenshot = pyautogui.screenshot(
        region=(x1, y1, width, height)
    )

    target_color = rgb_value

    for x in range(screenshot.width):

        if not running:
            return

        for y in range(screenshot.height):

            if screenshot.getpixel((x, y)) == target_color:

                click_x = x1 + x
                click_y = y1 + y

                mouse_controller.position = (click_x, click_y)
                mouse_controller.click(Button.left, 1)

                update_status(
                    f"색상 발견 → ({click_x}, {click_y})",
                    "#2ecc71",
                )

                stop_clicking()

                if f_position:
                    time.sleep(0.1)

                    mouse_controller.position = f_position
                    mouse_controller.click(Button.left, 1)

                    update_status(
                        f"좌석지정 완료 → {f_position}",
                        "#2ecc71",
                    )

                return


# ============================================================
# 12. 키보드 이벤트
# ============================================================

def on_press(key):
    try:
        key_char = key.char.lower()

        if key_char == "a":
            save_position_a()
        elif key_char == "b":
            save_position_b()
        elif key_char == "c":
            start_rectangle()
        elif key_char == "d":
            end_rectangle()
        elif key_char == "e":
            save_rgb_value()
        elif key_char == "f":
            save_position_f()
        elif key_char == "g":
            save_position_g()
        elif key_char == "h":
            save_position_h()
        elif key_char == "i":
            stop_clicking()

    except AttributeError:
        pass


# ============================================================
# 13. 키보드 리스너
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
# 14. 테마 관련
# ============================================================

def current_theme():
    return themes[theme_mode]


def apply_theme():
    theme = current_theme()

    app.setStyleSheet(f"""
        QWidget {{
            background: {theme["bg"]};
            color: {theme["fg"]};
            font-family: "Malgun Gothic";
            font-size: 9pt;
        }}
        #title {{
            font-size: 18pt;
            font-weight: bold;
        }}
        #subtitle {{
            color: {theme["sub_fg"]};
        }}
        QGroupBox {{
            background: {theme["surface"]};
            border: 1px solid {theme["border"]};
            border-radius: 6px;
            margin-top: 24px;
            font-size: 10pt;
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 4px;
        }}
        QGroupBox QLabel {{
            background: {theme["surface"]};
            font-size: 9pt;
            font-weight: normal;
        }}
        #color_display {{
            border: 1px solid {theme["border"]};
        }}
        #status {{
            padding: 8px;
            font-size: 10pt;
            font-weight: bold;
        }}
        QLineEdit {{
            background: {theme["entry_bg"]};
            color: {theme["entry_fg"]};
            border: 1px solid {theme["border"]};
            padding: 4px;
            font-size: 9pt;
            font-weight: normal;
        }}
        QPushButton {{
            background: {theme["normal_button"]};
            color: {theme["normal_button_fg"]};
            border: none;
            padding: 7px;
            font-size: 9pt;
            font-weight: normal;
        }}
        #start, #stop {{
            color: white;
            padding: 8px;
            font-size: 10pt;
            font-weight: bold;
        }}
        #start {{
            background: {theme["start"]};
        }}
        #stop {{
            background: {theme["stop"]};
        }}
        #start:disabled, #stop:disabled {{
            background: {theme["border"]};
            color: {theme["sub_fg"]};
        }}
    """)


def toggle_theme():
    global theme_mode

    if theme_mode == "light":
        theme_mode = "dark"
        theme_button.setText("☀  라이트 모드")
    else:
        theme_mode = "light"
        theme_button.setText("🌙  다크 모드")

    apply_theme()


# ============================================================
# 15. 종료 함수
# ============================================================

def close_program():
    global running

    running = False
    stop_listener()


# ============================================================
# 16. GUI 생성
# ============================================================

app = QApplication(sys.argv)

gui_bridge = GuiBridge()
gui_bridge.call.connect(gui_bridge.run)

window = QWidget()
window.setWindowTitle("검정구역 취켓팅 매크로")
window.setMinimumWidth(460)

main_layout = QVBoxLayout(window)
main_layout.setContentsMargins(20, 20, 20, 20)
main_layout.setSpacing(6)


def add_group(title, widgets):
    group = QGroupBox(title)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(15, 10, 15, 10)

    for widget in widgets:
        layout.addWidget(widget)

    main_layout.addWidget(group)


# ============================================================
# 17. 상단 헤더
# ============================================================

title_label = QLabel("검정구역 취켓팅 매크로")
title_label.setObjectName("title")

subtitle_label = QLabel("단축키를 이용하여 좌표와 탐색 영역을 설정하세요.")
subtitle_label.setObjectName("subtitle")

main_layout.addWidget(title_label)
main_layout.addWidget(subtitle_label)


# ============================================================
# 18. 좌표 설정
# ============================================================

label_a = QLabel("좌석영역 1 (A)   지정 안됨")
label_b = QLabel("좌석영역 2 (B)   지정 안됨")
label_f = QLabel("좌석지정 완료 (F)   지정 안됨")
label_g = QLabel("새로고침 계속 (G)   지정 안됨")
label_h = QLabel("지정석 펼치기 (H)   지정 안됨")

add_group(
    "📍 좌표 설정",
    [label_a, label_b, label_f, label_g, label_h],
)


# ============================================================
# 19. 색상 탐색 영역
# ============================================================

label_rectangle_start = QLabel("탐색 시작 (C)   지정 안됨")
label_rectangle_end = QLabel("탐색 끝 (D)   지정 안됨")

add_group(
    "🔲 색 탐색 영역",
    [label_rectangle_start, label_rectangle_end],
)


# ============================================================
# 20. 옵션 설정
# ============================================================

rgb_title = QLabel("🎨 탐색 색상")

# 입력칸은 클릭했을 때만 포커스를 받아서
# 단축키(A ~ I)가 입력칸에 타이핑되지 않게 한다.
rgb_entry = QLineEdit("(0, 0, 0)")
rgb_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
rgb_entry.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
rgb_entry.returnPressed.connect(modify_rgb_value)

color_display = QLabel("E 키로 색상 지정")
color_display.setObjectName("color_display")
color_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
color_display.setMinimumHeight(36)

time_title = QLabel("⏱ 클릭 간격")

time_entry = QLineEdit("3")
time_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
time_entry.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
time_entry.returnPressed.connect(update_click_delay)

add_group(
    "⚙ 옵션 설정",
    [rgb_title, rgb_entry, color_display, time_title, time_entry],
)


# ============================================================
# 21. 제어 영역
# ============================================================

start_button = QPushButton("▶  매크로 시작")
start_button.setObjectName("start")
start_button.clicked.connect(start_clicking)

stop_button = QPushButton("■  매크로 정지")
stop_button.setObjectName("stop")
stop_button.setEnabled(False)
stop_button.clicked.connect(stop_clicking)

theme_button = QPushButton("🌙  다크 모드")
theme_button.clicked.connect(toggle_theme)

exit_button = QPushButton("✕  프로그램 종료 (I)")
exit_button.clicked.connect(app.quit)

status_label = QLabel("● 매크로 정지")
status_label.setObjectName("status")
status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

add_group(
    "🕹 매크로 제어",
    [start_button, stop_button, theme_button, exit_button, status_label],
)

main_layout.addStretch()


# ============================================================
# 22. 초기화 / 실행
# ============================================================

apply_theme()
start_listener()

# 종료 버튼 / 창 닫기 모두 여기로 모인다.
app.aboutToQuit.connect(close_program)

window.show()
sys.exit(app.exec())
