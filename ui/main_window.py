import os
import logging

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QListWidget, QListWidgetItem, QProgressBar,
    QAction, QMessageBox, QDialog, QTextBrowser,
    QSizePolicy, QFrame, QAbstractItemView, QStyle,
    QStyledItemDelegate, QTabWidget, QStyleFactory,
)
from PyQt5.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import (
    QFont, QColor, QIcon, QPainter, QPen, QPixmap, QDesktopServices,
)
from PyQt5.QtSvg import QSvgRenderer

from core.usb_manager import USBManager
from core.format_converter import FormatConverter
from core.admin_check import is_admin
from ui.styles import MAIN_STYLE
from ui.components import DarkPalette
from utils.i18n import resource_path, Translator
from logger import logger
import config


# ─────────────────────────────────────────────────────────────────────────────
# SVG helper
# ─────────────────────────────────────────────────────────────────────────────

def load_svg(relative_path, size=24):
    path = resource_path(relative_path)
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QPixmap(size, size)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


# ─────────────────────────────────────────────────────────────────────────────
# Device list item delegate
# ─────────────────────────────────────────────────────────────────────────────

class DeviceItemDelegate(QStyledItemDelegate):

    _FS_COLORS = {
        "NTFS":  ("#388bfd", "#1a2d4d"),
        "FAT32": ("#3fb950", "#1a3327"),
        "EXFAT": ("#d29922", "#362a0f"),
        "REFS":  ("#bc8cff", "#2b1f4a"),
    }

    def paint(self, painter, option, index):
        device = index.data(Qt.UserRole)
        if not device:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect.adjusted(6, 3, -6, -3)
        selected = bool(option.state & QStyle.State_Selected)
        hovered  = bool(option.state & QStyle.State_MouseOver)

        bg_col     = QColor("#1f3352" if selected else "#21262d" if hovered else "#161b22")
        border_col = QColor("#388bfd" if selected else "#30363d")

        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_col)
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(border_col, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)

        dot_x, dot_y, dot_r = rect.left() + 14, rect.center().y(), 4
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#388bfd" if selected else "#484f58"))
        painter.drawEllipse(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)

        tx = dot_x + dot_r + 10
        letter = device.get("letter", "?:").replace("\\", "")
        label  = device.get("label", "Unidad USB")

        painter.setPen(QColor("#e6edf3"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(tx, rect.top() + 19, letter)

        painter.setPen(QColor("#8b949e"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(tx, rect.top() + 33, label[:26])

        fs = (device.get("filesystem") or "?").upper()
        fg, bg2 = self._FS_COLORS.get(fs, ("#8b949e", "#21262d"))
        badge_w, badge_h = 50, 18
        bx = rect.right() - badge_w - 8
        by = rect.center().y() - badge_h // 2
        painter.setBrush(QColor(bg2))
        painter.setPen(QPen(QColor(fg), 1))
        painter.drawRoundedRect(bx, by, badge_w, badge_h, 9, 9)
        painter.setPen(QColor(fg))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(bx, by, badge_w, badge_h, Qt.AlignCenter, fs)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 56)


# ─────────────────────────────────────────────────────────────────────────────
# Background conversion thread
# ─────────────────────────────────────────────────────────────────────────────

class ConversionWorker(QThread):
    finished         = pyqtSignal(str)
    error            = pyqtSignal(str)
    progress_updated = pyqtSignal(str, int)

    def __init__(self, drive_letter, new_fs, parent=None):
        super().__init__(parent)
        self.drive_letter = drive_letter
        self.new_fs       = new_fs
        self._converter   = None

    def run(self):
        def on_progress(msg, pct):
            self.progress_updated.emit(msg, pct)

        self._converter = FormatConverter(progress_callback=on_progress)
        try:
            self._converter.convert(self.drive_letter, self.new_fs)
            self.finished.emit(self.drive_letter)
        except InterruptedError:
            self.error.emit("Conversion cancelada por el usuario")
        except Exception as e:
            logger.error("Conversion error: %s", e, exc_info=True)
            self.error.emit(str(e))

    def cancel(self):
        if self._converter:
            self._converter.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# About dialog
# ─────────────────────────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    _STYLE = """
        QDialog      { background-color: #0d1117; }
        QLabel       { color: #e6edf3; }
        QTextBrowser { background-color: #161b22; border: 1px solid #30363d;
                       border-radius: 6px; color: #e6edf3; padding: 10px; }
        QPushButton  { background-color: #21262d; color: #e6edf3;
                       border: 1px solid #30363d; border-radius: 6px;
                       padding: 7px 16px; font-weight: 600; }
        QPushButton:hover { background-color: #30363d; }
        QTabWidget::pane  { border: 1px solid #30363d; border-radius: 6px;
                            background-color: #161b22; }
        QTabBar::tab      { background: #21262d; color: #8b949e;
                            padding: 7px 20px; border-top-left-radius: 4px;
                            border-top-right-radius: 4px; margin-right: 2px; }
        QTabBar::tab:selected { background: #388bfd; color: #ffffff; }
    """

    def __init__(self, translator, parent=None):
        super().__init__(parent)
        self.tr_ = translator
        self.setFixedSize(480, 390)
        self.setStyleSheet(self._STYLE)
        self._build()

    def _t(self, key):
        return self.tr_.gettext(key)

    def _build(self):
        self.setWindowTitle(f"{self._t('MENU_ABOUT')} — {config.APP_NAME}")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        ico_lbl = QLabel()
        ico_lbl.setPixmap(QIcon(resource_path("resources/icon.ico")).pixmap(40, 40))
        hdr.addWidget(ico_lbl)
        hdr.addSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(3)
        app_lbl = QLabel(config.APP_NAME)
        app_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        app_lbl.setStyleSheet("color: #388bfd;")
        sub_lbl = QLabel(f"v{config.APP_VERSION}  ·  {config.AUTHOR}")
        sub_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
        col.addWidget(app_lbl)
        col.addWidget(sub_lbl)
        hdr.addLayout(col)
        hdr.addStretch()
        root.addLayout(hdr)

        # Tabs
        tabs = QTabWidget()

        info_w = QWidget()
        il = QVBoxLayout(info_w)
        il.setContentsMargins(10, 10, 10, 10)
        info_tb = QTextBrowser()
        info_tb.setOpenExternalLinks(True)
        info_tb.setHtml(f"""
            <p style="color:#8b949e;margin:0 0 10px;">{self._t('ABOUT_SUBTITLE')}</p>
            <table cellspacing="6">
                <tr><td style="color:#8b949e;padding-right:20px;">{self._t('ABOUT_AUTHOR_LBL')}</td>
                    <td style="color:#e6edf3;font-weight:bold;">{config.AUTHOR}</td></tr>
                <tr><td style="color:#8b949e;">{self._t('ABOUT_VERSION_LBL')}</td>
                    <td style="color:#e6edf3;">{config.APP_VERSION}</td></tr>
                <tr><td style="color:#8b949e;">{self._t('ABOUT_LICENSE_LBL')}</td>
                    <td style="color:#e6edf3;">Apache 2.0</td></tr>
                <tr><td style="color:#8b949e;">{self._t('ABOUT_REPO_LBL')}</td>
                    <td><a href="{config.GITHUB_URL}" style="color:#388bfd;">{config.GITHUB_URL}</a></td></tr>
            </table>
        """)
        il.addWidget(info_tb)
        tabs.addTab(info_w, self._t("ABOUT_TAB_INFO"))

        cr_w = QWidget()
        crl = QVBoxLayout(cr_w)
        crl.setContentsMargins(10, 10, 10, 10)
        cr_tb = QTextBrowser()
        cr_tb.setOpenExternalLinks(True)
        cr_tb.setHtml(self._t("ABOUT_CREDITS_BODY"))
        crl.addWidget(cr_tb)
        tabs.addTab(cr_w, self._t("ABOUT_TAB_CREDITS"))

        root.addWidget(tabs)

        btns = QHBoxLayout()
        btns.setSpacing(8)

        donate_btn = QPushButton(self._t("ABOUT_DONATE"))
        donate_btn.setStyleSheet("background-color:#8b5cf6;color:#fff;border:none;")
        donate_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(config.PAYPAL_URL)))
        btns.addWidget(donate_btn)

        gh_btn = QPushButton(self._t("ABOUT_GITHUB"))
        gh_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(config.GITHUB_URL)))
        btns.addWidget(gh_btn)

        btns.addStretch()

        close_btn = QPushButton(self._t("ABOUT_CLOSE"))
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)

        root.addLayout(btns)


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class ChangeFormatUSB(QMainWindow):

    def __init__(self):
        super().__init__()
        self.translator  = Translator()
        self.usb_manager = USBManager()
        self._devices    = []
        self._worker     = None
        self._converting = False

        self.setStyleSheet(MAIN_STYLE)
        self.setPalette(DarkPalette())
        self.setStyle(QStyleFactory.create("Fusion"))

        self._setup_ui()
        self._setup_menu()
        self.setWindowIcon(QIcon(resource_path("resources/icon.ico")))
        self._retranslate_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_devices)
        self._refresh_timer.start(config.REFRESH_INTERVAL)
        self._refresh_devices()

        if not is_admin():
            QTimer.singleShot(400, self._warn_admin)

    # ── shortcut ──────────────────────────────────────────────────────────
    def _t(self, key):
        return self.translator.gettext(key)

    # ─────────────────────────────── UI build ────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle(config.APP_NAME)
        self.setMinimumSize(880, 560)
        self.resize(980, 640)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_left_panel())
        root.addWidget(self._build_right_panel(), 1)

    # ── Left panel ────────────────────────────────────────────────────────

    def _build_left_panel(self):
        panel = QWidget()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(244)
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        header = QWidget()
        header.setObjectName("panelHeader")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(10)
        usb_ico = QLabel()
        usb_ico.setPixmap(load_svg("resources/icons/usb.svg", 20))
        hl.addWidget(usb_ico)
        title_lbl = QLabel(config.APP_NAME)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet("color: #e6edf3;")
        hl.addWidget(title_lbl)
        hl.addStretch()
        vl.addWidget(header)

        sec_row = QHBoxLayout()
        sec_row.setContentsMargins(14, 10, 10, 4)
        self._lbl_section_devices = QLabel()
        self._lbl_section_devices.setObjectName("sectionLabel")
        sec_row.addWidget(self._lbl_section_devices)
        sec_row.addStretch()

        self._refresh_btn = QPushButton()
        self._refresh_btn.setObjectName("refreshBtn")
        self._refresh_btn.setFixedSize(26, 26)
        self._refresh_btn.setIcon(QIcon(load_svg("resources/icons/refresh.svg", 16)))
        self._refresh_btn.setIconSize(QSize(16, 16))
        self._refresh_btn.clicked.connect(self._refresh_devices)
        sec_row.addWidget(self._refresh_btn)
        vl.addLayout(sec_row)

        self._device_list = QListWidget()
        self._device_list.setItemDelegate(DeviceItemDelegate())
        self._device_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._device_list.setFocusPolicy(Qt.NoFocus)
        self._device_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._device_list.itemSelectionChanged.connect(self._on_device_selected)
        vl.addWidget(self._device_list)

        self._lbl_no_dev = QLabel()
        self._lbl_no_dev.setObjectName("noDeviceLabel")
        self._lbl_no_dev.setAlignment(Qt.AlignCenter)
        self._lbl_no_dev.hide()
        vl.addWidget(self._lbl_no_dev)

        vl.addStretch()
        return panel

    # ── Right panel ───────────────────────────────────────────────────────

    def _build_right_panel(self):
        panel = QWidget()
        panel.setObjectName("rightPanel")
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(36, 30, 36, 30)
        vl.setSpacing(22)

        # Empty state
        self._empty_w = QWidget()
        el = QVBoxLayout(self._empty_w)
        el.setAlignment(Qt.AlignCenter)
        el.setSpacing(12)
        empty_ico = QLabel()
        empty_ico.setPixmap(load_svg("resources/icons/usb.svg", 64))
        empty_ico.setAlignment(Qt.AlignCenter)
        el.addWidget(empty_ico)
        self._lbl_empty_title = QLabel()
        self._lbl_empty_title.setObjectName("emptyTitle")
        self._lbl_empty_title.setAlignment(Qt.AlignCenter)
        el.addWidget(self._lbl_empty_title)
        self._lbl_empty_sub = QLabel()
        self._lbl_empty_sub.setObjectName("emptySubtitle")
        self._lbl_empty_sub.setAlignment(Qt.AlignCenter)
        el.addWidget(self._lbl_empty_sub)
        vl.addWidget(self._empty_w, 1)

        # Device content
        self._device_w = QWidget()
        self._device_w.hide()
        dl = QVBoxLayout(self._device_w)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(22)

        dh = QHBoxLayout()
        dh.setSpacing(14)
        self._dev_ico_lbl = QLabel()
        dh.addWidget(self._dev_ico_lbl)
        name_col = QVBoxLayout()
        name_col.setSpacing(3)
        self._dev_name_lbl = QLabel()
        self._dev_name_lbl.setObjectName("deviceName")
        self._dev_sub_lbl = QLabel()
        self._dev_sub_lbl.setObjectName("deviceSub")
        name_col.addWidget(self._dev_name_lbl)
        name_col.addWidget(self._dev_sub_lbl)
        dh.addLayout(name_col)
        dh.addStretch()
        self._fs_badge = QLabel()
        self._fs_badge.setObjectName("fsBadge")
        dh.addWidget(self._fs_badge)
        dl.addLayout(dh)

        # Info cards
        cr = QHBoxLayout()
        cr.setSpacing(12)
        self._card_total = self._make_card()
        self._card_free  = self._make_card()
        self._card_used  = self._make_card()
        cr.addWidget(self._card_total)
        cr.addWidget(self._card_free)
        cr.addWidget(self._card_used)
        dl.addLayout(cr)

        div = QFrame()
        div.setObjectName("divider")
        div.setFrameShape(QFrame.HLine)
        dl.addWidget(div)

        # Convert section
        self._lbl_section_convert = QLabel()
        self._lbl_section_convert.setObjectName("sectionTitle")
        dl.addWidget(self._lbl_section_convert)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(12)
        self._lbl_format = QLabel()
        self._lbl_format.setStyleSheet("color: #8b949e;")
        fmt_row.addWidget(self._lbl_format)
        self._format_combo = QComboBox()
        self._format_combo.addItems(config.SUPPORTED_FORMATS)
        fmt_row.addWidget(self._format_combo)
        fmt_row.addStretch()
        dl.addLayout(fmt_row)

        btn_row = QHBoxLayout()
        self._convert_btn = QPushButton()
        self._convert_btn.setObjectName("convertBtn")
        self._convert_btn.setIcon(QIcon(load_svg("resources/icons/convert.svg", 18)))
        self._convert_btn.setIconSize(QSize(18, 18))
        self._convert_btn.setFixedHeight(46)
        self._convert_btn.clicked.connect(self._start_conversion)
        btn_row.addWidget(self._convert_btn)
        btn_row.addStretch()
        dl.addLayout(btn_row)

        # Progress section
        self._progress_w = QWidget()
        self._progress_w.hide()
        pl = QVBoxLayout(self._progress_w)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(8)
        status_row = QHBoxLayout()
        self._status_lbl = QLabel()
        self._status_lbl.setObjectName("statusLabel")
        status_row.addWidget(self._status_lbl, 1)
        self._cancel_btn = QPushButton()
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setFixedHeight(28)
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        status_row.addWidget(self._cancel_btn)
        pl.addLayout(status_row)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        pl.addWidget(self._progress_bar)
        dl.addWidget(self._progress_w)
        dl.addStretch()

        vl.addWidget(self._device_w, 1)
        return panel

    def _make_card(self):
        card = QWidget()
        card.setObjectName("infoCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumHeight(74)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(4)
        card._val = QLabel("—")
        card._val.setObjectName("cardValue")
        card._cap = QLabel()
        card._cap.setObjectName("cardLabel")
        cl.addWidget(card._val)
        cl.addWidget(card._cap)
        return card

    # ─────────────────────────────── i18n ────────────────────────────────

    def _retranslate_ui(self):
        """Update every translatable string in the window."""
        t = self._t

        self.setWindowTitle(config.APP_NAME)

        # Left panel
        self._lbl_section_devices.setText(t("SECTION_DEVICES"))
        self._lbl_no_dev.setText(t("NO_DEVICES"))
        self._refresh_btn.setToolTip(t("REFRESH_TOOLTIP"))

        # Empty state
        self._lbl_empty_title.setText(t("EMPTY_TITLE"))
        self._lbl_empty_sub.setText(t("EMPTY_SUBTITLE"))

        # Info cards captions
        self._card_total._cap.setText(t("CARD_TOTAL"))
        self._card_free._cap.setText(t("CARD_FREE"))
        self._card_used._cap.setText(t("CARD_USED"))

        # Convert section
        self._lbl_section_convert.setText(t("SECTION_CONVERT"))
        self._lbl_format.setText(t("FORMAT_LABEL"))
        self._convert_btn.setText(t("CONVERT_BTN"))
        self._cancel_btn.setText(t("CANCEL_BTN"))

        # Status (only if not in the middle of something)
        if not self._converting:
            self._status_lbl.setText(t("STATUS_PREPARING"))

        # Menu bar — rebuild to apply new text
        self._setup_menu()

    # ─────────────────────────────── Menu ────────────────────────────────

    def _setup_menu(self):
        mb = self.menuBar()
        mb.clear()

        lang_menu = mb.addMenu(self._t("MENU_LANGUAGE"))
        for code, name in self.translator.get_available_languages().items():
            act = QAction(name, self)
            act.triggered.connect(lambda _, c=code: self._change_language(c))
            lang_menu.addAction(act)

        help_menu = mb.addMenu(self._t("MENU_HELP"))
        about_act = QAction(self._t("MENU_ABOUT"), self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _change_language(self, code):
        self.translator.set_language(code)
        self._retranslate_ui()

    # ─────────────────────────────── Devices ─────────────────────────────

    def _refresh_devices(self):
        sel_letter = None
        cur = self._device_list.currentItem()
        if cur:
            d = cur.data(Qt.UserRole)
            if d:
                sel_letter = d.get("letter")

        self._devices = self.usb_manager.get_usb_devices()
        self._device_list.clear()

        if self._devices:
            self._lbl_no_dev.hide()
            restore_item = None
            for dev in self._devices:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, dev)
                item.setSizeHint(QSize(200, 56))
                self._device_list.addItem(item)
                if dev.get("letter") == sel_letter:
                    restore_item = item
            if restore_item:
                self._device_list.setCurrentItem(restore_item)
        else:
            self._lbl_no_dev.show()
            self._show_empty_state()

    def _on_device_selected(self):
        items = self._device_list.selectedItems()
        if not items:
            self._show_empty_state()
            return
        device = items[0].data(Qt.UserRole)
        if device:
            self._show_device_info(device)

    def _show_empty_state(self):
        self._empty_w.show()
        self._device_w.hide()

    def _show_device_info(self, device):
        self._empty_w.hide()
        self._device_w.show()

        letter = device.get("letter", "?:").replace("\\", "")
        label  = device.get("label", "Unidad USB")
        fs     = (device.get("filesystem") or "FAT32").upper()
        total  = int(device.get("size") or 0)
        free   = int(device.get("free") or 0)
        used   = total - free

        def fmt(b):
            if b >= 1024 ** 3:
                return f"{b / 1024**3:.1f} GB"
            if b >= 1024 ** 2:
                return f"{b / 1024**2:.0f} MB"
            return f"{b / 1024:.0f} KB"

        self._dev_ico_lbl.setPixmap(load_svg("resources/icons/usb.svg", 32))
        self._dev_name_lbl.setText(label)
        self._dev_sub_lbl.setText(f"{letter}  ·  {fmt(total)}")

        _fs_map = {
            "NTFS":  ("#388bfd", "#1a2d4d"),
            "FAT32": ("#3fb950", "#1a3327"),
            "EXFAT": ("#d29922", "#362a0f"),
            "REFS":  ("#bc8cff", "#2b1f4a"),
        }
        fc, bc = _fs_map.get(fs, ("#8b949e", "#21262d"))
        self._fs_badge.setText(fs)
        self._fs_badge.setStyleSheet(
            f"background-color:{bc}; color:{fc}; "
            f"border:1px solid {fc}; border-radius:10px; "
            f"padding:3px 12px; font-weight:bold; font-size:12px;"
        )

        self._card_total._val.setText(fmt(total))
        self._card_free._val.setText(fmt(free))
        self._card_used._val.setText(fmt(used))

        fs_display = fs.replace("EXFAT", "exFAT")
        try:
            cur_idx = config.SUPPORTED_FORMATS.index(fs_display)
        except ValueError:
            cur_idx = 0
        self._format_combo.setCurrentIndex((cur_idx + 1) % len(config.SUPPORTED_FORMATS))

        self._convert_btn.setEnabled(not self._converting)

    # ─────────────────────────────── Conversion ──────────────────────────

    def _start_conversion(self):
        items = self._device_list.selectedItems()
        if not items:
            return
        device = items[0].data(Qt.UserRole)
        if not device:
            return

        letter     = device.get("letter", "?:").replace("\\", "")
        new_fs     = self._format_combo.currentText()
        current_fs = (device.get("filesystem") or "").upper()

        if _same_format(current_fs, new_fs.upper()):
            self._msgbox(
                QMessageBox.Information,
                self._t("SAME_FORMAT_TITLE"),
                self._t("SAME_FORMAT_MSG").format(drive=letter, format=new_fs),
            )
            return

        confirm_msg = self._t("CONFIRM_MSG").format(
            drive=letter, format=new_fs, current=current_fs
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle(self._t("CONFIRM_TITLE"))
        dlg.setIcon(QMessageBox.Question)
        dlg.setText(confirm_msg)
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dlg.setDefaultButton(QMessageBox.No)
        dlg.setStyleSheet(self._MSG_STYLE)
        if dlg.exec_() != QMessageBox.Yes:
            return

        self._converting = True
        self._convert_btn.setEnabled(False)
        self._device_list.setEnabled(False)
        self._format_combo.setEnabled(False)
        self._progress_w.show()
        self._progress_bar.setValue(0)
        self._status_lbl.setText(self._t("STATUS_PREPARING"))
        self._cancel_btn.setEnabled(True)

        self._worker = ConversionWorker(letter, new_fs, self)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _cancel_conversion(self):
        if self._worker and self._worker.isRunning():
            self._status_lbl.setText(self._t("STATUS_CANCELLING"))
            self._cancel_btn.setEnabled(False)
            self._worker.cancel()

    def _on_progress(self, message, percent):
        self._status_lbl.setText(message)
        self._progress_bar.setValue(percent)

    def _on_finished(self, drive_letter):
        self._progress_bar.setValue(100)
        self._status_lbl.setText(self._t("STATUS_DONE"))
        self._unlock_ui()
        self._msgbox(
            QMessageBox.Information,
            self._t("SUCCESS_TITLE"),
            self._t("SUCCESS_MSG").format(drive=drive_letter),
        )
        self._progress_w.hide()
        self._worker = None
        QTimer.singleShot(800, self._refresh_devices)

    def _on_error(self, error_msg):
        self._status_lbl.setText(self._t("STATUS_ERROR"))
        self._unlock_ui()
        self._msgbox(
            QMessageBox.Critical,
            self._t("ERROR_TITLE"),
            self._t("ERROR_MSG").format(error=error_msg),
        )
        self._progress_w.hide()
        self._worker = None

    def _unlock_ui(self):
        self._converting = False
        self._convert_btn.setEnabled(True)
        self._device_list.setEnabled(True)
        self._format_combo.setEnabled(True)
        self._cancel_btn.setEnabled(True)

    # ─────────────────────────────── Helpers ─────────────────────────────

    _MSG_STYLE = """
        QMessageBox { background-color: #161b22; }
        QLabel      { color: #e6edf3; }
        QPushButton { background-color: #21262d; color: #e6edf3;
                      border: 1px solid #30363d; border-radius: 5px;
                      padding: 7px 18px; min-width: 70px; }
        QPushButton:hover { background-color: #30363d; }
    """

    def _msgbox(self, icon, title, text):
        dlg = QMessageBox(self)
        dlg.setIcon(icon)
        dlg.setWindowTitle(title)
        dlg.setText(text)
        dlg.setStyleSheet(self._MSG_STYLE)
        dlg.exec_()

    def _show_about(self):
        AboutDialog(self.translator, self).exec_()

    def _warn_admin(self):
        self._msgbox(
            QMessageBox.Warning,
            self._t("ADMIN_REQUIRED_TITLE"),
            self._t("ADMIN_REQUIRED_MSG"),
        )

    def closeEvent(self, event):
        if self._converting and self._worker and self._worker.isRunning():
            dlg = QMessageBox(self)
            dlg.setWindowTitle(self._t("CLOSE_TITLE"))
            dlg.setIcon(QMessageBox.Warning)
            dlg.setText(self._t("CLOSE_MSG"))
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            dlg.setDefaultButton(QMessageBox.No)
            dlg.setStyleSheet(self._MSG_STYLE)
            if dlg.exec_() == QMessageBox.Yes:
                self._worker.cancel()
                self._worker.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ─────────────────────────────────────────────────────────────────────────────

def _same_format(a, b):
    if a == b:
        return True
    if a in ("FAT", "FAT32") and b in ("FAT", "FAT32"):
        return True
    return False
