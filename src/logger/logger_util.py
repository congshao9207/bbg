import logging  # 设置日志打印的库
import re
import codecs
import os
import re
import time
from logging.handlers import BaseRotatingHandler
from pathlib import Path



class DailyRotatingFileHandler(BaseRotatingHandler):
    """
    同`logging.TimedRotatingFileHandler`类似，不过这个handler：
    - 可以支持多进程
    - 只支持自然日分割
    - 暂不支持UTC
    """

    def __init__(self, filename, backup_count=0, encoding=None, delay=False, utc=False, **kwargs):
        self.backup_count = backup_count
        self.utc = utc
        self.suffix = "%Y-%m-%d"
        self.base_log_path = Path(filename)
        self.base_filename = self.base_log_path.name
        self.current_filename = self._compute_fn()
        self.current_log_path = self.base_log_path.with_name(self.current_filename)
        BaseRotatingHandler.__init__(self, filename, 'a', encoding, delay)

    def shouldRollover(self, record):
        """
        判断是否该滚动日志，如果当前时间对应的日志文件名与当前打开的日志文件名不一致，则需要滚动日志
        """
        if self.current_filename != self._compute_fn():
            return True
        return False

    def doRollover(self):
        """
        滚动日志
        """
        # 关闭旧的日志文件
        if self.stream:
            self.stream.close()
            self.stream = None

        # 计算新的日志文件
        self.current_filename = self._compute_fn()
        self.current_log_path = self.base_log_path.with_name(self.current_filename)
        # 打开新的日志文件
        if not self.delay:
            self.stream = self._open()

        # 删除过期日志
        self.delete_expired_files()

    def _compute_fn(self):
        """
        计算当前时间对应的日志文件名
        """
        return self.base_filename + "." + time.strftime(self.suffix, time.localtime())

    def _open(self):
        """
        打开新的日志文件，同时更新base_filename指向的软链，修改软链不会对日志记录产生任何影响
        """
        if self.encoding is None:
            stream = open(str(self.current_log_path), self.mode)
        else:
            stream = codecs.open(str(self.current_log_path), self.mode, self.encoding)

        # 删除旧的软链
        if self.base_log_path.exists():
            try:
                # 如果base_log_path不是软链或者指向的日志文件不对，则先删除该软链
                if not self.base_log_path.is_symlink() or os.readlink(self.base_log_path) != self.current_filename:
                    os.remove(self.base_log_path)
            except OSError:
                pass

        # 建立新的软链
        try:
            os.symlink(self.current_filename, str(self.base_log_path))
        except OSError:
            pass
        return stream
    def delete_expired_files(self):
        """
        删除过期的日志
        """
        if self.backup_count <= 0:
            return

        file_names = os.listdir(str(self.base_log_path.parent))
        result = []
        prefix = self.base_filename + "."
        plen = len(prefix)
        for file_name in file_names:
            if file_name[:plen] == prefix:
                suffix = file_name[plen:]
                if re.match(r"^\d{4}-\d{2}-\d{2}(\.\w+)?$", suffix):
                    result.append(file_name)
        if len(result) < self.backup_count:
            result = []
        else:
            result.sort()
            result = result[:len(result) - self.backup_count]

        for file_name in result:
            os.remove(str(self.base_log_path.with_name(file_name)))



class LoggerUtil:
    __LOGGER_CONFIG = None
    file_handler = None

    def logger(self, module_name):
        if self.__LOGGER_CONFIG is None:
            log_path = "../logs/localLog.log"
            import os
            os.makedirs(log_path, exist_ok=True)
            # interval 滚动周期，
            # when="MIDNIGHT", interval=1 表示每天0点为更新点，每天生成一个文件
            # backupCount  表示日志保存个数
            file_handler = DailyRotatingFileHandler(
                filename=log_path, backup_count=30
            )
            # filename="mylog" suffix设置，会生成文件名为mylog.2020-02-25.log
            file_handler.suffix = "%Y-%m-%d.log"
            # extMatch是编译好正则表达式，用于匹配日志文件名后缀
            # 需要注意的是suffix和extMatch一定要匹配的上，如果不匹配，过期日志不会被删除。
            file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}.log$")
            # 定义日志输出格式
            file_handler.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] [%(process)d] [%(levelname)s] - %(module)s.%(funcName)s (%(filename)s:%(lineno)d) - %(message)s"
                )
            )
        # 创建logger对象。传入logger名字
        logger = logging.getLogger(module_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        return logger

