import subprocess
import win32file
import win32con
import win32api
import time
import psutil
import ctypes
import sys
import os
import logging
import shutil
import tempfile
from utils.threading import run_in_thread

logger = logging.getLogger(__name__)

# Constantes
MAX_RETRIES = 3
RETRY_DELAY = 2
MOUNT_WAIT_TIME = 5

class FormatConverter:
    def __init__(self):
        self.current_process = None
        self.is_converting = False
        self.current_worker = None
        self.backup_dir = None

    @run_in_thread
    def iniciar_conversion(self, letra_unidad, nuevo_fs, callback_exito, callback_error):
        logger.debug(f"Iniciando conversión para {letra_unidad} a {nuevo_fs}")
        if self.is_converting:
            msg_error = "Ya hay una conversión en progreso"
            logger.warning(msg_error)
            callback_error(msg_error)
            return
            
        self.is_converting = True
        try:
            # Normalizar letra de unidad
            letra_unidad = self.normalizar_letra_unidad(letra_unidad)
            if not letra_unidad:
                msg_error = "Formato de unidad inválido"
                logger.error(msg_error)
                callback_error(msg_error)
                return
                
            logger.debug(f"Verificando estado de la unidad: {letra_unidad}")
            if not self.unidad_lista(letra_unidad):
                msg_error = f"Unidad {letra_unidad} no está lista o está en uso"
                logger.error(msg_error)
                callback_error(msg_error)
                return
                
            # Detectar sistema de archivos actual
            fs_actual = obtener_tipo_fs(letra_unidad)
            logger.info(f"Sistema de archivos actual: {fs_actual}")

            if fs_actual is None:
                msg_error = f"No se pudo detectar el sistema de archivos de {letra_unidad}"
                logger.error(msg_error)
                callback_error(msg_error)
                return

            # Normalizar nombres
            fs_actual = fs_actual.upper()
            nuevo_fs = nuevo_fs.upper()

            # Si ya está en el formato deseado
            if self.es_formato_equivalente(fs_actual, nuevo_fs):
                logger.info("La unidad ya está en el formato deseado.")
                callback_exito(letra_unidad)
                return

            # Casos que permiten conversión sin pérdida de datos
            if (fs_actual in ["FAT", "FAT32"] and nuevo_fs == "NTFS"):
                # Desmontar antes de convertir
                if not self.desmontar_unidad(letra_unidad):
                    msg_error = f"Error al desmontar {letra_unidad} para conversión"
                    logger.error(msg_error)
                    callback_error(msg_error)
                    return
                    
                cmd = f'convert {letra_unidad} /FS:NTFS /X'
                timeout = 300
                logger.info(f"Ejecutando comando NTFS: {cmd}")
                self._ejecutar_comando(cmd, timeout, letra_unidad, callback_exito, callback_error)
            # Conversiones que requieren copia de seguridad
            else:
                logger.info(f"Iniciando conversión segura para {fs_actual} -> {nuevo_fs}")
                self._convertir_con_copia(letra_unidad, nuevo_fs, callback_exito, callback_error)
                
        except Exception as e:
            logger.exception(f"Error inesperado: {str(e)}")
            callback_error(f"Error inesperado: {str(e)}")
        finally:
            self.current_process = None
            self.is_converting = False
            logger.debug("Estado de conversión reiniciado")

    def normalizar_letra_unidad(self, letra_unidad):
        """Normaliza la letra de unidad a formato 'X:'"""
        if not letra_unidad:
            return None
            
        letra_unidad = letra_unidad.strip().upper()
        if len(letra_unidad) == 1:
            return f"{letra_unidad}:"
        elif len(letra_unidad) == 2 and letra_unidad[1] == ':':
            return letra_unidad
        return None

    def es_formato_equivalente(self, actual, nuevo):
        """Determina si los formatos son equivalentes"""
        if actual == nuevo:
            return True
        if actual in ["FAT", "FAT32"] and nuevo in ["FAT", "FAT32"]:
            return True
        return False

    def _ejecutar_comando(self, comando, timeout, letra_unidad, callback_exito, callback_error):
        """Ejecuta un comando de conversión con manejo de errores"""
        ruta_bat = None
        try:
            # Crear archivo batch en directorio temporal
            with tempfile.NamedTemporaryFile(suffix='.bat', delete=False) as bat_file:
                ruta_bat = bat_file.name
                bat_file.write(f"@echo off\n{comando}\nexit\n".encode('utf-8'))
            logger.debug(f"Archivo batch creado: {ruta_bat}")
            
            # Ejecutar comando
            self.current_process = subprocess.Popen(
                ['cmd.exe', '/C', ruta_bat],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            stdout, stderr = self.current_process.communicate(timeout=timeout)
            codigo_retorno = self.current_process.returncode
            
            logger.info(f"Salida del comando:\n{stdout}")
            if stderr:
                logger.error(f"Errores del comando:\n{stderr}")
            
            if codigo_retorno == 0:
                logger.info(f"Conversión exitosa para {letra_unidad}")
                self.actualizar_unidad(letra_unidad)
                time.sleep(MOUNT_WAIT_TIME)
                callback_exito(letra_unidad)
            else:
                msg_error = stderr.strip() or stdout.strip() or f"Código de error: {codigo_retorno}"
                logger.error(f"Error en conversión: {msg_error}")
                callback_error(f"Error {codigo_retorno}: {msg_error}")
                
        except subprocess.TimeoutExpired:
            logger.error("Tiempo de espera agotado")
            if self.current_process:
                self.current_process.kill()
            callback_error("Tiempo de espera agotado en la conversión")
        except Exception as e:
            logger.exception(f"Error ejecutando comando: {str(e)}")
            callback_error(f"Error ejecutando comando: {str(e)}")
        finally:
            # Limpieza segura
            if ruta_bat and os.path.exists(ruta_bat):
                try:
                    os.remove(ruta_bat)
                except Exception as e:
                    logger.warning(f"No se pudo eliminar archivo temporal: {str(e)}")

    def _convertir_con_copia(self, letra_unidad, nuevo_fs, callback_exito, callback_error):
        """Conversión segura usando copia temporal de datos"""
        logger.info(f"Iniciando conversión segura para {letra_unidad} a {nuevo_fs}")
        
        try:
            # Paso 1: Verificar espacio disponible
            espacio_usado = self.calcular_espacio_usado(letra_unidad)
            if espacio_usado is None:
                msg_error = f"No se pudo calcular espacio usado en {letra_unidad}"
                logger.error(msg_error)
                callback_error(msg_error)
                return

            unidad_sistema = os.environ.get('SystemDrive', 'C:')
            # CORRECCIÓN: Asegurar que la unidad termine con \
            if not unidad_sistema.endswith('\\'):
                unidad_sistema += '\\'
                
            espacio_libre = psutil.disk_usage(unidad_sistema).free
            
            if espacio_libre < espacio_usado * 1.2:
                msg_error = (f"Espacio insuficiente en {unidad_sistema}. "
                            f"Necesario: {self.format_bytes(espacio_usado * 1.2)} "
                            f"Disponible: {self.format_bytes(espacio_libre)}")
                logger.error(msg_error)
                callback_error(msg_error)
                return
                
            # Paso 2: Crear directorio temporal
            # CORRECCIÓN: Crear directorio base si no existe
            temp_base = os.path.join(unidad_sistema, "Temp")
            if not os.path.exists(temp_base):
                try:
                    os.makedirs(temp_base)
                    logger.info(f"Directorio temporal creado: {temp_base}")
                except Exception as e:
                    logger.error(f"No se pudo crear directorio temporal: {str(e)}")
                    callback_error(f"Error creando directorio temporal: {str(e)}")
                    return
                    
            self.backup_dir = tempfile.mkdtemp(
                prefix=f"USB_BACKUP_{letra_unidad.replace(':', '')}_", 
                dir=temp_base
            )
            logger.info(f"Directorio backup creado: {self.backup_dir}")
            
            # Paso 3: Copiar datos
            if not self.copiar_datos(letra_unidad, self.backup_dir, callback_error):
                return
                
            # Paso 4: Desmontar unidad antes de formatear
            logger.info(f"Desmontando unidad antes de formatear: {letra_unidad}")
            if not self.desmontar_unidad(letra_unidad):
                msg_error = f"No se pudo desmontar {letra_unidad} para formateo"
                logger.error(msg_error)
                callback_error(msg_error)
                return
                
            # Paso 5: Formatear unidad
            if not self.formatear_unidad(letra_unidad, nuevo_fs, callback_error):
                return
                
            # Esperar que la unidad esté disponible
            if not self.esperar_unidad_lista(letra_unidad):
                msg_error = f"Unidad {letra_unidad} no disponible después de formateo"
                logger.error(msg_error)
                callback_error(msg_error)
                return
                
            # Paso 6: Restaurar datos
            if not self.restaurar_datos(self.backup_dir, letra_unidad, callback_error):
                return
                
            # Paso 7: Limpieza
            self.limpiar_backup()
            
            logger.info("Conversión segura completada exitosamente")
            callback_exito(letra_unidad)
            
        except Exception as e:
            logger.exception(f"Error en conversión segura: {str(e)}")
            callback_error(f"Error en conversión segura: {str(e)}")
            try:
                self.limpiar_backup()
            except Exception:
                logger.warning("Error al limpiar durante excepción")

    def calcular_espacio_usado(self, letra_unidad):
        """Calcula el espacio usado en la unidad"""
        try:
            return psutil.disk_usage(letra_unidad).used
        except Exception as e:
            logger.error(f"Error calculando espacio: {str(e)}")
            return None

    def format_bytes(self, bytes):
        """Formatea bytes a una representación legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024
        return f"{bytes:.2f} GB"

    def copiar_datos(self, origen, destino, callback_error):
        """Copia datos usando robocopy con reintentos"""
        # Usar ruta raíz de la unidad (agregar \ al final)
        origen = os.path.join(origen, '')
        comando = f'robocopy "{origen}" "{destino}" /E /COPY:DAT /DCOPY:T /R:3 /W:5 /NP /NFL /NDL /NJH /NJS'
        logger.info(f"Copiando datos: {comando}")
        
        for intento in range(MAX_RETRIES):
            try:
                proceso = subprocess.run(
                    comando,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3600  # 1 hora máximo
                )
                
                # Robocopy retorna 0-7 como éxito, 8+ como error
                if proceso.returncode <= 7:
                    logger.info(f"Copia exitosa (intento {intento+1}), código: {proceso.returncode}")
                    return True
                    
                logger.warning(f"Intento {intento+1} fallido: {proceso.stderr or proceso.stdout}")
                time.sleep(RETRY_DELAY)
                
            except subprocess.TimeoutExpired:
                logger.error(f"Tiempo agotado copiando datos (intento {intento+1})")
                
        msg_error = f"Error al copiar datos después de {MAX_RETRIES} intentos"
        logger.error(msg_error)
        callback_error(msg_error)
        return False

    def formatear_unidad(self, letra_unidad, fs, callback_error):
        """Formatea la unidad usando el comando de Windows"""
        # Quitar los dos puntos para el nombre del volumen
        nombre_volumen = f"USB-{letra_unidad.strip(':')}"
        
        # Construir comando correctamente
        comando = f'format {letra_unidad} /FS:{fs} /Q /V:{nombre_volumen}'
        logger.info(f"Formateando unidad: {comando}")
        
        try:
            # Crear comando con respuesta automática Y
            full_cmd = f'echo Y| {comando}'
            
            proceso = subprocess.run(
                full_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=600  # 10 minutos máximo
            )
            
            if proceso.returncode == 0:
                logger.info("Formateo exitoso")
                return True
                
            msg_error = f"Error en formateo (código {proceso.returncode}): {proceso.stderr or proceso.stdout}"
            logger.error(msg_error)
            callback_error(msg_error)
            return False
            
        except subprocess.TimeoutExpired:
            msg_error = "Tiempo agotado en formateo"
            logger.error(msg_error)
            callback_error(msg_error)
            return False
        except Exception as e:
            logger.exception(f"Error inesperado al formatear: {str(e)}")
            callback_error(f"Error inesperado al formatear: {str(e)}")
            return False

    def restaurar_datos(self, origen, destino, callback_error):
        """Restaura datos usando robocopy con reintentos"""
        # Usar ruta raíz para destino (agregar \ al final)
        destino = os.path.join(destino, '')
        comando = f'robocopy "{origen}" "{destino}" /E /COPY:DAT /DCOPY:T /R:3 /W:5 /NP /NFL /NDL /NJH /NJS'
        logger.info(f"Restaurando datos: {comando}")
        
        for intento in range(MAX_RETRIES):
            try:
                proceso = subprocess.run(
                    comando,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3600  # 1 hora máximo
                )
                
                if proceso.returncode <= 7:
                    logger.info(f"Restauración exitosa (intento {intento+1}), código: {proceso.returncode}")
                    return True
                    
                logger.warning(f"Intento {intento+1} fallido: {proceso.stderr or proceso.stdout}")
                time.sleep(RETRY_DELAY)
                
            except subprocess.TimeoutExpired:
                logger.error(f"Tiempo agotado restaurando datos (intento {intento+1})")
                
        msg_error = f"Error al restaurar datos después de {MAX_RETRIES} intentos"
        logger.error(msg_error)
        callback_error(msg_error)
        return False

    def limpiar_backup(self):
        """Elimina el directorio de backup si existe"""
        if self.backup_dir and os.path.exists(self.backup_dir):
            try:
                shutil.rmtree(self.backup_dir, ignore_errors=True)
                logger.info(f"Backup eliminado: {self.backup_dir}")
            except Exception as e:
                logger.warning(f"Error eliminando backup: {str(e)}")
            finally:
                self.backup_dir = None

    def esperar_unidad_lista(self, letra_unidad, max_intentos=10):
        """Espera a que la unidad esté disponible después de formatear"""
        for i in range(max_intentos):
            if os.path.exists(letra_unidad):
                try:
                    # Verificar si podemos listar el contenido
                    os.listdir(letra_unidad)
                    return True
                except OSError:
                    logger.debug(f"Unidad {letra_unidad} aún no lista (intento {i+1})")
            time.sleep(1)
        return False

    def unidad_lista(self, letra_unidad):
        """Verifica si la unidad está lista para ser formateada"""
        try:
            if not os.path.exists(letra_unidad):
                logger.warning(f"La unidad {letra_unidad} no existe")
                return False

            # Verificar si la unidad está en uso
            for _ in range(MAX_RETRIES):
                if not self.hay_procesos_usando_unidad(letra_unidad):
                    return True
                self.terminar_procesos_unidad(letra_unidad)
                time.sleep(RETRY_DELAY)
                
            return False
        except Exception as e:
            logger.error(f"Error verificando unidad {letra_unidad}: {str(e)}")
            return False
        
    def hay_procesos_usando_unidad(self, letra_unidad):
        """Comprueba si hay procesos usando la unidad"""
        letra_unidad = letra_unidad.upper()
        if not letra_unidad.endswith(':'):
            letra_unidad += ':'
        
        for proc in psutil.process_iter():
            try:
                archivos = proc.open_files()
                for archivo in archivos:
                    if archivo.path.upper().startswith(letra_unidad):
                        logger.warning(f"Proceso usando unidad: {proc.pid} {proc.name()}")
                        return True
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        return False

    def terminar_procesos_unidad(self, letra_unidad):
        """Termina procesos que usan la unidad"""
        letra_unidad = letra_unidad.upper()
        if not letra_unidad.endswith(':'):
            letra_unidad += ':'
        
        procesos_terminados = False
        
        for proc in psutil.process_iter():
            try:
                archivos = proc.open_files()
                for archivo in archivos:
                    if archivo.path.upper().startswith(letra_unidad):
                        logger.warning(f"Terminando proceso {proc.pid} usando {letra_unidad}")
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                            procesos_terminados = True
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                            continue
                        break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        
        return procesos_terminados

    def desmontar_unidad(self, letra_unidad):
        """Desmonta la unidad forzosamente"""
        try:
            letra_normalizada = letra_unidad.replace(":", "").strip().upper()
            if not letra_normalizada:
                logger.error(f"Letra de unidad inválida: {letra_unidad}")
                return False
                
            ruta_dispositivo = f"\\\\.\\{letra_normalizada}:"
            logger.debug(f"Desmontando unidad: {ruta_dispositivo}")
            
            self.terminar_procesos_unidad(letra_unidad)
            time.sleep(RETRY_DELAY)
            
            handle = win32file.CreateFile(
                ruta_dispositivo,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_EXISTING,
                0,
                None
            )
            
            win32file.DeviceIoControl(
                handle,
                0x90020,  # FSCTL_DISMOUNT_VOLUME
                None,
                None
            )
            
            win32file.CloseHandle(handle)
            logger.info(f"Unidad {letra_unidad} desmontada exitosamente")
            return True
        except Exception as e:
            logger.error(f"Error desmontando unidad {letra_unidad}: {str(e)}")
            return False

    def actualizar_unidad(self, letra_unidad):
        """Actualiza la unidad en el sistema"""
        try:
            logger.debug(f"Actualizando unidad: {letra_unidad}")
            ctypes.windll.win32api.SetVolumeMountPointW(
                f"{letra_unidad}\\", 
                f"{letra_unidad}\\"
            )
            logger.info(f"Unidad {letra_unidad} actualizada en el sistema")
        except Exception as e:
            logger.warning(f"Error al actualizar unidad: {str(e)}")

    def cancelar_conversion(self):
        """Cancela la conversión en progreso"""
        if self.current_worker:
            self.current_worker.detener()
        if self.current_process:
            self.current_process.terminate()
        self.limpiar_backup()
        self.is_converting = False
        logger.info("Conversión cancelada por el usuario")

# Función para obtener tipo de sistema de archivos
def obtener_tipo_fs(letra_unidad):
    try:
        # Asegurar formato correcto X:
        if len(letra_unidad) == 1:
            letra_unidad += ':'
        elif len(letra_unidad) == 2 and letra_unidad[1] != ':':
            letra_unidad = letra_unidad[0] + ':'
            
        info_volumen = win32api.GetVolumeInformation(letra_unidad)
        return info_volumen[4]  # Tipo de sistema de archivos
    except Exception as e:
        logger.error(f"Error obteniendo sistema de archivos: {str(e)}")
        return None