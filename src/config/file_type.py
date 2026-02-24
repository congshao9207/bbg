# @Time : 2/22/22 11:58 AM 
# @Author : lixiaobo
# @File : file_type.py 
# @Software: PyCharm
from enum import Enum


class FileTypeEnum(Enum):
    XLS = "xls"
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    ZIP = "zip"
    RAR = "rar"
