import os
import logging
import webbrowser

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QListWidget, QListWidgetItem, QProgressBar,
    QMenu, QAction, QMessageBox, QDialog, QTextBrowser,
    QSizePolicy, QFrame, QAbstractItemView, QApplication, QStyle,
    QStyledItemDelegate, QTabWidget, QStyleFactory,
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, QThread, pyqtSignal, QUrl,
)
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


# ──────────────────────────────────────────────────────────────────────────────
# SVG helper
# ──────────────────────────────────────────────────────────────────────────────

def load_svg(relative_path, size=24):
    """Render an SVG resource file into a QPixmap of the given pixel size."""
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


# ──────────────────────────────────────────────────────────────────────────────
# Custom list-item delegate — draws a modern card per device
# ──────────────────────────────────────────────────────────────────────────────

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

        # Card background
        if selected:
            bg_col     = QColor("#1f3352")
            border_col = QColor("#388bfd")
        elif hovered:
            bg_col     = QColor("#21262d")
            border_col = QColor("#30363d")
        else:
            bg_col     = QColor("#161b22")
            border_col = QColor("#30363d")

        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_col)
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(border_col, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)

        # Small accent dot (acts as a quick USB indicator)
        dot_x = rect.left() + 14
        dot_y = rect.center().y()
        dot_r = 4
        dot_col = QColor("#388bfd") if selected else QColor("#484f58")
        painter.setPen(Qt.NoPen)
        painter.setBrush(dot_col)
        painter.drawEllipse(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)

        # Drive letter + label
        tx = dot_x + dot_r + 10
        letter = device.get("letter", "?:").replace("\\", "")
        label  = device.get("label", "Unidad USB")

        painter.setPen(QColor("#e6edf3"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(tx, rect.top() + 19, letter)

        painter.setPen(QColor("#8b949e"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(tx, rect.top() + 33, label[:26])

        # FS badge (right side)
        fs = (device.get("filesystem") or "?").upper()
        fg, bg2 = self._FS_COLORS.get(fs, ("#8b949e", "#21262d"))
        badge_w, badge_h = 50, 18
        bx = rect.right() - badge_w - 8
        by = rect.center().y() - badge_h // 2

        bg2_c = QColor(bg2)
        painter.setBrush(bg2_c)
        painter.setPen(QPen(QColor(fg), 1))
        painter.drawRoundedRect(bx, by, badge_w, badge_h, 9, 9)

        painter.setPen(QColor(fg))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(bx, by, badge_w, badge_h, Qt.AlignCenter, fs)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(200, 56)


# ──────────────────────────────────────────────────────────────────────────────
# Background conversion thread
# ──────────────────────────────────────────────────────────────────────────────

class ConversionWorker(QThread):
    finished        = pyqtSignal(str)         # drive letter on success
    error           = pyqtSignal(str)         # error message
    progress_updated = pyqtSignal(str, int)   # (status message, 0-100)

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


# ──────────────────────────────────────────────────────────────────────────────
# About dialog
# ──────────────────────────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    _STYLE = """
        QDialog        { background-color: #0d1117; }
        QLabel         { color: #e6edf3; }
        QTextBrowser   {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #e6edf3;
            padding: 10px;
        }
        QPushButton {
            background-color: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 7px 16px;
            font-weight: 600;
        }
        QPushButton:hover { background-color: #30363d; }
        QTabWidget::pane {
            border: 1px solid #30363d;
            border-radius: 6px;
            background-color: #161b22;
        }
        QTabBar::tab {
            background: #21262d;
            color: #8b949e;
            padding: 7px 20px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        QTabBar::tab:selected { background: #388bfd; color: #ffffff; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {config.APP_NAME}")
        self.setFixedSize(480, 390)
        self.setStyleSheet(self._STYLE)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        # Header ──────────────────────────────────────────
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

        # Tabs ────────────────────────────────────────────
        tabs = QTabWidget()

        # — Info tab
        info_w = QWidget()
        il = QVBoxLayout(info_w)
        il.setContentsMargins(10, 10, 10, 10)
        info_tb = QTextBrowser()
        info_tb.setOpenExternalLinks(True)
        info_tb.setHtml(f"""
            <p style="color:#8b949e;margin:0 0 10px;">
                Herramienta para convertir el formato de unidades USB<br>sin perder datos.
            </p>
            <table cellspacing="6">
                <tr>
                    <td style="color:#8b949e;padding-right:20px;">Autor</td>
                    <td style="color:#e6edf3;font-weight:bold;">{config.AUTHOR}</td>
                </tr>
                <tr>
                    <td style="color:#8b949e;">Version</td>
                    <td style="color:#e6edf3;">{config.APP_VERSION}</td>
                </tr>
                <tr>
                    <td style="color:#8b949e;">Licencia</td>
                    <td style="color:#e6edf3;">Apache 2.0</td>
                </tr>
                <tr>
                    <td style="color:#8b949e;">Repositorio</td>
                    <td>
                        <a href="{config.GITHUB_URL}" style="color:#388bfd;">
                            {config.GITHUB_URL}
                        </a>
                    </td>
                </tr>
            </table>
        """)
        il.addWidget(info_tb)
        tabs.addTab(info_w, "Informacion")

        # — Credits tab
        cr_w = QWidget()
        crl = QVBoxLayout(cr_w)
        crl.setContentsMargins(10, 10, 10, 10)
        cr_tb = QTextBrowser()
        cr_tb.setOpenExternalLinks(True)
        cr_tb.setHtml("""
            <p style="color:#8b949e;">Desarrollado con:</p>
            <ul style="color:#e6edf3;margin:0;padding-left:18px;">
                <li>Python 3.12</li>
                <li>PyQt5 — interfaz grafica</li>
                <li>PyInstaller — distribución ejecutable</li>
                <li>psutil, wmi, pywin32 — integracion Windows</li>
            </ul>
            <p style="color:#8b949e;margin-top:12px;">
                Iconos SVG de
                <a href="https://www.svgrepo.com" style="color:#388bfd;">svgrepo.com</a>
            </p>
        """)
        crl.addWidget(cr_tb)
        tabs.addTab(cr_w, "Creditos")

        root.addWidget(tabs)

        # Bottom buttons ──────────────────────────────────
        btns = QHBoxLayout()
        btns.setSpacing(8)

        donate_btn = QPushButton("Donar")
        donate_btn.setStyleSheet(
            "background-color:#8b5cf6;color:#fff;border:none;"
        )
        donate_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(config.PAYPAL_URL))
        )
        btns.addWidget(donate_btn)

        gh_btn = QPushButton("GitHub")
        gh_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(config.GITHUB_URL))
        )
        btns.addWidget(gh_btn)

        btns.addStretch()

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)

        root.addLayout(btns)


# ──────────────────────────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────────────────────────

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

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_devices)
        self._refresh_timer.start(config.REFRESH_INTERVAL)
        self._refresh_devices()

        if not is_admin():
            QTimer.singleShot(400, self._warn_admin)

    # ─────────────────────────────── UI build ──────────────────────────────

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

    # ── Left panel ───────────────────────────────────────────────────────

    def _build_left_panel(self):
        panel = QWidget()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(244)
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # Header
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

        # Section row
        sec_row = QHBoxLayout()
        sec_row.setContentsMargins(14, 10, 10, 4)
        sec_lbl = QLabel("DISPOSITIVOS")
        sec_lbl.setObjectName("sectionLabel")
        sec_row.addWidget(sec_lbl)
        sec_row.addStretch()

        self._refresh_btn = QPushButton()
        self._refresh_btn.setObjectName("refreshBtn")
        self._refresh_btn.setFixedSize(26, 26)
        self._refresh_btn.setIcon(QIcon(load_svg("resources/icons/refresh.svg", 16)))
        self._refresh_btn.setIconSize(QSize(16, 16))
        self._refresh_btn.setToolTip("Actualizar lista")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        sec_row.addWidget(self._refresh_btn)
        vl.addLayout(sec_row)

        # Device list
        self._device_list = QListWidget()
        self._device_list.setItemDelegate(DeviceItemDelegate())
        self._device_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._device_list.setFocusPolicy(Qt.NoFocus)
        self._device_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._device_list.itemSelectionChanged.connect(self._on_device_selected)
        vl.addWidget(self._device_list)

        # No-device hint
        self._no_dev_lbl = QLabel("Sin dispositivos USB")
        self._no_dev_lbl.setObjectName("noDeviceLabel")
        self._no_dev_lbl.setAlignment(Qt.AlignCenter)
        self._no_dev_lbl.hide()
        vl.addWidget(self._no_dev_lbl)

        vl.addStretch()
        return panel

    # ── Right panel ──────────────────────────────────────────────────────

    def _build_right_panel(self):
        panel = QWidget()
        panel.setObjectName("rightPanel")
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(36, 30, 36, 30)
        vl.setSpacing(22)

        # ── Empty state
        self._empty_w = QWidget()
        el = QVBoxLayout(self._empty_w)
        el.setAlignment(Qt.AlignCenter)
        el.setSpacing(12)

        empty_ico = QLabel()
        empty_ico.setPixmap(load_svg("resources/icons/usb.svg", 64))
        empty_ico.setAlignment(Qt.AlignCenter)
        el.addWidget(empty_ico)

        e_title = QLabel("Selecciona un dispositivo USB")
        e_title.setObjectName("emptyTitle")
        e_title.setAlignment(Qt.AlignCenter)
        el.addWidget(e_title)

        e_sub = QLabel("Los dispositivos conectados aparecen en el panel izquierdo.")
        e_sub.setObjectName("emptySubtitle")
        e_sub.setAlignment(Qt.AlignCenter)
        el.addWidget(e_sub)

        vl.addWidget(self._empty_w, 1)

        # ── Device content (hidden until device selected)
        self._device_w = QWidget()
        self._device_w.hide()
        dl = QVBoxLayout(self._device_w)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(22)

        # Device header
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

        # Info cards row
        cr = QHBoxLayout()
        cr.setSpacing(12)
        self._card_total = self._make_card("Total")
        self._card_free  = self._make_card("Libre")
        self._card_used  = self._make_card("Usado")
        cr.addWidget(self._card_total)
        cr.addWidget(self._card_free)
        cr.addWidget(self._card_used)
        dl.addLayout(cr)

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFrameShape(QFrame.HLine)
        dl.addWidget(div)

        # Convert-to section
        sec = QLabel("CONVERTIR FORMATO")
        sec.setObjectName("sectionTitle")
        dl.addWidget(sec)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(12)
        fmt_lbl = QLabel("Formato de destino:")
        fmt_lbl.setStyleSheet("color: #8b949e;")
        fmt_row.addWidget(fmt_lbl)
        self._format_combo = QComboBox()
        self._format_combo.addItems(config.SUPPORTED_FORMATS)
        fmt_row.addWidget(self._format_combo)
        fmt_row.addStretch()
        dl.addLayout(fmt_row)

        # Convert button
        btn_row = QHBoxLayout()
        self._convert_btn = QPushButton("  Convertir Formato")
        self._convert_btn.setObjectName("convertBtn")
        conv_ico = load_svg("resources/icons/convert.svg", 18)
        self._convert_btn.setIcon(QIcon(conv_ico))
        self._convert_btn.setIconSize(QSize(18, 18))
        self._convert_btn.setFixedHeight(46)
        self._convert_btn.clicked.connect(self._start_conversion)
        btn_row.addWidget(self._convert_btn)
        btn_row.addStretch()
        dl.addLayout(btn_row)

        # Progress section (hidden initially)
        self._progress_w = QWidget()
        self._progress_w.hide()
        pl = QVBoxLayout(self._progress_w)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(8)

        status_row = QHBoxLayout()
        self._status_lbl = QLabel("Preparando...")
        self._status_lbl.setObjectName("statusLabel")
        status_row.addWidget(self._status_lbl, 1)

        self._cancel_btn = QPushButton("Cancelar")
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

    def _make_card(self, caption):
        card = QWidget()
        card.setObjectName("infoCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumHeight(74)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(4)
        val = QLabel("—")
        val.setObjectName("cardValue")
        lbl = QLabel(caption)
        lbl.setObjectName("cardLabel")
        cl.addWidget(val)
        cl.addWidget(lbl)
        card._val = val
        return card

    # ─────────────────────────────── Menu ──────────────────────────────────

    def _setup_menu(self):
        mb = self.menuBar()

        lang_menu = mb.addMenu("Idioma")
        for code, name in self.translator.get_available_languages().items():
            act = QAction(name, self)
            act.triggered.connect(lambda _, c=code: self.translator.set_language(c))
            lang_menu.addAction(act)

        help_menu = mb.addMenu("Ayuda")
        about_act = QAction("Acerca de", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ─────────────────────────────── Devices ───────────────────────────────

    def _refresh_devices(self):
        # Preserve current selection by drive letter
        sel_letter = None
        cur = self._device_list.currentItem()
        if cur:
            d = cur.data(Qt.UserRole)
            if d:
                sel_letter = d.get("letter")

        self._devices = self.usb_manager.get_usb_devices()
        self._device_list.clear()

        if self._devices:
            self._no_dev_lbl.hide()
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
            self._no_dev_lbl.show()
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

        # Header
        self._dev_ico_lbl.setPixmap(load_svg("resources/icons/usb.svg", 32))
        self._dev_name_lbl.setText(label)
        self._dev_sub_lbl.setText(f"{letter}  ·  {fmt(total)}")

        # FS badge
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

        # Cards
        self._card_total._val.setText(fmt(total))
        self._card_free._val.setText(fmt(free))
        self._card_used._val.setText(fmt(used))

        # Pre-select a different format than current
        fs_display = fs.replace("EXFAT", "exFAT")
        try:
            cur_idx = config.SUPPORTED_FORMATS.index(fs_display)
        except ValueError:
            cur_idx = 0
        self._format_combo.setCurrentIndex((cur_idx + 1) % len(config.SUPPORTED_FORMATS))

        self._convert_btn.setEnabled(not self._converting)

    # ─────────────────────────────── Conversion ────────────────────────────

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

        # Same-format check
        if _same_format(current_fs, new_fs.upper()):
            self._msgbox(
                QMessageBox.Information,
                "Sin cambios",
                f"La unidad {letter} ya usa el formato {new_fs}.\n"
                "Selecciona un formato diferente.",
            )
            return

        # Confirmation
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Confirmar conversion")
        dlg.setIcon(QMessageBox.Question)
        dlg.setText(
            f"<b>Convertir {letter} → {new_fs}</b><br><br>"
            f"Formato actual: <b>{current_fs}</b><br>"
            f"Formato nuevo:  <b>{new_fs}</b><br><br>"
            "Se intentara preservar todos los datos de la unidad.<br>"
            "<span style='color:#d29922;font-size:12px;'>"
            "Se recomienda tener un respaldo antes de continuar."
            "</span>"
        )
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dlg.setDefaultButton(QMessageBox.No)
        dlg.setStyleSheet(self._MSG_STYLE)
        if dlg.exec_() != QMessageBox.Yes:
            return

        # Lock UI
        self._converting = True
        self._convert_btn.setEnabled(False)
        self._device_list.setEnabled(False)
        self._format_combo.setEnabled(False)
        self._progress_w.show()
        self._progress_bar.setValue(0)
        self._status_lbl.setText("Iniciando conversion...")
        self._cancel_btn.setEnabled(True)

        self._worker = ConversionWorker(letter, new_fs, self)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _cancel_conversion(self):
        if self._worker and self._worker.isRunning():
            self._status_lbl.setText("Cancelando operacion...")
            self._cancel_btn.setEnabled(False)
            self._worker.cancel()

    def _on_progress(self, message, percent):
        self._status_lbl.setText(message)
        self._progress_bar.setValue(percent)

    def _on_finished(self, drive_letter):
        self._progress_bar.setValue(100)
        self._status_lbl.setText("Conversion completada")
        self._unlock_ui()
        self._msgbox(
            QMessageBox.Information,
            "Conversion exitosa",
            f"La unidad <b>{drive_letter}</b> fue convertida correctamente.",
        )
        self._progress_w.hide()
        self._worker = None
        QTimer.singleShot(800, self._refresh_devices)

    def _on_error(self, error_msg):
        self._status_lbl.setText("Error durante la conversion")
        self._unlock_ui()
        self._msgbox(
            QMessageBox.Critical,
            "Error en la conversion",
            f"<b>Se produjo un error:</b><br><br>{error_msg}",
        )
        self._progress_w.hide()
        self._worker = None

    def _unlock_ui(self):
        self._converting = False
        self._convert_btn.setEnabled(True)
        self._device_list.setEnabled(True)
        self._format_combo.setEnabled(True)
        self._cancel_btn.setEnabled(True)

    # ─────────────────────────────── Helpers ───────────────────────────────

    _MSG_STYLE = """
        QMessageBox  { background-color: #161b22; }
        QLabel       { color: #e6edf3; }
        QPushButton  {
            background-color: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 5px;
            padding: 7px 18px;
            min-width: 70px;
        }
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
        AboutDialog(self).exec_()

    def _warn_admin(self):
        self._msgbox(
            QMessageBox.Warning,
            "Permisos de administrador",
            "<b>Se requieren permisos de administrador.</b><br><br>"
            "Algunas operaciones pueden fallar sin privilegios elevados.<br>"
            "Ejecuta el programa como administrador para mejores resultados.",
        )

    def closeEvent(self, event):
        if self._converting and self._worker and self._worker.isRunning():
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Conversion en progreso")
            dlg.setIcon(QMessageBox.Warning)
            dlg.setText(
                "<b>Hay una conversion en curso.</b><br><br>"
                "Si sales ahora la unidad podria quedar en un estado inconsistente.<br>"
                "¿Seguro que deseas salir?"
            )
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


def _same_format(a, b):
    """Return True if a and b represent the same effective filesystem."""
    if a == b:
        return True
    if a in ("FAT", "FAT32") and b in ("FAT", "FAT32"):
        return True
    return False
