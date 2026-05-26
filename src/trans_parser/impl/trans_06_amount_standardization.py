
from config.trans_config import INCOME_PATTERN, OUTCOME_PATTERN
import re

from trans_parser.task_base_executor import TaskBaseExecutor


class TransAmountStandardization(TaskBaseExecutor):
    """
    将流水文件中交易金额标准化
    author:汪腾飞
    created_time:20200630
    updated_time_v1:20200911,搜索标签列时,要同时包含进账关键字和出账关键字,避免只有一类关键字;去除金额列不符合要求的字符的时候
        先删除空格,再删除负号结尾的字符
    updated_time_v2:20201223,将所有正则匹配格式都纳入配置文件
    updated_time_v3:20220420,新增智能删除及智能纠偏功能
    """
    # 预编译正则表达式
    INCOME_PAT = re.compile(INCOME_PATTERN)
    OUTCOME_PAT = re.compile(OUTCOME_PATTERN)
    USE_CLEAN_PAT = re.compile(r'[\\\"\'\s^-]')  # 交易用途清理
    WHITESPACE_PAT = re.compile(r'\s')
    OTHER_CATEGORY_PAT = re.compile(r'(其他|其它|不计收支)')
    COLUMN_CLEAN_PAT = re.compile(r'[(（\\\/]')  # 列名清理
    DIGIT_PAIR_PAT = re.compile(r'(12|21)')  # 数字对匹配

    def __init__(self):
        super().__init__()
        self.df = None
        self.amt_col = None
        self.tag = None

    def _trans_use(self):
        type_col = self.col_mapping()['use_col']
        if len(type_col):
            # 向量化优化：避免eval和apply
            self.df['trans_use'] = ''
            for col in type_col:
                self.df['trans_use'] += self.df[col].fillna('').astype(str)
            # 使用str.replace进行向量化清理
            self.df['trans_use'] = self.df['trans_use'].str.replace(self.USE_CLEAN_PAT, '', regex=True)
        else:
            self.df['trans_use'] = ''

    def _find_tag_col(self):
        """
        在金额列中寻找是否有标签列,如果存在标签列则新增一列'tag'将标签列对应的出账表示为-1,进账表示为1
        :return:
        """
        length = len(self.amt_col)
        for index in range(-length, 0):
            col = self.amt_col[index]
            temp = self.df[col].astype(str).str.replace(self.WHITESPACE_PAT, '', regex=True).value_counts()
            index = ''.join([str(_) for _ in temp.index])
            if len(temp) in [2, 3] and (self.INCOME_PAT.search(index) or self.OUTCOME_PAT.search(index) or
                                        self.DIGIT_PAIR_PAT.search(index)):
                tag = col
                # self.df['tag'] = self.df[tag].astype(str).apply(lambda x: re.sub(OUTCOME_FULL_PATTERN, '1', x)).\
                #     apply(lambda x: 1 if x != '1' else -1)
                self.df['tag'] = self.df[tag].astype(str).apply(
                    lambda x: -1 if self.OUTCOME_PAT.search(x) else 0 if self.OTHER_CATEGORY_PAT.search(x) else 1)
                # 微信支付宝流水其它里面的信用卡还款作为出账
                # if self.parse_context.parse_task.trans_flow_src_type in [2, 3]:
                #     self.df.loc[(self.df['tag'] == 0) & (self.df.trans_use.str.contains('信用卡还款')), 'tag'] = -1
                if self.parse_context.parse_task.trans_flow_src_type == 3:
                    self.df.loc[(self.df['tag'] == 0) & (self.df.trans_use.str.contains('零钱提现|经营账户提现|还款|零钱通转出|购买理财通')), 'tag'] = -1
                    self.df.loc[(self.df['tag'] == 0) & (self.df.trans_use.str.contains('零钱充值|转入零钱通')), 'tag'] = 1
                    self.df.loc[self.df.trans_use.str.contains('转入零钱通来自零钱|零钱通转出到零钱'), 'tag'] = 0
                self.df['verif_label'] = self.df[tag].astype(str).apply(
                    lambda x: '' if self.OUTCOME_PAT.search(x) or self.INCOME_PAT.search(x) else 'T99')

                self.amt_col.remove(col)
                return 1
            if col == '交易类型':
                self.amt_col.remove(col)
                self.amt_col.append(col)
        return 0

    def _remove_amt_col(self):
        """
        去除金额列中不符合规范的列，仅保留非0值最多的一列或者两列
        :return:
        """
        length = len(self.amt_col)
        col_map = {}
        income_cnt, outcome_cnt, amt_cnt, tbd_cnt = 0, 0, 0, 0
        for index in range(-length, 0):
            col = self.amt_col[index]
            col1 = self.COLUMN_CLEAN_PAT.sub(' ', col)
            col_list = col1.split(maxsplit=2)
            if len(col_list) == 2 and \
                    ((self.INCOME_PAT.search(col_list[0]) and self.OUTCOME_PAT.search(col_list[1])) or
                     (self.INCOME_PAT.search(col_list[1]) and self.OUTCOME_PAT.search(col_list[0]))):
                col1 = col_list[1]
            else:
                col1 = col
            # ========== 性能优化：使用向量化方法替代逐行apply ==========
            # 原代码：self.df[col] = self.df[col].apply(self.value_trans)
            # 将每个金额列数据类型都替换为字符串,先将字符串中的空格都替换为空,再将字符串中的非数字小数点负号替换为空,或者以负号结尾的数据替换为空
            self.df[col] = self.value_trans_vectorized(self.df[col])
            # ========== 性能优化结束 ==========
            temp_cnt = self.df[self.df[col] != 0].shape[0]
            if self.INCOME_PAT.search(col1) and self.OUTCOME_PAT.search(col1):
                if temp_cnt - self.df.shape[0] * 0.5 > 0 and temp_cnt > amt_cnt:
                    col_map['amt_index'], amt_cnt = index, temp_cnt
                elif temp_cnt > tbd_cnt:
                    col_map['tbd_index'], tbd_cnt = index, temp_cnt
            elif self.INCOME_PAT.search(col1) and temp_cnt > income_cnt:
                col_map['income_index'], income_cnt = index, temp_cnt
            elif self.OUTCOME_PAT.search(col1) and temp_cnt > outcome_cnt:
                col_map['outcome_index'], outcome_cnt = index, temp_cnt
            elif temp_cnt > amt_cnt:
                col_map['amt_index'], amt_cnt = index, temp_cnt
        if 'amt_index' in col_map:
            self.amt_col = [self.amt_col[col_map['amt_index']]]
        elif 'income_index' in col_map and 'outcome_index' in col_map:
            self.amt_col = [self.amt_col[col_map['income_index']], self.amt_col[col_map['outcome_index']]]
        elif 'income_index' in col_map and 'outcome_index' not in col_map and 'tbd_index' in col_map:
            self.amt_col = [self.amt_col[col_map['income_index']], self.amt_col[col_map['tbd_index']]]
        elif 'income_index' not in col_map and 'outcome_index' in col_map and 'tbd_index' in col_map:
            self.amt_col = [self.amt_col[col_map['tbd_index']], self.amt_col[col_map['out_come_index']]]
        elif 'income_index' in col_map and 'outcome_index' not in col_map and income_cnt - self.df.shape[0] * 0.5 > 0:
            self.amt_col = [self.amt_col[col_map['income_index']]]
        elif 'income_index' not in col_map and 'outcome_index' in col_map and outcome_cnt - self.df.shape[0] * 0.5 > 0:
            self.amt_col = [self.amt_col[col_map['outcome_index']]]
        else:
            raise ValueError("缺失交易金额列或进账金额列或出账金额列")
        return

    def _one_col_match(self, col: str, col_name='trans_amt'):
        """
        将对应的金额列转化为标准浮点型数据
        :param col: 需要转化的列名
        :param col_name: 转化后的列名
        :return:
        """
        if not self.tag:
            self.df['tag'] = -1 if self.OUTCOME_PAT.search(col) and not self.INCOME_PAT.search(col) else 1
        if self.df[self.df['tag'] == -1][col].sum() < 0:
            self.df['tag'] = 1
        # ========== 性能优化：使用向量化方法 ==========
        # 原代码：self.df[col_name] = self.df.apply(lambda x: self.value_trans(x[col]) * x['tag'], axis=1)
        self.df[col_name] = self.value_trans_vectorized(self.df[col]) * self.df['tag']
        # ========== 性能优化结束 ==========
        self.df = self.df[self.df[col_name] != 0]
        return

    def _multi_col_match(self):
        """
        交易金额列存在多列时的处理
        :return:
        """
        # ========== 性能优化：使用向量化方法批量处理 ==========
        # 原代码：for col in self.amt_col: self.df[col] = self.df[col].apply(self.value_trans)
        for col in self.amt_col:
            self.df[col] = self.value_trans_vectorized(self.df[col])
        # ========== 性能优化结束 ==========
        length = len(self.amt_col)
        if length == 1:
            if self.tag:
                if self.df.loc[self.df['tag'] == -1][self.amt_col[0]].sum() < 0:
                    self.df['trans_amt'] = self.df[self.amt_col[0]]
                else:
                    self.df['trans_amt'] = self.df['tag']*self.df[self.amt_col[0]]
            else:
                self.df['trans_amt'] = self.df[self.amt_col[0]]
        elif length == 2:
            if self.tag:
                self.df['trans_amt'] = self.df[self.amt_col[0]] + self.df[self.amt_col[1]]
                if self.df.loc[self.df['tag'] == -1]['trans_amt'].sum() >= 0:
                    self.df['trans_amt'] = self.df['tag'] * self.df['trans_amt']
            else:
                neg = self.df[self.amt_col[1]].sum()
                multi = 1 if neg < 0 else -1
                self.df['trans_amt'] = self.df[self.amt_col[0]] + multi * self.df[self.amt_col[1]]
        self.df = self.df[self.df['trans_amt'] != 0]
        return

    def execute(self):
        self.df = self.trans_data
        self._trans_use()  # 提前清洗交易用途列，提供给微信流水使用
        self.amt_col = self.col_mapping()['amt_col']
        self.tag = self._find_tag_col()
        self._remove_amt_col()
        length = len(self.amt_col)
        try:
            if length == 1:
                self._one_col_match(self.amt_col[0])
            else:
                self._multi_col_match()
            self.trans_data = self.df
            if self.df.shape[0] == 0:
                self.mark_err("解析失败：未找到交易金额列")
            elif self.df[(self.df['trans_amt'] > 1e8) | (self.df['trans_amt'] < -1e8)].shape[0] > 0:
                self.mark_err("流水中出现超限交易金额，请联系管理员解决")
        except ValueError as e:
            self.mark_err("解析失败：" + str(e))
