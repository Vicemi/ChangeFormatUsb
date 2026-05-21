from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt


class DarkPalette(QPalette):
    """Application-wide dark color palette."""

    def __init__(self):
        super().__init__()
        bg      = QColor("#0d1117")
        surface = QColor("#161b22")
        text    = QColor("#e6edf3")
        muted   = QColor("#8b949e")
        accent  = QColor("#388bfd")
        border  = QColor("#30363d")

        self.setColor(QPalette.Window,          bg)
        self.setColor(QPalette.WindowText,      text)
        self.setColor(QPalette.Base,            surface)
        self.setColor(QPalette.AlternateBase,   bg)
        self.setColor(QPalette.ToolTipBase,     surface)
        self.setColor(QPalette.ToolTipText,     text)
        self.setColor(QPalette.Text,            text)
        self.setColor(QPalette.Button,          surface)
        self.setColor(QPalette.ButtonText,      text)
        self.setColor(QPalette.BrightText,      Qt.white)
        self.setColor(QPalette.Highlight,       accent)
        self.setColor(QPalette.HighlightedText, Qt.white)
        self.setColor(QPalette.Link,            accent)
        self.setColor(QPalette.LinkVisited,     QColor("#bc8cff"))

        self.setColor(QPalette.Disabled, QPalette.Text,       muted)
        self.setColor(QPalette.Disabled, QPalette.ButtonText, muted)
        self.setColor(QPalette.Disabled, QPalette.WindowText, muted)
