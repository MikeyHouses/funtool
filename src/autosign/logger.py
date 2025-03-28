import logging

# 默认日志格式
DEFAULT_FORMAT = "[%(asctime)s][%(levelname)s][%(name)s] %(message)s"
DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"

def setup_logger(name, level=logging.INFO, format_str=None, datefmt=None):
    """
    设置并返回一个命名的日志器实例
    
    Args:
        name (str): 日志器名称
        level (int): 日志级别
        format_str (str): 日志格式
        datefmt (str): 日期格式
    
    Returns:
        logging.Logger: 配置好的日志器实例
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(level)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            format_str or DEFAULT_FORMAT,
            datefmt or DEFAULT_DATEFMT
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
