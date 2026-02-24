import pandas as pd
import decimal
import re
import difflib

from logger.logger_util import LoggerUtil
from parser.task_base_executor import TaskBaseExecutor
from config.trans_config import SIMILAR_THRESH
import itertools

logger = LoggerUtil().logger(__name__)


class VerifyAuthenticityExecutor(TaskBaseExecutor):
    """
    流水文件验证执行器，主要功能：
    1. 交易余额列识别与标准化
    2. 流水连续性校验
    3. 异常交易标签标记
    4. 交易对手信息验证
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
        """
        识别有效余额列核心逻辑
        步骤：
        1. 预处理排除无效余额列
        2. 选择非零值最多的列作为主余额列
        3. 校验条件：
           - 非零值占比需超过20%
           - 余额数值不得超过5亿
        错误处理：
           - 触发 mark_err 标记错误状态
        """
        self._remove_bal_col()
        # 保留非0值最多的列作为交易余额列，若余额列非零值低于20%则拒绝，若余额列存在超过1亿的数字报错
        bal_col = ''
        bal_cnt = 0
        for col in self.bal_col:
            self.df[col] = self.df[col].apply(self.value_trans)
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
        perfect_continuity = False
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
            # 若找到完美连续性，提前终止搜索，剪枝优化
            if temp_conti_cnt == 0:
                perfect_continuity = True
                df = temp_df  # 保留当前排序结果
                break  # 立即终止循环
            if temp_conti_cnt < all_conti_cnt:
                all_conti_cnt = temp_conti_cnt
                df = temp_df
                # if temp_conti_cnt == 0:
                #     return df, 0
        # 拆分日期
        # df['each_date'] = df['trans_time'].apply(lambda x: format(x, '%Y-%m-%d'))
        # df['each_date'] = df['trans_time'].dt.strftime('%Y-%m-%d')
        # date_list = sorted(df[~df['if_conti']]['each_date'].unique().tolist())
        if perfect_continuity:
            # 清理临时列（如果需要的话）
            # df = df.drop(columns=['should_bal', 'neg_bal', 'last_bal', 'if_conti'], errors='ignore')
            return df, 0
        time_list = sorted(df[~df['if_conti']]['trans_time'].drop_duplicates().tolist())
        if len(time_list) == 0:
            return df, 0
        # 若没有不连续的情况，则直接返回原始数据
        # if len(date_list) == 0:
        #     return df, 0
        final_df = pd.DataFrame()
        last_time_bal = None
        # last_time, end_time = pd.to_datetime('2000-01-01'), pd.to_datetime('2030-01-01')
        last_time, end_time = pd.to_datetime('2000-01-01'), df['trans_time'].max()
        total_cnt = 0
        # 对df重置索引
        df = df.reset_index(drop=True)
        # 第一条数据默认是连续的
        df.loc[0, 'if_conti'] = True
        for val_time in time_list:
            # if val_time.strftime("%Y-%m-%d") != '2024-04-24':
            #     continue
            # df已经按时间升序排列了，此处按索引来取last_df
            last_time_df = df[(df['trans_time'] > last_time) & (df['trans_time'] < val_time)]
            if last_time_df.shape[0] > 0:
                last_time_bal = last_time_df['account_balance'].to_list()[-1]
            time_df = df[df['trans_time'] == val_time]
            res_time_df, not_conti_time_cnt = self._single_time_sort(time_df, last_time_bal)
            total_cnt += not_conti_time_cnt
            last_time_bal = res_time_df['account_balance'].tolist()[-1]
            final_df = pd.concat([final_df, last_time_df, res_time_df], axis=0, ignore_index=True)
            last_time = val_time
        remaining_condition = df['trans_time'] > last_time
        remaining_df = df[remaining_condition]
        final_df1 = pd.concat([final_df, remaining_df], axis=0, ignore_index=True)
        return final_df1, total_cnt

    def _single_time_sort(self, df, last_bal=None):
        from math import isclose
        import numpy as np

        # 生成所有可能的索引排列（限制最大尝试次数）
        max_permutations = 1000
        permutations = [df.index.values, df.index.values[::-1]]

        # 添加倒序和样本排列
        if len(df) > 2:
            permutations.append(df.index.values[[1, 0] + list(range(2, len(df)))])

        # 生成随机排列（防止组合爆炸）
        for _ in range(max_permutations - 3):
            permutations.append(np.random.permutation(df.index))

        best_df = df.copy()
        min_violations = float('inf')

        # 遍历所有排列组合
        for perm in permutations:
            temp_df = df.loc[perm].reset_index(drop=True)
            violations = 0
            prev_bal = last_bal  # 使用传入的上期余额

            # 检查首行连续性
            if prev_bal is not None:
                actual_bal = temp_df.loc[0, 'account_balance']
                expected_add = prev_bal + temp_df.loc[0, 'trans_amt']
                expected_sub = prev_bal - temp_df.loc[0, 'trans_amt']
                if not (isclose(actual_bal, expected_add, abs_tol=0.1) or
                        isclose(actual_bal, expected_sub, abs_tol=0.1)):
                    violations += 1

            # 检查内部连续性
            for i in range(1, len(temp_df)):
                prev = temp_df.loc[i - 1, 'account_balance']
                curr = temp_df.loc[i, 'trans_amt']
                actual_bal = temp_df.loc[i, 'account_balance']

                expected_add = prev + curr
                expected_sub = prev - curr

                if not (isclose(actual_bal, expected_add, abs_tol=0.1) or
                        isclose(actual_bal, expected_sub, abs_tol=0.1)):
                    violations += 1

            # 更新最优解
            if violations < min_violations:
                min_violations = violations
                best_df = temp_df
                if violations == 0:
                    break

        # 对最优解进行二次优化
        if min_violations > 0:
            best_df = self._local_optimize(best_df, last_bal)

        return best_df, min_violations

    def _local_optimize(self, df, last_bal):
        """局部优化：交换相邻行尝试减少违规"""
        best_df = df.copy()
        min_viol = self._count_violations(df, last_bal)

        for i in range(len(df) - 1):
            # 交换相邻行
            temp_df = df.copy()
            temp_df.iloc[i:i + 2] = temp_df.iloc[i:i + 2][::-1]

            # 计算违规数
            new_viol = self._count_violations(temp_df, last_bal)

            # 保留更优解
            if new_viol < min_viol:
                best_df = temp_df
                min_viol = new_viol
                if min_viol == 0:
                    break

        return best_df

    @staticmethod
    def _count_violations(df, last_bal):
        """精确计算连续性违规次数"""
        from math import isclose
        violations = 0
        prev = last_bal

        for _, row in df.iterrows():
            if prev is not None:
                expected_add = prev + row['trans_amt']
                expected_sub = prev - row['trans_amt']
                if not (isclose(row['account_balance'], expected_add, abs_tol=0.1) or
                        isclose(row['account_balance'], expected_sub, abs_tol=0.1)):
                    violations += 1
            prev = row['account_balance']

        return violations

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
        self.df['concat_str'] = self.df.apply(
            lambda x: x['trans_channel'] + x['trans_type'] + x['trans_use'] + x['remark'], axis=1)
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
            result, cnt = self.correct_bal(self._balance_check(sort_df))
        else:
            result, cnt = self._balance_check(sort_df)
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
        IGNORE_OPPO_NAME_PATTERN = '微信|支付宝|财付通|余额宝|滴滴出行'
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
