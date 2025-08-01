import sys
import os
import traceback
from PyQt5.QtWidgets import QApplication
from ui.main_window import ChangeFormatUSB
from config import APP_NAME
from logger import logger

def excepthook(exc_type, exc_value, exc_traceback):
    """Captura excepciones no manejadas y las registra"""
    logger.critical("Unhandled exception", 
                    exc_info=(exc_type, exc_value, exc_traceback))
    
    # Mostrar mensaje de error en consola
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    
    # Mostrar mensaje de error en GUI si es posible
    try:
        from PyQt5.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Unhandled Exception")
        msg.setInformativeText(str(exc_value))
        msg.setWindowTitle("Error")
        msg.setDetailedText(traceback.format_exc())
        msg.exec_()
    except:
        pass

sys.excepthook = excepthook

def run_as_admin():
    """Solicita privilegios de administrador si no se está ejecutando como administrador."""
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        # Windows
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    if not is_admin:
        # Reejecutar el script como administrador
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit(0)
        else:
            print("Por favor, ejecute este programa como administrador/root.")
            sys.exit(1)

if __name__ == "__main__":
    # Verificar y solicitar privilegios de administrador
    run_as_admin()
    
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = ChangeFormatUSB()
    window.show()
    sys.exit(app.exec_())