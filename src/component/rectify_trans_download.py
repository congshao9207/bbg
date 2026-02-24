# @Time : 5/10/22 10:54 AM 
# @Author : lixiaobo
# @File : rectify_trans_download.py 
# @Software: PyCharm
import os

from flask_sqlalchemy_session import current_session
from openpyxl import Workbook
from sqlalchemy import text

from util.entity_iterator import EntityIterator
from config.file_type import FileTypeEnum
from model.model import TransFlow
from util.file_util import create_temp_file

TRANS_FLOW_TITLE = [
                    "交易时间",
                    "对方户名",
                    "交易金额",
                    "账户余额",
                    "币种",
                    "对方账户",
                    "对方开户行",
                    "交易渠道",
                    "交易类型",
                    "交易用途",
                    "备注",
                    "验证结果",
                    "创建时间"
                    ]


class RectifyTransDownload(object):

    def __init__(self, out_req_no):
        self.out_req_no = out_req_no
        self.directory, self.file_name = create_temp_file(FileTypeEnum.XLSX, out_req_no)

    def __enter__(self):
        self.full_path = self.directory + os.path.sep + self.file_name
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if os.path.exists(self.full_path):
            os.remove(self.full_path)

    def extract_to_file(self) -> (str, str):
        wb = Workbook()
        ws = wb.active
        ws.append(TRANS_FLOW_TITLE)

        query = current_session.query(TransFlow) \
            .filter(TransFlow.out_req_no == self.out_req_no) \
            .order_by(text("id asc"))
        for trans_flow in EntityIterator(query):
            for trans in trans_flow:
                item = list()
                item.append(trans.trans_time)
                item.append(trans.opponent_name)
                item.append(trans.trans_amt)
                item.append(trans.account_balance)
                item.append(trans.currency)
                item.append(trans.opponent_account_no)
                item.append(trans.opponent_account_bank)
                item.append(trans.trans_channel)
                item.append(trans.trans_type)
                item.append(trans.trans_use)
                item.append(trans.remark)
                item.append(trans.verif_label)
                item.append(trans.create_time)
                ws.append(item)
        wb.save(self.full_path)
        return self.directory, self.file_name
