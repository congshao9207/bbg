# @Time : 2/22/22 1:37 PM 
# @Author : lixiaobo
# @File : file_util.py 
# @Software: PyCharm
import hashlib
import os
import uuid

from config.file_type import FileTypeEnum
from config.trans_config import WORK_SPACE


def obtain_new_file_path(file_type):
    if isinstance(file_type, FileTypeEnum):
        return WORK_SPACE + os.path.sep + str(uuid.uuid1()) + "." + file_type.value
    else:
        return WORK_SPACE + os.path.sep + str(uuid.uuid1()) + "." + file_type


def create_temp_file(file_type, file_prefix=None):
    if not file_prefix:
        prefix = ""
    else:
        prefix = str(file_prefix)

    if type(file_type) == str:
        return WORK_SPACE, prefix + "_" + str(uuid.uuid1()) + "." + file_type.lower()
    else:
        return WORK_SPACE, prefix + "_" + str(uuid.uuid1()) + "." + file_type.value


def get_file_md5(file_path):
    with open(file_path, "rb") as f:
        file_content = f.read()
        md5hash = hashlib.md5(file_content)
        return md5hash.hexdigest()
