# @Time : 2/23/22 1:47 PM 
# @Author : lixiaobo
# @File : parse_context.py.py 
# @Software: PyCharm
from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)

COL_MAPPING = "col_mapping"

"""
|--------------------------------------------|
|keys在不同阶段被赋值，使用时需要关注，否则会引发NPE  |
|-----------------|--------------------------|
|   Key           |      Executor Step       |
|-----------------|--------------------------|
| col_mapping     |    03                    |
|----------------—|--------------------------|
"""


class ParseContext(object):
    def __init__(self, parse_task, file_path):
        self.parse_task = parse_task
        self.file_path = file_path
        self.trans_data = None

        """
        验证为可信
        验证为可疑
        """
        self.ver_res = "-"
        self.data = {}
        self.account_id = None

    def __enter__(self):
        logger.info("__enter__")

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("__exit__")

    def set_data(self, k, v):
        if k and v:
            self.data[k] = v

    def get_data(self, k):
        if k:
            return self.data.get(k)
