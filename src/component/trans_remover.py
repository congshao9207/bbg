# @Time : 5/18/22 10:19 AM 
# @Author : lixiaobo
# @File : trans_remover.py 
# @Software: PyCharm
import traceback

from flask_sqlalchemy_session import current_session

from config.res_code import ResCodeEnum
from logger.logger_util import LoggerUtil
from model.model import TransParseTask, OcrTask, TransAttachment, TransAccount, TransFlow

logger = LoggerUtil().logger(__name__)


class TransRemover(object):
    def __init__(self, out_req_no):
        self.out_req_no = out_req_no

    def execute(self) -> (ResCodeEnum, str):
        tpt_list = current_session.query(TransParseTask).filter(TransParseTask.out_req_no == self.out_req_no).all()
        if not tpt_list or len(tpt_list) == 0:
            return ResCodeEnum.RECORD_NOT_EXISTS, "trans parse task is not exists, outReqNo:" + self.out_req_no

        account_ids = list()
        attachment_ids = list()
        ocr_task_ids = list()
        for task in tpt_list:
            if task.account_id:
                account_ids.append(task.account_id)
            if task.origin_attachment_id:
                attachment_ids.append(task.origin_attachment_id)
            if task.result_attachment_id:
                attachment_ids.append(task.result_attachment_id)
            if task.ocr_post_attachment_id:
                attachment_ids.append(task.ocr_post_attachment_id)
            if task.ocr_task_id:
                ocr_task_ids.append(task.ocr_task_id)

        try:
            if len(account_ids) > 0:
                current_session.query(TransAccount).filter(TransAccount.id.in_(account_ids)).delete()
            if len(attachment_ids) > 0:
                current_session.query(TransAttachment).filter(TransAttachment.id.in_(attachment_ids)).delete()
            if len(ocr_task_ids) > 0:
                current_session.query(OcrTask).filter(OcrTask.id.in_(ocr_task_ids)).delete()

            current_session.query(TransParseTask).filter(TransParseTask.out_req_no == self.out_req_no).delete()
            current_session.query(TransFlow).filter(TransFlow.out_req_no == self.out_req_no).delete()
            current_session.commit()
        except Exception as e:
            logger.error("TransRemover exception:%s", traceback.format_exc())
            current_session.rollback()
            return ResCodeEnum.FAILED, str(e)
        return ResCodeEnum.SUCCESS, None
