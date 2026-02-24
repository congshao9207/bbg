# @Time : 4/21/22 9:43 AM 
# @Author : lixiaobo
# @File : OcrResultCheckExecutor.py 
# @Software: PyCharm
import datetime

from sqlalchemy import text

from config.process_status import ProcessStatusEnum
from config.trans_config import PARSE_TASK_TIMEOUT_MINUTES
from logger.logger_util import LoggerUtil
from model.model import OcrTask
from ocr.ocr_client import OcrClient
from ocr.ocr_result_processor import OcrResultProcessor

logger = LoggerUtil().logger(__name__)


class OcrResultQueryJobExecutor(object):
    def __init__(self, session):
        self.session = session

    def execute(self):
        page_index = 0
        per_size = 10
        time_out_minutes = abs(PARSE_TASK_TIMEOUT_MINUTES) * -1
        while True:
            last_date_time = datetime.datetime.now() + datetime.timedelta(minutes=time_out_minutes)
            ocr_tasks_statement = self.session.query(OcrTask)\
                .filter(OcrTask.process_status == ProcessStatusEnum.PROCESSING.name,
                        OcrTask.result_attachment_id == None,
                        OcrTask.created_date < last_date_time)\
                .order_by(text("id desc")).offset(page_index * per_size).limit(per_size)
            page_index = page_index + 1
            ocr_tasks = ocr_tasks_statement.all()
            if not ocr_tasks or len(ocr_tasks) == 0:
                logger.info("OcrResultQueryJobExecutor execute finished....")
                break
            for ocr_task in ocr_tasks:
                self._process_ocr_task(ocr_task)

    @staticmethod
    def _process_ocr_task(ocr_task):
        ocr_client = OcrClient(parse_no=ocr_task.parse_no)
        _, _, resp_json = ocr_client.ocr(ocr_client.call_back_result_query)
        if not resp_json:
            logger.error("call_back_result_query resp is none.")
            return

        p = OcrResultProcessor(resp_json, ocr_task.parse_no)
        p.process()



