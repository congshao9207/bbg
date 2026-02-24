import os
import re
import traceback
import uuid

from get_filename import get_filename

from component.preparser.pre_parse_util import date_time_format
from config.trans_config import WORK_SPACE, ILLEGAL_CHAR_RE
from logger.logger_util import LoggerUtil

logger = LoggerUtil().logger(__name__)


class PreParseContext(object):
    def __init__(self, file, file_pwd):
        self.file = file
        self.file_pwd = file_pwd
        self.is_local_file = type(file) == str
        self.ext = ''

        self.bank_name = ''
        self.bank_account = ''
        self.user_name = ''
        self.start_date = ''
        self.end_date = ''
        self.row_count = ''

    def __enter__(self):
        if self.is_local_file:
            self.ext = get_filename(self.file, "extension", -1)
            self.stand_file_path = self.file
            self.stand_file_name = get_filename(self.file, "filename", -1)
        else:
            self.ext = get_filename(self.file.filename, "extension", -1)
            self.stand_file_name = str(uuid.uuid1()) + "." + self.ext
            self.stand_file_path = WORK_SPACE + os.path.sep + self.stand_file_name
            self.file.save(self.stand_file_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.is_local_file:
            if os.path.exists(self.stand_file_path):
                os.remove(self.stand_file_path)

    def is_parse_succeed(self):
        return self.bank_name != '' or self.bank_account != ''

    def build_parse_data(self):
        try:
            self._format_data()
        except Exception as e:
            err_info = traceback.format_exc()
            logger.error(str(e) + "--" + err_info)
            logger.info("start_date:%s, end_date:%s", self.start_date, self.end_date)
        return {
            "bank_name": self.bank_name,
            "bank_account": self.bank_account,
            "user_name": self.user_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "row_count": self.row_count
        }

    def _format_data(self):
        if self.start_date:
            self.start_date = date_time_format(self.start_date)
        if self.end_date:
            self.end_date = date_time_format(self.end_date)
        if self.bank_name:
            self.bank_name = re.sub(ILLEGAL_CHAR_RE, "", self.bank_name)
        if self.bank_account:
            self.bank_account = re.sub(ILLEGAL_CHAR_RE, "", self.bank_account)
        if self.user_name:
            self.user_name = re.sub(ILLEGAL_CHAR_RE, "", self.user_name)
