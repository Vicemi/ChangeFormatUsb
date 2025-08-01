import logging
import os
from datetime import datetime

def setup_logger():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"debug_{timestamp}.log")
    
    logger = logging.getLogger("ChangeFormatUSB")
    logger.setLevel(logging.DEBUG)
    
    # Formato
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Handler para archivo
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()