# @Time : 2/23/22 4:58 PM
# @Author : lixiaobo
# @File : task_query_component.py
# @Software: PyCharm
import json

from flask import jsonify
from flask_sqlalchemy_session import current_session
from sqlalchemy import func

from config.process_status import is_finished, ProcessStatusEnum
from config.res_code import ResCodeEnum
from entity.resp_entity import RespEntity
from model.model import TransParseTask, TransFlow
from util.string_util import is_empty


class TaskQueryComponent(object):
    def __init__(self, out_req_no):
        self.out_req_no = out_req_no

    def _build_data(self, task=None):
        attachment_id = str(task.result_attachment_id) if task and task.result_attachment_id else ""
        return {
            "outReqNo": self.out_req_no,
            "attachmentId": attachment_id,
        }

    def analyze_task_res(self):
        re = RespEntity()
        task = current_session.query(TransParseTask).filter(TransParseTask.out_req_no == self.out_req_no).first()
        if not task:
            return re.with_res_enum(ResCodeEnum.EXCEPTION, "outReqNo is exists:" + self.out_req_no, self._build_data())

        if is_finished(task.process_status):
            stats_data = {}
            if task.process_status == ProcessStatusEnum.DONE.name:
                stats_data = self._stats_trans_flow()
            if not is_empty(task.resp_msg):
                msg = json.loads(task.resp_msg)
                msg["stats"] = stats_data
                return jsonify(msg)
            else:
                msg = task.memo if task.memo else "timely assembly."
                return re.with_res_enum(ResCodeEnum.EXCEPTION, msg, data=self._build_data(task), stats=stats_data)
        else:
            return re.with_res_enum(ResCodeEnum.PROCESSING, data=self._build_data(task))

    def _stats_trans_flow(self):
        stats_sql = f'''
                SELECT  
                    min(trans_time),
                    max(trans_time),
                    count(*),
                    SUM(CASE WHEN trans_amt >0 THEN trans_amt  ELSE 0 END) as income_scale,  
                    SUM(CASE WHEN trans_amt <0 THEN trans_amt ELSE 0 END) as expense_scale
                FROM trans_flow tf 
                where out_req_no ='{self.out_req_no}'
        '''

        stats_data = current_session.execute(stats_sql).first()
        if not stats_data:
            return {}

        start_date = stats_data[0]
        if start_date:
            start_date = start_date.strftime("%Y-%m-%d")
        end_date = stats_data[1]
        if end_date:
            end_date = end_date.strftime("%Y-%m-%d")
        row_count = stats_data[2]
        if row_count:
            row_count = int(row_count)
        income_scale = stats_data[3]
        if income_scale:
            income_scale = float(income_scale)
        expense_scale = stats_data[4]
        if expense_scale:
            expense_scale = float(expense_scale)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "row_count": row_count,
            "income_scale": income_scale,
            "expense_scale": expense_scale
        }
