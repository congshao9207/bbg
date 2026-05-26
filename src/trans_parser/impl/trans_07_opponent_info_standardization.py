
import re

from trans_parser.task_base_executor import TaskBaseExecutor


class TransOpponentInfoStandardization(TaskBaseExecutor):
    """
    将流水文件中所有交易对手相关信息(交易对手姓名,交易对手账号,交易对手开户行)标准化
    author:汪腾飞
    created_time:20200630
    updated_time_v1:20200818,去除所有列中无意义字符
    updated_time_v2:20201125,去除所有列中的引号
    """

    def __init__(self):
        super().__init__()
        self.df = None

    def execute(self):
        self.df = self.trans_data
        self._opinfo_match('opname_col', 'opponent_name')
        self._opinfo_match('opacc_col', 'opponent_account_no')
        self._opinfo_match('opbank_col', 'opponent_account_bank')

    def _remove_opinfo_col(self, opponent_info):
        """
        去除交易对手列中不符合规范的列
        :return:
        """
        print(self.col_mapping())
        string = ''.join([str(_) for _ in self.col_mapping()[opponent_info]])
        print(string)
        # 删除其中非空唯一值数量低于4的列
        for index in range(-len(self.col_mapping()[opponent_info]), 0):
            col = self.col_mapping()[opponent_info][index]
            if self.df[col].nunique() < 4:
                self.col_mapping()[opponent_info].remove(col)
        # 存在"收付方/收(付)方/对方/对手"等字段直接定义为交易对手列
        if re.search(r"(收.?付|对方|对手)", string):
            for col in self.col_mapping()[opponent_info]:
                if re.search(r"(收.?付|对方|对手)", col):
                    self.col_mapping()[opponent_info] = [col]
                    return
        # 若交易对手列大于2,且存在对立两列,则将对立两列挑出来,并将付款方放在第一位
        if len(self.col_mapping()[opponent_info]) >= 2:
            if re.search(r'(收.*[付发]|[付发].*收)', string):
                for index in range(-len(self.col_mapping()[opponent_info]), 0):
                    col = self.col_mapping()[opponent_info][index]
                    if (not (re.search(r'收', col) or re.search(r'[付发]', col))) or re.search(r'名义', col):
                        self.col_mapping()[opponent_info].remove(col)
                # 将付款人放在列表第一位,收款人放在第二位
                if re.search(r'收', self.col_mapping()[opponent_info][0]):
                    self.col_mapping()[opponent_info].reverse()
            else:
                for index in range(-len(self.col_mapping()[opponent_info]), 0):
                    col = self.col_mapping()[opponent_info][index]
                    if re.search(r'(名义|子)', col):
                        self.col_mapping()[opponent_info].remove(col)
        return

    def _opinfo_match(self, opponent_info, col_name):
        print(col_name)
        self._remove_opinfo_col(opponent_info)
        length = len(self.col_mapping()[opponent_info])
        comp = re.compile(r'[\\\"\'＇\s^-]')
        self.df[self.col_mapping()[opponent_info]] = self.df[self.col_mapping()[opponent_info]].fillna('').astype(str)
        if length == 1:
            self.df[col_name] = self.df[self.col_mapping()[opponent_info][0]].apply(lambda x: re.sub(comp, '', x))
        elif length == 2:
            neg = self.col_mapping()[opponent_info][0]
            pos = self.col_mapping()[opponent_info][1]
            for i in self.df.index:
                if self.df.loc[i, 'trans_amt'] > 0:
                    self.df.loc[i, col_name] = re.sub(comp, '', self.df.loc[i, neg])
                else:
                    self.df.loc[i, col_name] = re.sub(comp, '', self.df.loc[i, pos])
        elif length > 3:
            self.df[col_name] = self.df[self.col_mapping()[opponent_info][0]].apply(lambda x: re.sub(comp, '', x))
        else:
            self.df[col_name] = ''
        return
