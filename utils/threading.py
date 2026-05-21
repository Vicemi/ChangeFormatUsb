"""
Threading utilities.
The actual conversion runs inside a QThread (ConversionWorker in ui/main_window.py).
This module is kept for any future use of background tasks.
"""
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QThread

logger = logging.getLogger(__name__)


class Worker(QObject):
    """Generic worker for running a callable inside a QThread."""

    finished = pyqtSignal()
    success  = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, task, *args, **kwargs):
        super().__init__()
        self.task   = task
        self.args   = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.task(*self.args, **self.kwargs)
            self.success.emit(result)
        except Exception as e:
            logger.error("Worker error: %s", e, exc_info=True)
            self.error.emit(str(e))
        finally:
            self.finished.emit()
