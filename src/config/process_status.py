# @Time : 2/22/22 3:23 PM 
# @Author : lixiaobo
# @File : process_status.py 
# @Software: PyCharm
from enum import Enum


class ProcessStatusEnum(Enum):
    PENDING = 0
    PROCESSING = 1
    DONE = 2
    FAILED = 3


FINISHED_STATUS = [
    ProcessStatusEnum.DONE.name,
    ProcessStatusEnum.FAILED.name
]


def is_finished(status):
    return status in FINISHED_STATUS
