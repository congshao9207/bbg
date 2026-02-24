import re

import pandas as pd

from config.trans_config import MAX_TITLE_NUMBER, TRANS_TIME_PATTERN, \
    TRANS_AMT_PATTERN, TRANS_BAL_PATTERN, ACCOUNTING_DATE_PATTERN
from logger.logger_util import LoggerUtil
from parser.task_base_executor import TaskBaseExecutor

logger = LoggerUtil().logger(__name__)


class TransFileLoadExecutor(TaskBaseExecutor):
    """
    若上传流水文件类型是xls*文件，将调用此类进行数据读取
    """
    def __init__(self):
        super().__init__()
        self.sheet_name = None
        self.title = None
        self.read_type = 'xls'

    def execute(self):
        self.sheet_name, self.title = self._find_title()
        if self.sheet_name is None or self.sheet_name == '' or self.title is None:
            if self.sheet_name is None:
                self.mark_err('文件读取异常_1')
            else:
                self.mark_err('上传失败,无法找到标题行,流水文件内容有误')
            return
        self.trans_data = self._convert_to_data_frame()
        self.trans_data.rename(columns=lambda x: re.sub(r'[\\/\"\'\s]', '', str(x)), inplace=True)

    def _find_title(self):
        """
        从文件中的所有sheet中寻找存在流水标题行的文件，如果存在则跳出循环
        :return:
        """
        with open(self.file_path, "rb") as file:
            try:
                title_df = pd.read_excel(file, nrows=MAX_TITLE_NUMBER, header=None, sheet_name=None, engine='openpyxl')
                index_list = title_df.keys()
            except Exception as e:
                logger.info("----读取失败原因r1:%s----" % str(e))
                try:
                    title_df = pd.read_html(file, skiprows=range(MAX_TITLE_NUMBER, 100000), header=None)
                    self.read_type = 'html'
                    index_list = range(len(title_df))
                except Exception as e:
                    logger.info("----读取失败原因r2:%s----" % str(e))
                    return None, None
        # 遍历所有sheet
        for k in index_list:
            v = title_df[k]
            if v.shape[0] == 0:
                continue
            max_len = 0  # 最大列
            title = -1  # 标题行号
            cnt = 0  # 遍历行数计数
            for row in v.itertuples():
                temp = [re.sub(r'\s', '', str(x)) for x in row if re.sub(r'\s', '', str(x)) != '']
                temp_len = len(temp)
                string = ''.join(temp)
                if ((re.search(TRANS_TIME_PATTERN, string) or re.search(ACCOUNTING_DATE_PATTERN, string)) and
                        re.search(TRANS_AMT_PATTERN, string) and re.search(TRANS_BAL_PATTERN, string)) or \
                        (re.search(TRANS_TIME_PATTERN, string) and re.search(TRANS_AMT_PATTERN, string) and
                         self.parse_context.parse_task.trans_flow_src_type in [2, 3, '2', '3']):
                    if temp_len > max_len:
                        title = cnt
                        max_len = temp_len
                cnt += 1
            if title != -1:
                return k, title
        return '', None

    def _convert_to_data_frame(self):
        df = None
        # dtypes = {'对方账号': pd.np.str}
        with open(self.file_path, "rb") as file:
            try:
                df = pd.read_excel(file, header=self.title, dtype=str, sheet_name=self.sheet_name, engine='openpyxl')
            except Exception as e:
                logger.info("----读取失败, 将进行重试原因r3:%s----" % str(e))
                try:
                    df = pd.read_html(file, header=self.title)[self.sheet_name]
                except Exception as e2:
                    logger.info("----读取失败原因r3:%s----" % str(e2))
                    self.mark_err('文件读取异常-2')
            return df
