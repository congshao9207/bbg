# @Time : 8/5/22 1:56 PM 
# @Author : lixiaobo
# @File : file_encoding_rectify.py.py 
# @Software: PyCharm
import codecs
import traceback

import chardet

from config.file_type import FileTypeEnum
from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)


class FileEncodingRectify(object):
    def __init__(self, ext, file_path):
        self.ext = ext
        self.file_path = file_path

    def rectify_encoding(self):
        if self.ext != FileTypeEnum.CSV.value:
            return

        origin_file_encoding = self._obtain_file_encoding()
        if not origin_file_encoding:
            return

        try:
            with codecs.open(filename=self.file_path, mode='r', encoding=origin_file_encoding) as fi:
                data = fi.read()
                with open(self.file_path, mode='w', encoding="utf-8") as fo:
                    fo.write(data)
        except Exception as e:
            logger.error("rectify_encoding exception, cause:%s", str(e))
            logger.error("TransRemover exception:%s", traceback.format_exc())

    def _obtain_file_encoding(self):
        with open(self.file_path, 'rb') as f:
            data = f.read()
            result = chardet.detect(data)
            encoding = None
            if result:
                encoding = result.get("encoding")
            logger.info("rectify_encoding, file path:%s, file encoding:%s",self.file_path, encoding)
            return encoding
