import traceback

from model.model import transform_flow_str
import pandas as pd
import numpy as np
import datetime
import re
from config.label_config import *


def get_trans_flow_src_type_by_account_id(account_id, df_trans_parse):
    df_temp = df_trans_parse[df_trans_parse['account_id'] == account_id]
    if not df_temp.empty:
        return df_temp['trans_flow_src_type'].tolist()[0]
    else:
        return None


class TransSingleLabel:
    """
    单账户标签画像表清洗并落库
    author:汪腾飞
    created_time:20200706
    updated_time_v1:20201125,夜间交易风险和家庭不稳定风险以及民间借贷风险逻辑调整
    updated_time_v2:20210207,民间借贷剔除关联关系，当特殊交易类型命中医院时，将命中医院关键字的字符加到备注列里面
    """

    def __init__(self, session, account_id, df, user_name, user_type, query_data_array):
        self.session = session
        self.query_data_array = query_data_array
        # self.report_req_no = trans_flow.report_req_no
        self.account_id = account_id
        self.df = df
        self.user_name = user_name
        self.user_type = user_type
        self.create_time = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')
        self.label_list = []
        self.trans_label_list = []
        self.spouse_name = 'None'

    def process(self):
        if self.df is None:
            return
        self._choose_index()
        self._relationship_dict()
        # 新增，提前处理关联关系
        self._isrelationship()

        if pd.isnull(self.df.trans_flow_src_type.values[0]) or self.df.trans_flow_src_type.values[0] == 1:
            self._loan_type_label()
            self._unusual_type_label()
        elif self.df.trans_flow_src_type.values[0] in (2, 3):
            self._loan_type_label_third_pay()
            self._unusual_type_label_third_pay()

        self._in_out_order()
        self.usual_trans_type()
        self.save_raw_data()
        transform_flow_str(self.session, self.label_list, 'TransFlowPortrait')
        transform_flow_str(self.session, self.trans_label_list, 'TransFlowLabel')

    # def _choose_index(self):
    #     """
    #     剔除冲正、抹账、冲销相关数据
    #     v2 优化：使用向量化merge替代O(n^2)循环
    #     """
    #     temp_df = self.df.copy()
    #     concat_list = ['trans_channel', 'trans_use', 'remark']
    #     temp_df[concat_list] = temp_df[concat_list].fillna('').astype(str)
    #     temp_df['text'] = temp_df['trans_channel'] + temp_df['trans_use'] + temp_df['remark']
    #     index_list1 = temp_df[temp_df.text.str.contains(BIG_IN_OUT_EXCEPT)].index.tolist()
    #     to_drop = set()
    #     if len(index_list1) > 0:
    #         # 向量化：使用merge一次性查找所有匹配的冲正对
    #         reversal_rows = temp_df.loc[index_list1, ['opponent_name', 'trans_amt']].copy()
    #         reversal_rows['neg_amt'] = -reversal_rows['trans_amt']
    #         reversal_rows['rev_idx'] = reversal_rows.index
    #
    #         temp_reset = temp_df.reset_index()
    #         merged = temp_reset.merge(
    #             reversal_rows[['opponent_name', 'neg_amt', 'rev_idx']],
    #             left_on=['opponent_name', 'trans_amt'],
    #             right_on=['opponent_name', 'neg_amt'],
    #             how='inner'
    #         )
    #         if not merged.empty:
    #             to_drop.update(merged['index'].tolist())
    #             to_drop.update(merged['rev_idx'].tolist())
    #     self.df = self.df.drop(index=list(to_drop)).reset_index(drop=True)

    def _choose_index(self):
        """
        剔除冲正、抹账、冲销相关数据
        """
        temp_df = self.df.copy()
        concat_list = ['trans_channel', 'trans_use', 'remark']
        temp_df[concat_list] = temp_df[concat_list].fillna('').astype(str)
        temp_df['text'] = temp_df['trans_channel'] + temp_df['trans_use'] + temp_df['remark']
        index_list1 = temp_df[temp_df.text.str.contains(BIG_IN_OUT_EXCEPT)].index.tolist()
        to_drop = set()
        for idx in range(len(index_list1)):
            row = temp_df.loc[index_list1[idx]]
            matched = temp_df[
                (temp_df['opponent_name'] == row['opponent_name']) &
                (temp_df['trans_amt'] == -row['trans_amt'])
                ].index.tolist()
            # # 可选：排除自己（如果存在自反情况，一般不会）
            matched = [i for i in matched if i != idx]
            to_drop.add(index_list1[idx])
            if matched:
                # 成对删除：只删第一个匹配项（避免多删）
                try:
                    to_drop.add(matched[0])
                except Exception as e:
                    raise Exception(e)
        self.df = self.df.drop(index=list(to_drop)).reset_index(drop=True)

    # def _choose_index(self):
    #     """
    #     剔除冲正、抹账相关数据
    #     """
    #     temp_df = self.df
    #     concat_list = ['trans_channel', 'trans_use', 'remark']
    #     temp_df[concat_list] = temp_df[concat_list].fillna('').astype(str)
    #     temp_df['text'] = temp_df['trans_channel'] + temp_df['trans_use'] + temp_df['remark']
    #     index_list1 = temp_df[temp_df.text.str.contains(BIG_IN_OUT_EXCEPT)].index.tolist()
    #     index_list2 = []
    #     for left_i in index_list1:
    #         row1 = temp_df.loc[left_i, :]
    #         if left_i > 0:
    #             row2 = temp_df.loc[left_i - 1, :]
    #         else:
    #             continue
    #         if getattr(row1, 'opponent_name') == getattr(row2, 'opponent_name') and \
    #                 getattr(row1, 'trans_amt') + getattr(row2, 'trans_amt') == 0:
    #             index_list2.append(left_i - 1)
    #             index_list2.append(left_i)
    #     self.df = self.df.drop(index=index_list2).reset_index(drop=True)

    def _relationship_dict(self):
        """
        生成姓名和关联关系对应的字典,需要将编码形式的关联关系转化为中文关联关系
        v1.2,忽略掉全部担保人
        v2 担保人不忽略
        v3 优化：使用 re.escape 替代手动转义，预编译关系正则
        :return:
        """
        length = len(self.query_data_array)
        self.relation_dict = dict()
        self.relation_dict[self.user_name] = 'U_PERSONAL' if self.user_type == 'PERSONAL' else 'U_COMPANY'
        for i in range(length):
            temp = self.query_data_array[i]
            base_type_detail = temp['baseTypeDetail']
            name = re.escape(temp['name'])
            self.relation_dict[name] = base_type_detail
            if base_type_detail in ['U_PER_SP_PERSONAL', 'U_COM_CT_SP_PERSONAL']:
                self.spouse_name = str(temp['name'])
        # 预编译关联关系正则，用于后续 _isrelationship 和 loan_type 匹配
        if self.relation_dict:
            self._relation_pattern = re.compile('|'.join(self.relation_dict.keys()))
        else:
            self._relation_pattern = None

    def _isrelationship(self):
        """
        本模块获取关联关系
        v2 优化：使用预编译正则
        """
        if self._relation_pattern is not None:
            self.df['relationship'] = self.df['opponent_name'].astype(str).str.extract(
                self._relation_pattern, expand=False
            ).map(self.relation_dict)
        else:
            self.df['relationship'] = None

    # def _isrelationship(self):
    #     """
    #     本模块获取关联关系
    #     """
    #     for i, v in self.relation_dict.items():
    #         self.df.loc[self.df['opponent_name'].astype(str).str.contains(i), 'relationship'] = v

    def _loan_type_label(self):
        """
        包括交易对手类型标签opponent_type,贷款类型标签loan_type,是否还款标签is_repay,是否结息标签is_interest
        是否结息前一周标签is_before_interest_repay
        v2 优化：向量化日期提取、abs、itertuples循环替换为merge/groupby操作
        :return:
        """
        concat_list = ['opponent_name', 'trans_channel', 'trans_type', 'trans_use', 'remark']
        self.df[concat_list] = self.df[concat_list].fillna('').astype(str)
        # 交易对手标签赋值,1个人,2企业,其他为空
        self.df['opponent_type'] = self.df['opponent_name'].apply(self._opponent_type)
        # 向量化日期提取
        self.df['year_month'] = self.df['trans_time'].dt.strftime('%Y-%m')
        self.df['year'] = self.df['trans_time'].dt.year
        self.df['month'] = self.df['trans_time'].dt.month
        self.df['day'] = self.df['trans_time'].dt.day
        # 将字符串列合并到一起
        self.df['concat_str'] = self.df['opponent_name'] + ';' + self.df['trans_channel'] + ';' + \
            self.df['trans_type'] + ';' + self.df['trans_use'] + ';' + self.df['remark']
        # 贷款类型赋值,优先级从上至下
        our_inst = "￥￥￥$$$$"
        # 消金
        self.df.loc[(self.df['concat_str'].str.contains(CONSUME_FINANCE)) &
                    (~self.df['concat_str'].str.contains(CONSUME_FINANCE_EXCEPT)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '消金'
        # 融资租赁
        self.df.loc[(self.df['concat_str'].str.contains(FINANCE_LEASE)) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '融资租赁'
        # 担保
        self.df.loc[(self.df['concat_str'].str.contains(GUARANTEE)) &
                    (~self.df['concat_str'].str.contains(GUARANTEE_EXCEPT)) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '担保'
        # 保理
        self.df.loc[(self.df['concat_str'].str.contains(FACTORING)) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '保理'
        # 小贷
        self.df.loc[~(self.df['concat_str'].str.contains(SMALL_LOAN_EXCEPT)) &
                    (self.df['concat_str'].str.contains(SMALL_LOAN)) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '小贷'

        # 银行放款
        self.df.loc[(self.df.trans_amt > 0) &
                    ((self.df.opponent_name.str.contains(BANK_LOAN_OPPONENT_NAME)) |
                     ((self.df.opponent_name.isin([self.user_name, ""])) &
                      (self.df.concat_str.str.contains(BANK_LOAN_REMARK)))) &
                    ((~self.df.concat_str.str.contains(BANK_LOAN_CONCAT_STR_EXCEPT)) |
                     (self.df.concat_str.str.contains(BANK_LOAN_CONCAT_STR_COMPATIBLE))) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.astype(str).str.contains(BANK_LOAN_OPPONENT_NAME_EXCEPT)), 'bank_loan'] = 1
        # 银行还款
        self.df.loc[(self.df.trans_amt < 0) &
                    (((self.df.concat_str.str.contains("还贷|自动还款|贷款利息|约定还款|贷款回收|批量代扣|约定还款|收回利息|贷款业务|批量扣款|还本金")) &
                      (self.df.opponent_name.isin([self.user_name, ""]))) |
                     ((self.df.concat_str.str.contains(BANK_REPAY_CONCAT_STR)) &
                      (self.df.opponent_name.str.contains(BANK_REPAY_OPPONENT_NAME))) |
                     (self.df.opponent_name.str.contains("信用卡还款|贷记卡本转贷|信用卡转账还款"))) &
                    (pd.isnull(self.df.loan_type)), 'bank_repay'] = 1
        # 受托支付 — 向量化查找
        self.df['entrust_pay'] = 0
        entrust_mask = (self.df.trans_amt < 0) & (self.df.concat_str.str.contains(ENTRUSTED_PAY))
        self.df.loc[entrust_mask, 'entrust_pay'] = 1
        # 受托支付补充：银行放款3天内同金额流出
        bank_income = self.df[self.df.bank_loan == 1]
        if not bank_income.empty:
            bank_income_tmp = bank_income[['trans_time', 'trans_amt']].copy()
            bank_income_tmp['time_lower'] = bank_income_tmp['trans_time']
            bank_income_tmp['time_upper'] = bank_income_tmp['trans_time'] + datetime.timedelta(days=3)
            bank_income_tmp['neg_amt'] = -bank_income_tmp['trans_amt']
            # 使用merge向量化查找匹配行
            df_reset = self.df.reset_index()
            df_reset['row_index'] = df_reset.index
            entrust_candidates = df_reset[
                (df_reset['trans_time'].notna()) &
                (df_reset['opponent_name'] == '') &
                (~df_reset['concat_str'].str.contains(ENTRUSTED_PAY))
            ]
            if not entrust_candidates.empty:
                merged_entrust = entrust_candidates.merge(
                    bank_income_tmp[['neg_amt', 'time_lower', 'time_upper']],
                    left_on='trans_amt',
                    right_on='neg_amt',
                    how='inner'
                )
                time_mask = (merged_entrust['trans_time'] > merged_entrust['time_lower']) & \
                            (merged_entrust['trans_time'] < merged_entrust['time_upper'])
                matched_entrust = merged_entrust[time_mask]
                if not matched_entrust.empty:
                    # 每组只取第一个匹配行
                    first_match = matched_entrust.groupby('row_index').first().reset_index()
                    self.df.loc[first_match['index'], 'entrust_pay'] = 1

        # 银行
        self.df.loc[(self.df.bank_loan == 1) |
                    ((self.df.bank_repay == 1) & (self.df.entrust_pay != 1)), 'loan_type'] = "银行"
        # 第三方支付
        self.df.loc[(((self.df['concat_str'].str.contains(THIRD_REPAY_1)) &
                      (self.df['concat_str'].str.contains(THIRD_REPAY_2)) &
                      (~self.df['concat_str'].str.contains(THIRD_REPAY_EXCEPT))) |
                     self.df['concat_str'].str.contains(THIRD_REPAY_3)) &
                    (pd.isnull(self.df.loan_type)), 'loan_type'] = '第三方支付'
        # 其他金融 — 使用预编译关联关系正则
        other_finance_relation_mask = False
        if self._relation_pattern is not None:
            other_finance_relation_mask = self.df['opponent_name'].str.contains(
                self._relation_pattern, regex=True
            )
        self.df.loc[
            (((self.df['concat_str'].str.contains(OTHER_FINANCE)) &
              (~self.df['concat_str'].str.contains(OTHER_FINANCE_EXCEPT))) |
             ((self.df['concat_str'].str.contains(OTHER_FINANCE_PER)) & (self.df.opponent_type != 1)) |
             (other_finance_relation_mask &
              (self.df['concat_str'].str.contains(OTHER_FINANCE_RELATION)))) &
            (~self.df['trans_channel'].str.contains(OTHER_FINANCE_CHANNEL_EXCEPT)) &
            (pd.isnull(self.df.loan_type)) &
            (~self.df.opponent_name.str.contains(OTHER_FINANCE_ENT_EXCEPT)), 'loan_type'] = '其他金融'
        # 民间借贷
        trans_amt_abs = self.df['trans_amt'].abs()
        self.df.loc[(trans_amt_abs > 500) &
                    (~self.df['concat_str'].str.contains('|'.join(self.relation_dict.keys()))) &
                    ((((self.df['concat_str'].str.contains(PRIVATE_LENDING)) |
                       ((self.df['concat_str'].str.contains(PRIVATE_LENDING_COMPATIBLE)) &
                        (self.df['opponent_name'] != ''))) &
                      (~self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_1))) |
                     ((self.df['trans_amt'] < 0) & (self.df['concat_str'].str.contains(PRIVATE_LENDING_INTEREST)) &
                      (~self.df['concat_str'].str.contains(PRIVATE_LENDING_INTEREST_EXCEPT)))) &
                    (~self.df['opponent_name'].str.contains(PRIVATE_LENDING_OPPONENT_NAME)) &
                    (self.df['opponent_name'] != '') &
                    (pd.isnull(self.df.loan_type)), 'loan_type'] = '民间借贷'

        # 持续月份民间借贷检测 — 向量化groupby+shift（预过滤+groupby检测连续月份）
        is_null_loan = pd.isnull(self.df.loan_type)
        amt_abs = self.df['trans_amt'].abs()
        relation_keys_str = '|'.join(self.relation_dict.keys()) if self.relation_dict else ''
        conti_filter = (
            (amt_abs > MIN_PRIVATE_LENDING) &
            (pd.notnull(self.df['opponent_type'])) &
            (self.df['opponent_name'] != '') &
            (~self.df['opponent_name'].str.contains(PRIVATE_LENDING_OPPONENT_NAME)) &
            (is_null_loan)
        )
        if relation_keys_str:
            conti_filter = conti_filter & (~self.df['concat_str'].str.contains(relation_keys_str))
        conti_base = self.df[conti_filter].copy()
        if not conti_base.empty:
            except_mask = self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_2)
            except_names = set(self.df[except_mask]['opponent_name'])
            conti_base = conti_base[~conti_base['opponent_name'].isin(except_names)]
            if not conti_base.empty:
                # 保存原始索引并排序
                conti_base['_orig_idx'] = conti_base.index
                conti_base = conti_base.sort_values(['opponent_name', 'trans_amt', 'trans_time']).reset_index(drop=True)
                conti_base['month_offset'] = conti_base.apply(lambda r: r['trans_time'].year * 12 + r['trans_time'].month, axis=1)
                conti_base['prev_month_offset'] = conti_base.groupby(['opponent_name', 'trans_amt'])['month_offset'].shift(1)
                conti_base['month_diff'] = conti_base['month_offset'] - conti_base['prev_month_offset']
                conti_base['new_group'] = (conti_base['month_diff'] != 1).fillna(True).astype(int)
                conti_base['conti_group'] = conti_base.groupby(['opponent_name', 'trans_amt'])['new_group'].cumsum()
                # 按连续组统计
                conti_stats = conti_base.groupby(
                    ['opponent_name', 'trans_amt', 'conti_group'], as_index=False
                ).agg(
                    cnt=('trans_amt', 'count'),
                    min_day=('day', 'min'),
                    max_day=('day', 'max'),
                    _orig_indices=('_orig_idx', list)
                )
                valid_conti = conti_stats[
                    (conti_stats['cnt'] >= MIN_CONTI_MONTHS) &
                    ((conti_stats['max_day'] - conti_stats['min_day']) <= MAX_INTERVAL_DAYS)
                ]
                if not valid_conti.empty:
                    # 取该(opponent_name, trans_amt)原始行的loan_type
                    orig_loan_types = self.df.groupby(['opponent_name', 'trans_amt'])['loan_type'].first()
                    for _, group_row in valid_conti.iterrows():
                        key = (group_row['opponent_name'], group_row['trans_amt'])
                        loan_type_val = orig_loan_types.get(key, pd.NA)
                        if pd.isna(loan_type_val):
                            loan_type_val = '民间借贷'
                        idx_list = group_row['_orig_indices']
                        if idx_list and len(idx_list) > 0:
                            self.df.loc[idx_list, 'loan_type'] = loan_type_val

        # 是否还款标签
        self.df.loc[(pd.notnull(self.df['loan_type'])) & (self.df['trans_amt'] < 0), 'is_repay'] = 1

        # 是否结息标签
        self.df['is_interest'] = None
        interest_df = self.df.loc[(self.df.month % 3 == 0) &
                                  (self.df.day.isin([20, 21])) &
                                  (self.df.trans_amt > 0) &
                                  ((self.df.opponent_name == '') |
                                   (self.df.opponent_name == self.user_name) |
                                   (self.df.opponent_name.str.contains(INTEREST_OPPO_KEY_WORD))) &
                                  (self.df.concat_str.str.contains(INTEREST_KEY_WORD)) &
                                  (~self.df.concat_str.str.contains(NON_INTEREST_KEY_WORD))]
        interest_df.reset_index(drop=False, inplace=True)
        group_df = interest_df.groupby(by=['year', 'month'], as_index=False).agg({'trans_amt': min})
        index_list = interest_df.loc[group_df.index.tolist(), 'index'].tolist()
        self.df.loc[index_list, 'is_interest'] = 1
        if self.df[self.df.is_interest == 1].empty and self.df[pd.notna(self.df.remark)
                                                               & (self.df.remark != "")].empty:
            interest_df = self.df.loc[(self.df.month % 3 == 0) &
                                      (self.df.day.isin([20, 21, 22])) &
                                      (self.df.trans_amt > 0) &
                                      (self.df.opponent_name == '')]
            interest_df.reset_index(drop=False, inplace=True)
            group_df = interest_df.groupby(by=['year', 'month'], as_index=False).agg({'trans_amt': min})
            index_list = interest_df.loc[group_df.index.tolist(), 'index'].tolist()
            self.df.loc[index_list, 'is_interest'] = 1

        # 是否还款到期前一周标签 — 向量化
        repay_dates = self.df[self.df['is_repay'] == 1]['trans_time']
        if not repay_dates.empty:
            all_dates = self.df['trans_time']
            # 对每个还款日期，找到前7天内的行
            for repay_date in repay_dates:
                seven_days_ago = repay_date - datetime.timedelta(days=7)
                self.df.loc[(self.df.trans_time >= seven_days_ago) &
                            (self.df.trans_time < repay_date), 'is_before_interest_repay'] = 1
        self.df.drop(['year', 'month', 'day'], axis=1, inplace=True)

    def _loan_type_label_third_pay(self):
        """
        v2 优化：向量化日期、abs操作；向量化连续月份检测
        """
        concat_list = ['opponent_name', 'remark']
        self.df[concat_list] = self.df[concat_list].fillna('').astype(str)
        self.df['is_interest'] = None
        # 交易对手标签赋值,1个人,2企业,其他为空
        self.df['opponent_type'] = self.df['opponent_name'].apply(self._opponent_type)
        self.df['year_month'] = self.df['trans_time'].dt.strftime('%Y-%m')
        self.df['year'] = self.df['trans_time'].dt.year
        self.df['month'] = self.df['trans_time'].dt.month
        self.df['day'] = self.df['trans_time'].dt.day
        # 将字符串列合并到一起
        self.df['concat_str'] = self.df['opponent_name'] + ';' + self.df['remark']
        # 贷款类型赋值,优先级从上至下
        our_inst = "￥￥￥$$$$"
        # 消金
        self.df.loc[(self.df.trans_amt < 0) &
                    (self.df['opponent_name'].str.contains(CONSUME_FINANCE)) &
                    (~self.df['opponent_name'].str.contains(CONSUME_FINANCE_EXCEPT)) &
                    ((self.df['trans_use'] == '商户消费') | (pd.isnull(self.df['trans_use']))) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '消金'
        # 融资租赁
        self.df.loc[(self.df.trans_amt < 0) &
                    (self.df['opponent_name'].str.contains(FINANCE_LEASE)) &
                    (pd.isnull(self.df.loan_type)) &
                    ((self.df['trans_use'] == '商户消费') | (pd.isnull(self.df['trans_use']))) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '融资租赁'
        # 担保
        self.df.loc[(self.df.trans_amt < 0) &
                    (self.df['opponent_name'].str.contains(GUARANTEE)) &
                    (~self.df['opponent_name'].str.contains(GUARANTEE_EXCEPT)) &
                    ((self.df['trans_use'] == '商户消费') | (pd.isnull(self.df['trans_use']))) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '担保'
        # 保理
        self.df.loc[(self.df['opponent_name'].str.contains(FACTORING)) &
                    ((self.df['trans_use'] == '商户消费') | (pd.isnull(self.df['trans_use']))) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '保理'
        # 小贷
        self.df.loc[~(self.df['opponent_name'].str.contains(SMALL_LOAN_EXCEPT)) &
                    (self.df['opponent_name'].str.contains(SMALL_LOAN)) &
                    ((self.df['trans_use'] == '商户消费') | (pd.isnull(self.df['trans_use']))) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '小贷'
        # 银行
        self.df.loc[(self.df['concat_str'].str.contains(WXZFB_BANK_LOAN)) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(our_inst)), 'loan_type'] = '银行'
        # 其他金融
        self.df.loc[(self.df['opponent_name'].str.contains(OTHER_FINANCE)) &
                    (~self.df['opponent_name'].str.contains(OTHER_FINANCE_EXCEPT)) &
                    (pd.isnull(self.df.loan_type)) &
                    (~self.df.opponent_name.str.contains(OTHER_FINANCE_ENT_EXCEPT)), 'loan_type'] = '其他金融'
        # 民间借贷
        self.df.loc[(self.df['trans_amt'].abs() > 500) &
                    (self.df['concat_str'].str.contains(PRIVATE_LENDING)) &
                    (~self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_WX)) &
                    (pd.isnull(self.df.loan_type)), 'loan_type'] = '民间借贷'
        # 持续月份民间借贷检测 — 向量化
        is_null_loan = pd.isnull(self.df.loan_type)
        amt_abs = self.df['trans_amt'].abs()
        conti_filter = (
            (amt_abs > MIN_PRIVATE_LENDING) &
            (self.df['opponent_name'] != '') &
            (~self.df['opponent_name'].str.contains(PRIVATE_LENDING_OPPONENT_NAME)) &
            (is_null_loan)
        )
        except_mask = self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_2)
        conti_filter = conti_filter & (~except_mask)
        conti_base = self.df[conti_filter].copy()
        if not conti_base.empty:
            conti_base['_orig_idx'] = conti_base.index
            conti_base = conti_base.sort_values(['opponent_name', 'trans_amt', 'trans_time']).reset_index(drop=True)
            conti_base['month_offset'] = conti_base['year'] * 12 + conti_base['month']
            conti_base['prev_month_offset'] = conti_base.groupby(['opponent_name', 'trans_amt'])['month_offset'].shift(1)
            conti_base['month_diff'] = conti_base['month_offset'] - conti_base['prev_month_offset']
            conti_base['new_group'] = (conti_base['month_diff'] != 1).fillna(True).astype(int)
            conti_base['conti_group'] = conti_base.groupby(['opponent_name', 'trans_amt'])['new_group'].cumsum()
            conti_stats = conti_base.groupby(
                ['opponent_name', 'trans_amt', 'conti_group'], as_index=False
            ).agg(
                cnt=('trans_amt', 'count'),
                min_day=('day', 'min'),
                max_day=('day', 'max'),
                _orig_indices=('_orig_idx', list)
            )
            valid_conti = conti_stats[
                (conti_stats['cnt'] >= MIN_CONTI_MONTHS) &
                ((conti_stats['max_day'] - conti_stats['min_day']) <= MAX_INTERVAL_DAYS)
            ]
            if not valid_conti.empty:
                orig_loan_types = self.df.groupby(['opponent_name', 'trans_amt'])['loan_type'].first()
                for _, group_row in valid_conti.iterrows():
                    key = (group_row['opponent_name'], group_row['trans_amt'])
                    loan_type_val = orig_loan_types.get(key, pd.NA)
                    if pd.isna(loan_type_val):
                        loan_type_val = '民间借贷'
                    idx_list = group_row['_orig_indices']
                    if idx_list and len(idx_list) > 0:
                        self.df.loc[idx_list, 'loan_type'] = loan_type_val

    def _unusual_type_label(self):
        self.df['op_name'] = self.df.opponent_name
        no_channel_list = ['opponent_name', 'trans_type', 'trans_use', 'remark']
        no_oppo_channel_list = ['trans_type', 'trans_use', 'remark']
        self.df[no_channel_list] = self.df[no_channel_list].fillna('').astype(str)
        self.df[no_oppo_channel_list] = self.df[no_oppo_channel_list].fillna('').astype(str)
        # 将字符串列合并到一起
        self.df['no_channel_str'] = self.df['opponent_name'] + ';' + self.df['trans_type'] + ';' + \
                                    self.df['trans_use'] + ';' + self.df['remark']
        self.df['no_oppo_channel_str'] = self.df['trans_type'] + ';' + self.df['trans_use'] + ';' + self.df['remark']
        self.df['user_type'] = self.user_type
        self.df['unusual_trans_type'] = \
            pd.Series(np.where((self.df['concat_str'].str.contains(GAMBLE) &
                                (~self.df['concat_str'].str.contains("收费站"))) &
                               ((self.df['trans_amt'] < 0) |
                                ((self.df['no_oppo_channel_str'].str.contains(GAMBLE_INCOME)) &
                                 (self.df['trans_amt'] > 0))), '博彩', '')) + ';' + \
            pd.Series(np.where((self.df['concat_str'].str.contains(AMUSEMENT)) &
                               (self.df['trans_amt'] < 0) &
                               (~self.df['concat_str'].str.contains(AMUSEMENT_EXCEPT)) &
                               (self.df['op_name'] != ""), '娱乐', '')) + ';' + \
            pd.Series(np.where((self.df['op_name'].str.contains(CASE_DISPUTES)) &
                               (self.df['trans_amt'] < 0), '案件纠纷', '')) + ';' + \
            pd.Series(np.where(((self.df['no_channel_str'].str.contains(SECURITY_FINES) &
                                 (~self.df['concat_str'].str.contains(SECURITY_FINES_EXCEPT))) |
                                (self.df['op_name'].str.contains(SECURITY_EXPENSE_FINES))) &
                               (self.df['trans_amt'] < 0), '治安罚款', '')) + ';' + \
            pd.Series(np.where((self.df['concat_str'].str.contains(INSURANCE_CLAIMS)) &
                               (self.df['op_name'] != ""), '保险理赔', '')) + ';' + \
            pd.Series(np.where((self.df['op_name'].str.contains(STOCK_OPPONENT_NAME)) &
                               (self.df['remark'].str.contains(STOCK_REMARK)), '股票期货', '')) + ';' + \
            pd.Series(np.where((self.df['user_type'] == 'PERSONAL') &
                               (self.df['trans_amt'] < 0) &
                               (((self.df['concat_str'].str.contains(HOSPITAL)) &
                                 (~self.df['concat_str'].str.contains(HOSPITAL_EXCEPT))) |
                                ((self.df['concat_str'].str.contains(HOSPITAL_2)) &
                                 (~self.df['concat_str'].str.contains(HOSPITAL_EXCEPT_2)))) &
                               (self.df['op_name'] != ""), '医院', '')) + ';' + \
            pd.Series(np.where((((self.df['loan_type'] == '担保') &
                                 (self.df['concat_str'].str.contains(LOAN_GUAR_ABNORMAL))) |
                                ((self.df['concat_str'].str.contains(LOAN_ABNORMAL)) &
                                 (~self.df['concat_str'].str.contains(LOAN_ABNORMAL_EXCEPT)))) &
                               (self.df['trans_amt'] < 0) &
                               (self.df['op_name'] != ""), '贷款异常', '')) + ';' + \
            pd.Series(np.where((self.df['remark'].str.contains(GUAR_ABNORMAL)) &
                               (self.df['trans_amt'] < 0) &
                               (self.df['op_name'] != ""), '对外担保异常', '')) + ';' + \
            pd.Series(np.where((self.df['concat_str'].str.contains(NORITOMO)) &
                               (self.df['op_name'] != ""), '典当', '')) + ';' + \
            pd.Series(np.where((self.df['trans_amt'] > 0) &
                               (self.df['concat_str'].str.contains(Un_Operating_Income)), '营业外收入', ''))
        # 全部未命中的行赋值为空值
        self.df['unusual_trans_type'] = np.where(self.df['unusual_trans_type'].str.replace(';', '') == '',
                                                 None, self.df['unusual_trans_type'])
        # 成本支出项
        self.df['cost_type'] = np.where(
            (self.df['trans_amt'] < 0) & (self.df['no_channel_str'].str.contains(SALARY)), '工资',
            np.where((self.df['no_channel_str'].str.contains(UTILITIES)) & (self.df['trans_amt'] < 0) & (
                ~self.df['no_channel_str'].str.contains(UTILITIES_EXCEPT)), '水电',
                     np.where((self.df['no_channel_str'].str.contains(TAX)) & (self.df['trans_amt'] < 0) & (
                         ~self.df['no_channel_str'].str.contains(TAX_EXCEPT)), '税费',
                              np.where((self.df['no_channel_str'].str.contains(RENT)) & (self.df['trans_amt'] < 0) & (
                                  ~self.df['no_channel_str'].str.contains(RENT_EXCEPT)), '房租',
                                       np.where((self.df['no_channel_str'].str.contains(SOCIAL_INSURANCE)) & (
                                                   self.df['trans_amt'] < 0), '保险',
                                                np.where((self.df['no_channel_str'].str.contains(GONGJIJIN)) & (
                                                            self.df['trans_amt'] < 0), '公积金',
                                                         np.where((self.df['no_channel_str'].str.contains(VARIABLE_COST)) & (self.df['trans_amt'] < 0) & (
                                                                 ~self.df['no_channel_str'].str.contains(
                                                                     VARIABLE_COST_EXCEPT)), '可变成本',
                                                             None)))))))  # 增加公积金
        # self.df['cost_type'] = np.where(
        #     (self.df['trans_amt'] < 0) & (self.df['no_channel_str'].str.contains(SALARY)), '工资', np.where(
        #         (self.df['no_channel_str'].str.contains(UTILITIES)) & (self.df['trans_amt'] < 0) &
        #         (~self.df['no_channel_str'].str.contains(UTILITIES_EXCEPT)), '水电', np.where(
        #             (self.df['no_channel_str'].str.contains(TAX)) & (self.df['trans_amt'] < 0) &
        #             (~self.df['no_channel_str'].str.contains(TAX_EXCEPT)), '税费', np.where(
        #                 (self.df['no_channel_str'].str.contains(RENT)) & (self.df['trans_amt'] < 0), '房租', np.where(
        #                     (self.df['no_channel_str'].str.contains(INSURANCE)) & (self.df['trans_amt'] < 0), '保险',
        #                     np.where((self.df['no_channel_str'].str.contains(VARIABLE_COST)) &
        #                              (self.df['trans_amt'] < 0)& (
        #          ~self.df['no_channel_str'].str.contains(VARIABLE_COST_EXCEPT)), '可变成本', None))))))

        # for row in self.df.itertuples():
        #     # 将合并列拉出来
        #     concat_str = getattr(row, 'concat_str')
        #     no_channel_str = getattr(row, 'no_channel_str')
        #     no_oppo_channel_str = getattr(row, 'no_oppo_channel_str')
        #     op_name = getattr(row, 'op_name')
        #     trans_amt = getattr(row, 'trans_amt')
        #     # loan_type = getattr(row, 'loan_type')
        #     remark = getattr(row, 'remark')
        #     # 异常交易类型
        #     unusual_type = []
        #     # 博彩
        #     if (re.search(GAMBLE, concat_str) and
        #         (trans_amt < 0 or (trans_amt > 0 and re.search(GAMBLE_INCOME, no_oppo_channel_str)))) \
        #             and op_name != "":
        #         unusual_type.append('博彩')
        #     # 娱乐
        #     if (re.search(AMUSEMENT, concat_str) and trans_amt < 0 and
        #         re.search(AMUSEMENT_EXCEPT, concat_str) is None) \
        #             and op_name != "":
        #         unusual_type.append('娱乐')
        #     # 案件纠纷
        #     if re.search(CASE_DISPUTES, op_name) and trans_amt < 0:
        #         unusual_type.append('案件纠纷')
        #     # 治安罚款
        #     if (re.search(SECURITY_EXPENSE_FINES, op_name) and (trans_amt < 0)) \
        #             or (re.search(SECURITY_FINES, no_channel_str) and
        #                 re.search(SECURITY_FINES_EXCEPT, concat_str) is None):
        #         unusual_type.append('治安罚款')
        #     # 保险理赔
        #     if re.search(INSURANCE_CLAIMS, concat_str) and op_name != "":
        #         unusual_type.append('保险理赔')
        #     # 股票期货
        #     if re.search(STOCK_OPPONENT_NAME, op_name) and re.search(STOCK_REMARK, remark):
        #         unusual_type.append('股票期货')
        #     # 医院
        #     if self.user_type == "PERSONAL" and trans_amt < 0 and re.search(HOSPITAL, concat_str) and \
        #             re.search(HOSPITAL_EXCEPT, concat_str) is None and op_name != "":
        #         unusual_type.append('医院')
        #
        #     # 贷款异常
        #     if trans_amt < 0 and ((hasattr(row, 'loan_type') and
        #                            getattr(row, 'loan_type') == '担保' and
        #                            re.search(LOAN_GUAR_ABNORMAL, concat_str)) or
        #                           (re.search(LOAN_ABNORMAL, concat_str))) \
        #             and op_name != "":
        #         unusual_type.append('贷款异常')
        #     # 对外担保异常
        #     if trans_amt < 0 and re.search(GUAR_ABNORMAL, remark) and op_name != "":
        #         unusual_type.append('对外担保异常')
        #     # 典当
        #     if re.search(NORITOMO, concat_str) and op_name != "":
        #         unusual_type.append('典当')
        #
        #     # 添加标签到df
        #     if len(unusual_type) > 0:
        #         self.df.loc[row.Index, 'unusual_trans_type'] = ';'.join(unusual_type)
        #     else:
        #         self.df.loc[row.Index, 'unusual_trans_type'] = None
        #
        #     # 成本支出类别标签
        #     if re.search(SALARY, no_channel_str):
        #         self.df.loc[row.Index, 'cost_type'] = '工资'
        #     elif re.search(UTILITIES, no_channel_str):
        #         self.df.loc[row.Index, 'cost_type'] = '水电'
        #     elif re.search(TAX, no_channel_str):
        #         self.df.loc[row.Index, 'cost_type'] = '税费'
        #     elif re.search(RENT, no_channel_str):
        #         self.df.loc[row.Index, 'cost_type'] = '房租'
        #     elif re.search(INSURANCE, no_channel_str):
        #         self.df.loc[row.Index, 'cost_type'] = '保险'
        #     elif re.search(VARIABLE_COST, no_channel_str):
        #         self.df.loc[row.Index, 'cost_type'] = '可变成本'
        #     else:
        #         self.df.loc[row.Index, 'cost_type'] = None

    def usual_trans_type(self):
        """
        v2 优化：向量化日期格式化、abs操作
        """
        self.df['date'] = self.df['trans_time'].dt.strftime('%Y-%m-%d')
        no_oppo_list = ['trans_channel', 'trans_type', 'trans_use', 'remark']
        self.df[no_oppo_list] = self.df[no_oppo_list].fillna('').astype(str)
        # 将字符串列合并到一起
        self.df['no_oppo_str'] = self.df['trans_channel'] + ';' + self.df['trans_type'] + ';' + \
            self.df['trans_use'] + ';' + self.df['remark']

        # 其他画像之是否整进整出标签
        # 20220913 整进整出金额调整为10万的整万
        trans_amt_abs = self.df.trans_amt.abs()
        big_in_out_df = self.df[(trans_amt_abs >= 100000) &
                                (self.df.trans_amt % 10000 == 0) &
                                (~self.df.concat_str.str.contains(BIG_IN_OUT_EXCEPT))]
        big_in_date = big_in_out_df[big_in_out_df.trans_amt > 0]['date'].tolist()
        big_out_date = big_in_out_df[big_in_out_df.trans_amt < 0]['date'].tolist()
        big_in_out_date = list(set(big_in_date).intersection(set(big_out_date)))
        big_in_out_list = big_in_out_df[big_in_out_df.date.isin(big_in_out_date)].index.tolist()
        self.df.loc[big_in_out_list, 'big_in_out'] = "整进整出"

        # 其他画像之快进快出标签
        # 20220913 快进快出金额调整为20万
        fast_in_out_df = self.df[(trans_amt_abs >= 200000) &
                                 (self.df.opponent_name != '') &
                                 (~self.df.opponent_name.str.contains(FAST_IN_OUT_OPPONENT_NAME_EXCEPT)) &
                                 (~self.df.concat_str.str.contains(FAST_IN_OUT_EXCEPT))]
        fast_in_date = fast_in_out_df[fast_in_out_df.trans_amt > 0]['date'].tolist()
        fast_out_date = fast_in_out_df[fast_in_out_df.trans_amt < 0]['date'].tolist()
        fast_in_out_date = list(set(fast_in_date).intersection(set(fast_out_date)))
        fast_in_out_list = fast_in_out_df[fast_in_out_df.date.isin(fast_in_out_date)].index.tolist()
        self.df.loc[fast_in_out_list, 'fast_in_out'] = "快进快出"

        # 其他画像之家庭不稳定标签
        # 银行流水判断关联关系和交易对手类型，微信支付宝流水判断交易类型
        self.df.loc[(~self.df['opponent_name'].astype(str).str.contains(f'{self.spouse_name}|老婆|/')) &
                    (((pd.notnull(self.df["account_balance"])) &
                      (pd.isna(self.df['relationship'])) &
                      (self.df['opponent_type'] == 1)) |
                     ((pd.isnull(self.df["account_balance"])) &
                      (self.df['trans_use'].astype(str).str.contains("微信红包|转账")))) &
                    (self.df['trans_amt'].abs().isin(FAMILY_RISK_AMT)), 'family_risk'] = '家庭不稳定'

        # 其他画像之理财行为标签
        # 理财行为取值逻辑：组合列含有到期、赎回、理财收益 且交易金额 >0 或含有认购、买入、理财本金 且交易金额 < 0
        financing_df = self.df[((self.df.trans_amt > 0) & (self.df.no_oppo_str.str.contains(FINANCING_INCOME))) |
                               ((self.df.trans_amt > 100) & (self.df.no_oppo_str.str.contains('理财'))) |
                               ((self.df.trans_amt < 0) & (self.df.no_oppo_str.str.contains(FINANCING_EXPENSE))) |
                               ((self.df.trans_amt < -100) & (self.df.no_oppo_str.str.contains('理财')))]
        financing_list = financing_df.index.tolist()
        self.df.loc[financing_list, 'financing'] = "理财行为"

        # 其他画像之房产买卖
        house_sale_df = self.df[(self.df.concat_str.str.contains(HOUSE_TRADE)) &
                                (~self.df.concat_str.str.contains(HOUSE_TRADE_EXCEPT_1)) &
                                (self.df.opponent_name.astype(str).str.contains(HOUSE_OPPO)) &
                                (self.df.trans_amt.abs() >= 2e4)]
        house_sale_list = house_sale_df.index.tolist()
        self.df.loc[house_sale_list, 'house_sale'] = "房产买卖"

        # 其他画像之与本行交易
        self.df.loc[self.df[(self.df.opponent_name == '北部湾银行')].index.tolist(), 'bank_intra_trans'] = '本行交易'

        usual_col_list = ['big_in_out', 'fast_in_out', 'family_risk', 'financing', 'house_sale']
        self.df['usual_trans_type'] = self.df.apply(
            lambda x: ','.join([x[y] for y in usual_col_list if y in x and pd.notna(x[y])]), axis=1)
        self.df.drop([x for x in usual_col_list if x in self.df], axis=1, inplace=True)

    def _unusual_type_label_third_pay(self):
        """
        v2 优化：向量化日期格式化
        """
        self.df['date'] = self.df['trans_time'].dt.strftime('%Y-%m-%d')
        self.df['unusual_trans_type'] = \
            pd.Series(np.where((self.df['opponent_name'].str.contains(GAMBLE)) &
                               (~self.df['opponent_name'].str.contains("收费站")), '博彩', '')) + ';' + \
            pd.Series(np.where((self.df['opponent_name'].str.contains(AMUSEMENT)) &
                               (self.df['trans_amt'] < 0) &
                               (~self.df['opponent_name'].str.contains(AMUSEMENT_EXCEPT)), '娱乐', '')) + ';' + \
            pd.Series(np.where((self.df['opponent_name'].str.contains(CASE_DISPUTES)) &
                               (self.df['trans_amt'] < 0), '案件纠纷', '')) + ';' + \
            pd.Series(np.where(((self.df['opponent_name'].str.contains(SECURITY_FINES)) &
                                (~self.df['opponent_name'].str.contains(SECURITY_FINES_EXCEPT))) |
                               ((self.df['opponent_name'].str.contains(SECURITY_EXPENSE_FINES)) &
                                (self.df['trans_amt'] < 0)), '治安罚款', '')) + ';' + \
            pd.Series(np.where((self.df['opponent_name'].str.contains(INSURANCE_CLAIMS)), '保险理赔', '')) + ';' + \
            pd.Series(np.where((self.df['opponent_name'].str.contains(STOCK_OPPONENT_NAME)) &
                               (self.df['remark'].str.contains(STOCK_REMARK)), '股票期货', '')) + ';' + \
            pd.Series(np.where((self.df['trans_amt'] < 0) &
                               (((self.df['opponent_name'].str.contains(HOSPITAL)) &
                                 (~self.df['opponent_name'].str.contains(HOSPITAL_EXCEPT))) |
                                ((self.df['opponent_name'].str.contains(HOSPITAL_2)) &
                                 (~self.df['opponent_name'].str.contains(HOSPITAL_EXCEPT_2)))), '医院', '')) + ';' + \
            pd.Series(np.where((self.df['trans_amt'] < 0) &
                               (self.df['opponent_name'].str.contains(REWARD)) &
                               (~self.df['opponent_name'].str.contains(REWARD_EXCEPT)), '直播打赏', '')) + ';' + \
            pd.Series(np.where((self.df['concat_str'].str.contains(NORITOMO)), '典当', '')) + ';' + \
            pd.Series(np.where((self.df['trans_amt'] > 0) &
                               (self.df['opponent_name'].str.contains(COUPON_CLIPPER_1)) &
                               (self.df['opponent_name'].str.contains(COUPON_CLIPPER_2)), '薅羊毛', '')) + ';' + \
            pd.Series(np.where((self.df['trans_amt'] > 0) &
                               (self.df['concat_str'].str.contains(Un_Operating_Income)), '营业外收入', ''))
        # 全部未命中的行赋值为空值
        self.df['unusual_trans_type'] = np.where(self.df['unusual_trans_type'].str.replace(';', '') == '',
                                                 None, self.df['unusual_trans_type'])

        # 成本支出项
        self.df['cost_type'] = np.where(
            (self.df['trans_amt'] < 0) & (self.df['opponent_name'].str.contains(SALARY)), '工资',
            np.where((self.df['opponent_name'].str.contains(UTILITIES)) & (self.df['trans_amt'] < 0) & (
                ~self.df['opponent_name'].str.contains(UTILITIES_EXCEPT)), '水电',
                     np.where((self.df['opponent_name'].str.contains(TAX)) & (self.df['trans_amt'] < 0) & (
                         ~self.df['opponent_name'].str.contains(TAX_EXCEPT)), '税费',
                              np.where((self.df['opponent_name'].str.contains(RENT)) & (self.df['trans_amt'] < 0) &
                                       (~self.df['opponent_name'].str.contains(RENT_EXCEPT)), '房租',
                                       np.where((self.df['opponent_name'].str.contains(SOCIAL_INSURANCE)) & (
                                                   self.df['trans_amt'] < 0), '保险',
                                                np.where((self.df['opponent_name'].str.contains(GONGJIJIN)) & (
                                                            self.df['trans_amt'] < 0), '公积金',
                                                         np.where((self.df['opponent_name'].str.contains(VARIABLE_COST)) & (self.df['trans_amt'] < 0) & (
                                                                 ~self.df['opponent_name'].str.contains(
                                                                     VARIABLE_COST_EXCEPT)), '可变成本', None)))))))
        # self.df['cost_type'] = np.where(
        #     (self.df['trans_amt'] < 0) & (self.df['opponent_name'].str.contains(SALARY)), '工资', np.where(
        #         (self.df['opponent_name'].str.contains(UTILITIES)) & (self.df['trans_amt'] < 0) &
        #         (~self.df['opponent_name'].str.contains(UTILITIES_EXCEPT)), '水电', np.where(
        #             (self.df['opponent_name'].str.contains(TAX)) & (self.df['trans_amt'] < 0) &
        #             (~self.df['opponent_name'].str.contains(TAX_EXCEPT)), '税费', np.where(
        #                 (self.df['opponent_name'].str.contains(RENT)) & (self.df['trans_amt'] < -500) &
        #                 (~self.df['opponent_name'].str.contains(RENT_EXCEPT)), '房租', np.where(
        #                     (self.df['opponent_name'].str.contains(INSURANCE)) &
        #                     (self.df['trans_use'] == '商户消费') & (self.df['trans_amt'] < 0), '保险',
        #                     np.where((self.df['opponent_name'].str.contains(VARIABLE_COST)) &
        #                              (self.df['trans_amt'] < 0), '可变成本', None))))))
        # for row in self.df.itertuples():
        #     opponent_name = getattr(row, 'opponent_name')
        #     remark = getattr(row, 'remark')
        #     trans_amt = getattr(row, 'trans_amt')
        #     # 异常交易类型
        #     unusual_type = []
        #     # 医院
        #     if ((re.search(HOSPITAL, opponent_name) and re.search(HOSPITAL_EXCEPT, opponent_name) is None) or
        #             re.search(HOSPITAL, remark)) and trans_amt < 0:
        #         unusual_type.append('医院')
        #     # 娱乐
        #     if re.search(AMUSEMENT, opponent_name) or re.search(AMUSEMENT, remark):
        #         unusual_type.append('娱乐')
        #     # 博彩
        #     if re.search(GAMBLE, opponent_name) or re.search(GAMBLE, remark):
        #         unusual_type.append('博彩')
        #     # 股票期货
        #     if (re.search(STOCK_OPPONENT_NAME, opponent_name) or re.search(STOCK_REMARK, remark)) \
        #             and re.search(WXZFB_STOCK_OPPONENT_NAME_EXCEPT, opponent_name) is None:
        #         unusual_type.append('股票期货')
        #     # 写入原df
        #     if len(unusual_type) > 0:
        #         self.df.loc[row.Index, 'unusual_trans_type'] = ';'.join(unusual_type)
        #     else:
        #         self.df.loc[row.Index, 'unusual_trans_type'] = None

    @staticmethod
    def _opponent_type(op_name):
        if len(op_name) > 6 and re.search(ENT_TYPE, op_name) is not None:
            return 2
        else:
            if len(op_name) <= 15:
                cleaned_name = re.sub(TYPE_EXCEPT_1, '', op_name)
                if re.match(TYPE_START_1, cleaned_name):
                    cleaned_name = re.sub(TYPE_EXCEPT_2, '', cleaned_name)
                elif re.match(TYPE_START_2, cleaned_name):
                    cleaned_name = cleaned_name.split()[-1]
                else:
                    cleaned_name = re.sub(r' ', '', cleaned_name)
                if 2 <= len(cleaned_name) <= 3:
                    if re.search(TYPE_EXCEPT_3, cleaned_name) is None and \
                            re.match(TYPE_EXCEPT_4, cleaned_name) is None:
                        return 1

    def _in_out_order(self):
        """
        v2 优化：合并groupby操作，使用merge替代逐行loc设置排序
        """
        # 预编译正则
        stronger_rel_pattern = '|'.join(STRONGER_RELATIONSHIP)
        unusual_oppo_pattern = '|'.join(UNUSUAL_OPPO_NAME)

        base_filter = (
            pd.notnull(self.df.opponent_name) &
            pd.isna(self.df.loan_type) &
            pd.isna(self.df.unusual_trans_type)
        )
        income_df = self.df[base_filter & (self.df.trans_amt > 0)].copy()
        expense_df = self.df[base_filter & (self.df.trans_amt < 0)].copy()

        exclude_cond = (
            income_df.relationship.astype(str).str.contains(stronger_rel_pattern) |
            income_df.opponent_name.astype(str).str.contains(unusual_oppo_pattern)
        )
        income_df = income_df[~exclude_cond]

        exclude_cond_exp = (
            expense_df.relationship.astype(str).str.contains(stronger_rel_pattern) |
            expense_df.opponent_name.astype(str).str.contains(unusual_oppo_pattern)
        )
        expense_df = expense_df[~exclude_cond_exp]

        # 按 opponent_type 拆分
        income_per_df = income_df[income_df.opponent_type == 1]
        income_com_df = income_df[income_df.opponent_type == 2]
        expense_per_df = expense_df[expense_df.opponent_type == 1]
        expense_com_df = expense_df[expense_df.opponent_type == 2]

        # 用字典映射实现批量排序赋值
        def _build_order_map(df, agg_col='trans_amt', agg_func='sum', ascending=False, top_k=20):
            return {
                name: idx + 1
                for idx, name in enumerate(
                    df.groupby('opponent_name')[agg_col].agg(agg_func)
                    .sort_values(ascending=ascending).index.tolist()[:top_k]
                )
            }

        # 按交易笔数排序（count）
        income_per_cnt_map = _build_order_map(income_per_df, agg_func='count', ascending=False)
        income_com_cnt_map = _build_order_map(income_com_df, agg_func='count', ascending=False)
        expense_per_cnt_map = _build_order_map(expense_per_df, agg_func='count', ascending=False)
        expense_com_cnt_map = _build_order_map(expense_com_df, agg_func='count', ascending=False)

        # 按交易金额排序（sum）
        income_per_amt_map = _build_order_map(income_per_df, agg_func='sum', ascending=False)
        income_com_amt_map = _build_order_map(income_com_df, agg_func='sum', ascending=False)
        expense_per_amt_map = _build_order_map(expense_per_df, agg_func='sum', ascending=True)
        expense_com_amt_map = _build_order_map(expense_com_df, agg_func='sum', ascending=True)

        # 使用 map 批量赋值（比逐行循环快得多）
        self.df['income_cnt_order'] = self.df['opponent_name'].map(
            lambda x: income_per_cnt_map.get(x) or income_com_cnt_map.get(x)
        )
        self.df['expense_cnt_order'] = self.df['opponent_name'].map(
            lambda x: expense_per_cnt_map.get(x) or expense_com_cnt_map.get(x)
        )
        self.df['income_amt_order'] = self.df['opponent_name'].map(
            lambda x: income_per_amt_map.get(x) or income_com_amt_map.get(x)
        )
        self.df['expense_amt_order'] = self.df['opponent_name'].map(
            lambda x: expense_per_amt_map.get(x) or expense_com_amt_map.get(x)
        )

    @staticmethod
    def label_no(row):
        trans_amt = getattr(row, 'trans_amt')
        loan_type = getattr(row, 'loan_type') if pd.notna(getattr(row, 'loan_type')) else ''
        unusual_trans_type = getattr(row, 'unusual_trans_type') if pd.notna(getattr(row, 'unusual_trans_type')) else ''
        usual_trans_type = getattr(row, 'usual_trans_type') if pd.notna(getattr(row, 'usual_trans_type')) else ''
        relationship = getattr(row, 'relationship') if pd.notna(getattr(row, 'relationship')) else ''
        is_interest = getattr(row, 'is_interest') if pd.notna(getattr(row, 'is_interest')) else 0
        cost_type = getattr(row, 'cost_type') if pd.notna(getattr(row, 'cost_type', None)) else ''
        if trans_amt > 0:
            if relationship != '':
                label_no = '01' + RELATIONSHIP_LABEL.get(relationship, '010105')
            elif loan_type != '':
                label_no = LOAN_TYPE_INCOME_LABEL.get(loan_type, '01010200')
            elif unusual_trans_type != '':
                label_no = ';'.join([SPECIAL_INCOME_TRANS_TYPE_LABEL.get(label, '01010300')
                                     for label in unusual_trans_type.split(';')])
            elif usual_trans_type != '':
                label_no = ';'.join(['01' + USUAL_TRANS_TYPE_LABEL.get(label, '020100')
                                     for label in usual_trans_type.split(';')])
            elif is_interest == 1:
                label_no = '01020201'
            else:
                label_no = '01020202'
        else:
            if relationship != '':
                label_no = '02' + RELATIONSHIP_LABEL.get(relationship, '010105')
            elif loan_type != '':
                label_no = LOAN_TYPE_EXPENSE_LABEL.get(loan_type, '02010300')
            elif unusual_trans_type != '':
                label_no = ';'.join([SPECIAL_EXPENSE_TRANS_TYPE_LABEL.get(label, '02010400')
                                     for label in unusual_trans_type.split(';')])
            elif cost_type != '':
                label_no = COST_TYPE_LABEL.get(cost_type, '02020201')
            elif usual_trans_type != '':
                label_no = ';'.join(['02' + USUAL_TRANS_TYPE_LABEL.get(label, '020100')
                                     for label in usual_trans_type.split(';')])
            else:
                label_no = '02020201'
        return label_no.split(';')

    def save_raw_data(self):
        """
        v2 优化：向量化日期操作（dt.date/dt.strftime替代apply）
        """
        # 原始数据列名
        self.df['flow_id'] = self.df['id']
        self.df['account_id'] = self.account_id
        self.df['trans_flow_src_type'] = np.where(self.df['trans_flow_src_type'].isin([2, 3]), 1, 0)
        # 向量化日期操作
        self.df['trans_date'] = self.df['trans_time'].dt.date
        self.df['trans_time'] = self.df['trans_time'].dt.strftime('%H:%M:%S')
        self.df['remark_type'] = self.df['remark']
        self.df['phone'] = None
        self.df['is_sensitive'] = np.where((pd.notna(self.df['loan_type'])) |
                                           (pd.notna(self.df['unusual_trans_type'])), 1, None)
        self.df['create_time'] = self.create_time
        self.df['update_time'] = self.create_time
        self.label_list = self.df.to_dict('records')
        for row in self.df.itertuples():
            label_dict = dict()
            label_dict['trans_flow_id'] = getattr(row, 'id')
            label_no_list = self.label_no(row)
            label_dict['created_date'] = self.create_time
            label_dict['label_no'] = label_no_list[0] if len(label_no_list) > 0 else 0
            parts = []
            lt = getattr(row, 'loan_type', None)
            if pd.notna(lt):
                parts.extend(['#' + i + '#' for i in str(lt).split(',') if i])
            ut = getattr(row, 'unusual_trans_type', None)
            if pd.notna(ut):
                parts.extend(['#' + i + '#' for i in str(ut).split(';') if i])
            uu = getattr(row, 'usual_trans_type', None)
            if pd.notna(uu):
                parts.extend(['#' + i + '#' for i in str(uu).split(',') if i])
            label_name_join = ';'.join(parts)
            label_dict['label_name'] = label_name_join if label_name_join != '' else '#其他经营#'
            self.trans_label_list.append(label_dict)
