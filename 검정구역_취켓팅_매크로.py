import tkinter as tk
from tkinter import messagebox
from pynput.mouse import Controller, Button
from pynput.keyboard import Listener
import pyautogui
import threading
import time


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

def update_status(text, fg=None):
    def _update():
        status_label.config(text=text)
        if fg:
            status_label.config(fg=fg)
    root.after(0, _update)


def set_label_text(label, text):
    root.after(0, lambda: label.config(text=text))


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
        rgb_entry.config(state="normal")
        rgb_entry.delete(0, tk.END)
        rgb_entry.insert(0, str(rgb_value))
        rgb_entry.config(state="disabled")
        update_color_display()

    root.after(0, _update)


def modify_rgb_value(event=None):
    global rgb_value

    new_rgb = rgb_entry.get().strip()

    try:
        new_rgb = new_rgb.strip("()")
        r, g, b = map(int, new_rgb.split(","))

        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            raise ValueError

        rgb_value = (r, g, b)
        update_color_display()
        rgb_entry.config(state="disabled")

    except ValueError:
        messagebox.showerror(
            "RGB 오류",
            "RGB 형식이 올바르지 않습니다.\n\n예: (255, 0, 0)",
        )
        rgb_entry.config(state="normal")
        rgb_entry.delete(0, tk.END)
        rgb_entry.insert(0, str(rgb_value))
        rgb_entry.config(state="disabled")


def enable_rgb_entry(event=None):
    rgb_entry.config(state="normal")
    rgb_entry.delete(0, tk.END)
    rgb_entry.insert(0, str(rgb_value))
    rgb_entry.focus_set()


def update_color_display():
    r, g, b = rgb_value
    color_hex = f"#{r:02x}{g:02x}{b:02x}"
    color_display.config(bg=color_hex, text=f"RGB {rgb_value}")


# ============================================================
# 6. 클릭 간격 함수
# ============================================================

def update_click_delay(event=None):
    global click_delay

    try:
        new_delay = float(time_entry.get())

        if new_delay <= 0:
            raise ValueError

        click_delay = new_delay

        update_status(
            f"클릭 간격이 {click_delay}초로 설정되었습니다.",
            current_theme()["status"],
        )

        time_entry.config(state="disabled")

    except ValueError:
        messagebox.showerror(
            "입력 오류",
            "0보다 큰 숫자를 입력하세요.\n\n예: 3 또는 1.5",
        )
        time_entry.config(state="normal")
        time_entry.delete(0, tk.END)
        time_entry.insert(0, str(click_delay))
        time_entry.config(state="disabled")


def enable_time_entry(event=None):
    time_entry.config(state="normal")
    time_entry.delete(0, tk.END)
    time_entry.insert(0, str(click_delay))
    time_entry.focus_set()


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

    start_button.config(state="disabled")
    stop_button.config(state="normal")

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

    start_button.config(state="normal")
    stop_button.config(state="disabled")


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

    root.config(bg=theme["bg"])

    apply_widget_theme(root, theme)

    title_label.config(
        fg=theme["fg"],
        bg=theme["bg"],
    )

    subtitle_label.config(
        fg=theme["sub_fg"],
        bg=theme["bg"],
    )

    status_label.config(bg=theme["surface"])

    for entry in [rgb_entry, time_entry]:
        entry.config(
            bg=theme["entry_bg"],
            fg=theme["entry_fg"],
            insertbackground=theme["entry_fg"],
        )


def apply_widget_theme(widget, theme):

    if isinstance(widget, tk.Label):
        widget.config(
            bg=theme["surface"],
            fg=theme["fg"],
        )

    elif isinstance(widget, tk.LabelFrame):
        widget.config(
            bg=theme["surface"],
            fg=theme["fg"],
            highlightbackground=theme["border"],
        )

    elif isinstance(widget, tk.Frame):
        widget.config(
            bg=theme["surface"],
        )

    elif isinstance(widget, tk.Button):

        if widget == start_button:
            widget.config(
                bg=theme["start"],
                fg="white",
                activebackground=theme["start"],
                activeforeground="white",
            )

        elif widget == stop_button:
            widget.config(
                bg=theme["stop"],
                fg="white",
                activebackground=theme["stop"],
                activeforeground="white",
            )

        else:
            widget.config(
                bg=theme["normal_button"],
                fg=theme["normal_button_fg"],
                activebackground=theme["normal_button"],
                activeforeground=theme["normal_button_fg"],
            )

    for child in widget.winfo_children():
        apply_widget_theme(child, theme)


def toggle_theme():
    global theme_mode

    if theme_mode == "light":
        theme_mode = "dark"
        theme_button.config(text="☀  라이트 모드")
    else:
        theme_mode = "light"
        theme_button.config(text="🌙  다크 모드")

    apply_theme()


# ============================================================
# 15. 종료 함수
# ============================================================

def close_program():
    global running

    running = False
    stop_listener()
    root.destroy()


# ============================================================
# 16. GUI 생성
# ============================================================

root = tk.Tk()

root.title("검정구역 취켓팅 매크로")
root.geometry("460x760")
root.minsize(460, 700)
root.configure(bg=themes["light"]["bg"])


# ============================================================
# 17. 상단 헤더
# ============================================================

header = tk.Frame(
    root,
    bg=themes["light"]["bg"],
)

header.pack(
    fill="x",
    padx=20,
    pady=(20, 10),
)


title_label = tk.Label(
    header,
    text="검정구역 취켓팅 매크로",
    font=("맑은 고딕", 18, "bold"),
    bg=themes["light"]["bg"],
)

title_label.pack(anchor="w")


subtitle_label = tk.Label(
    header,
    text="단축키를 이용하여 좌표와 탐색 영역을 설정하세요.",
    font=("맑은 고딕", 9),
    bg=themes["light"]["bg"],
)

subtitle_label.pack(
    anchor="w",
    pady=(4, 0),
)


# ============================================================
# 18. 좌표 설정
# ============================================================

frame_positions = tk.LabelFrame(
    root,
    text="  📍 좌표 설정  ",
    font=("맑은 고딕", 10, "bold"),
    padx=15,
    pady=10,
)

frame_positions.pack(
    fill="x",
    padx=20,
    pady=6,
)


label_a = tk.Label(
    frame_positions,
    text="좌석영역 1 (A)   지정 안됨",
    anchor="w",
)

label_b = tk.Label(
    frame_positions,
    text="좌석영역 2 (B)   지정 안됨",
    anchor="w",
)

label_f = tk.Label(
    frame_positions,
    text="좌석지정 완료 (F)   지정 안됨",
    anchor="w",
)

label_g = tk.Label(
    frame_positions,
    text="새로고침 계속 (G)   지정 안됨",
    anchor="w",
)

label_h = tk.Label(
    frame_positions,
    text="지정석 펼치기 (H)   지정 안됨",
    anchor="w",
)

for label in [label_a, label_b, label_f, label_g, label_h]:
    label.pack(
        fill="x",
        pady=3,
    )


# ============================================================
# 19. 색상 탐색 영역
# ============================================================

frame_area = tk.LabelFrame(
    root,
    text="  🔲 색 탐색 영역  ",
    font=("맑은 고딕", 10, "bold"),
    padx=15,
    pady=10,
)

frame_area.pack(
    fill="x",
    padx=20,
    pady=6,
)


label_rectangle_start = tk.Label(
    frame_area,
    text="탐색 시작 (C)   지정 안됨",
    anchor="w",
)

label_rectangle_end = tk.Label(
    frame_area,
    text="탐색 끝 (D)   지정 안됨",
    anchor="w",
)

label_rectangle_start.pack(
    fill="x",
    pady=3,
)

label_rectangle_end.pack(
    fill="x",
    pady=3,
)


# ============================================================
# 20. 옵션 설정
# ============================================================

frame_options = tk.LabelFrame(
    root,
    text="  ⚙ 옵션 설정  ",
    font=("맑은 고딕", 10, "bold"),
    padx=15,
    pady=12,
)

frame_options.pack(
    fill="x",
    padx=20,
    pady=6,
)


rgb_title = tk.Label(
    frame_options,
    text="🎨 탐색 색상",
)

rgb_title.pack(anchor="w")


rgb_entry = tk.Entry(
    frame_options,
    width=20,
    justify="center",
)

rgb_entry.insert(
    0,
    "(0, 0, 0)",
)

rgb_entry.pack(
    pady=6,
)

rgb_entry.bind(
    "<Return>",
    modify_rgb_value,
)

rgb_entry.bind(
    "<Button-1>",
    enable_rgb_entry,
)

rgb_entry.config(
    state="disabled",
    disabledbackground="white",
    disabledforeground="black",
)


color_display = tk.Label(
    frame_options,
    text="E 키로 색상 지정",
    width=24,
    height=2,
    relief="solid",
)

color_display.pack(
    fill="x",
    pady=(2, 10),
)


time_title = tk.Label(
    frame_options,
    text="⏱ 클릭 간격",
)

time_title.pack(anchor="w")


time_entry = tk.Entry(
    frame_options,
    width=20,
    justify="center",
)

time_entry.insert(
    0,
    "3",
)

time_entry.pack(
    pady=6,
)

time_entry.bind(
    "<Return>",
    update_click_delay,
)

time_entry.bind(
    "<Button-1>",
    enable_time_entry,
)

time_entry.config(
    state="disabled",
    disabledbackground="white",
    disabledforeground="black",
)


# ============================================================
# 21. 제어 영역
# ============================================================

frame_controls = tk.LabelFrame(
    root,
    text="  🕹 매크로 제어  ",
    font=("맑은 고딕", 10, "bold"),
    padx=15,
    pady=12,
)

frame_controls.pack(
    fill="x",
    padx=20,
    pady=6,
)


start_button = tk.Button(
    frame_controls,
    text="▶  매크로 시작",
    command=start_clicking,
    font=("맑은 고딕", 10, "bold"),
    relief="flat",
    bd=0,
    pady=8,
)

start_button.pack(
    fill="x",
    pady=4,
)


stop_button = tk.Button(
    frame_controls,
    text="■  매크로 정지",
    command=stop_clicking,
    state="disabled",
    font=("맑은 고딕", 10, "bold"),
    relief="flat",
    bd=0,
    pady=8,
)

stop_button.pack(
    fill="x",
    pady=4,
)


theme_button = tk.Button(
    frame_controls,
    text="🌙  다크 모드",
    command=toggle_theme,
    relief="flat",
    bd=0,
    pady=7,
)

theme_button.pack(
    fill="x",
    pady=4,
)


exit_button = tk.Button(
    frame_controls,
    text="✕  프로그램 종료 (I)",
    command=close_program,
    relief="flat",
    bd=0,
    pady=7,
)

exit_button.pack(
    fill="x",
    pady=4,
)


status_label = tk.Label(
    frame_controls,
    text="● 매크로 정지",
    font=("맑은 고딕", 10, "bold"),
    pady=8,
)

status_label.pack(
    fill="x",
)


# ============================================================
# 22. 초기화 / 실행
# ============================================================

apply_theme()

listener_thread = threading.Thread(
    target=start_listener,
    daemon=True,
)

listener_thread.start()

root.protocol(
    "WM_DELETE_WINDOW",
    close_program,
)

root.mainloop()
