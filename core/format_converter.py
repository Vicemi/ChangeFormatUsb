import os
import subprocess
import shutil
import time
import logging
import tempfile
import threading

logger = logging.getLogger(__name__)


class FormatConverter:
    """Handles USB drive format conversion safely, without blocking the UI thread."""

    def __init__(self, progress_callback=None):
        self._progress_callback = progress_callback
        self._cancelled = threading.Event()
        self._process = None
        self._lock = threading.Lock()

    # ──────────────────────────── Public API ─────────────────────────────

    def cancel(self):
        """Signal cancellation and terminate any running subprocess."""
        self._cancelled.set()
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass

    def convert(self, drive_letter, target_format):
        """
        Convert the USB drive to target_format.
        Runs synchronously — must be called from a background thread.
        Raises RuntimeError, TimeoutError, or InterruptedError on failure.
        """
        self._cancelled.clear()

        letter = drive_letter.strip().upper().replace("\\", "").replace(":", "")
        drive_path = f"{letter}:\\"
        target = target_format.strip().upper()

        current_fs = self._get_fs(drive_path)
        logger.info("Converting %s: %s -> %s", drive_path, current_fs, target)

        if self._formats_equivalent(current_fs, target):
            self._progress("La unidad ya tiene el formato deseado", 100)
            return

        self._progress("Verificando procesos activos en la unidad...", 3)
        self._close_processes(drive_path)

        if target == "NTFS" and current_fs in ("FAT", "FAT32"):
            self._fat_to_ntfs(letter, drive_path)
        else:
            sys_drive = os.environ.get("SystemDrive", "C:")
            self._backup_convert(drive_path, letter, target, sys_drive)

    # ──────────────────────────── Internal helpers ────────────────────────

    def _is_cancelled(self):
        return self._cancelled.is_set()

    def _progress(self, message, percent):
        if self._progress_callback:
            try:
                self._progress_callback(message, int(percent))
            except Exception:
                pass

    def _get_fs(self, drive_path):
        try:
            import win32api
            info = win32api.GetVolumeInformation(drive_path)
            return (info[4] or "FAT32").upper()
        except Exception:
            return "UNKNOWN"

    @staticmethod
    def _formats_equivalent(a, b):
        if a == b:
            return True
        if a in ("FAT", "FAT32") and b in ("FAT", "FAT32"):
            return True
        return False

    def _close_processes(self, drive_path):
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name", "open_files"]):
                try:
                    for f in proc.info["open_files"] or []:
                        if f.path.upper().startswith(drive_path.upper()):
                            proc.terminate()
                            break
                except Exception:
                    pass
        except Exception:
            pass

    # ──────────────────────────── Subprocess runner ───────────────────────

    def _run_proc(self, args, timeout=300):
        """
        Launch a subprocess and poll it until completion, checking for
        cancellation every 50 ms. Returns (returncode, list[str] stdout lines).
        """
        if self._is_cancelled():
            raise InterruptedError("Operacion cancelada")

        with self._lock:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=False,
            )
        proc = self._process
        lines = []
        deadline = time.monotonic() + timeout

        try:
            while True:
                if self._is_cancelled():
                    proc.terminate()
                    raise InterruptedError("Operacion cancelada")

                if time.monotonic() > deadline:
                    proc.terminate()
                    raise TimeoutError(f"Tiempo agotado ({timeout}s)")

                raw = proc.stdout.readline()
                if raw:
                    decoded = raw.decode("cp850", errors="replace").rstrip()
                    if decoded:
                        lines.append(decoded)

                rc = proc.poll()
                if rc is not None:
                    rest = proc.stdout.read()
                    if rest:
                        for ln in rest.decode("cp850", errors="replace").splitlines():
                            if ln.strip():
                                lines.append(ln)
                    return rc, lines

                time.sleep(0.05)
        finally:
            with self._lock:
                if self._process is proc:
                    self._process = None

    # ──────────────────────────── FAT → NTFS (in-place) ──────────────────

    def _fat_to_ntfs(self, letter, drive_path):
        self._progress("Convirtiendo FAT32 a NTFS sin perdida de datos...", 10)

        bat = tempfile.NamedTemporaryFile(
            suffix=".bat", delete=False, mode="w", encoding="utf-8"
        )
        bat.write(f"@echo off\r\necho Y | convert {letter}: /FS:NTFS /X\r\n")
        bat.close()

        try:
            rc, _ = self._run_proc(["cmd.exe", "/C", bat.name], timeout=600)
        finally:
            try:
                os.unlink(bat.name)
            except Exception:
                pass

        # Verify FS after conversion — convert.exe may return non-zero even on success
        fs_after = self._get_fs(drive_path)
        if fs_after == "NTFS":
            self._progress("Conversion a NTFS completada correctamente", 100)
        elif rc != 0:
            raise RuntimeError(
                f"La conversion a NTFS fallo (codigo de salida {rc}). "
                "Intenta cerrar todos los archivos abiertos en la unidad."
            )
        else:
            self._progress("Conversion a NTFS completada correctamente", 100)

    # ──────────────────────────── Backup + reformat ───────────────────────

    def _backup_convert(self, drive_path, letter, target, sys_drive):
        import psutil as _ps

        # 1 — Verify available space
        self._progress("Calculando espacio disponible...", 5)
        try:
            used = _ps.disk_usage(drive_path).used
        except Exception as e:
            raise RuntimeError(f"No se pudo calcular el espacio usado: {e}")

        sys_root = sys_drive.rstrip("\\") + "\\"
        try:
            available = _ps.disk_usage(sys_root).free
        except Exception as e:
            raise RuntimeError(f"No se pudo calcular espacio libre en {sys_root}: {e}")

        required = int(used * 1.25)
        if available < required:
            raise RuntimeError(
                f"Espacio insuficiente en {sys_root}.\n"
                f"Necesario:   {required / 1024**3:.1f} GB\n"
                f"Disponible: {available / 1024**3:.1f} GB"
            )

        # 2 — Create temp backup directory
        temp_base = os.path.join(sys_root, "Temp")
        os.makedirs(temp_base, exist_ok=True)
        backup_dir = tempfile.mkdtemp(prefix=f"USB_{letter}_", dir=temp_base)
        logger.info("Backup directory: %s", backup_dir)

        try:
            # 3 — Copy data
            self._progress("Copiando datos al directorio de respaldo...", 10)
            self._robocopy(drive_path, backup_dir, base_pct=10, max_pct=54)

            if self._is_cancelled():
                raise InterruptedError("Operacion cancelada")

            # 4 — Unmount
            self._progress("Desmontando la unidad...", 57)
            self._unmount(letter)
            time.sleep(2)

            # 5 — Format
            self._progress(f"Formateando unidad como {target}...", 62)
            self._format_drive(letter, target)

            # 6 — Wait for drive to become accessible
            self._progress("Esperando disponibilidad de la unidad...", 76)
            self._wait_drive(drive_path, timeout=90)

            # 7 — Restore data
            self._progress("Restaurando datos desde el respaldo...", 80)
            self._robocopy(backup_dir, drive_path.rstrip("\\"), base_pct=80, max_pct=96)

            self._progress("Limpiando archivos temporales...", 97)

        finally:
            try:
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir, ignore_errors=True)
            except Exception:
                pass

    # ──────────────────────────── Robocopy ───────────────────────────────

    def _robocopy(self, src, dst, base_pct=0, max_pct=100):
        src = src.rstrip("\\")
        dst = dst.rstrip("\\")
        args = [
            "robocopy", src, dst,
            "/E",       # copy subdirectories, including empty ones
            "/COPYALL", # copy all file attributes
            "/R:2",     # 2 retries on failure
            "/W:3",     # 3-second wait between retries
            "/NP",      # no percent-done progress
            "/NFL",     # no file list
            "/NDL",     # no directory list
        ]

        with self._lock:
            if self._is_cancelled():
                raise InterruptedError("Operacion cancelada")
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        proc = self._process
        files = 0
        deadline = time.monotonic() + 7200  # 2-hour hard limit

        try:
            while True:
                if self._is_cancelled():
                    proc.terminate()
                    raise InterruptedError("Operacion cancelada")

                if time.monotonic() > deadline:
                    proc.terminate()
                    raise TimeoutError("Tiempo agotado al copiar datos (limite 2 horas)")

                raw = proc.stdout.readline()
                if raw:
                    text = raw.decode("cp850", errors="replace").strip()
                    if text and not text.startswith("-"):
                        files += 1
                        pct = min(base_pct + files * 0.4, max_pct)
                        self._progress(f"Copiando: {text[:80]}", int(pct))

                rc = proc.poll()
                if rc is not None:
                    # robocopy exit codes 0–7 indicate success/info, 8+ are errors
                    if rc >= 8:
                        raise RuntimeError(
                            f"Error al copiar datos (robocopy codigo {rc}). "
                            "Verifica que la unidad no este protegida contra escritura."
                        )
                    break

                time.sleep(0.04)
        finally:
            with self._lock:
                if self._process is proc:
                    self._process = None

    # ──────────────────────────── Format ─────────────────────────────────

    def _format_drive(self, letter, fs):
        bat = tempfile.NamedTemporaryFile(
            suffix=".bat", delete=False, mode="w", encoding="utf-8"
        )
        bat.write(f"@echo off\r\necho Y | format {letter}: /FS:{fs} /Q /Y\r\n")
        bat.close()
        try:
            rc, _ = self._run_proc(["cmd.exe", "/C", bat.name], timeout=120)
            if rc != 0:
                raise RuntimeError(
                    f"El formateo fallo (codigo {rc}). "
                    "Asegurate de que la unidad no este en uso."
                )
        finally:
            try:
                os.unlink(bat.name)
            except Exception:
                pass

    # ──────────────────────────── Unmount ────────────────────────────────

    def _unmount(self, letter):
        try:
            import win32file
            import win32con
            handle = win32file.CreateFile(
                f"\\\\.\\{letter}:",
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                (win32con.FILE_SHARE_READ
                 | win32con.FILE_SHARE_WRITE
                 | win32con.FILE_SHARE_DELETE),
                None,
                win32con.OPEN_EXISTING,
                0,
                None,
            )
            try:
                win32file.DeviceIoControl(handle, 0x90020, None, None)  # FSCTL_DISMOUNT_VOLUME
            finally:
                win32file.CloseHandle(handle)
        except Exception as exc:
            logger.warning("API unmount failed (%s) — falling back to diskpart", exc)
            self._unmount_diskpart(letter)

    def _unmount_diskpart(self, letter):
        script = tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w"
        )
        script.write(f"select volume {letter}\nremove all dismount\n")
        script.close()
        try:
            self._run_proc(["diskpart", "/s", script.name], timeout=30)
        finally:
            try:
                os.unlink(script.name)
            except Exception:
                pass

    # ──────────────────────────── Wait for drive ─────────────────────────

    def _wait_drive(self, drive_path, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._is_cancelled():
                raise InterruptedError("Operacion cancelada")
            try:
                if os.path.exists(drive_path):
                    os.listdir(drive_path)
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError(
            f"La unidad {drive_path} no estuvo disponible despues de {timeout}s"
        )
