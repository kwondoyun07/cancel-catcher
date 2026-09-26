"""공통 컴포넌트 미리보기. 실행: uv run python -m cancel_catcher.ui.gallery

모든 컴포넌트를 상태별로 실제 Qt로 그려서 HTML 한 장으로 만들고 브라우저로 연다.
"""

import base64
import html
import sys
import tempfile
import webbrowser
from pathlib import Path

from PySide6.QtCore import QBuffer, QPointF
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from cancel_catcher.ui.components import (
    THEMES,
    Button,
    Caption,
    KeyCap,
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

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>공통 컴포넌트</title>
<style>
  body { margin: 40px 24px; background: #f2f2f2; color: #111; font: 14px/1.6 "Malgun Gothic", system-ui, sans-serif; }
  h1 { margin: 0; font-size: 24px; }
  h2 { margin: 40px 0 0; font-size: 17px; }
  p { margin: 4px 0 12px; color: #555; }
  table { border-collapse: collapse; background: #fff; }
  th, td { padding: 10px 16px; border: 1px solid #ddd; text-align: left; vertical-align: middle; }
  th { font-size: 12px; font-weight: normal; color: #666; background: #fafafa; }
  code { font: 12px/1.5 Consolas, monospace; white-space: pre; }
  td.light { background: LIGHT_BG; }
  td.dark { background: DARK_BG; }
  img { display: block; }
</style>
</head>
<body>
<h1>공통 컴포넌트</h1>
<p>cancel_catcher/ui/components.py를 실제 Qt로 그린 모습이에요. 컴포넌트를 고친 뒤 <code>uv run python -m cancel_catcher.ui.gallery</code>를 다시 실행하면 갱신돼요.</p>
SECTIONS
</body>
</html>
"""


def noop(*args):
    pass


def then(widget, *calls):
    for call in calls:
        call(widget)
    return widget


def panel(status, state, highlight=False):
    buttons = QHBoxLayout()
    buttons.setSpacing(8)
    buttons.addWidget(then(Button("시작", "green", noop), lambda b: b.setEnabled(state != "running")))
    buttons.addWidget(then(Button("정지 (I)", "red", noop), lambda b: b.setEnabled(state == "running")))
    box = Panel(StatusBar(status, state), buttons)
    box.set_highlight(highlight)
    return box


def picker():
    box = RegionPicker(noop)
    box.resize(520, 300)
    box.origin, box.current = QPointF(140, 110), QPointF(360, 230)
    return box


def color_row(text):
    row = Row("E", "찾을 색", then(TextInput(text, 130, noop), lambda i: i.setPlaceholderText("#FF0000 / 255,0,0")),
              LinkButton("고르기", noop))
    row.cap.setProperty("required", True)
    if text:
        row.cap.set_color((124, 104, 238))
    return row


# (컴포넌트, [(상태, 코드, 만드는 함수, 너비)])
GROUPS = [
    (Title, [
        ("기본", 'Title("검정치마 취켓팅 매크로")', lambda: Title("검정치마 취켓팅 매크로"), None),
    ]),
    (Caption, [
        ("기본", 'Caption("이 창을 한 번 클릭해 두고 …")',
         lambda: Caption("이 창을 한 번 클릭해 두고, 브라우저 위에 마우스만 올린 채 키를 누르면 그 위치가 저장돼요."), 380),
    ]),
    (SectionTitle, [
        ("기본", 'SectionTitle("구역 차례로 클릭")', lambda: SectionTitle("구역 차례로 클릭"), None),
    ]),
    (StatusBar, [
        ("idle", 'StatusBar("대기 중")', lambda: Panel(StatusBar("대기 중")), 360),
        ("running", 'status.set_status("찾는 중 (3초 간격)", "running")',
         lambda: Panel(StatusBar("찾는 중 (3초 간격)", "running")), 360),
        ("error", 'status.set_status("구역 2, 찾을 색부터 정하세요", "error")',
         lambda: Panel(StatusBar("구역 2, 찾을 색부터 정하세요", "error")), 360),
        ("info", 'status.set_status("클릭 간격을 3초로 바꿨어요")',
         lambda: Panel(StatusBar("클릭 간격을 3초로 바꿨어요", "info")), 360),
    ]),
    (Button, [
        ("green", 'Button("시작", "green", on_click)', lambda: Button("시작", "green", noop), 180),
        ("red", 'Button("정지 (I)", "red", on_click)', lambda: Button("정지 (I)", "red", noop), 180),
        ("yellow", 'Button("노랑 버튼", "yellow", on_click)', lambda: Button("노랑 버튼", "yellow", noop), 180),
        ("비활성", "button.setEnabled(False)",
         lambda: then(Button("시작", "green", noop), lambda b: b.setEnabled(False)), 180),
    ]),
    (LinkButton, [
        ("기본", 'LinkButton("고르기", on_click)', lambda: LinkButton("고르기", noop), None),
    ]),
    (TextInput, [
        ("기본", 'TextInput("3", 48, on_done)', lambda: TextInput("3", 48, noop), None),
        ("안내 글자", 'input.setPlaceholderText("#FF0000 / 255,0,0")',
         lambda: then(TextInput("", 130, noop), lambda i: i.setPlaceholderText("#FF0000 / 255,0,0")), None),
    ]),
    (NumberInput, [
        ("기본", "NumberInput(2, 1, 10, on_change)", lambda: NumberInput(2, 1, 10, noop), None),
    ]),
    (KeyCap, [
        ("저장 전", 'KeyCap("F")', lambda: KeyCap("F"), None),
        ("필수, 저장 전", 'cap.setProperty("required", True)',
         lambda: then(KeyCap("1"), lambda c: c.setProperty("required", True)), None),
        ("저장 후", "cap.set_saved()", lambda: then(KeyCap("1"), KeyCap.set_saved), None),
        ("색", "cap.set_color((124, 104, 238))",
         lambda: then(KeyCap("E"), lambda c: c.set_color((124, 104, 238))), None),
    ]),
    (Row, [
        ("키 없음", 'Row("", "구역 수 (1~10)", NumberInput(…), QLabel("개"))',
         lambda: Row("", "구역 수 (1~10)", NumberInput(2, 1, 10, noop), QLabel("개")), 380),
        ("찾을 색, 정하기 전", 'Row("E", "찾을 색", TextInput(…), LinkButton("고르기", …))',
         lambda: color_row(""), 380),
        ("찾을 색, 정한 뒤", "cap.set_color(색), input.setText(to_hex(색))",
         lambda: color_row("#7C68EE"), 380),
    ]),
    (SlotRow, [
        ("저장 전", 'SlotRow("F", "좌석지정 완료")', lambda: SlotRow("F", "좌석지정 완료"), 380),
        ("필수, 저장 전", 'SlotRow("1", "구역 1", required=True)',
         lambda: SlotRow("1", "구역 1", required=True), 180),
        ("저장 후", "row.set_value((812, 440))",
         lambda: then(SlotRow("1", "구역 1", required=True), lambda r: r.set_value((812, 440))), 180),
        ("안내 문구", 'SlotRow("C", "찾을 영역", empty="C를 누르고 드래그", required=True)',
         lambda: SlotRow("C", "찾을 영역", empty="C를 누르고 드래그", required=True), 380),
    ]),
    (Panel, [
        ("기본", "Panel(StatusBar(…), 버튼 줄)", lambda: panel("대기 중", "idle"), 380),
        ("찾는 중", 'status.set_status(…, "running")', lambda: panel("찾는 중 (3초 간격)", "running"), 380),
        ("highlight", "panel.set_highlight(True)",
         lambda: panel("빈자리를 눌렀어요 (1024, 388)", "found", True), 380),
    ]),
    (RegionPicker, [
        ("드래그 중", "RegionPicker(on_pick)", picker, None),
    ]),
]


def snapshot(widget, width):
    # 바탕색과 여백을 주려고 감싼다. RegionPicker는 반투명이라 그대로 찍는다.
    if not isinstance(widget, RegionPicker):
        frame = QWidget()
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 12, 12, 12)
        box.addWidget(widget)
        if width:
            frame.setFixedWidth(width + 24)
        frame.adjustSize()
        widget = frame

    pixmap = widget.grab()
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    data = base64.b64encode(buffer.data().data()).decode()
    size = round(pixmap.width() / pixmap.devicePixelRatio())
    return f'<img width="{size}" alt="" src="data:image/png;base64,{data}">'


def show_gallery():
    app = QApplication.instance() or QApplication(sys.argv)

    shots = {}
    for theme in THEMES:
        app.setStyleSheet(stylesheet(theme))
        for cls, states in GROUPS:
            for state, _, make, width in states:
                shots[theme, cls, state] = snapshot(make(), width)

    sections = []
    for cls, states in GROUPS:
        rows = "".join(
            f"<tr><td>{html.escape(state)}</td><td><code>{html.escape(code)}</code></td>"
            f'<td class="light">{shots["light", cls, state]}</td>'
            f'<td class="dark">{shots["dark", cls, state]}</td></tr>'
            for state, code, _, _ in states
        )
        sections.append(
            f"<h2>{cls.__name__}</h2><p>{html.escape(cls.__doc__.strip().splitlines()[0])}</p>"
            f"<table><tr><th>상태</th><th>코드</th><th>라이트</th><th>다크</th></tr>{rows}</table>"
        )

    page = Path(tempfile.gettempdir()) / "cancel-catcher-components.html"
    page.write_text(
        PAGE.replace("LIGHT_BG", THEMES["light"]["bg"])
        .replace("DARK_BG", THEMES["dark"]["bg"])
        .replace("SECTIONS", "\n".join(sections)),
        encoding="utf-8",
    )
    print(page)
    webbrowser.open(page.as_uri())


if __name__ == "__main__":
    show_gallery()
