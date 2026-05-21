"""
ChangeFormatUSB — Self-contained installer wizard.
Embeds ChangeFormatUSB.exe as payload; no external tools required.
"""

import os
import sys
import shutil
import subprocess
import winreg

from PyQt5.QtCore    import Qt, QThread, pyqtSignal
from PyQt5.QtGui     import QPalette, QColor, QPixmap, QPainter
from PyQt5.QtSvg     import QSvgRenderer
from PyQt5.QtWidgets import (
    QApplication, QDialog, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QTextEdit, QProgressBar,
    QFileDialog, QFrame, QMessageBox,
)


# ─── constants ────────────────────────────────────────────────────────────────

APP_NAME      = "ChangeFormatUSB"
APP_VERSION   = "2.0"
PUBLISHER     = "Vicemi"
REGISTRY_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ChangeFormatUSB"

DEFAULT_INSTALL_DIR = os.path.join(
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    APP_NAME,
)

WIZARD_STEPS = ["Welcome", "Options", "Install", "Finish"]


# ─── resource helpers ─────────────────────────────────────────────────────────

def _base_dir() -> str:
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    # dev: file is in setup/, resources are one level up
    return os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def resource_path(rel: str) -> str:
    return os.path.join(_base_dir(), rel)


def payload_path() -> str:
    return resource_path(os.path.join("dist", "ChangeFormatUSB.exe"))


def load_svg(rel: str, size: int = 48) -> QPixmap:
    full = resource_path(rel)
    renderer = QSvgRenderer(full)
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    renderer.render(painter)
    painter.end()
    return px


# ─── stylesheet ───────────────────────────────────────────────────────────────

STYLE = """
QDialog, QWidget {
    background: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QFrame#sidebar {
    background: #010409;
    border-right: 1px solid #21262d;
}
QFrame#bottomBar {
    background: #161b22;
    border-top: 1px solid #21262d;
}
/* ── step labels ── */
QLabel#step     { color:#484f58;  font-size:11px; padding:4px 16px; }
QLabel#stepDone { color:#3fb950;  font-size:11px; padding:4px 16px; }
QLabel#stepActive{color:#388bfd;  font-size:11px; font-weight:700; padding:4px 16px; }
/* ── page titles ── */
QLabel#pageTitle { color:#e6edf3; font-size:17px; font-weight:700; }
QLabel#pageSub   { color:#8b949e; font-size:12px; }
/* ── inputs ── */
QLineEdit {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e6edf3;
    selection-background-color: #388bfd;
}
QLineEdit:focus { border-color: #388bfd; }
/* ── checkboxes ── */
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width:16px; height:16px;
    border:1px solid #30363d;
    border-radius:4px;
    background:#161b22;
}
QCheckBox::indicator:checked {
    background:#388bfd;
    border-color:#388bfd;
    image: url();        /* ticked via color only */
}
/* ── progress ── */
QProgressBar {
    background:#21262d;
    border:none;
    border-radius:4px;
    height:8px;
    text-align:center;
    color:transparent;
}
QProgressBar::chunk { background:#388bfd; border-radius:4px; }
/* ── log ── */
QTextEdit {
    background:#161b22;
    border:1px solid #21262d;
    border-radius:6px;
    color:#8b949e;
    font-family:'Consolas', monospace;
    font-size:11px;
    padding:6px;
}
/* ── navigation buttons ── */
QPushButton#nextBtn {
    background:#238636; color:#e6edf3;
    border:none; border-radius:6px;
    padding:8px 24px; font-size:13px; font-weight:500;
    min-width:100px;
}
QPushButton#nextBtn:hover    { background:#2ea043; }
QPushButton#nextBtn:disabled { background:#21262d; color:#484f58; }
QPushButton#backBtn, QPushButton#cancelBtn {
    background:transparent; color:#8b949e;
    border:1px solid #30363d; border-radius:6px;
    padding:8px 18px; font-size:13px; min-width:70px;
}
QPushButton#backBtn:hover, QPushButton#cancelBtn:hover {
    background:#21262d; color:#e6edf3; border-color:#8b949e;
}
QPushButton#browseBtn {
    background:#161b22; color:#8b949e;
    border:1px solid #30363d; border-radius:6px;
    padding:6px 14px; font-size:12px;
}
QPushButton#browseBtn:hover { background:#21262d; color:#e6edf3; }
/* ── section labels ── */
QLabel#sectionLbl {
    color:#484f58; font-size:10px; font-weight:700;
    letter-spacing:1px;
}
"""


# ─── uninstaller batch template ───────────────────────────────────────────────

_UNINSTALL_BAT = """\
@echo off
setlocal
echo.
echo  ChangeFormatUSB Uninstaller
echo  ===========================
echo.
echo  Press any key to remove ChangeFormatUSB or close this window to cancel.
pause > nul
echo.
echo  Removing application files...
rd /s /q "{install_dir}" 2>nul
echo  Removing registry entries...
reg delete "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ChangeFormatUSB" /f 2>nul
echo  Removing shortcuts...
del /f /q "{desktop_lnk}" 2>nul
del /f /q "{startmenu_lnk}" 2>nul
echo.
echo  Uninstallation complete.
echo.
pause
(goto) 2>nul & del "%~f0"
"""


# ─── installation worker ──────────────────────────────────────────────────────

class InstallWorker(QThread):
    logged   = pyqtSignal(str)
    advanced = pyqtSignal(int)   # 0–100
    finished = pyqtSignal(bool, str)

    def __init__(self, install_dir: str, desktop: bool, start_menu: bool):
        super().__init__()
        self.install_dir  = install_dir
        self.desktop      = desktop
        self.start_menu   = start_menu

    # shortcuts
    @property
    def _desktop_lnk(self) -> str:
        return os.path.join(
            os.environ.get("PUBLIC", r"C:\Users\Public"),
            "Desktop", f"{APP_NAME}.lnk"
        )

    @property
    def _startmenu_lnk(self) -> str:
        return os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs",
            f"{APP_NAME}.lnk"
        )

    def run(self):
        try:
            self._do_install()
            self.finished.emit(True, "")
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _step(self, msg: str, pct: int):
        self.logged.emit(msg)
        self.advanced.emit(pct)

    def _do_install(self):
        dst_exe = os.path.join(self.install_dir, "ChangeFormatUSB.exe")

        # 1 — create directory
        self._step(f"Creating directory: {self.install_dir}", 10)
        os.makedirs(self.install_dir, exist_ok=True)

        # 2 — copy payload
        src = payload_path()
        if not os.path.isfile(src):
            raise FileNotFoundError(f"Payload not found: {src}")
        self._step("Copying ChangeFormatUSB.exe ...", 30)
        shutil.copy2(src, dst_exe)

        # 3 — write uninstaller batch
        self._step("Writing uninstaller ...", 50)
        uninstall_bat = os.path.join(self.install_dir, "uninstall.bat")
        with open(uninstall_bat, "w", encoding="utf-8") as fh:
            fh.write(_UNINSTALL_BAT.format(
                install_dir  = self.install_dir,
                desktop_lnk  = self._desktop_lnk,
                startmenu_lnk= self._startmenu_lnk,
            ))

        # 4 — register in Windows Programs & Features
        self._step("Registering in Windows ...", 65)
        self._write_registry(dst_exe, uninstall_bat)

        # 5 — desktop shortcut
        if self.desktop:
            self._step("Creating desktop shortcut ...", 78)
            self._create_lnk(dst_exe, self._desktop_lnk)

        # 6 — Start Menu shortcut
        if self.start_menu:
            self._step("Creating Start Menu shortcut ...", 88)
            self._create_lnk(dst_exe, self._startmenu_lnk)

        self._step("Done.", 100)

    def _write_registry(self, exe_path: str, uninstall_bat: str):
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY)
        entries = [
            ("DisplayName",      winreg.REG_SZ,    APP_NAME),
            ("DisplayVersion",   winreg.REG_SZ,    APP_VERSION),
            ("Publisher",        winreg.REG_SZ,    PUBLISHER),
            ("InstallLocation",  winreg.REG_SZ,    self.install_dir),
            ("DisplayIcon",      winreg.REG_SZ,    exe_path),
            ("UninstallString",  winreg.REG_SZ,    f'cmd /c "{uninstall_bat}"'),
            ("NoModify",         winreg.REG_DWORD,  1),
            ("NoRepair",         winreg.REG_DWORD,  1),
        ]
        for name, kind, value in entries:
            winreg.SetValueEx(key, name, 0, kind, value)
        winreg.CloseKey(key)

    def _create_lnk(self, target: str, link_path: str):
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        sc    = shell.CreateShortCut(link_path)
        sc.TargetPath       = target
        sc.WorkingDirectory = os.path.dirname(target)
        sc.IconLocation     = target
        sc.save()


# ─── wizard pages ─────────────────────────────────────────────────────────────

class BasePage(QWidget):
    def on_enter(self): pass


class WelcomePage(BasePage):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 16)
        lay.setSpacing(0)

        # icon
        ico = QLabel()
        ico.setPixmap(load_svg("resources/icons/usb.svg", 60))
        ico.setAlignment(Qt.AlignCenter)
        lay.addWidget(ico)

        lay.addSpacing(14)

        title = QLabel(f"Welcome to {APP_NAME} {APP_VERSION}")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        lay.addWidget(title)

        lay.addSpacing(6)

        sub = QLabel(
            "This wizard will guide you through the installation.\n"
            "Click <b>Next</b> to choose your installation options."
        )
        sub.setObjectName("pageSub")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(22)

        # feature list
        features = [
            ("convert.svg", "Convert between NTFS, FAT32, exFAT and ReFS"),
            ("drive.svg",   "Data is preserved during the conversion"),
            ("info.svg",    "Simple and fast interface for Windows 10/11"),
        ]
        for svg, text in features:
            row = QHBoxLayout()
            row.setSpacing(10)
            row.setContentsMargins(20, 0, 0, 0)
            ic = QLabel()
            ic.setPixmap(load_svg(f"resources/icons/{svg}", 16))
            ic.setFixedSize(16, 16)
            row.addWidget(ic)
            lb = QLabel(text)
            lb.setStyleSheet("color:#8b949e; font-size:12px;")
            row.addWidget(lb)
            row.addStretch()
            lay.addLayout(row)
            lay.addSpacing(6)

        lay.addStretch()


class OptionsPage(BasePage):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 28, 36, 16)
        lay.setSpacing(0)

        title = QLabel("Installation Options")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        lay.addSpacing(6)

        sub = QLabel("Choose where to install and which shortcuts to create.")
        sub.setObjectName("pageSub")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(18)

        # install path
        path_lbl = QLabel("INSTALLATION FOLDER")
        path_lbl.setObjectName("sectionLbl")
        lay.addWidget(path_lbl)

        lay.addSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.dir_edit = QLineEdit(DEFAULT_INSTALL_DIR)
        row.addWidget(self.dir_edit, 1)
        browse = QPushButton("Browse")
        browse.setObjectName("browseBtn")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        lay.addLayout(row)

        lay.addSpacing(4)

        self.space_lbl = QLabel()
        self.space_lbl.setStyleSheet("color:#484f58; font-size:11px;")
        lay.addWidget(self.space_lbl)

        lay.addSpacing(18)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border:none; border-top:1px solid #21262d;")
        lay.addWidget(sep)

        lay.addSpacing(14)

        sc_lbl = QLabel("SHORTCUTS")
        sc_lbl.setObjectName("sectionLbl")
        lay.addWidget(sc_lbl)

        lay.addSpacing(8)

        self.chk_desktop = QCheckBox("Create desktop shortcut")
        self.chk_desktop.setChecked(True)
        lay.addWidget(self.chk_desktop)

        lay.addSpacing(6)

        self.chk_startmenu = QCheckBox("Add to Start Menu")
        self.chk_startmenu.setChecked(True)
        lay.addWidget(self.chk_startmenu)

        lay.addStretch()

    def on_enter(self):
        self._refresh_space()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Installation Folder",
            self.dir_edit.text() or DEFAULT_INSTALL_DIR,
        )
        if path:
            self.dir_edit.setText(os.path.normpath(path))
            self._refresh_space()

    def _refresh_space(self):
        try:
            drive = (self.dir_edit.text() or "C:\\")[:3]
            _, _, free = shutil.disk_usage(drive)
            self.space_lbl.setText(f"Available: {free // (1024 * 1024):,} MB")
        except Exception:
            self.space_lbl.setText("")

    @property
    def install_dir(self) -> str:
        return self.dir_edit.text().strip() or DEFAULT_INSTALL_DIR

    @property
    def create_desktop(self) -> bool:
        return self.chk_desktop.isChecked()

    @property
    def create_startmenu(self) -> bool:
        return self.chk_startmenu.isChecked()


class ProgressPage(BasePage):
    def __init__(self):
        super().__init__()
        self._worker = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 28, 36, 16)
        lay.setSpacing(0)

        self.title_lbl = QLabel("Installing...")
        self.title_lbl.setObjectName("pageTitle")
        lay.addWidget(self.title_lbl)

        lay.addSpacing(6)

        sub = QLabel("Please wait while ChangeFormatUSB is being installed.")
        sub.setObjectName("pageSub")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(18)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        lay.addWidget(self.progress)

        lay.addSpacing(12)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log)

    def start(self, install_dir: str, desktop: bool, start_menu: bool,
              on_done, on_fail):
        self.log.clear()
        self.progress.setValue(0)
        self.title_lbl.setText("Installing...")
        self._worker = InstallWorker(install_dir, desktop, start_menu)
        self._worker.logged.connect(lambda m: self.log.append(f"  {m}"))
        self._worker.advanced.connect(self.progress.setValue)
        self._worker.finished.connect(
            lambda ok, msg: on_done() if ok else on_fail(msg)
        )
        self._worker.start()


class DonePage(BasePage):
    def __init__(self):
        super().__init__()
        self._install_dir = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 16)
        lay.setSpacing(0)

        ico = QLabel()
        ico.setPixmap(load_svg("resources/icons/success.svg", 58))
        ico.setAlignment(Qt.AlignCenter)
        lay.addWidget(ico)

        lay.addSpacing(16)

        title = QLabel("Installation complete!")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        lay.addSpacing(8)

        sub = QLabel(
            f"{APP_NAME} {APP_VERSION} has been installed successfully.\n"
            "You can now convert your USB drive formats without data loss."
        )
        sub.setObjectName("pageSub")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(24)

        self.chk_launch = QCheckBox(f"Launch {APP_NAME} now")
        self.chk_launch.setChecked(True)
        lay.addWidget(self.chk_launch, alignment=Qt.AlignCenter)

        lay.addStretch()

    def set_install_dir(self, path: str):
        self._install_dir = path

    def launch_if_checked(self):
        if not self.chk_launch.isChecked():
            return
        exe = os.path.join(self._install_dir, "ChangeFormatUSB.exe")
        if os.path.isfile(exe):
            subprocess.Popen(
                [exe],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )


# ─── main installer window ────────────────────────────────────────────────────

class InstallerWindow(QDialog):
    def __init__(self):
        super().__init__(None, Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — Setup")
        self.setFixedSize(640, 450)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── sidebar ──────────────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(155)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 28, 0, 20)
        sb.setSpacing(0)

        app_ico = QLabel()
        app_ico.setPixmap(load_svg("resources/icons/usb.svg", 38))
        app_ico.setAlignment(Qt.AlignCenter)
        sb.addWidget(app_ico)

        sb.addSpacing(8)

        name_l = QLabel(APP_NAME)
        name_l.setAlignment(Qt.AlignCenter)
        name_l.setStyleSheet("color:#e6edf3; font-size:13px; font-weight:700;")
        sb.addWidget(name_l)

        ver_l = QLabel(f"v{APP_VERSION}")
        ver_l.setAlignment(Qt.AlignCenter)
        ver_l.setStyleSheet("color:#484f58; font-size:11px;")
        sb.addWidget(ver_l)

        sb.addSpacing(26)

        # step indicator labels
        self._step_lbls: list[QLabel] = []
        for step in WIZARD_STEPS:
            lbl = QLabel(f"  {step}")
            lbl.setObjectName("step")
            sb.addWidget(lbl)
            sb.addSpacing(2)
            self._step_lbls.append(lbl)

        sb.addStretch()

        by = QLabel(f"by {PUBLISHER}")
        by.setAlignment(Qt.AlignCenter)
        by.setStyleSheet("color:#21262d; font-size:10px;")
        sb.addWidget(by)

        root.addWidget(sidebar)

        # ── right side ───────────────────────────────────────────────────────
        right_wrap = QWidget()
        right_wrap.setStyleSheet("background:#0d1117;")
        right_lay = QVBoxLayout(right_wrap)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        # pages
        self._stack = QStackedWidget()
        self._p_welcome  = WelcomePage()
        self._p_options  = OptionsPage()
        self._p_progress = ProgressPage()
        self._p_done     = DonePage()

        for p in [self._p_welcome, self._p_options, self._p_progress, self._p_done]:
            self._stack.addWidget(p)

        right_lay.addWidget(self._stack, 1)

        # bottom bar
        bottom = QFrame()
        bottom.setObjectName("bottomBar")
        bottom.setFixedHeight(58)
        btn_row = QHBoxLayout(bottom)
        btn_row.setContentsMargins(20, 0, 20, 0)
        btn_row.setSpacing(8)

        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("backBtn")
        self._back_btn.clicked.connect(self._go_back)
        btn_row.addWidget(self._back_btn)

        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("nextBtn")
        self._next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self._next_btn)

        right_lay.addWidget(bottom)
        root.addWidget(right_wrap, 1)

        self._goto(0)

    # ── navigation ────────────────────────────────────────────────────────────

    def _goto(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._stack.currentWidget().on_enter()
        self._refresh_step_labels(idx)
        self._refresh_buttons(idx)

    def _refresh_step_labels(self, current: int):
        for i, lbl in enumerate(self._step_lbls):
            if i < current:
                name = "stepDone"
            elif i == current:
                name = "stepActive"
            else:
                name = "step"
            lbl.setObjectName(name)
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def _refresh_buttons(self, idx: int):
        is_first    = idx == 0
        is_progress = idx == 2
        is_done     = idx == 3

        self._back_btn.setVisible(not is_first and not is_progress and not is_done)
        self._cancel_btn.setVisible(not is_progress and not is_done)
        self._next_btn.setEnabled(not is_progress)

        if is_done:
            self._next_btn.setText("Finish")
        elif idx == 1:
            self._next_btn.setText("Install")
        else:
            self._next_btn.setText("Next")

    def _go_next(self):
        idx = self._stack.currentIndex()

        if idx == 1:
            # validate install dir
            d = self._p_options.install_dir
            if not d:
                QMessageBox.warning(self, "Invalid path", "Please enter a valid installation folder.")
                return
            # start install
            self._goto(2)
            self._p_progress.start(
                d,
                self._p_options.create_desktop,
                self._p_options.create_startmenu,
                on_done=self._on_install_done,
                on_fail=self._on_install_failed,
            )
        elif idx == 3:
            self._p_done.launch_if_checked()
            self.accept()
        else:
            self._goto(idx + 1)

    def _go_back(self):
        idx = self._stack.currentIndex()
        if idx > 0:
            self._goto(idx - 1)

    def _on_install_done(self):
        self._p_done.set_install_dir(self._p_options.install_dir)
        self._goto(3)

    def _on_install_failed(self, msg: str):
        QMessageBox.critical(
            self,
            "Installation Failed",
            f"<b>An error occurred during installation:</b><br><br>{msg}",
        )
        self._goto(1)


# ─── entry point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # dark palette
    pal = QPalette()
    bg   = QColor("#0d1117")
    surf = QColor("#161b22")
    txt  = QColor("#e6edf3")
    acc  = QColor("#388bfd")
    pal.setColor(QPalette.Window,          bg)
    pal.setColor(QPalette.WindowText,      txt)
    pal.setColor(QPalette.Base,            surf)
    pal.setColor(QPalette.AlternateBase,   bg)
    pal.setColor(QPalette.Text,            txt)
    pal.setColor(QPalette.Button,          QColor("#21262d"))
    pal.setColor(QPalette.ButtonText,      txt)
    pal.setColor(QPalette.Highlight,       acc)
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase,     surf)
    pal.setColor(QPalette.ToolTipText,     txt)
    app.setPalette(pal)
    app.setStyleSheet(STYLE)

    win = InstallerWindow()
    win.exec_()


if __name__ == "__main__":
    main()
