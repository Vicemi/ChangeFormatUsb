import sys
import os
import json
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtCore, QtWidgets
from ui.main_window import ChangeFormatUSB
from config import APP_NAME
from logger import logger

def cargar_traducciones(app):
    """Carga las traducciones según el idioma del sistema"""
    try:
        # Determinar ruta base dependiendo si está congelado o no
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            # En entornos congelados, las traducciones pueden estar en diferentes ubicaciones
            posibles_rutas = [
                os.path.join(base_path, 'resources', 'translations'),
                os.path.join(base_path, 'translations'),
                os.path.join(base_path, 'resources', 'translations'),
            ]
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            posibles_rutas = [
                os.path.join(base_path, 'resources', 'translations'),
                os.path.join(base_path, 'translations'),
            ]
        
        # Obtener idioma del sistema
        idioma = QtCore.QLocale.system().name()
        idioma_base = idioma.split('_')[0]  # Por ejemplo, 'es' de 'es_ES'
        
        # Buscar el archivo de traducción en las posibles rutas
        ruta_traduccion = None
        for ruta_base in posibles_rutas:
            # Intentar con idioma completo (ej: es_ES.json)
            ruta_completa = os.path.join(ruta_base, f'{idioma}.json')
            if os.path.exists(ruta_completa):
                ruta_traduccion = ruta_completa
                break
            
            # Intentar con idioma base (ej: es.json)
            ruta_base_idioma = os.path.join(ruta_base, f'{idioma_base}.json')
            if os.path.exists(ruta_base_idioma):
                ruta_traduccion = ruta_base_idioma
                break
        
        # Cargar traducción si se encontró
        if ruta_traduccion and os.path.exists(ruta_traduccion):
            try:
                # Instalar traducciones en la aplicación
                traductor = QtCore.QTranslator()
                if traductor.load(ruta_traduccion):
                    app.installTranslator(traductor)
                    logger.info(f"Traducción cargada: {ruta_traduccion}")
                else:
                    logger.error(f"No se pudo cargar la traducción: {ruta_traduccion}")
                
                # Cargar también el archivo JSON para traducciones personalizadas
                with open(ruta_traduccion, 'r', encoding='utf-8') as f:
                    app.traducciones = json.load(f)
                    logger.info(f"Traducciones JSON cargadas: {ruta_traduccion}")
                    
            except Exception as e:
                logger.error(f"Error cargando traducción: {str(e)}")
        else:
            logger.warning(f"No se encontró archivo de traducción para {idioma} o {idioma_base}")
    
    except Exception as e:
        logger.error(f"Error en cargar_traducciones: {str(e)}")

def excepthook(exc_type, exc_value, exc_traceback):
    """Captura excepciones no manejadas y las registra"""
    logger.critical("Unhandled exception", 
                    exc_info=(exc_type, exc_value, exc_traceback))
    
    # Mostrar mensaje de error en consola
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    
    # Mostrar mensaje de error en GUI si es posible
    try:
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setText("Error crítico")
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
        if sys.platform == "win32":
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            is_admin = os.getuid() == 0
    except Exception as e:
        logger.error(f"Error verificando privilegios: {str(e)}")
        is_admin = False
    
    if not is_admin:
        try:
            if sys.platform == "win32":
                import ctypes
                # Reejecutar con privilegios de administrador
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                sys.exit(0)
            else:
                logger.warning("Por favor, ejecute este programa como administrador/root.")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error solicitando privilegios de administrador: {str(e)}")
            # Continuar sin privilegios (algunas funciones podrían fallar)

def main():
    # Configurar registro
    logger.info("Iniciando aplicación...")
    
    # Verificar y solicitar privilegios de administrador
    run_as_admin()
    
    # Crear aplicación
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    
    # Cargar traducciones ANTES de crear la ventana principal
    cargar_traducciones(app)
    
    # Crear y mostrar ventana principal
    window = ChangeFormatUSB()
    window.show()
    
    # Ejecutar bucle principal
    exit_code = app.exec_()
    
    logger.info("Aplicación finalizada")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())