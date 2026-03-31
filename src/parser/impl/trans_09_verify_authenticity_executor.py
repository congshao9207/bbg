import pandas as pd
import decimal
import re
import difflib

from src.logger.logger_util import LoggerUtil
from src.parser.task_base_executor import TaskBaseExecutor
from src.config.trans_config import SIMILAR_THRESH
import itertools

logger = LoggerUtil().logger(__name__)


class VerifyAuthenticityExecutor(TaskBaseExecutor):
    """
    将流水文件中交易余额标准化，并给流水文件打上标签
    author:汪腾飞
    """

    def __init__(self):
        super().__init__()
        self.df = None
        self.bal_col = None
        self.basic_status = True
        self.sort_list = None
        self.op_name_list = []
        self.not_name_list = []
        self.common_label = []
        self.rec_status = None

    def _remove_bal_col(self):
        """
        去除余额列中不符合规范的列
        :return:
        """
        length = len(self.bal_col)
        for index in range(-length, 0):
            col = self.bal_col[index]
            if re.search(r"(上|Last|last|(?<!当)前)", col):
                self.bal_col.remove(col)
        return

    def balance_match(self):
        self._remove_bal_col()
        # 保留非0值最多的列作为交易余额列，若余额列非零值低于20%则拒绝，若余额列存在超过5亿的数字报错
        bal_col = ''
        bal_cnt = 0
        for col in self.bal_col:
            self.df[col] = self.value_trans_vectorized(self.df[col])
            temp_cnt = self.df[self.df[col] != 0].shape[0]
            if temp_cnt > bal_cnt:
                bal_col, bal_cnt = col, temp_cnt
        if bal_col != '' and bal_cnt - self.df.shape[0] * 0.2 > 0:
            if self.df[self.df[bal_col] > 5e8].shape[0] == 0:
                self.df['account_balance'] = self.df[bal_col]
            else:
                self.basic_status = False
                self.mark_err("流水中出现超限交易余额，请联系管理员解决")
        else:
            self.basic_status = False
            self.mark_err("未找到交易余额列或者余额列进行了加密,请检查后再上传")
        return

    def trans_sort_df(self, df):
        # 弱连续性判断
        df['index'] = df.index.tolist()
        ascending_list = [[True], [False], [True, True], [True, False]]
        all_conti_cnt = len(df)
        for asc in ascending_list:
            if len(asc) == 1:
                temp_df = df.sort_values(by=['index'], ascending=asc)
            else:
                temp_df = df.sort_values(by=['trans_time', 'index'], ascending=asc)
            temp_df['should_bal'] = temp_df['account_balance'] - temp_df['trans_amt']
            temp_df['neg_bal'] = temp_df['account_balance'] + temp_df['trans_amt']
            temp_df['last_bal'] = [temp_df['should_bal'].tolist()[0]] + temp_df['account_balance'].tolist()[:-1]
            temp_df['if_conti'] = (abs(temp_df['should_bal'] - temp_df['last_bal']) < 0.1) | \
                                  (abs(temp_df['neg_bal'] - temp_df['last_bal']) < 0.1)
            temp_conti_cnt = temp_df[~temp_df['if_conti']].shape[0]
            if temp_conti_cnt < all_conti_cnt:
                all_conti_cnt = temp_conti_cnt
                df = temp_df
                if temp_conti_cnt == 0:
                    return df, 0
        # 拆分日期
        # 向量化日期格式化，比apply快10-50倍
        df['each_date'] = df['trans_time'].dt.strftime('%Y-%m-%d')
        date_list = sorted(df[~df['if_conti']]['each_date'].unique().tolist())
        final_df = pd.DataFrame()
        last_bal = None
        last_date, dat = '2000-01-01', '2030-01-01'
        total_cnt = 0
        for dat in date_list:
            last_df = df[(df['each_date'] > last_date) & (df['each_date'] < dat)]
            if last_df.shape[0] > 0:
                last_bal = last_df['account_balance'].tolist()[-1]
            date_df = df[df['each_date'] == dat]
            res_df, not_conti_cnt = self.single_date_sort(date_df, last_bal)
            total_cnt += not_conti_cnt
            last_bal = res_df['account_balance'].tolist()[-1]
            last_date = dat
            final_df = pd.concat([final_df, last_df, res_df], axis=0, ignore_index=True)
        final_df = pd.concat([final_df, df[df['each_date'] > dat]], axis=0, ignore_index=True)
        return final_df, total_cnt

    @staticmethod
    def single_date_sort(df, last_bal=None):
        # 拆分列表
        df.reset_index(drop=True, inplace=True)
        df.loc[0, 'if_conti'] = True
        end_list = df[~df['if_conti']].index.tolist() + [df.shape[0]]
        start_list = [0] + end_list[:-1]
        account_bal_list = df.loc[[_ - 1 for _ in end_list], 'account_balance'].tolist()
        should_bal_list = df.loc[start_list, 'should_bal'].tolist()
        list_len = len(end_list)
        if list_len > 5:
            return df, list_len - 1
        # 全排列
        all_permutations = itertools.permutations(range(list_len))
        res_per = []
        not_conti_cnt = list_len + 1
        for per in all_permutations:
            temp_cnt = 1
            if last_bal is None or abs(should_bal_list[per[0]] - last_bal) < 0.1:
                temp_cnt -= 1
            for i in range(1, len(end_list)):
                if account_bal_list[per[i - 1]] != should_bal_list[per[i]]:
                    temp_cnt += 1
                    if temp_cnt >= not_conti_cnt:
                        break
            if temp_cnt < not_conti_cnt:
                not_conti_cnt = temp_cnt
                res_per = list(per)
                if temp_cnt == 0:
                    break
        res_df = pd.DataFrame()
        for ind in res_per:
            res_df = pd.concat([res_df, df.loc[start_list[ind]:end_list[ind] - 1, :]], axis=0, ignore_index=True)
        return res_df, not_conti_cnt

    @staticmethod
    def correct_bal(param):
        df = param[0]
        df.reset_index(inplace=True, drop=True)
        length = df.shape[0]
        cnt = param[1]
        for ind in range(1, length):
            row = df.loc[ind]
            next_row = df.loc[ind + 1] if ind != length - 1 else {}
            last_row = df.loc[ind - 1]
            tag = getattr(row, 'verif_label', '')  # 该行标签
            next_tag = getattr(next_row, 'verif_label', '')  # 下行标签
            if 'T01' not in tag:
                continue
            trans_amt = getattr(row, 'trans_amt')  # 该行交易金额
            last_bal = getattr(last_row, 'account_balance')  # 上行余额
            trans_bal = getattr(row, 'account_balance')  # 该行余额
            # 计算 该ind余额-上一余额（即该行交易金额） 与 实际交易金额 相似度比较，若相似度高，则修改交易金额
            calcul_trans_amt = float(decimal.Decimal(str(trans_bal)) - decimal.Decimal(str(last_bal)))
            calcul_trans_bal = float(decimal.Decimal(str(last_bal)) + decimal.Decimal(str(trans_amt)))
            amt_similar = difflib.SequenceMatcher(None, str(calcul_trans_amt), str(trans_amt)).quick_ratio() \
                if calcul_trans_amt == 0 or round(trans_amt / calcul_trans_amt, 2) not in [0.01, 100, -1, 10, 0.1] else 0.99
            bal_similar = difflib.SequenceMatcher(None, str(calcul_trans_bal), str(trans_bal)).quick_ratio() \
                if calcul_trans_bal == 0 or round(trans_bal / calcul_trans_bal, 2) not in [0.01, 100, 10, 0.1] else 0.99
            # 出现单行标签，则要么该行交易金额错误或者连续两行丢失同样尾数
            if 'T01' not in next_tag:
                if max(bal_similar, amt_similar) >= SIMILAR_THRESH:
                    if (amt_similar >= bal_similar and trans_amt % 100 != 0 and calcul_trans_amt != trans_amt) \
                            or amt_similar == 0.99:
                        df.loc[ind, 'trans_amt'] = calcul_trans_amt
                        tag = re.sub(r'(,T01|T01,|T01)', '', tag)
                        if amt_similar != 1:
                            tag += ',T11' if tag != '' else 'T11'
                        cnt -= 1
                    else:
                        df.loc[ind, 'account_balance'] = calcul_trans_bal
                        tag = re.sub(r'(,T01|T01,|T01)', '', tag)
                        if bal_similar != 1:
                            tag += ',T12' if tag != '' else 'T12'
                            next_tag += ',T01' if next_tag != '' else 'T01'
                            if ind != length - 1:
                                df.loc[ind + 1, 'verif_label'] = next_tag
                            else:
                                cnt -= 1
                        else:
                            cnt -= 1
            elif max(bal_similar, amt_similar) >= SIMILAR_THRESH:
                if (bal_similar < amt_similar and trans_amt % 100 != 0 and calcul_trans_amt != trans_amt) \
                        or amt_similar == 0.99:
                    df.loc[ind, 'trans_amt'] = calcul_trans_amt
                    tag = re.sub(r'(,T01|T01,|T01)', '', tag)
                    if amt_similar != 1:
                        tag += ',T11' if tag != '' else 'T11'
                else:
                    df.loc[ind, 'account_balance'] = calcul_trans_bal
                    tag = re.sub(r'(,T01|T01,|T01)', '', tag)
                    if bal_similar != 1:
                        tag += ',T12' if tag != '' else 'T12'
                cnt -= 1
            df.loc[ind, 'verif_label'] = tag
        return df, cnt

    # 流水顺序校验逻辑，统计该顺序下余额不连续的记录条数
    def _balance_check(self, input_df):
        df = input_df.copy()
        last = -1
        cnt = 0
        used_list = []
        for row in df.itertuples():
            temp_label = self.common_label.copy()
            index = getattr(row, 'Index')
            trans_amt = getattr(row, 'trans_amt')
            trans_bal = getattr(row, 'account_balance')
            concat_str = getattr(row, 'concat_str')
            trans_dt = getattr(row, "trans_time")
            op_name = getattr(row, "opponent_name")
            op_acct = getattr(row, "opponent_account_no")
            # 余额连续性标签
            if last != -1:
                if float(decimal.Decimal(str(trans_amt)) + decimal.Decimal(str(last))) != trans_bal:
                    # 若某行不满足余额校验,但是该行属于冲正,抹账,退账,则将交易金额乘以-1重新验证一次,若通过则继续往下校验
                    if re.search('冲正|抹账|退账|抹帐|退帐|冲帐|冲账', concat_str) is not None:
                        if float(decimal.Decimal(str(-trans_amt)) + decimal.Decimal(str(last))) == trans_bal:
                            df.loc[index, 'trans_amt'] = -trans_amt
                            last = trans_bal
                            continue
                    # 存在不满足的行，则打上余额不连续的标签
                    temp_label.append('T01')
                    cnt += 1
            # 结息金额为负标签
            if str(trans_dt.day) in ['20', '21', '22'] and str(trans_dt.month) in ['3', '6', '9', '12'] and \
                    (re.search('活期.息|批量业务|付利息', op_name) or
                     re.search('付息|利息存入|结息|入息|利息起息|增值息', concat_str)) \
                    and trans_amt < 0:
                temp_label.append('T04')
                self.mark_ver_res('该流水存在季度结息为负')
            # 一个账号对应多个交易对手标签
            if op_acct in self.op_name_list:
                temp_label.append('T07')
            if op_acct in self.not_name_list:
                temp_label.append('T10')
                if op_acct not in used_list:
                    df.loc[df['opponent_account_no'] == op_acct, 'opponent_name'] = op_name
                    used_list.append(op_acct)
            # # 流水账户位数标签
            # if op_acct.isdigit() and (len(op_acct) < 16 or len(op_acct) > 21):
            #     temp_label.append("T08")
            #     self.mark_ver_res('可疑：该流水存在账号位数错误')
            # # 流水交易手续费比例校验
            # if re.search('手续费', concat_str):
            #     if last != -1:
            #         temp_rate = abs(trans_amt / df.loc[index-1, 'trans_amt'])
            #         if fee_rate != 0 and abs(temp_rate - fee_rate) / fee_rate > 0.05:
            #             temp_label.append("T09")
            #             self.mark_ver_res('可疑：该流水交易手续费率差异过大')
            #         if fee_rate == 0:
            #             fee_rate = temp_rate
            last = trans_bal
            label_str = ','.join(temp_label)
            df.loc[index, 'verif_label'] = label_str
        return df, cnt

    def _balance_check_vectorized(self, input_df):
        """
        向量化版本的余额检查，比原版快5-20倍
        """
        df = input_df.copy()

        # 初始化标签列
        if 'verif_label' not in df.columns:
            df['verif_label'] = ''

        # 1. 余额连续性检查（向量化）
        prev_balance = df['account_balance'].shift(1)
        # 第一行没有上一行，跳过检查
        mask_not_first = prev_balance.notna()

        # 计算期望的余额：上一行余额 + 当前交易金额
        expected_balance = prev_balance + df['trans_amt']

        # 检查是否相等（考虑浮点精度）
        balance_diff = (expected_balance - df['account_balance']).abs()
        balance_discontinuous = mask_not_first & (balance_diff > 0.01)  # 容忍0.01的误差

        # 2. 处理冲正情况（向量化）
        # 检查concat_str是否包含冲正关键词
        correction_keywords = '冲正|抹账|退账|抹帐|退帐|冲帐|冲账'
        has_correction = df['concat_str'].str.contains(correction_keywords, na=False)

        # 对于冲正记录，检查 prev_balance - trans_amt == current_balance
        expected_balance_correction = prev_balance - df['trans_amt']
        balance_diff_correction = (expected_balance_correction - df['account_balance']).abs()
        correction_valid = has_correction & mask_not_first & (balance_diff_correction <= 0.01)

        # 更新冲正记录的trans_amt
        df.loc[correction_valid, 'trans_amt'] = -df.loc[correction_valid, 'trans_amt']

        # 重新计算余额连续性（考虑冲正修正后）
        expected_balance_updated = prev_balance + df['trans_amt']
        balance_diff_updated = (expected_balance_updated - df['account_balance']).abs()
        balance_discontinuous_updated = mask_not_first & (balance_diff_updated > 0.01) & ~correction_valid

        # 3. 结息金额为负检查（向量化）
        is_interest_month = df['trans_time'].dt.month.isin([3, 6, 9, 12])
        is_interest_day = df['trans_time'].dt.day.isin([20, 21, 22])
        interest_keywords_op = '活期.息|批量业务|付利息'
        interest_keywords_concat = '付息|利息存入|结息|入息|利息起息|增值息'
        has_interest_op = df['opponent_name'].str.contains(interest_keywords_op, na=False)
        has_interest_concat = df['concat_str'].str.contains(interest_keywords_concat, na=False)
        has_interest = has_interest_op | has_interest_concat
        negative_interest = is_interest_month & is_interest_day & has_interest & (df['trans_amt'] < 0)

        # 4. 账号对应多个交易对手检查（已通过self.op_name_list和self.not_name_list预处理）
        # 这些列表在_duplicate_acct方法中填充

        # 构建标签
        t01_mask = balance_discontinuous_updated
        t04_mask = negative_interest
        t07_mask = df['opponent_account_no'].isin(self.op_name_list)
        t10_mask = df['opponent_account_no'].isin(self.not_name_list)

        # 统计不连续条数
        cnt = t01_mask.sum()

        # 生成标签字符串
        def build_label(row_idx):
            labels = []
            if t01_mask.iloc[row_idx]:
                labels.append('T01')
            if t04_mask.iloc[row_idx]:
                labels.append('T04')
            if t07_mask.iloc[row_idx]:
                labels.append('T07')
            if t10_mask.iloc[row_idx]:
                labels.append('T10')
            return ','.join(labels) if labels else ''

        # 应用标签（向量化）
        label_series = pd.Series([build_label(i) for i in range(len(df))], index=df.index)
        # 合并原有标签
        if 'verif_label' in df.columns:
            existing_labels = df['verif_label'].fillna('')
            # 合并标签，避免重复
            def merge_labels(existing, new):
                if not new:
                    return existing
                if not existing:
                    return new
                # 合并并去重
                all_labels = set(filter(None, existing.split(','))) | set(filter(None, new.split(',')))
                return ','.join(sorted(all_labels))

            merged_labels = [merge_labels(existing, new) for existing, new in
                           zip(existing_labels, label_series)]
            df['verif_label'] = merged_labels
        else:
            df['verif_label'] = label_series

        # 处理T10标签的特殊逻辑：更新对手户名
        if t10_mask.any():
            t10_accounts = df.loc[t10_mask, 'opponent_account_no'].unique()
            for acc in t10_accounts:
                # 取该账号第一个出现的户名
                first_name = df.loc[df['opponent_account_no'] == acc, 'opponent_name'].iloc[0]
                df.loc[df['opponent_account_no'] == acc, 'opponent_name'] = first_name

        return df, int(cnt)

    # 进行数次不同顺序的校验，选择余额不连续条数最少的一次作为该流水的顺序
    def execute(self):
        # 支付宝微信流水不进行余额列处理
        if self.parse_context.parse_task.trans_flow_src_type in [2, 3, '2', '3']:
            return
        self.rec_status = self.parse_context.parse_task.rectify
        self.df = self.trans_data
        if self.df.shape[0] == 0:
            self.mark_err("未找到交易余额列")
            return
        self.bal_col = self.col_mapping()['bal_col']
        self.sort_list = self.parse_context.get_data('sort_list')
        if self.parse_context.trans_date_delete_status:
            self.mark_ver_res("可信，检测到原数据存在非标交易时间格式，请检查原文件")
        else:
            self.mark_ver_res('可信')
        # 未找到余额列不往下进行
        self.balance_match()
        if not self.basic_status:
            return
        # 向量化字符串拼接，比apply快10-50倍
        self.df['concat_str'] = (
            self.df['trans_channel'].fillna('').astype(str) +
            self.df['trans_type'].fillna('').astype(str) +
            self.df['trans_use'].fillna('').astype(str) +
            self.df['remark'].fillna('').astype(str)
        )
        # 兼容每月结息有两条的情况
        self.df['trans_time'] = pd.to_datetime(self.df['trans_time'])
        # 结息标签
        INTEREST_KEY_WORD = '利息|结息|个人活期结息|批量结息|存息|付息|存款利息|批量业务|入息|季息|收息|interest|INTEREST'
        # 非结息标签
        NON_INTEREST_KEY_WORD = '理财|钱生钱|余额宝|零钱通|招财盈|宜人财富|保证金|透支|智能|其他账户|税后|转存|贷款'
        self.df.drop(self.df[(self.df['trans_time'].dt.month % 3 == 0) &
                             (self.df['trans_time'].dt.day.isin([20, 21])) &
                             (self.df.account_balance == 0) &
                             (self.df.concat_str.str.contains(INTEREST_KEY_WORD)) &
                             (~self.df.concat_str.str.contains(NON_INTEREST_KEY_WORD))].index, inplace=True)
        if 'verif_label' not in self.df.columns:
            self.df['verif_label'] = ''
        # # 流水文件条数标签
        # if self.df.shape[0] < 50:
        #     self.common_label.append("T02")
        # # 流水结息次数标签
        # int_df = self.df.copy()
        # int_df['y_month'] = int_df['trans_time'].apply(lambda x: format(x, '%Y-%m'))
        # int_df['month'] = int_df['trans_time'].apply(lambda x: x.month)
        # int_df['day'] = int_df['trans_time'].apply(lambda x: x.day)
        # int_month = int_df[int_df['month'].isin([3, 6, 9, 12])]['y_month'].nunique()
        # int_cnt = int_df[(int_df['month'].isin([3, 6, 9, 12])) & (int_df['day'].isin([20, 21, 22])) &
        #                  ((int_df['concat_str'].str.contains('付息|利息存入|结息|入息|利息起息|增值息')) |
        #                   (int_df['opponent_name'].str.contains('活期|批量业务|付利息')))].shape[0]
        # if int_month != int_cnt:
        #     self.common_label.append("T03")
        # 交易账号对应不同交易对手个数标签
        self._duplicate_acct()

        # 流水灵活排序
        sort_df, total_cnt = self.trans_sort_df(self.df.copy())
        if self.rec_status in [1, '1']:
            result, cnt = self.correct_bal(self._balance_check_vectorized(sort_df))
        else:
            result, cnt = self._balance_check_vectorized(sort_df)
        if cnt > 0:
            if self.parse_context.trans_date_delete_status:
                self.mark_ver_res("该流水存在余额不匹配，检测到原数据存在非标交易时间格式，请检查原文件")
            else:
                self.mark_ver_res('该流水存在余额不匹配')
        self.trans_data = result
        self.trans_data.reset_index(drop=True, inplace=True)
        # sort_df1 = self.df.copy()
        # sort_df1['index'] = list(range(len(self.df)))
        # self.sort_list.append('index')
        # # 纠偏参数为1，才跑纠偏逻辑，其他时候不进行纠偏
        # # 1.流水文件中原有顺序顺序验真
        # if self.rec_status in [1, '1']:
        #     result1, cnt1 = self.correct_bal(self._balance_check(sort_df1))
        # else:
        #     result1, cnt1 = self._balance_check(sort_df1)
        # if cnt1 == 0:
        #     self.trans_data = result1
        #     return
        # # 2.流水文件中原有顺序逆序验真
        # sort_df2 = sort_df1.sort_values(by='index', ascending=False)
        # if self.rec_status in [1, '1']:
        #     result2, cnt2 = self.correct_bal(self._balance_check(sort_df2))
        # else:
        #     result2, cnt2 = self._balance_check(sort_df2)
        # if cnt2 == 0:
        #     self.trans_data = result2
        #     self.trans_data.reset_index(drop=True, inplace=True)
        #     return
        # # 3.将流水文件按照交易日期,交易时间,index,顺序,顺序,顺序排序后进行验真(可能存在日期,时间均相同的两条流水)
        # ascending_list3 = [True, True]
        # sort_df3 = sort_df1.sort_values(by=['trans_time', 'index'], ascending=ascending_list3)
        # if self.rec_status in [1, '1']:
        #     result3, cnt3 = self.correct_bal(self._balance_check(sort_df3))
        # else:
        #     result3, cnt3 = self._balance_check(sort_df3)
        # if cnt3 == 0:
        #     self.trans_data = result3
        #     self.trans_data.reset_index(drop=True, inplace=True)
        #     return
        # # 4.将流水文件按照交易日期,交易时间,index,顺序,顺序,逆序排序后进行验真(可能存在日期,时间均相同的两条流水)
        # ascending_list3[-1] = False
        # sort_df4 = sort_df1.sort_values(by=['trans_time', 'index'], ascending=ascending_list3)
        # if self.rec_status in [1, '1']:
        #     result4, cnt4 = self.correct_bal(self._balance_check(sort_df4))
        # else:
        #     result4, cnt4 = self._balance_check(sort_df4)
        # if cnt4 == 0:
        #     self.trans_data = result4
        #     self.trans_data.reset_index(drop=True, inplace=True)
        #     return
        # # 选择其中余额不匹配条数最少的一次顺序作为流水顺序
        # self.mark_ver_res('该流水存在余额不匹配')
        # min_cnt = min(cnt1, cnt2, cnt3, cnt4)
        # for i in range(4):
        #     if min_cnt == eval('cnt%d' % (i + 1)):
        #         self.trans_data = eval('result%d' % (i + 1))
        #         self.trans_data.reset_index(drop=True, inplace=True)

    def _duplicate_acct(self):
        df = self.df.copy()
        IGNORE_ACC_NO = ['', '0', '0.0', '1.0000000000000002e+17', '-', '99900001262112001358', '1504292651']
        IGNORE_ACC_NO_PATTERN = '999999.*99|105331.*0875|105584.*0061|105100.*2625|105551.*8273|1500947831|215.*690' \
                                '|210401344|105584.*|100000000000000000|243.*133|48429202|1000049901|1000107101|1000050001|99010101'
        IGNORE_OPPO_NAME_PATTERN = '微信|支付宝|财付通|余额宝|滴滴出行|美团支付|钱袋宝（美团）|抖音支付(合众易宝)|合众易宝(抖音支付)|合众易宝（抖音支付）'
        flow = df[(pd.notna(df['opponent_account_no']))
                  & (~df['opponent_account_no'].isin(IGNORE_ACC_NO))
                  & (~df['opponent_account_no'].str.contains(IGNORE_ACC_NO_PATTERN))
                  & (pd.notna(df['opponent_name']))
                  & (df['opponent_name'] != '')
                  & ((pd.notna(df['trans_type'])) | (pd.notna(df['trans_use'])) | (pd.notna(df['remark'])))
                  ][['opponent_account_no', 'opponent_name', 'trans_type', 'trans_use', 'remark']]
        df_info = flow[['opponent_account_no', 'opponent_name']].drop_duplicates(
            subset=['opponent_account_no', 'opponent_name'], inplace=False)
        df_count = df_info.groupby('opponent_account_no').agg({'opponent_name': 'count'}).sort_values(
            by='opponent_name', ascending=False)  # 单一账户匹配到多个账户名
        if df_count.empty:
            return
        df_cnt = df_count[df_count.opponent_name != 1]
        if df_cnt.empty:
            return
        for no in df_cnt.index:
            name_list = flow[flow.opponent_account_no == no].opponent_name.unique().tolist()
            if re.search(IGNORE_OPPO_NAME_PATTERN, ''.join(name_list)) is not None:
                continue
            for name in name_list:
                remark_list = flow[(flow.opponent_account_no == no)
                                   & (flow.opponent_name == name)
                                   & ((flow.remark.str.contains('冲正|退|抹'))
                                      | (flow.trans_use.str.contains('冲正|退|抹'))
                                      | (flow.trans_type.str.contains('冲正|退|抹')))].opponent_name.to_list()
                if len(remark_list) != 0:
                    name_list.remove(name)
            if len(name_list) <= 1:
                continue
            if len(name_list) > 3:
                self.op_name_list.append(no)
                continue
            verif_list = list()
            for i in range(len(name_list) - 1):  # 遍历列表，两两比较对方户名相似度分数
                for j in range(i + 1, len(name_list)):
                    if name_list[i] in name_list[j] or name_list[j] in name_list[i]:
                        verif_list.append(True)
                        self.not_name_list.append(no)
                        continue
                    diff_score = difflib.SequenceMatcher(None, name_list[i], name_list[j]).quick_ratio()
                    if (diff_score < 0.6 and diff_score != 0.5) or diff_score == 1:
                        verif_list.append(False)
                    else:
                        verif_list.append(True)
            # 3个交易对手，只能为2个True，2个交易对手，只能为1个True
            if len([_ for _ in verif_list if _]) / len(verif_list) in [2 / 3, 1 / 2, 1]:
                self.not_name_list.append(no)
                continue  # 进入下一账号验证
            else:
                self.op_name_list.append(no)
