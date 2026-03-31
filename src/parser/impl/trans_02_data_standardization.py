import re

import pandas as pd

from src.config.trans_config import DTTIME_PATTERN, DATE_PATTERN, AMT_PATTERN, IGNORE_PATTERN, \
    INCOME_PATTERN, OUTCOME_PATTERN, SHORT_DATE_PATTERN
from src.parser.task_base_executor import TaskBaseExecutor


class TransDataStandardization(TaskBaseExecutor):
    """
    流水数据标准化
    将流水数据中与标题行相同的数据删除,将流水数据中头部和尾部不符合规范的数据删除
    1.现在会将整行只有<=3个非空单元格的行删除，而不是整行为空的才删除，这样可以直接删除掉存在统计信息的行，同时也可以将多行标题的第二行删除
    2.现在会正确删除掉所有与标题行完全一致的行，不会再造成有标题行没有删掉而存在时间列存在空值的情况
    """

    def __init__(self):
        super().__init__()
        self.title_status = False

    def _title_standard(self):
        """
        若标题行存在两行,将标题行标准化,并将标题状态替换为True,表示标题行发生过替换
        :return:
        """
        df = self.trans_data
        col_list = list(df.columns)
        for col_index in range(len(col_list)):
            target_col_index = col_index + 1
            if '发生额' == col_list[col_index] or '发生额元' == col_list[col_index]:
                c1 = str(df.iloc[0, col_index]).strip()
                # c2 = str(df.iloc[0, col_index + 1]).strip()
                # 安全检查：确保索引在有效范围内 (0 到 total_cols-1)
                if target_col_index <= len(col_list) - 1:
                    c2 = str(df.iloc[0, target_col_index]).strip()
                else:
                    # 如果索引越界，给 c2 一个默认值（如空字符串）或处理异常逻辑
                    c2 = ""
                if (re.search(OUTCOME_PATTERN, c1) and re.search(INCOME_PATTERN, c2)) or \
                        (re.search(OUTCOME_PATTERN, c2) and re.search(INCOME_PATTERN, c1)):
                    df.rename(columns={col_list[col_index]: c1, col_list[col_index+1]: c2}, inplace=True)
                    self.title_status = True
                    df.drop(0, axis=0, inplace=True)
                break
        df.dropna(axis=0, inplace=True, thresh=3)

        def merge(l1, l2):
            i, j = 0, 0
            res, inv = [], 0
            length1, length2 = len(l1), len(l2)
            while i < length1 and j < length2:
                if l1[i] <= l2[j]:
                    res.append(l1[i])
                    i += 1
                else:
                    res.append(l2[j])
                    j += 1
                    inv += length1 - i
            if i < len(l1):
                res.extend(l1[i:])
            else:
                res.extend(l2[j:])
            return res, inv

        def inversions(l: list):
            if len(l) <= 1:
                return l, 0
            elif len(l) == 2:
                return [min(l), max(l)], 0 if l[0] <= l[1] else 1
            mid = len(l) // 2
            left, a = inversions(l[:mid])
            right, b = inversions(l[mid:])
            r, inv = merge(left, right)
            return r, inv + a + b

        # 若存在交易序号列或序号列，先根据交易序号进行排序
        if '交易序号' in col_list or '序号' in col_list:
            num_col = '交易序号' if '交易序号' in col_list else '序号'
            df['交易序号'] = df[num_col].apply(lambda x: int(str(x).strip()) if str(x).strip().isnumeric() else None)
            df['交易序号'].fillna(method='ffill', inplace=True)
            df.sort_values(by='交易序号', ascending=True, inplace=True)
            # 计算逆序数比例
            inverse_list, inverse = inversions(list(df.index))
            inverse_ratio = 2 * inverse / (len(inverse_list) * (len(inverse_list) - 1)) if len(inverse_list) > 1 else 0
            if 0.1 < inverse_ratio < 0.9:
                df.sort_index(inplace=True)
        df.reset_index(drop=True, inplace=True)
        self.trans_data = df

    def _remove_invalid_row(self):
        df = self.trans_data
        tail_cnt = 0
        remove_list = []
        for tail in range(len(df) - 1, -1, -1):
            if self._entire_row_values_match(df.loc[tail, :]):
                if tail_cnt == 0:
                    tail_cnt += 1
                    remove_list.append(tail)
                    continue
                else:
                    break
            else:
                remove_list.append(tail)
                df.drop(remove_list, axis=0, inplace=True)
                remove_list = []
                tail_cnt = 0
        for head in df.index:
            if self._entire_row_values_match(df.loc[head, :]):
                break
            else:
                df.drop(head, axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)
        self.trans_data = df

    def _remove_title_row(self):
        col = self.trans_data.columns
        col = [x for x in col if 'Unnamed' not in x]
        remove_list = []
        # next_row = False
        for index in self.trans_data.index:
            row = self.trans_data.loc[index, :]
            # if next_row:
            #     next_row = False
            #     continue
            value = row.values
            value = [y for y in value if pd.notna(y)]
            if value == col:
                remove_list.append(index)
                # if self.title_status:
                #     remove_list.append(index + 1)
                #     next_row = True
        self.trans_data.drop(remove_list, axis=0, inplace=True)

    @staticmethod
    def _entire_row_values_match(value):
        dttime_pat = re.compile(DTTIME_PATTERN)
        date_pat = re.compile(DATE_PATTERN)
        short_pat = re.compile(SHORT_DATE_PATTERN)
        amt_pat = re.compile(AMT_PATTERN)
        sum_pat = re.compile(IGNORE_PATTERN)
        # 时间格式计数,累计到1停止,即至少需要包含一列交易时间
        time_cnt = 0
        # 金额格式计数,累计到2停止,即至少需要包含一列交易金额和一列余额
        amt_cnt = 0
        for val in value:
            temp = str(val)
            # 将该单元格值转换成字符串,取其中是数字的字符连接起来
            string = ''.join([_ for _ in temp if _.isdigit()])
            # 若原始单元格值中包含忽略格式中的字符,则该列不符合要求,返回False
            if re.match(sum_pat, temp):
                return False
            # 若时间格式单元格个数不到1,则需要判断该单元格是否是时间格式,判断通过则直接进行下一个单元格的判断(防止某单元格同时满足时间和金额)
            if time_cnt != 1:
                if re.match(dttime_pat, string) or re.match(date_pat, string) or re.match(short_pat, string):
                    time_cnt += 1
                    continue
            # 若金额格式单元格个数不到2,则需要判断该单元格是否是金额格式
            if amt_cnt != 2:
                if re.match(amt_pat, string):
                    amt_cnt += 1
            # 若已经找到一个时间格式,两个金额格式则返回True
            if time_cnt == 1 and amt_cnt == 2:
                return True
        # 遍历完都没有找到不少于一个的时间格式,和不少于两个的金额格式则返回False
        if time_cnt == 1 and amt_cnt == 2:
            return True
        return False

    def execute(self):
        self._title_standard()
        if self.parse_context.parse_task.trans_flow_src_type in [1, '1']:
            self._remove_invalid_row()
            self._remove_title_row()
