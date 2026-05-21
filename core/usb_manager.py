import logging
import psutil

logger = logging.getLogger(__name__)


class USBManager:
    def __init__(self):
        self._cache = []

    def get_usb_devices(self):
        """
        Return a list of removable USB drives with detailed info.
        Falls back to cached data if WMI is unavailable.
        """
        try:
            import wmi
            c = wmi.WMI()
            devices = []

            for disk in c.Win32_LogicalDisk(DriveType=2):  # DriveType 2 = Removable
                try:
                    letter = disk.DeviceID  # e.g. "E:"
                    drive_path = letter + "\\"

                    try:
                        usage = psutil.disk_usage(drive_path)
                        total = usage.total
                        free = usage.free
                    except Exception:
                        total = int(disk.Size or 0)
                        free = int(disk.FreeSpace or 0)

                    devices.append({
                        "letter":     letter,
                        "filesystem": disk.FileSystem or "Desconocido",
                        "size":       total,
                        "free":       free,
                        "label":      disk.VolumeName or "Unidad USB",
                    })
                except Exception as e:
                    logger.warning("Error processing device %s: %s", disk.DeviceID, e)
                    continue

            self._cache = devices
            return devices

        except Exception as e:
            logger.error("WMI unavailable (%s) — returning cached devices", e)
            return self._cache
