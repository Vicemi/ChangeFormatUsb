import ctypes
import sys
import os
import win32com.shell.shell as shell
from logger import logger

def is_admin():
    """Verifica si la aplicación se está ejecutando como administrador"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Relanza la aplicación con privilegios de administrador"""
    if not is_admin():
        logger.warning("Reiniciando con privilegios de administrador")
        
        # Obtener la ruta del ejecutable
        executable = sys.executable
        params = ' '.join([f'"{arg}"' for arg in sys.argv])
        
        # Ejecutar con privilegios
        shell.ShellExecuteEx(lpVerb='runas', lpFile=executable, lpParameters=params)
        sys.exit(0)