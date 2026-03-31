# @Time : 2/28/22 9:52 AM 
# @Author : lixiaobo
# @File : trans_04_title_match_executor.py
# @Software: PyCharm
import re

from src.component.parse_context import COL_MAPPING
from src.config.trans_config import TRANS_TIME_PATTERN, TRANS_AMT_PATTERN, TRANS_BAL_PATTERN, \
    TRANS_OPNAME_PATTERN, TRANS_OPACCT_PATTERN, TRANS_OPBANK_PATTERN, TRANS_CUR_PATTERN, TRANS_CHANNEL_PATTERN, \
    TRANS_TYP_PATTERN, TRANS_USE_PATTERN, TRANS_REMARK_PATTERN, ACCOUNTING_DATE_PATTERN
from src.parser.task_base_executor import TaskBaseExecutor


class TitleMatchExecutor(TaskBaseExecutor):
    # 预编译正则表达式，避免每次execute重复编译
    TIME_PAT = re.compile(TRANS_TIME_PATTERN)
    AMT_PAT = re.compile(TRANS_AMT_PATTERN)
    BAL_PAT = re.compile(TRANS_BAL_PATTERN)
    CUR_PAT = re.compile(TRANS_CUR_PATTERN)
    OPNAME_PAT = re.compile(TRANS_OPNAME_PATTERN)
    OPACC_PAT = re.compile(TRANS_OPACCT_PATTERN)
    OPBANK_PAT = re.compile(TRANS_OPBANK_PATTERN)
    CHN_PAT = re.compile(TRANS_CHANNEL_PATTERN)
    TYP_PAT = re.compile(TRANS_TYP_PATTERN)
    USE_PAT = re.compile(TRANS_USE_PATTERN)
    MARK_PAT = re.compile(TRANS_REMARK_PATTERN)
    ACC_PAT = re.compile(ACCOUNTING_DATE_PATTERN)
    COL_CLEAN_PAT = re.compile(r'[\\/\"\'\s]')

    def __init__(self):
        super().__init__()
        self.col_mapping = {
            'time_col': [],
            'amt_col': [],
            'bal_col': [],
            'cur_col': [],
            'opname_col': [],
            'opacc_col': [],
            'opbank_col': [],
            'chn_col': [],
            'typ_col': [],
            'use_col': [],
            'mark_col': [],
            'acc_time_col': []
        }

    def execute(self):
        df = self.trans_data
        """
        将标题行粗略分配到对应的数据库标题列中
        :return:
        """
        for col in df.columns:
            temp_col = self.COL_CLEAN_PAT.sub('', str(col))
            if self.TIME_PAT.search(temp_col):
                self.col_mapping['time_col'].append(col)
            elif self.AMT_PAT.search(temp_col):
                self.col_mapping['amt_col'].append(col)
            elif self.BAL_PAT.search(temp_col):
                self.col_mapping['bal_col'].append(col)
            elif self.CUR_PAT.search(temp_col):
                self.col_mapping['cur_col'].append(col)
            elif self.OPNAME_PAT.search(temp_col):
                self.col_mapping['opname_col'].append(col)
            elif self.OPACC_PAT.search(temp_col):
                self.col_mapping['opacc_col'].append(col)
            elif self.OPBANK_PAT.search(temp_col):
                self.col_mapping['opbank_col'].append(col)
            elif self.CHN_PAT.search(temp_col):
                self.col_mapping['chn_col'].append(col)
            elif self.TYP_PAT.search(temp_col):
                self.col_mapping['typ_col'].append(col)
            elif self.USE_PAT.search(temp_col):
                self.col_mapping['use_col'].append(col)
            elif self.MARK_PAT.search(temp_col):
                self.col_mapping['mark_col'].append(col)
            elif self.ACC_PAT.search(temp_col):
                self.col_mapping['acc_time_col'].append(col)  # 修复：使用col而不是temp_col
        self.attach_context(COL_MAPPING, self.col_mapping)
