import wmi
import psutil

class USBManager:
    def __init__(self):
        self.cached_devices = []
        
    def get_usb_devices(self):
        """Obtiene dispositivos USB con información detallada usando WMI y psutil"""
        try:
            usb_drives = []
            c = wmi.WMI()
            for drive in c.Win32_LogicalDisk(DriveType=2):
                try:
                    # Obtener información adicional con psutil
                    usage = psutil.disk_usage(drive.DeviceID)
                    
                    device_info = {
                        'letter': drive.DeviceID,
                        'filesystem': drive.FileSystem or "Desconocido",
                        'size': drive.Size or usage.total,
                        'free': drive.FreeSpace or usage.free,
                        'label': drive.VolumeName or "Sin etiqueta"
                    }
                    usb_drives.append(device_info)
                except Exception as e:
                    print(f"Error procesando dispositivo: {e}")
                    continue
            self.cached_devices = usb_drives
            return usb_drives
        except Exception as e:
            print(f"Error obteniendo dispositivos USB: {e}")
            return self.cached_devices  # Devuelve caché en caso de error