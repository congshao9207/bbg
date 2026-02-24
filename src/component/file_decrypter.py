# @Time : 8/20/22 9:32 AM 
# @Author : lixiaobo
# @File : file_decryptor.py 
# @Software: PyCharm
from json2obj import JSONObjectMapper

from config.file_type import FileTypeEnum
from config.trans_config import PDF_DECRYPT_FLAG
from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)


class FileDecrypter(object):
    def __init__(self, ext, file_path, param):
        self.ext = ext
        self.file_path = file_path
        self.param = param

    def decrypt(self):
        if self.ext != FileTypeEnum.PDF.value:
            logger.info("file type:%s, file decrypter is not support")
            return
        if PDF_DECRYPT_FLAG != "ON":
            logger.info("the env PDF_DECRYPT_FLAG:%s, file decrypter is nothing to do.", PDF_DECRYPT_FLAG)
            return
        param_obj = JSONObjectMapper(self.param)
        if "filepwd" not in param_obj:
            logger.info("the param filepwd is not exists, decrypter is nothing to do.")
            return
        filepwd = param_obj.filepwd
        filepwd = filepwd if filepwd else ""
        logger.info("filepwd:%s, decrypt begin...", filepwd)
        try:
            import pikepdf
            with pikepdf.open(self.file_path, password=filepwd, allow_overwriting_input=True) as pdf:
                pdf.save(self.file_path)
            logger.info("file decrypt finished....%s", self.file_path)
        except Exception as e:
            logger.info("decrypt exception:%s", str(e))






