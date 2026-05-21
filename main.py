import sys
import os
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5 import QtCore

from ui.main_window import ChangeFormatUSB
from config import APP_NAME
from logger import logger


def _excepthook(exc_type, exc_value, exc_tb):
    """Capture unhandled exceptions, log them and show a dialog."""
    logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_tb),
    )
    traceback.print_exception(exc_type, exc_value, exc_tb)
    try:
        dlg = QMessageBox()
        dlg.setIcon(QMessageBox.Critical)
        dlg.setWindowTitle("Error inesperado")
        dlg.setText(str(exc_value))
        dlg.setDetailedText(traceback.format_exc())
        dlg.exec_()
    except Exception:
        pass


sys.excepthook = _excepthook


def _request_admin():
    """Re-launch the process with elevated privileges if not already admin."""
    try:
        if sys.platform != "win32":
            return
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return
        # Re-launch elevated
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join(f'"{a}"' for a in sys.argv),
            None, 1,
        )
        sys.exit(0)
    except Exception as e:
        logger.warning("Could not request admin privileges: %s", e)


def main():
    logger.info("Starting %s v%s", APP_NAME, __import__("config").APP_VERSION)

    _request_admin()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Respect system locale for Qt internals
    locale = QtCore.QLocale.system().name()
    logger.info("System locale: %s", locale)

    window = ChangeFormatUSB()
    window.show()

    code = app.exec_()
    logger.info("Application exited with code %d", code)
    return code


if __name__ == "__main__":
    sys.exit(main())
