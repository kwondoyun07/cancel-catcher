"""검정치마 취켓팅 매크로. 실행: uv run main.py

코드는 cancel_catcher/, 문서는 docs/에 있다.
"""

import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from cancel_catcher.ui.window import MainWindow

app = QApplication(sys.argv)

# 색 고르기 창 같은 Qt 기본 창을 한국어로
translator = QTranslator()
if translator.load(QLocale("ko"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
    app.installTranslator(translator)

window = MainWindow(app)
window.show()
sys.exit(app.exec())
