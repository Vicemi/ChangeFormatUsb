from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex
import logging

logger = logging.getLogger(__name__)

class Worker(QObject):
    finished = pyqtSignal()
    success = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, task, *args, **kwargs):
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self.mutex = QMutex()
        self.running = True
        self.thread = None
        
    def run(self):
        try:
            logger.debug(f"Worker started in thread: {QThread.currentThread()}")
            result = self.task(*self.args, **self.kwargs)
            if self.running:
                logger.debug("Emitting success signal")
                self.success.emit(result)
        except Exception as e:
            if self.running:
                logger.error(f"Worker error: {str(e)}")
                self.error.emit(str(e))
        finally:
            if self.running:
                logger.debug("Emitting finished signal")
                self.finished.emit()
    
    def stop(self):
        logger.debug("Stopping worker")
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()
        self.finished.emit()

def run_in_thread(task):
    def wrapper(*args, **kwargs):
        # Create worker and thread
        worker = Worker(task, *args, **kwargs)
        thread = QThread()
        
        # Store references
        worker.thread = thread
        thread.worker = worker
        
        # Move worker to thread
        worker.moveToThread(thread)
        
        # Connect signals
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        # Connect result signals
        if 'callback_success' in kwargs:
            worker.success.connect(kwargs['callback_success'])
        if 'callback_error' in kwargs:
            worker.error.connect(kwargs['callback_error'])
        
        # Start thread and return reference
        thread.start()
        return worker
    return wrapper