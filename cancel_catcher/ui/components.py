"""공통 UI 컴포넌트.

색은 신호등처럼 초록 / 빨강 / 노랑 세 가지만 쓴다.
    초록: 실행 중, 찾음, 저장됨, 시작
    빨강: 오류, 정지
    노랑: 대기, 아직 저장 안 된 필수 키

모양은 전부 stylesheet()에 있고, 컴포넌트는 [속성]만 바꾼다.

미리보기: uv run python -m cancel_catcher.ui.gallery → 브라우저에서 컴포넌트 모음이 열린다.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#facc15"

BLACK = "#000000"
WHITE = "#ffffff"

# 테마마다 바뀌는 건 바탕 / 글자 / 회색뿐
THEMES = {
    "light": {
        "bg": "#ffffff",
        "fg": "#000000",
        "muted": "#707070",
        "line": "#e4e4e4",
        "empty": "#e6e6e6",
        "empty_fg": "#4d4d4d",
    },
    "dark": {
        "bg": "#1a1a1a",
        "fg": "#f0f0f0",
        "muted": "#8f8f8f",
        "line": "#333333",
        "empty": "#2e2e2e",
        "empty_fg": "#b0b0b0",
    },
}


# 스타일시트의 [속성] 선택자는 polish를 다시 해야 반영된다.
def restyle(widget, name, value):
    widget.setProperty(name, value)
    for w in [widget, *widget.findChildren(QWidget)]:
        w.style().unpolish(w)
        w.style().polish(w)


# ============================================================
# 글자
# ============================================================

class Title(QLabel):
    """창 맨 위 제목 한 줄"""


class Caption(QLabel):
    """회색 작은 글씨 (설명)"""

    def __init__(self, text):
        super().__init__(text)
        self.setWordWrap(True)


class SectionTitle(QLabel):
    """묶음 제목 (위에 여백이 있다)"""


# ============================================================
# 신호등 상태
# ============================================================

class Lamp(QWidget):
    """신호등 램프 하나. color: "red" / "yellow" / "green" """

    def __init__(self, color):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(16, 16)
        self.setProperty("color", color)


class StatusBar(QWidget):
    """신호등(빨강 노랑 초록) + 상태 문구. 검정 Panel 안에서 쓴다.

    state: idle, info → 노랑 / running, found → 초록 / error → 빨강
    """

    LIT = {
        "idle": "yellow",
        "info": "yellow",
        "running": "green",
        "found": "green",
        "error": "red",
    }

    def __init__(self, text, state="idle"):
        super().__init__()
        self.lamps = {color: Lamp(color) for color in ("red", "yellow", "green")}
        self.label = QLabel()
        self.label.setWordWrap(True)

        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        for lamp in self.lamps.values():
            box.addWidget(lamp)
        box.addSpacing(8)
        box.addWidget(self.label, 1)

        self.set_status(text, state)

    def set_status(self, text, state="info"):
        self.label.setText(text)
        for color, lamp in self.lamps.items():
            lamp.setProperty("lit", color == self.LIT[state])
        restyle(self, "state", state)


# ============================================================
# 버튼 / 입력
# ============================================================

class Button(QPushButton):
    """색 버튼. color: "green" / "red" / "yellow" """

    def __init__(self, text, color, on_click):
        super().__init__(text)
        self.setProperty("color", color)
        self.clicked.connect(on_click)


class LinkButton(QPushButton):
    """글자만 있는 버튼"""

    def __init__(self, text, on_click):
        super().__init__(text)
        self.clicked.connect(on_click)


class TextInput(QLineEdit):
    """밑줄 입력칸. Enter를 누르거나 칸을 벗어나면 on_done()으로 적용한다.

    클릭했을 때만 포커스를 받고, 적용하면 포커스를 놓는다.
    입력칸에 포커스가 남아 있으면 단축키가 막히기 때문.
    """

    def __init__(self, text, width, on_done):
        super().__init__(text)
        self.setFixedWidth(width)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.editingFinished.connect(on_done)
        self.editingFinished.connect(self.clearFocus)


class NumberInput(QSpinBox):
    """정수 입력칸 (minimum ~ maximum을 넘으면 입력이 안 된다). 바뀔 때마다 on_change(값)."""

    def __init__(self, value, minimum, maximum, on_change):
        super().__init__()
        self.setRange(minimum, maximum)
        self.setValue(value)
        self.setFixedWidth(48)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.valueChanged.connect(on_change)
        self.editingFinished.connect(self.clearFocus)


# ============================================================
# 단축키 칸 / 줄
# ============================================================

class KeyCap(QLabel):
    """단축키 글자 칸. 저장 전엔 회색(필수면 노랑), 저장하면 초록."""

    def __init__(self, key):
        super().__init__(key)
        self.setFixedSize(26, 26)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_saved(self):
        restyle(self, "saved", True)

    def set_color(self, rgb):
        r, g, b = rgb
        # 밝은 색 위에는 검은 글자, 어두운 색 위에는 흰 글자
        fg = BLACK if r * 299 + g * 587 + b * 114 > 128000 else WHITE
        self.setStyleSheet(f"background: #{r:02x}{g:02x}{b:02x}; color: {fg};")


class Row(QWidget):
    """[키 칸] 이름 ........ 오른쪽 위젯들. key가 없으면 칸 자리만 비워 둔다."""

    def __init__(self, key, name, *widgets):
        super().__init__()

        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)

        if key:
            self.cap = KeyCap(key)
            box.addWidget(self.cap)
        else:
            box.addSpacing(26)

        box.addWidget(QLabel(name))
        box.addStretch()

        for widget in widgets:
            box.addWidget(widget)


class SlotRow(Row):
    """위치 저장 줄. 저장 전엔 empty 문구, 저장하면 좌표 + 초록 칸.

    required면 저장 전 키 칸이 노랑이라 먼저 채울 곳이 보인다.
    """

    def __init__(self, key, name, empty="지정 안 됨", required=False):
        value = QLabel(empty)
        value.setObjectName("value")
        super().__init__(key, name, value)
        self.value = value
        self.cap.setProperty("required", required)

    def set_value(self, value):
        self.value.setText(str(value))
        restyle(self.value, "saved", True)
        self.cap.set_saved()


# ============================================================
# 상자
# ============================================================

class Panel(QWidget):
    """검정 상자. 위젯과 레이아웃을 위에서부터 쌓는다. highlight 하면 초록."""

    def __init__(self, *items):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        box = QVBoxLayout(self)
        box.setContentsMargins(18, 18, 18, 18)
        box.setSpacing(14)

        for item in items:
            if isinstance(item, QWidget):
                box.addWidget(item)
            else:
                box.addLayout(item)

    def set_highlight(self, on):
        restyle(self, "highlight", on)


# ============================================================
# 화면 영역 고르기
# ============================================================

class RegionPicker(QWidget):
    """캡처 도구처럼 마우스가 있는 모니터 위를 드래그해서 사각형을 고른다.

    on_pick(왼쪽 위, 오른쪽 아래)에는 마우스 클릭과 같은 실제 픽셀 좌표가 넘어간다.
    Esc나 오른쪽 클릭은 취소.
    """

    HINT = "드래그해서 찾을 영역을 그리세요. 취소는 Esc 또는 오른쪽 클릭"

    def __init__(self, on_pick):
        super().__init__()
        self.on_pick = on_pick
        self.origin = None
        self.current = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self.setGeometry(screen.geometry())

    def showEvent(self, event):
        self.activateWindow()  # Esc를 받으려면 포커스가 필요하다

    # Qt 좌표 → 실제 픽셀. 모니터의 왼쪽 위는 두 좌표가 같고, 그 안에서만 배율이 곱해진다.
    def to_pixels(self, point):
        ratio = self.devicePixelRatioF()
        origin = self.geometry().topLeft()
        return (
            round(origin.x() + point.x() * ratio),
            round(origin.y() + point.y() * ratio),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self.origin:
            box = QRectF(self.origin, self.current).normalized()
            # 완전 투명(알파 0)이면 클릭이 뒤 창으로 빠지므로 1만 남긴다.
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(box, QColor(0, 0, 0, 1))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(GREEN), 2))
            painter.drawRect(box)

        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        hint_box = painter.boundingRect(
            self.rect(), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.HINT
        ).adjusted(-14, -8, 14, 8).translated(0, 48)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 200))
        painter.drawRoundedRect(hint_box, 8, 8)
        painter.setPen(QColor(WHITE))
        painter.drawText(hint_box, Qt.AlignmentFlag.AlignCenter, self.HINT)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            self.close()
            return
        self.origin = self.current = event.position()
        self.update()

    def mouseMoveEvent(self, event):
        if self.origin:
            self.current = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if not self.origin or event.button() != Qt.MouseButton.LeftButton:
            return

        self.current = event.position()
        self.close()

        x1, y1 = self.to_pixels(self.origin)
        x2, y2 = self.to_pixels(self.current)

        # 클릭만 하고 끌지 않았으면 취소로 본다.
        if x1 != x2 and y1 != y2:
            self.on_pick((min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2)))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


# ============================================================
# 스타일
# ============================================================

def stylesheet(theme):
    t = THEMES[theme]

    return f"""
        QWidget {{
            background: {t["bg"]};
            color: {t["fg"]};
            font-family: "Malgun Gothic";
            font-size: 10pt;
        }}

        Title {{
            font-size: 13pt;
            font-weight: bold;
        }}
        Caption {{
            color: {t["muted"]};
            font-size: 9pt;
        }}
        SectionTitle {{
            padding-top: 12px;
            font-weight: bold;
        }}

        Button {{
            color: {BLACK};
            border: 2px solid transparent;
            border-radius: 6px;
            padding: 8px;
            font-size: 10pt;
            font-weight: bold;
        }}
        Button[color="green"] {{
            background: {GREEN};
        }}
        Button[color="red"] {{
            background: {RED};
        }}
        Button[color="yellow"] {{
            background: {YELLOW};
        }}
        Button:focus {{
            border-color: {t["fg"]};
        }}
        Button:disabled {{
            background: {t["empty"]};
            color: {t["muted"]};
        }}
        LinkButton {{
            background: transparent;
            color: {t["muted"]};
            border: none;
            padding: 4px 0;
            font-size: 9pt;
        }}
        LinkButton:hover, LinkButton:focus {{
            color: {t["fg"]};
        }}
        TextInput, NumberInput {{
            background: transparent;
            border: none;
            border-bottom: 1px solid {t["line"]};
            padding: 2px;
        }}
        TextInput:focus, NumberInput:focus {{
            border-bottom-color: {t["fg"]};
        }}

        KeyCap {{
            background: {t["empty"]};
            color: {t["empty_fg"]};
            border: 1px solid {t["line"]};
            border-radius: 5px;
            font-weight: bold;
        }}
        KeyCap[required="true"] {{
            background: {YELLOW};
            color: {BLACK};
            border-color: {YELLOW};
        }}
        KeyCap[saved="true"] {{
            background: {GREEN};
            color: {BLACK};
            border-color: {GREEN};
        }}
        #value {{
            color: {t["muted"]};
        }}
        #value[saved="true"] {{
            color: {t["fg"]};
        }}

        Panel {{
            background: {BLACK};
            border-radius: 10px;
        }}
        Panel QLabel {{
            background: transparent;
            color: {WHITE};
        }}
        StatusBar QLabel {{
            font-size: 13pt;
            font-weight: bold;
        }}
        Lamp {{
            background: #333333;
            border-radius: 8px;
        }}
        Lamp[color="red"][lit="true"] {{
            background: {RED};
        }}
        Lamp[color="yellow"][lit="true"] {{
            background: {YELLOW};
        }}
        Lamp[color="green"][lit="true"] {{
            background: {GREEN};
        }}
        Panel Button:focus {{
            border-color: {WHITE};
        }}
        Panel Button:disabled {{
            background: #262626;
            color: #6b6b6b;
        }}

        Panel[highlight="true"] {{
            background: {GREEN};
        }}
        Panel[highlight="true"] QLabel {{
            color: {BLACK};
        }}
        Panel[highlight="true"] Lamp {{
            background: {BLACK};
        }}
        Panel[highlight="true"] Lamp[lit="true"] {{
            background: {GREEN};
            border: 2px solid {BLACK};
        }}
        Panel[highlight="true"] Button:enabled {{
            background: {BLACK};
            color: {WHITE};
        }}
    """
