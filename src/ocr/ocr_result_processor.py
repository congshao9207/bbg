# @Time : 4/16/22 1:57 PM
# @Author : lixiaobo
# @File : ocr_result_processor.py
# @Software: PyCharm
import os
import time
import traceback
from datetime import datetime

from flask_sqlalchemy_session import current_session

from component.attachment_file_compression import AttachmentFileCompression
from config.file_type import FileTypeEnum
from config.process_status import ProcessStatusEnum, is_finished
from logger.logger_util import LoggerUtil
from model.model import OcrTask, TransParseTask
from ocr.ocr_result_to_xlsx import OcrResultToXlsx
from util.distributed_lock_proxy import DistributedLockProxy
from util.magfin_redis import trans_parse_queue, redis_conn

logger = LoggerUtil().logger(__name__)


class OcrResultProcessor(object):
    def __init__(self, resp_json, parse_no=None):
        self.resp_json = resp_json
        self.cause = None
        # 此处传入parse_no在主动查询时，如果未从报文中解析到parse_no也能根据传入的参数更新任务记录表相关数据
        self.parse_no = parse_no
        self.group_no = None
        self.transFlowSrcType = None
        self.flowData = None
        self.result_attachment_id = None
        self.result_file_type = None

    def _pre_execute(self):
        if self.resp_json["resCode"] != 0:
            self.cause = self.resp_json["resMsg"]

        data = self.resp_json["data"]
        self.parse_no = data.get("parseNo")
        self.transFlowSrcType = data.get("transFlowSrcType")
        self.flowData = data.get("result")

        self.group_no = data.get("groupNo")
        if not self.group_no:
            self.group_no = str(round(time.time()))

    def process(self):
        logger.info("OcrResultProcessor begin...")
        result_file_path = None
        lock = None
        acquired = False
        try:
            self._pre_execute()
            logger.info("acquire distributed lock, group_no:%s", self.group_no)
            lock = DistributedLockProxy(redis_conn, resource_key=self.group_no)
            acquired = lock.acquire()
            if self.cause:
                logger.warn("ocr result: %s", self.cause)
                return

            converter = OcrResultToXlsx(self.flowData)
            result_file_path = converter.to_xlsx()
            self.result_file_type = FileTypeEnum.XLSX.value

            afc = AttachmentFileCompression()
            # reserved json
            afc.persistence_json(self.flowData, self.parse_no)
            self.result_attachment_id = afc.persistence_file(result_file_path, None, self.result_file_type)

        except Exception as e:
            trace = traceback.format_exc()
            logger.error("ocr result process exception:%s", trace)
            self._append_cause(str(e.__class__) + str(e))
        finally:
            status = ProcessStatusEnum.FAILED if self.cause else ProcessStatusEnum.DONE
            ocr_task_id = self._update_ocr_task(status, self.cause)
            if ocr_task_id:
                parse_task_id = self._update_parse_task(ocr_task_id, status, self.cause)
                if status == ProcessStatusEnum.DONE and parse_task_id:
                    # Trigger trans flow parse, add task_id to queue.
                    trans_parse_queue.enqueue(parse_task_id)
            if result_file_path:
                os.remove(result_file_path)
            if lock and acquired:
                lock.release()

    def _update_ocr_task(self, status, cause):
        ocr_task = current_session.query(OcrTask).filter(OcrTask.parse_no == self.parse_no).first()
        if ocr_task:
            if is_finished(ocr_task.process_status):
                logger.warn("ocr_task is finished, ignore it, out_req_no:%s", ocr_task.out_req_no)
                return None
            ocr_task.process_status = status.name
            if cause:
                ocr_task.set_memo("ocr-notify:" + cause)
            ocr_task.result_attachment_id = self.result_attachment_id
            ocr_task.result_file_type = self.result_file_type
            ocr_task.last_modified_date = datetime.now()

            current_session.add(ocr_task)
            current_session.commit()
            return ocr_task.id
        return None

    def _update_parse_task(self, ocr_task_id, status, cause):
        parse_task = current_session.query(TransParseTask).filter(TransParseTask.ocr_task_id == ocr_task_id).first()
        if parse_task:
            if is_finished(parse_task.process_status):
                logger.warn("parse_task is finished, ignore it, out_req_no:%s", parse_task.out_req_no)
                return None
            parse_task.result_attachment_id = self.result_attachment_id
            parse_task.result_file_type = self.result_file_type
            parse_task.trans_flow_src_type = self.transFlowSrcType
            parse_task.ocr_post_attachment_id = self.result_attachment_id
            if status == ProcessStatusEnum.DONE:
                parse_task.process_status = ProcessStatusEnum.PROCESSING.name
            else:
                parse_task.process_status = status.name
            if cause:
                parse_task.set_memo("ocr-notify:" + cause)

            parse_task.last_modified_date = datetime.now()
            current_session.add(parse_task)
            current_session.commit()
            return parse_task.id
        return None

    def _append_cause(self, info):
        if self.cause:
            self.cause = self.cause + "," + info
        else:
            self.cause = info
