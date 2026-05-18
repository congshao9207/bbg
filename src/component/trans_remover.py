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

# 每批删除 TransFlow 的行数，防止锁住太多行导致锁等待超时 并给下面字段加上索引
# ALTER TABLE trans_flow ADD INDEX idx_out_req_no (out_req_no)
_DELETE_BATCH_SIZE = 500


class TransRemover(object):
    def __init__(self, out_req_no):
        self.out_req_no = out_req_no

    @staticmethod
    def _batch_delete_flow(out_req_no):
        """
        分批删除 TransFlow 记录，每批单独提交，避免长事务锁住大量行。
        通过主键排序分批查询 ID，将一批 ID 统一删除后立即提交，释放行锁。
        无 FOR UPDATE，避免阻塞并发写入；乐观重试，未删完的下一轮循环继续。
        """
        total_deleted = 0
        while True:
            # 每次按主键顺序取一批 ID，走聚簇索引避免全表扫描
            batch_ids = current_session.query(TransFlow.id) \
                .filter(TransFlow.out_req_no == out_req_no) \
                .order_by(TransFlow.id) \
                .limit(_DELETE_BATCH_SIZE) \
                .all()

            if not batch_ids:
                break

            ids = [row[0] for row in batch_ids]
            deleted = current_session.query(TransFlow) \
                .filter(TransFlow.id.in_(ids)) \
                .delete(synchronize_session=False)
            current_session.commit()
            total_deleted += deleted
            logger.info("batch deleted %d trans_flow rows (out_req_no=%s), total=%d",
                        deleted, out_req_no, total_deleted)

        return total_deleted

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
            # 第1步：单独事务分批删除 TransFlow（最耗时的操作）
            self._batch_delete_flow(self.out_req_no)

            # 第2步：在另一个独立事务中删除其余关联表
            if len(account_ids) > 0:
                current_session.query(TransAccount).filter(TransAccount.id.in_(account_ids)).delete()
            if len(attachment_ids) > 0:
                current_session.query(TransAttachment).filter(TransAttachment.id.in_(attachment_ids)).delete()
            if len(ocr_task_ids) > 0:
                current_session.query(OcrTask).filter(OcrTask.id.in_(ocr_task_ids)).delete()

            current_session.query(TransParseTask).filter(TransParseTask.out_req_no == self.out_req_no).delete()
            current_session.commit()
        except Exception as e:
            logger.error("TransRemover exception:%s", traceback.format_exc())
            current_session.rollback()
            return ResCodeEnum.FAILED, str(e)
        return ResCodeEnum.SUCCESS, None
