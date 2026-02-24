# @Time : 2/23/22 1:42 PM 
# @Author : lixiaobo
# @File : trans_parse_task_base_executor.py 
# @Software: PyCharm
from component.parse_context import COL_MAPPING
import re


class TaskBaseExecutor(object):
    def __init__(self):
        self.file_path = None
        self.session = None
        self.parse_context = None
        self.last_err = None

    @property
    def trans_data(self):
        return self.parse_context.trans_data

    @trans_data.setter
    def trans_data(self, trans_data):
        self.parse_context.trans_data = trans_data

    def col_mapping(self):
        return self.parse_context.get_data(COL_MAPPING)

    def attach_context(self, k, v):
        if k and v:
            self.parse_context.set_data(k, v)

    def fetch_context_data(self, k):
        if not k:
            return None
        self.parse_context.get_data(k)

    def execute(self):
        """
        如果处理失败，需要调用`mark_err`方法记录失败原因
        :return:
        """
        pass

    def mark_ver_res(self, ver_res: str):
        """
        验证结果标记
        :param ver_res:
        :return:
        """
        self.parse_context.ver_res = ver_res

    def trans_date_delete_status_init(self):
        self.parse_context.trans_date_delete_status = False

    def trans_date_delete_status(self):
        self.parse_context.trans_date_delete_status = True

    def mark_err(self, err):
        """
        异常信息标记
        :param err:
        :return:
        """
        self.last_err = err

    def init(self, file_path, session, parse_context):
        self.file_path = file_path
        self.session = session
        self.parse_context = parse_context
        self.last_err = None

    def get_last_err(self):
        return self.last_err

    @staticmethod
    def value_trans(value):
        try:
            value = str(value)
            # 将所有汉字替换为？
            value = re.sub(r'[\u4e00-\u9fa5]', '？', value)
            # 将？之间最后一个包含数字的字符串提取出来
            if '？' in value:
                value = [x for x in value.split('？') if re.search(r'\d', x)][-1]
            # 保留最后一个小数点
            if value.count('.') > 1:
                value = re.sub(r'[.]', '', value, value.count('.') - 1)
            # 删除空白字符及连续两个负号及末尾的负号
            value = re.sub(r'\s|--|-$', '', value)
            # 将O替换为0，l替换为1，并删除除数字、负号、小数点之外的所有字符
            value = re.sub(r'[^\d.-]', '', value.replace('O', '0').replace('l', '1'))
            # 最多保留开头的第一个负号
            value = ('-' if value.startswith('-') else '') + re.sub(r'-', '', value)
            # 转换为数值型
            res = round(float(value), 2)
        except (ValueError, TypeError, OverflowError, IndexError):
            res = 0
        return res
