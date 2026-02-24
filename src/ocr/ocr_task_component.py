# @Time : 4/16/22 8:29 AM 
# @Author : lixiaobo
# @File : ocr_task_component.py 
# @Software: PyCharm
from datetime import datetime

from config.process_status import ProcessStatusEnum
from model.model import OcrTask
from ocr.ocr_client import OcrClient


class OcrTaskComponent(object):
    def __init__(self, task, file_path, session):
        self.task = task
        self.file_path = file_path
        self.session = session

    def start_ocr_task(self):
        ocr_client = OcrClient(file_path=self.file_path, group_no=self.task.group_no)
        cause, parse_no, _ = ocr_client.ocr(ocr_client.call_back_upload)
        # 创建ocr任务
        ocr_task_id = self._create_task(cause, parse_no)
        return cause, ocr_task_id

    def _create_task(self, cause, parse_no):
        ocr_task = OcrTask()
        ocr_task.out_req_no = self.task.out_req_no
        ocr_task.parse_no = parse_no
        ocr_task.origin_attachment_id = self.task.origin_attachment_id
        ocr_task.origin_file_type = self.task.origin_file_type
        ocr_task.result_attachment_id = None
        ocr_task.result_file_type = None
        if cause:
            ocr_task.process_status = ProcessStatusEnum.FAILED.name
            ocr_task.set_memo("ocr-resp:" + cause)
        else:
            ocr_task.process_status = ProcessStatusEnum.PROCESSING.name
            ocr_task.set_memo("ocr-resp:成功")
        ocr_task.created_date = datetime.now()
        ocr_task.last_modified_date = datetime.now()

        self.session.add(ocr_task)
        self.session.commit()
        return ocr_task.id
