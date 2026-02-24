# @Time : 4/16/22 11:30 AM
# @Author : lixiaobo
# @File : TransParser.py 
# @Software: PyCharm
import os
import traceback
from datetime import datetime

from config.process_status import ProcessStatusEnum
from excepts.exceptions import ServerException
from logger.logger_util import LoggerUtil
from model.model import TransAttachment
from ocr.ocr_task_component import OcrTaskComponent
from util.distributed_lock_proxy import DistributedLockProxy
from util.file_util import obtain_new_file_path
from util.magfin_redis import trans_parse_queue, redis_conn

import shutil
from config.trans_config import NAS_STORAGE_PATH
from datetime import datetime

logger = LoggerUtil().logger(__name__)


class TaskOcrScheduler(object):
    def __init__(self, task, session):
        self.task = task
        self.session = session

        self.file_path = None
        self.executors = []
        self.acquired = False
        self.distributed_lock = None

    def __enter__(self):
        self.distributed_lock = DistributedLockProxy(redis_conn, resource_key=self.task.group_no)
        self.acquired = self.distributed_lock.acquire_no_block()
        if not self.acquired:
            trans_parse_queue.enqueue(self.task.id)
            return None
        return self

    def __call__(self, *args, **kwargs):
        logger.info("task_ocr_scheduler, task: %s", self.task)
        cause = None
        ocr_task_id = None
        try:
            if not self._restore_file():
                raise ServerException("restore file exception, task_id:" + str(self.task.id))
            ocr_task_component = OcrTaskComponent(self.task, self.file_path, self.session)
            cause, ocr_task_id = ocr_task_component.start_ocr_task()
        except Exception as e:
            cause = str(e)
            stack_trace = traceback.format_exc()
            logger.error("task scheduler exception: %s", cause)
            logger.error(stack_trace)
        finally:
            self._finish_task(cause, ocr_task_id)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_path:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
        if self.acquired:
            self.distributed_lock.release()

    def _finish_task(self, cause, ocr_task_id):
        if self.acquired:
            process_status = ProcessStatusEnum.PROCESSING
            if cause:
                process_status = ProcessStatusEnum.FAILED
            self.task.process_status = process_status.name
            self.task.set_memo(cause)
            self.task.last_modified_date = datetime.now()
            self.task.ocr_task_id = ocr_task_id
            self.session.add(self.task)
            self.session.commit()

    def _restore_file(self):
        if not self.task.origin_attachment_id:
            logger.error("task %d, origin_attachment_id is null", self.task.id)
            return False
        attachment = self.session.query(TransAttachment)\
            .filter(TransAttachment.id == self.task.origin_attachment_id) \
            .first()

        self.file_path = obtain_new_file_path(self.task.origin_file_type)
        current_date = datetime.now().strftime("%Y%m%d")
        restore_file = os.path.join(NAS_STORAGE_PATH, current_date, attachment.trans_data.decode("utf-8"))
        # shutil.copy2(restore_file, self.file_path)
        logger.info("restore file path: %s", self.file_path)
        with open(restore_file, 'rb') as src_file:
            with open(self.file_path, "wb") as f:
                shutil.copyfileobj(src_file, f)
        return True