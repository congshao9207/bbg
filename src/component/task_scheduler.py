# @Time : 2/23/22 11:30 AM 
# @Author : lixiaobo
# @File : TransParser.py 
# @Software: PyCharm
import json
import os
import shutil
import time
import traceback
from datetime import datetime

from component.parse_context import ParseContext
from config.file_type import FileTypeEnum
from config.process_status import ProcessStatusEnum
from config.res_code import ResCodeEnum
from config.trans_config import WAITING_INTERVAL
from excepts.exceptions import ServerException
from logger.logger_util import LoggerUtil
from model.model import TransAttachment
from parser.impl.trans_01_file_load_executor import TransFileLoadExecutor
from parser.impl.trans_02_data_standardization import TransDataStandardization
from parser.impl.trans_03_rectify_executor import RectifyExecutor
from parser.impl.trans_04_title_match_executor import TitleMatchExecutor
from parser.impl.trans_05_time_standardization import TransTimeStandardization
from parser.impl.trans_06_amount_standardization import TransAmountStandardization
from parser.impl.trans_07_opponent_info_standardization import TransOpponentInfoStandardization
from parser.impl.trans_08_other_info_standardization import TransOtherInfoStandardization
from parser.impl.trans_09_verify_authenticity_executor import VerifyAuthenticityExecutor
from parser.impl.trans_10_raw_data_persistence import TransFlowRawData
from util.distributed_lock_proxy import DistributedLockProxy
from util.file_util import obtain_new_file_path
from util.magfin_redis import trans_parse_queue, redis_conn
from util.string_util import is_empty
from config.trans_config import NAS_STORAGE_PATH
from datetime import datetime

logger = LoggerUtil().logger(__name__)


class TaskScheduler(object):
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
            logger.info("acquire lock for task_id:%d is false, enqueue again", self.task.id)
            time.sleep(WAITING_INTERVAL)
            trans_parse_queue.enqueue(self.task.id)
            return None
        return self

    def __call__(self, *args, **kwargs):
        logger.info("TransParseTaskExecutor, task_id: %s", self.task.id)
        if not self._init_task_executor():
            return

        cause = None
        parse_context = None
        try:
            if not self._restore_file():
                raise ServerException("restore file exception, task_id:" + str(self.task.id))

            parse_context = ParseContext(self.task, self.file_path)
            with parse_context:
                for executor in self.executors:
                    executor.init(self.file_path, self.session, parse_context)
                    executor.execute()
                    logger.info("executor:%s, trans_data:%s", str(executor), str(parse_context.trans_data))
                    err = executor.get_last_err()
                    if not is_empty(err):
                        cause = err
                        return
                    # 责任链模式，或者有更好的设计模式来处理
        except Exception as e:
            cause = str(e)
            stack_trace = traceback.format_exc()
            logger.error("task scheduler exception: %s", cause)
            logger.error(stack_trace)
        finally:
            ver_res = parse_context.ver_res if parse_context else None
            account_id = parse_context.account_id if parse_context else None
            self._finish_task(cause, ver_res, account_id)
            # parse_context.trans_data.to_excel('result.xlsx', engine="openpyxl")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_path:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
        if self.acquired:
            self.distributed_lock.release()

    def _finish_task(self, cause, ver_res, account_id):
        if self.acquired:
            process_status = ProcessStatusEnum.DONE
            if cause:
                process_status = ProcessStatusEnum.FAILED
            self.task.process_status = process_status.name
            self.task.set_memo(cause)
            self.task.account_id = account_id
            self.task.resp_msg = self._build_resp_msg(cause, ver_res)
            self.task.verify_res = ver_res
            self.task.last_modified_date = datetime.now()
            self.session.add(self.task)
            self.session.commit()

    def _restore_file(self):
        if not self.task.result_attachment_id:
            logger.error("task %d, result_attachment_id is null", self.task.id)
            return False
        attachment = self.session.query(TransAttachment) \
            .filter(TransAttachment.id == self.task.result_attachment_id) \
            .first()

        self.file_path = obtain_new_file_path(self.task.result_file_type)
        current_date = datetime.now().strftime("%Y%m%d")
        restore_file = os.path.join(NAS_STORAGE_PATH, current_date, attachment.trans_data.decode("utf-8"))
        # shutil.copy2(restore_file, self.file_path)
        logger.info("restore file path: %s", self.file_path)
        with open(restore_file, 'rb') as src_file:
            with open(self.file_path, 'wb') as f:
                shutil.copyfileobj(src_file, f)
        return True

    def _init_task_executor(self):
        try:
            self.executors.append(TransFileLoadExecutor())
            self.executors.append(TransDataStandardization())
            self.executors.append(RectifyExecutor())
            self.executors.append(TitleMatchExecutor())
            self.executors.append(TransTimeStandardization())
            self.executors.append(TransAmountStandardization())
            self.executors.append(TransOpponentInfoStandardization())
            self.executors.append(TransOtherInfoStandardization())
            self.executors.append(VerifyAuthenticityExecutor())
            self.executors.append(TransFlowRawData())
            return True
        except Exception as e:
            logger.fatal("Init task executor exception %s", str(e))
            return False

    def _build_resp_msg(self, cause, ver_res):
        res_code = ResCodeEnum.SUCCESS.value[0]
        res_msg = None
        if not is_empty(cause):
            res_code = ResCodeEnum.FAILED.value[0]
            res_msg = cause
        else:
            res_msg = ver_res

        if res_msg:
            res_msg = res_msg[:128]

        resp_msg = {
            "resCode": res_code,
            "resMsg": res_msg,
            "data": {
                "outReqNo": self.task.out_req_no,
                "attachmentId": str(self.task.result_attachment_id)
            }
        }
        return json.dumps(resp_msg)


