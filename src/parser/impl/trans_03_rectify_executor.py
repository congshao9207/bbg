from config.column_mapping import TITLE_RECTIFY, CHAR_MAPPING
from parser.task_base_executor import TaskBaseExecutor
import pandas as pd
import re


class RectifyExecutor(TaskBaseExecutor):
    """
        标题行中部分识错表头根据枚举值来修正
        对手账户中非数字用*替代去除
    """

    def __init__(self):
        super().__init__()

    def _rectify_title(self):
        df = self.trans_data
        for title in df.columns:
            temp = title
            for k, v in TITLE_RECTIFY.items():
                if title in v and k not in df.columns:
                    df.rename(columns={title: k}, inplace=True)
                    break
            for k, v in CHAR_MAPPING.items():
                temp = temp.replace(v[0], k)
            df.rename(columns={title: temp}, inplace=True)
        self.trans_data = df

    def _rectify_op_acc(self):
        df = self.trans_data
        pattern = re.compile(r'[^0-9]')
        acc_nos = []
        for acc_no in df['对方账户']:
            if pd.isna(acc_no):
                acc_nos.append(None)
                continue
            acc_no = re.sub(pattern, '*', str(acc_no))
            acc_nos.append(acc_no)
        df['对方账户'] = acc_nos
        self.trans_data = df

    def execute(self):
        # if self.parse_context.trans_task.rectify:
        self._rectify_title()
        if '对方账户' in self.trans_data.columns and \
                self.parse_context.parse_task.trans_flow_src_type in [2, 3, '2', '3']:
            self._rectify_op_acc()
