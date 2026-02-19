from typing import Optional
from pathlib import Path
import logging
import sys
from inbox_agent.config import settings

def build_root_logger(log_file_path: Optional[str | Path] = None) -> None:
    if log_file_path is None:
        log_file_path = settings.PROJ_ROOT / 'logs' / 'inbox_agent.log'
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.getLogger("notion_client").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
