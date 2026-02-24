import logging
import os
from logging.config import fileConfig


class LoggerUtil:
    __LOGGER_CONFIG = None

    def logger(self, module_name):
        if self.__LOGGER_CONFIG is None:
            app_env = os.getenv("ENV", 'dev').lower()  # 读取环境变量
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 返回文件路径
            conf_file = os.path.join(root_dir, 'logger', 'logging-' + app_env + '.conf')  # 连接目录与文件名或目录
            fileConfig(fname=conf_file, disable_existing_loggers=False)  # 通过解析conf配置文件实现日志配置
            __LOGGER_CONFIG = "__inited__"
        logger = logging.getLogger(module_name)
        return logger
