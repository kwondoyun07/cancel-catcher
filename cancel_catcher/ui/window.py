"""메인 창. 공통 컴포넌트로 화면을 조립하고, 매크로 · 단축키와 잇는다."""

from functools import partial

from pynput.keyboard import Key
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QColorDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from cancel_catcher import screen
from cancel_catcher.hotkeys import Hotkeys
from cancel_catcher.macro import MAX_AREAS, Macro
from cancel_catcher.ui.components import (
    Button,
    Caption,
    LinkButton,
    NumberInput,
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

# 1 ~ 9, 0 키 → 구역 1 ~ 10
AREA_KEYS = [str((n + 1) % 10) for n in range(MAX_AREAS)]


# Qt 위젯은 GUI 스레드에서만 건드릴 수 있으므로
# 매크로 / 키보드 스레드에서는 시그널로 GUI 스레드에 넘긴다.
class GuiBridge(QObject):
    call = Signal(object)

    @Slot(object)
    def run(self, fn):
        fn()


class MainWindow(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("검정구역 취켓팅 매크로")
        self.setFixedWidth(420)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # 빈 곳을 누르면 입력칸 포커스가 빠지게

        self.bridge = GuiBridge()
        self.bridge.call.connect(self.bridge.run)

        self.macro = Macro(on_status=lambda text, state: self.gui(lambda: self.show_status(text, state)))
        self.theme = "light"
        self.picker = None  # 드래그 창. 참조를 안 잡아두면 바로 사라진다.

        self.build()
        self.apply_theme()
        self.fit_height(shrink=True)

        self.hotkeys = Hotkeys(
            int(self.winId()),
            keys={
                **{key: partial(self.save_area, n) for n, key in enumerate(AREA_KEYS)},
                "c": lambda: self.gui(self.pick_region),
                "e": self.capture_color,
                "f": partial(self.save_button, "f"),
                "g": partial(self.save_button, "g"),
                "h": partial(self.save_button, "h"),
            },
            always={
                "i": self.macro.stop,
                Key.esc: lambda: self.gui(self.close_picker),
            },
            on_error=lambda error: self.macro.on_status(f"단축키 처리 중 오류: {error}", "error"),
        )
        app.focusChanged.connect(self.on_focus_changed)
        app.aboutToQuit.connect(self.shutdown)
        self.hotkeys.start()

    def gui(self, fn):
        self.bridge.call.emit(fn)

    # ============================================================
    # 화면 조립
    # ============================================================

    def build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)

        # 제목 줄
        self.theme_button = LinkButton("다크 모드", self.toggle_theme)
        header = QHBoxLayout()
        header.addWidget(Title("검정구역 취켓팅 매크로"))
        header.addStretch()
        header.addWidget(self.theme_button)
        header.addSpacing(12)
        header.addWidget(LinkButton("종료", QApplication.quit))
        layout.addLayout(header)

        # 신호등 상자
        self.status_bar = StatusBar("대기 중")
        self.start_button = Button("시작", "green", self.macro.start)
        self.stop_button = Button("정지 (I)", "red", self.macro.stop)
        self.stop_button.setEnabled(False)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        self.panel = Panel(self.status_bar, buttons)
        layout.addWidget(self.panel)

        layout.addWidget(Caption("이 창을 한 번 클릭해 두고, 브라우저 위에 마우스만 올린 채 키를 누르면 그 위치가 저장돼요."))

        # 구역 차례로 클릭 (1 ~ 9, 0 키)
        layout.addWidget(SectionTitle("구역 차례로 클릭"))
        self.count_input = NumberInput(self.macro.area_count, 1, MAX_AREAS, self.set_area_count)
        layout.addWidget(Row("", "구역 수 (1~10)", self.count_input, QLabel("개")))

        self.area_rows = [SlotRow(key, f"구역 {n + 1}", required=True) for n, key in enumerate(AREA_KEYS)]
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        for n, row in enumerate(self.area_rows):
            grid.addWidget(row, n // 2, n % 2)
        layout.addLayout(grid)

        self.delay_input = TextInput(f"{self.macro.click_delay:g}", 48, self.apply_delay)
        layout.addWidget(Row("", "클릭 간격", self.delay_input, QLabel("초")))

        # 빈자리 찾기
        layout.addWidget(SectionTitle("빈자리 찾기"))
        self.region_row = SlotRow("C", "찾을 영역", empty="C를 누르고 드래그", required=True)
        layout.addWidget(self.region_row)

        self.color_input = TextInput("", 130, self.apply_color_text)
        self.color_input.setPlaceholderText("#FF0000 / 255,0,0")
        self.color_row = Row("E", "찾을 색", self.color_input, LinkButton("고르기", self.choose_color))
        self.color_row.cap.setProperty("required", True)
        layout.addWidget(self.color_row)

        # 찾은 뒤 / 20분마다 새로고침한 뒤
        self.button_rows = {
            "f": SlotRow("F", "좌석지정 완료"),
            "g": SlotRow("G", "새로고침 계속"),
            "h": SlotRow("H", "지정석 펼치기"),
        }
        layout.addWidget(SectionTitle("찾은 뒤"))
        layout.addWidget(self.button_rows["f"])
        layout.addWidget(SectionTitle("20분마다 새로고침한 뒤"))
        layout.addWidget(self.button_rows["g"])
        layout.addWidget(self.button_rows["h"])
        layout.addStretch()

        self.set_area_count(self.macro.area_count)

    # ============================================================
    # 상태 (GUI 스레드)
    # ============================================================

    def show_status(self, text, state="info"):
        self.status_bar.set_status(text, state)
        self.panel.set_highlight(state == "found")
        self.start_button.setEnabled(not self.macro.running)
        self.stop_button.setEnabled(self.macro.running)
        self.fit_height()  # 긴 문구는 두 줄이 된다

    def fit_height(self, shrink=False):
        # 줄바꿈되는 글이 있으면 Qt가 창 높이를 모자라게 잡아서 버튼이 눌린다.
        # 그래서 안쪽부터 모든 레이아웃에 남은 옛 크기를 버리고, 지금 폭에서 필요한 높이를 재서 맞춘다.
        for widget in reversed([self, *self.findChildren(QWidget)]):
            if widget.layout():
                widget.layout().invalidate()
                widget.layout().activate()
        height = self.heightForWidth(self.width())
        if height < 0:
            height = self.sizeHint().height()
        self.setMinimumHeight(height)
        if shrink or self.height() < height:
            self.resize(self.width(), height)

    def on_focus_changed(self, old, new):
        # 입력칸에서 타자 치는 동안에는 숫자 · 글자 단축키를 받지 않는다.
        self.hotkeys.typing = isinstance(new, (QLineEdit, QAbstractSpinBox))

    # ============================================================
    # 단축키로 저장 (키보드 스레드)
    # ============================================================

    def save_area(self, index):
        if index >= self.macro.area_count:
            return
        position = self.macro.mouse.position
        self.macro.areas[index] = position
        self.gui(lambda: self.area_rows[index].set_value(position))

    def save_button(self, key):
        position = self.macro.mouse.position
        self.macro.buttons[key] = position
        self.gui(lambda: self.button_rows[key].set_value(position))

    def capture_color(self):
        color = screen.pixel_color(*self.macro.mouse.position)
        self.gui(lambda: self.set_color(color))

    # ============================================================
    # 입력 (GUI 스레드)
    # ============================================================

    def set_area_count(self, count):
        self.macro.area_count = count
        for n, row in enumerate(self.area_rows):
            row.setVisible(n < count)
        self.fit_height(shrink=True)

    def apply_delay(self):
        try:
            delay = float(self.delay_input.text())
            if not delay > 0:
                raise ValueError
        except ValueError:
            self.show_status("간격은 0보다 큰 숫자로 입력하세요", "error")
        else:
            self.macro.click_delay = delay
            if self.macro.running:
                self.show_status(f"찾는 중 ({delay:g}초 간격)", "running")
            else:
                self.show_status(f"클릭 간격을 {delay:g}초로 바꿨어요")

        self.delay_input.setText(f"{self.macro.click_delay:g}")

    def set_color(self, color):
        self.macro.color = color
        self.color_row.cap.set_color(color)
        self.color_input.setText(screen.to_hex(color))

    def apply_color_text(self):
        text = self.color_input.text().strip()
        if text:
            try:
                self.set_color(screen.parse_color(text))
                return
            except ValueError:
                self.show_status("색은 #FF0000이나 255, 0, 0처럼 입력하세요", "error")

        # 비웠거나 틀렸으면 원래 색으로 되돌린다.
        self.color_input.setText(screen.to_hex(self.macro.color) if self.macro.color else "")

    def choose_color(self):
        initial = QColor(*self.macro.color) if self.macro.color else QColor("white")
        # 부모 없이 띄워야 이 창의 스타일이 섞이지 않는다. "화면 색 선택"으로 사이트 색도 찍을 수 있다.
        color = QColorDialog.getColor(initial, None, "찾을 색 고르기")
        if color.isValid():
            self.set_color((color.red(), color.green(), color.blue()))

    def pick_region(self):
        # 매크로가 마우스를 움직이는 동안에는 드래그가 꼬인다.
        if self.macro.running:
            self.show_status("정지한 뒤에 영역을 그리세요", "error")
            return

        self.picker = RegionPicker(self.save_region)
        self.picker.show()

    def save_region(self, start, end):
        self.macro.region = (*start, *end)
        self.region_row.set_value(f"{start} ~ {end}")

    def close_picker(self):
        if self.picker:
            self.picker.close()

    # ============================================================
    # 테마 / 종료
    # ============================================================

    def apply_theme(self):
        self.setStyleSheet(stylesheet(self.theme))

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.theme_button.setText("라이트 모드" if self.theme == "dark" else "다크 모드")
        self.apply_theme()

    def shutdown(self):
        self.macro.running = False
        self.hotkeys.stop()
