# @Time : 2/21/22 7:17 PM 
# @Author : lixiaobo
# @File : trans_parse_component.py 
# @Software: PyCharm
import os
import threading
import uuid

from flask_sqlalchemy_session import current_session
from get_filename import get_filename

from component.excel_file_adapter import ExcelFileAdapter
from component.file_decrypter import FileDecrypter
from component.file_encoding_rectify import FileEncodingRectify
from component.task_receiver import TaskReceiver
from component.trans_file_context import TransFileContext
from config.file_type import FileTypeEnum
from config.res_code import ResCodeEnum
from config.trans_config import WORK_SPACE
from entity.resp_entity import RespEntity
from logger.logger_util import LoggerUtil
from model.model import TransParseTask
from util.file_util import get_file_md5
from util.magfin_redis import trans_parse_queue

logger = LoggerUtil().logger(__name__)


class TransParseComponent(object):
    def __init__(self, app_id, param, file):
        self.app_id = app_id
        self.param = param
        self.file = file
        self.origin_file_name = self.file.filename
        self.file_hash = None

        self.file_context = TransFileContext()
        self.ext = get_filename(self.origin_file_name, "extension", -1)
        self.ocr_required = self.ext == FileTypeEnum.PDF.value
        self.stand_file_name = str(uuid.uuid1()) + "." + self.ext
        self.stand_file_path = WORK_SPACE + os.path.sep + self.stand_file_name
        self.file_context.attach(self.stand_file_path)

        self.resp = None
        self.logger = LoggerUtil().logger(__name__)

    def pre_check(self) -> bool:
        res_msg = ""
        if self.app_id is None:
            res_msg = "app_id is required"
        elif self.param is None:
            res_msg = "param is required"
        elif self.file is None:
            res_msg = "file is required"

        res_code = 0 if res_msg == '' else ResCodeEnum.PARAM_ERROR.value[0]

        if res_code != 0:
            self.resp = RespEntity.response(res_code, res_msg)
            return False
        logger.info("file path:%s", self.stand_file_path)
        self.file.save(self.stand_file_path)

        #if self._duplication_check():
        #    self.resp = RespEntity.with_res_enum(ResCodeEnum.FILE_DUPLICATION)
        #    return False

        return True

    def execute(self):
        if self.ocr_required:
            post_file_path = None
            fd = FileDecrypter(self.ext, self.stand_file_path, self.param)
            fd.decrypt()
        else:
            fer = FileEncodingRectify(self.ext, self.stand_file_path)
            fer.rectify_encoding()

            efa = ExcelFileAdapter(self.ext, self.stand_file_path)
            post_file_path = efa.to_xlsx()
            self.file_context.attach(post_file_path)

        tr = TaskReceiver(self.ocr_required,
                          self.param,
                          self.origin_file_name,
                          self.ext,
                          self.file_hash,
                          self.stand_file_path,
                          post_file_path)
        task_id = tr.receive_task()

        if not task_id:
            self.resp = RespEntity.with_res_enum(ResCodeEnum.FAILED)
        else:
            self.resp = RespEntity.with_res_enum(ResCodeEnum.SUCCESS)
            trans_parse_queue.enqueue(task_id)

    def get_last_resp(self):
        return self.resp

    def teardown(self, have_exception=False):
        if have_exception:
            try:
                backup_file_name = str(uuid.uuid1()) + "." + self.ext
                backup_file_path = WORK_SPACE + os.path.sep + backup_file_name
                with open(self.stand_file_path, "rb") as f:
                    data = f.read()
                    with open(backup_file_path, "wb") as dest:
                        dest.write(data)
                logger.warn("PARSE_EXCEPTION, BACKUP_FILE_PATH:%s", backup_file_path)
            except Exception as e:
                logger.error("teardown backup file exception, cause:%s", str(e))
        self.file_context.teardown()
        # 新增ocr文件清理
        if self.ocr_required and os.path.exists(self.stand_file_path):
            os.remove(self.stand_file_path)

    def _duplication_check(self):
        self.file_hash = get_file_md5(self.stand_file_path)

        exists = current_session.query(TransParseTask).filter(TransParseTask.file_hash == self.file_hash).count() > 0
        self.logger.info("file name %s, exists: %s", self.origin_file_name, exists)
        self.logger.info("pid: %s, thread_name: %s", os.getpid(), threading.current_thread().getName())
        return exists
