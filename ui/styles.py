"""
Application-wide QSS stylesheet.
Color palette: GitHub-dark inspired.
"""

MAIN_STYLE = """
/* ─── Global ─────────────────────────────────────────────── */
* {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 13px;
    color: #e6edf3;
}

QMainWindow {
    background-color: #0d1117;
}

QDialog {
    background-color: #0d1117;
}

QToolTip {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ─── Menu bar ────────────────────────────────────────────── */
QMenuBar {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 2px 6px;
    font-size: 13px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #21262d;
}
QMenu {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 16px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #21262d;
}
QMenu::separator {
    height: 1px;
    background: #30363d;
    margin: 4px 8px;
}

/* ─── Left panel ──────────────────────────────────────────── */
#leftPanel {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}
#panelHeader {
    background-color: #0d1117;
    border-bottom: 1px solid #30363d;
}
#sectionLabel {
    color: #8b949e;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
}

/* ─── Device list ─────────────────────────────────────────── */
QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px 2px;
}
QListWidget::item {
    background-color: transparent;
    border-radius: 6px;
    padding: 0;
    margin: 2px 6px;
    border: 1px solid transparent;
}
QListWidget::item:selected {
    background-color: #1f3352;
    border-color: #388bfd;
}
QListWidget::item:hover:!selected {
    background-color: #21262d;
    border-color: #30363d;
}

/* ─── Right panel ─────────────────────────────────────────── */
#rightPanel {
    background-color: #0d1117;
}

/* ─── Info cards ──────────────────────────────────────────── */
#infoCard {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
}
#cardValue {
    font-size: 20px;
    font-weight: 700;
    color: #e6edf3;
}
#cardLabel {
    font-size: 11px;
    color: #8b949e;
}

/* ─── Typography helpers ──────────────────────────────────── */
#sectionTitle {
    font-size: 11px;
    font-weight: 700;
    color: #8b949e;
    letter-spacing: 0.8px;
}
#deviceName {
    font-size: 20px;
    font-weight: 700;
    color: #e6edf3;
}
#deviceSub {
    font-size: 13px;
    color: #8b949e;
}
#emptyTitle {
    font-size: 16px;
    font-weight: 600;
    color: #484f58;
}
#emptySubtitle {
    font-size: 12px;
    color: #30363d;
}

/* ─── Format selector ─────────────────────────────────────── */
QComboBox {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 32px;
    min-width: 140px;
    font-size: 13px;
}
QComboBox:hover {
    border-color: #58a6ff;
    background-color: #262c36;
}
QComboBox:focus {
    border-color: #388bfd;
    outline: none;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8b949e;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    selection-background-color: #1f3352;
    selection-color: #e6edf3;
    outline: none;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 28px;
}

/* ─── Buttons ─────────────────────────────────────────────── */
#convertBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 700;
    padding: 11px 28px;
    min-width: 210px;
}
#convertBtn:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}
#convertBtn:pressed {
    background-color: #1a6e2e;
}
#convertBtn:disabled {
    background-color: #21262d;
    color: #484f58;
    border-color: #30363d;
}

#cancelBtn {
    background-color: transparent;
    color: #f85149;
    border: 1px solid #f85149;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 14px;
}
#cancelBtn:hover {
    background-color: rgba(248, 81, 73, 0.12);
}
#cancelBtn:disabled {
    color: #484f58;
    border-color: #484f58;
}

#refreshBtn {
    background-color: transparent;
    border: none;
    border-radius: 5px;
    padding: 3px;
}
#refreshBtn:hover {
    background-color: #21262d;
}

/* ─── Progress bar ────────────────────────────────────────── */
QProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
}
QProgressBar::chunk {
    background-color: #388bfd;
    border-radius: 3px;
}

/* ─── Divider ─────────────────────────────────────────────── */
#divider {
    background-color: #21262d;
    border: none;
    max-height: 1px;
    min-height: 1px;
}

/* ─── Status label ────────────────────────────────────────── */
#statusLabel {
    color: #8b949e;
    font-size: 12px;
    font-style: italic;
}

/* ─── Scrollbars ──────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #484f58;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
    width: 0;
}

/* ─── No-devices label ────────────────────────────────────── */
#noDeviceLabel {
    color: #484f58;
    font-size: 12px;
}
"""
