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
        :return:
        """
        length = len(self.query_data_array)
        self.relation_dict = dict()
        self.relation_dict[self.user_name] = 'U_PERSONAL' if self.user_type == 'PERSONAL' else 'U_COMPANY'
        for i in range(length):
            temp = self.query_data_array[i]
            # base_type_detail = base_type_mapping.get(temp['baseTypeDetail'])
            # 保存英文base_type
            base_type_detail = temp['baseTypeDetail']
            # if base_type_detail != '担保人':
            name = ''.join([y if y not in '\u0000\t\n\x00\\/*.+?' else f'\\{y}' for y in temp['name']])
            if name in ['*', '', '.', '?']:
                name = f'\\{name}'
            self.relation_dict[name] = base_type_detail

            # if base_type_detail in ['借款人配偶', '借款企业实际控制人配偶']:
            #     self.spouse_name = str(temp['name'])
            if base_type_detail in ['U_PER_SP_PERSONAL', 'U_COM_CT_SP_PERSONAL']:
                self.spouse_name = str(temp['name'])

    def _isrelationship(self):
        """
        本模块获取关联关系
        """
        for i, v in self.relation_dict.items():
            self.df.loc[self.df['opponent_name'].astype(str).str.contains(i), 'relationship'] = v

    def _loan_type_label(self):
        """
        包括交易对手类型标签opponent_type,贷款类型标签loan_type,是否还款标签is_repay,是否结息标签is_interest
        是否结息前一周标签is_before_interest_repay
        v1.1,调整先后顺序，补充部分字符
        v1.2, 调整字符
        :return:
        """
        concat_list = ['opponent_name', 'trans_channel', 'trans_type', 'trans_use', 'remark']
        self.df[concat_list] = self.df[concat_list].fillna('').astype(str)
        # 交易对手标签赋值,1个人,2企业,其他为空
        self.df['opponent_type'] = self.df['opponent_name'].apply(self._opponent_type)
        self.df['year_month'] = self.df['trans_time'].apply(lambda x: format(x, '%Y-%m'))
        self.df['year'] = self.df['trans_time'].apply(lambda x: x.year)
        self.df['month'] = self.df['trans_time'].apply(lambda x: x.month)
        self.df['day'] = self.df['trans_time'].apply(lambda x: x.day)
        # 将字符串列合并到一起
        self.df['concat_str'] = self.df['opponent_name'] + ';' + self.df['trans_channel'] + ';' + \
            self.df['trans_type'] + ';' + self.df['trans_use'] + ';' + self.df['remark']
        # 贷款类型赋值,优先级从上至下
        # 我司相关机构需从多头中剔除
        # our_inst = "重庆中金同盛小额贷款|磁石供应链商业保理|晋福融资担保|孚厘|中金同盛商业保理"
        our_inst = "￥￥￥$$$$"  # 占位符，必不可能命中
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
        # self.df.loc[(self.df.trans_amt > 0) &
        #             ((self.df.opponent_name.str.contains(BANK_LOAN_OPPONENT_NAME)) |
        #              ((self.df.opponent_name.isin([self.user_name, ""])) &
        #               (self.df.remark.str.contains(BANK_LOAN_REMARK)))) &
        #             ((~self.df.concat_str.str.contains(BANK_LOAN_CONCAT_STR_EXCEPT)) |
        #              (self.df.concat_str.str.contains(BANK_LOAN_CONCAT_STR_COMPATIBLE))) &
        #             (pd.isnull(self.df.loan_type)) &
        #             (~self.df.opponent_name.astype(str).str.contains(BANK_LOAN_OPPONENT_NAME_EXCEPT)), 'bank_loan'] = 1
        # 银行还款
        self.df.loc[(self.df.trans_amt < 0) &
                    (((self.df.concat_str.str.contains("还贷|自动还款|贷款利息|约定还款|贷款回收|批量代扣|约定还款|收回利息|贷款业务|批量扣款|还本金")) &
                      (self.df.opponent_name.isin([self.user_name, ""]))) |
                     ((self.df.concat_str.str.contains(BANK_REPAY_CONCAT_STR)) &
                      (self.df.opponent_name.str.contains(BANK_REPAY_OPPONENT_NAME))) |
                     (self.df.opponent_name.str.contains("信用卡还款|贷记卡本转贷|信用卡转账还款"))) &
                    (pd.isnull(self.df.loan_type)), 'bank_repay'] = 1

        # self.df.loc[(self.df.trans_amt < 0) &
        #             ((((self.df.opponent_name.str.contains(BANK_REPAY_OPPONENT_NAME)) |
        #                ((self.df.opponent_name.isin([self.user_name, ""])) &
        #                 (self.df.concat_str.str.contains(BANK_REPAY_CONCAT_STR)))) &
        #               ((~self.df.concat_str.str.contains(BANK_REPAY_CONCAT_STR_EXCEPT)) |
        #                (self.df.concat_str.str.contains(BANK_REPAY_CONCAT_STR_COMPATIBLE))) &
        #               (~self.df.opponent_name.astype(str).str.contains(BANK_REPAY_OPPONENT_NAME_EXCEPT))) |
        #              self.df.opponent_name.str.contains("信用卡还款")) &
        #             (pd.isnull(self.df.loan_type)), 'bank_repay'] = 1
        # 受托支付
        self.df.loc[(self.df.trans_amt < 0) &
                    (self.df.concat_str.str.contains(ENTRUSTED_PAY)), 'entrust_pay'] = 1
        bank_income = self.df[self.df.bank_loan == 1]
        entrust_list = set()
        if not bank_income.empty:
            for row in bank_income.itertuples():
                temp_amt = getattr(row, 'trans_amt')
                temp_dt = getattr(row, 'trans_time')
                day3_after = pd.to_datetime(temp_dt + datetime.timedelta(days=3))
                temp_df = self.df[(self.df.trans_time > temp_dt) &
                                  (self.df.trans_time < day3_after) &
                                  (self.df.trans_amt == -temp_amt) &
                                  (~self.df.concat_str.str.contains(ENTRUSTED_PAY)) &
                                  (self.df.opponent_name == "")]
                if not temp_df.empty:
                    temp_df.reset_index(drop=False, inplace=True)
                    temp_index = temp_df.loc[0, 'index']
                    entrust_list.add(temp_index)
        self.df.loc[list(entrust_list), 'entrust_pay'] = 1

        # 银行
        self.df.loc[(self.df.bank_loan == 1) |
                    ((self.df.bank_repay == 1)
                     & (self.df.entrust_pay != 1)), 'loan_type'] = "银行"
        # 第三方支付
        self.df.loc[(((self.df['concat_str'].str.contains(THIRD_REPAY_1)) &
                      (self.df['concat_str'].str.contains(THIRD_REPAY_2)) &
                      (~self.df['concat_str'].str.contains(THIRD_REPAY_EXCEPT))) |
                     self.df['concat_str'].str.contains(THIRD_REPAY_3)) &
                    (pd.isnull(self.df.loan_type)), 'loan_type'] = '第三方支付'
        # 其他金融
        self.df.loc[
            (((self.df['concat_str'].str.contains(OTHER_FINANCE)) &
              (~self.df['concat_str'].str.contains(OTHER_FINANCE_EXCEPT))) |
             ((self.df['concat_str'].str.contains(OTHER_FINANCE_PER)) & (self.df.opponent_type != 1)) |
             ((self.df['opponent_name'].str.contains('|'.join(self.relation_dict.keys()))) &
              (self.df['concat_str'].str.contains(OTHER_FINANCE_RELATION)))) &
            (~self.df['trans_channel'].str.contains(OTHER_FINANCE_CHANNEL_EXCEPT)) &
            (pd.isnull(self.df.loan_type)) &
            (~self.df.opponent_name.str.contains(OTHER_FINANCE_ENT_EXCEPT)), 'loan_type'] = '其他金融'
        # 民间借贷
        self.df.loc[(self.df['trans_amt'].apply(lambda x: abs(x)) > 500) &
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
        amt_group = self.df[
            (self.df['trans_amt'].apply(lambda x: abs(x)) > MIN_PRIVATE_LENDING) &
            (~self.df['concat_str'].str.contains('|'.join(self.relation_dict.keys()))) &
            (pd.notnull(self.df['opponent_type'])) &
            (~self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_2)) &
            (self.df['opponent_name'] != '') &
            (~self.df['opponent_name'].str.contains(PRIVATE_LENDING_OPPONENT_NAME)) &
            (pd.isnull(self.df.loan_type))
            ].groupby(['opponent_name', 'trans_amt'], as_index=False).agg({'month': len})
        amt_group = amt_group[amt_group['month'] >= MIN_CONTI_MONTHS]
        if amt_group.shape[0] > 0:
            mask = self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_2)
            for row in amt_group.itertuples():
                temp_name = getattr(row, 'opponent_name')
                temp_amt = getattr(row, 'trans_amt')

                # 用掩码筛选出所有匹配的行
                filtered_df = self.df[mask]
                filtered_name = set(filtered_df['opponent_name'])
                temp_df = self.df[(self.df['opponent_name'] == temp_name) &
                                  (self.df['trans_amt'] == temp_amt)]
                temp_df = temp_df[~temp_df['opponent_name'].isin(filtered_name)]
                if not temp_df.empty:
                    temp_df.reset_index(drop=False, inplace=True)
                    last_month = temp_df['trans_time'].tolist()[0]
                    temp_df.loc[0, 'conti'] = 1
                    conti_list = set()
                    temp_cnt = 1
                    now_index = 1
                    for index in temp_df.index.tolist()[1:]:
                        this_month = temp_df.loc[index, 'trans_time']
                        temp_interval = (this_month.year - last_month.year) * 12 + this_month.month - last_month.month
                        if temp_interval <= 1:
                            temp_df.loc[index, 'conti'] = now_index
                            if temp_interval == 1:
                                temp_cnt += 1
                                if temp_cnt >= MIN_CONTI_MONTHS:
                                    conti_list.add(now_index)
                        else:
                            now_index += 1
                            temp_df.loc[index, 'conti'] = now_index
                            temp_cnt = 1
                        last_month = this_month
                    conti_list = list(conti_list)
                    if len(conti_list) == 0:
                        continue
                    for i in conti_list:
                        conti_df = temp_df[temp_df['conti'] == i]
                        max_interval = conti_df['day'].max() - conti_df['day'].min()
                        if max_interval <= MAX_INTERVAL_DAYS:
                            if 'loan_type' not in conti_df.columns:
                                loan_type = '民间借贷'
                            else:
                                conti_type_df = conti_df[pd.notna(conti_df['loan_type'])]
                                if conti_type_df.shape[0] > 0:
                                    loan_type = conti_type_df['loan_type'].tolist()[0]
                                else:
                                    loan_type = '民间借贷'
                            self.df.loc[conti_df['index'].tolist(), 'loan_type'] = loan_type

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

        # 是否还款到期前一周标签
        repay_date_list = self.df[(self.df['is_repay'] == 1)]['trans_time'].tolist()
        for repay_date in repay_date_list:
            seven_days_ago = pd.to_datetime((repay_date - datetime.timedelta(days=7)).date())
            self.df.loc[(self.df.trans_time < repay_date) &
                        (self.df.trans_time >= seven_days_ago), 'is_before_interest_repay'] = 1
        self.df.drop(['year', 'month', 'day'], axis=1, inplace=True)

    def _loan_type_label_third_pay(self):
        concat_list = ['opponent_name', 'remark']
        self.df[concat_list] = self.df[concat_list].fillna('').astype(str)
        self.df['is_interest'] = None
        # 交易对手标签赋值,1个人,2企业,其他为空
        self.df['opponent_type'] = self.df['opponent_name'].apply(self._opponent_type)
        self.df['year_month'] = self.df['trans_time'].apply(lambda x: format(x, '%Y-%m'))
        self.df['year'] = self.df['trans_time'].apply(lambda x: x.year)
        self.df['month'] = self.df['trans_time'].apply(lambda x: x.month)
        self.df['day'] = self.df['trans_time'].apply(lambda x: x.day)
        # 将字符串列合并到一起
        self.df['concat_str'] = self.df['opponent_name'] + ';' + self.df['remark']
        # 贷款类型赋值,优先级从上至下
        # 我司相关机构需从多头中剔除
        # our_inst = "重庆中金同盛小额贷款|磁石供应链商业保理|晋福融资担保|孚厘|中金同盛商业保理"
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
        self.df.loc[(self.df['trans_amt'].apply(lambda x: abs(x)) > 500) &
                    (self.df['concat_str'].str.contains(PRIVATE_LENDING)) &
                    (~self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_WX)) &
                    (pd.isnull(self.df.loan_type)), 'loan_type'] = '民间借贷'
        amt_group = self.df[
            (self.df['trans_amt'].apply(lambda x: abs(x)) > MIN_PRIVATE_LENDING) &
            (~self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_2)) &
            (self.df['opponent_name'] != '') &
            (~self.df['opponent_name'].str.contains(PRIVATE_LENDING_OPPONENT_NAME)) &
            (pd.isnull(self.df.loan_type))
            ].groupby(['opponent_name', 'trans_amt'], as_index=False).agg({'month': len})
        amt_group = amt_group[amt_group['month'] >= MIN_CONTI_MONTHS]
        if amt_group.shape[0] > 0:
            mask = self.df['concat_str'].str.contains(PRIVATE_LENDING_EXCEPT_2)
            for row in amt_group.itertuples():
                temp_name = getattr(row, 'opponent_name')
                temp_amt = getattr(row, 'trans_amt')
                # 用掩码筛选出所有匹配的行
                filtered_df = self.df[mask]
                filtered_name = set(filtered_df['opponent_name'])
                temp_df = self.df[(self.df['opponent_name'] == temp_name) &
                                  (self.df['trans_amt'] == temp_amt)]
                temp_df = temp_df[~temp_df['opponent_name'].isin(filtered_name)]
                if not temp_df.empty:
                    temp_df.reset_index(drop=False, inplace=True)
                    last_month = temp_df['trans_time'].tolist()[0]
                    temp_df.loc[0, 'conti'] = 1
                    conti_list = set()
                    temp_cnt = 1
                    now_index = 1
                    for index in temp_df.index.tolist()[1:]:
                        this_month = temp_df.loc[index, 'trans_time']
                        temp_interval = (this_month.year - last_month.year) * 12 + this_month.month - last_month.month
                        if temp_interval <= 1:
                            temp_df.loc[index, 'conti'] = now_index
                            if temp_interval == 1:
                                temp_cnt += 1
                                if temp_cnt >= MIN_CONTI_MONTHS:
                                    conti_list.add(now_index)
                        else:
                            now_index += 1
                            temp_df.loc[index, 'conti'] = now_index
                            temp_cnt = 1
                        last_month = this_month
                    conti_list = list(conti_list)
                    if len(conti_list) == 0:
                        continue
                    for i in conti_list:
                        conti_df = temp_df[temp_df['conti'] == i]
                        max_interval = conti_df['day'].max() - conti_df['day'].min()
                        if max_interval <= MAX_INTERVAL_DAYS:
                            if 'loan_type' not in conti_df.columns:
                                loan_type = '民间借贷'
                            else:
                                conti_type_df = conti_df[pd.notna(conti_df['loan_type'])]
                                if conti_type_df.shape[0] > 0:
                                    loan_type = conti_type_df['loan_type'].tolist()[0]
                                else:
                                    loan_type = '民间借贷'
                            self.df.loc[conti_df['index'].tolist(), 'loan_type'] = loan_type

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
        self.df['date'] = self.df['trans_time'].apply(lambda x: datetime.datetime.strftime(x, '%Y-%m-%d'))
        no_oppo_list = ['trans_channel', 'trans_type', 'trans_use', 'remark']
        self.df[no_oppo_list] = self.df[no_oppo_list].fillna('').astype(str)
        # 将字符串列合并到一起
        self.df['no_oppo_str'] = self.df['trans_channel'] + ';' + self.df['trans_type'] + ';' + \
            self.df['trans_use'] + ';' + self.df['remark']

        # 其他画像之是否整进整出标签
        # 20220913 整进整出金额调整为10万的整万
        big_in_out_df = self.df[(self.df.trans_amt.apply(lambda x: abs(x)) >= 100000) &
                                (self.df.trans_amt.apply(lambda x: x % 10000) == 0) &
                                (~self.df.concat_str.str.contains(BIG_IN_OUT_EXCEPT))]
        big_in_date = big_in_out_df[big_in_out_df.trans_amt > 0]['date'].tolist()
        big_out_date = big_in_out_df[big_in_out_df.trans_amt < 0]['date'].tolist()
        big_in_out_date = list(set(big_in_date).intersection(set(big_out_date)))
        big_in_out_list = big_in_out_df[big_in_out_df.date.isin(big_in_out_date)].index.tolist()
        self.df.loc[big_in_out_list, 'big_in_out'] = "整进整出"

        # 其他画像之快进快出标签
        # 20220913 快进快出金额调整为20万
        fast_in_out_df = self.df[(self.df.trans_amt.apply(lambda x: abs(x)) >= 200000) &
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
        # 房产买卖取值逻辑：组合列含有买房、卖房、首付、售房、房地产、置业、购房、认筹、房产评估费、房屋评估费、房款 且不包含装修 且交易对手不包含买房、卖房、首付、售房、房地产、置业、购房、认筹 且交易对手不为空
        house_sale_df = self.df[(self.df.concat_str.str.contains(HOUSE_TRADE)) &
                                (~self.df.concat_str.str.contains(HOUSE_TRADE_EXCEPT_1)) &
                                (self.df.opponent_name.astype(str).str.contains(HOUSE_OPPO)) &
                                (self.df.trans_amt.abs() >= 2e4)]
        house_sale_list = house_sale_df.index.tolist()
        self.df.loc[house_sale_list, 'house_sale'] = "房产买卖"

        # 其他画像之与本行交易
        # 取交易对手为北部湾银行
        self.df.loc[self.df[(self.df.opponent_name == '北部湾银行')].index.tolist(), 'bank_intra_trans'] = '本行交易'

        usual_col_list = ['big_in_out', 'fast_in_out', 'family_risk', 'financing', 'house_sale']
        self.df['usual_trans_type'] = self.df.apply(
            lambda x: ','.join([x[y] for y in usual_col_list if y in x and pd.notna(x[y])]), axis=1)
        self.df.drop([x for x in usual_col_list if x in self.df], axis=1, inplace=True)

    def _unusual_type_label_third_pay(self):
        self.df['date'] = self.df['trans_time'].apply(lambda x: datetime.datetime.strftime(x, '%Y-%m-%d'))
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
        income_per_df = self.df[(pd.notnull(self.df.opponent_name)) & (self.df.trans_amt > 0) &
                                (self.df.opponent_type == 1) & (pd.isna(self.df.loan_type)) & (
                                    pd.isna(self.df.unusual_trans_type)) &
                                (~self.df.relationship.astype(str).str.contains('|'.join(STRONGER_RELATIONSHIP))) & (
                                    ~self.df.opponent_name.astype(str).str.contains('|'.join(UNUSUAL_OPPO_NAME)))]
        expense_per_df = self.df[(pd.notnull(self.df.opponent_name)) & (self.df.trans_amt < 0) &
                                 (self.df.opponent_type == 1) & (pd.isna(self.df.loan_type)) & (
                                     pd.isna(self.df.unusual_trans_type)) &
                                 (~self.df.relationship.astype(str).str.contains('|'.join(STRONGER_RELATIONSHIP))) & (
                                     ~self.df.opponent_name.astype(str).str.contains('|'.join(UNUSUAL_OPPO_NAME)))]
        income_com_df = self.df[(pd.notnull(self.df.opponent_name)) & (self.df.trans_amt > 0) &
                                (self.df.opponent_type == 2) & (pd.isna(self.df.loan_type)) & (
                                    pd.isna(self.df.unusual_trans_type))]
        income_com_df = income_com_df[
            (~income_com_df.opponent_name.astype(str).str.contains('|'.join(UNUSUAL_OPPO_NAME))) &
            (~income_com_df.relationship.astype(str).str.contains('|'.join(STRONGER_RELATIONSHIP)))]
        expense_com_df = self.df[(pd.notnull(self.df.opponent_name)) & (self.df.trans_amt < 0) &
                                 (self.df.opponent_type == 2) & (pd.isna(self.df.loan_type)) & (
                                     pd.isna(self.df.unusual_trans_type))]
        expense_com_df = expense_com_df[
            (~expense_com_df.opponent_name.astype(str).str.contains('|'.join(UNUSUAL_OPPO_NAME))) &
            (~expense_com_df.relationship.astype(str).str.contains('|'.join(STRONGER_RELATIONSHIP)))]
        income_per_cnt_list = income_per_df.groupby(by='opponent_name').agg({'trans_amt': len}). \
                                  sort_values(by='trans_amt', ascending=False).index.tolist()[:20]
        income_per_amt_list = income_per_df.groupby(by='opponent_name').agg({'trans_amt': sum}). \
                                  sort_values(by='trans_amt', ascending=False).index.tolist()[:20]
        expense_per_cnt_list = expense_per_df.groupby(by='opponent_name').agg({'trans_amt': len}). \
                                   sort_values(by='trans_amt', ascending=False).index.tolist()[:20]
        expense_per_amt_list = expense_per_df.groupby(by='opponent_name').agg({'trans_amt': sum}). \
                                   sort_values(by='trans_amt', ascending=True).index.tolist()[:20]
        income_com_cnt_list = income_com_df.groupby(by='opponent_name').agg({'trans_amt': len}). \
                                  sort_values(by='trans_amt', ascending=False).index.tolist()[:20]
        income_com_amt_list = income_com_df.groupby(by='opponent_name').agg({'trans_amt': sum}). \
                                  sort_values(by='trans_amt', ascending=False).index.tolist()[:20]
        expense_com_cnt_list = expense_com_df.groupby(by='opponent_name').agg({'trans_amt': len}). \
                                   sort_values(by='trans_amt', ascending=False).index.tolist()[:20]
        expense_com_amt_list = expense_com_df.groupby(by='opponent_name').agg({'trans_amt': sum}). \
                                   sort_values(by='trans_amt', ascending=True).index.tolist()[:20]
        for i in range(len(income_per_cnt_list)):
            self.df.loc[self.df['opponent_name'] == income_per_cnt_list[i], 'income_cnt_order'] = i + 1
        for i in range(len(income_com_cnt_list)):
            self.df.loc[self.df['opponent_name'] == income_com_cnt_list[i], 'income_cnt_order'] = i + 1
        for i in range(len(expense_per_cnt_list)):
            self.df.loc[self.df['opponent_name'] == expense_per_cnt_list[i], 'expense_cnt_order'] = i + 1
        for i in range(len(expense_com_cnt_list)):
            self.df.loc[self.df['opponent_name'] == expense_com_cnt_list[i], 'expense_cnt_order'] = i + 1
        for i in range(len(income_per_amt_list)):
            self.df.loc[self.df['opponent_name'] == income_per_amt_list[i], 'income_amt_order'] = i + 1
        for i in range(len(income_com_amt_list)):
            self.df.loc[self.df['opponent_name'] == income_com_amt_list[i], 'income_amt_order'] = i + 1
        for i in range(len(expense_per_amt_list)):
            self.df.loc[self.df['opponent_name'] == expense_per_amt_list[i], 'expense_amt_order'] = i + 1
        for i in range(len(expense_com_amt_list)):
            self.df.loc[self.df['opponent_name'] == expense_com_amt_list[i], 'expense_amt_order'] = i + 1

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
        # 原始数据列名
        self.df['flow_id'] = self.df['id']
        self.df['account_id'] = self.account_id
        # self.df['report_req_no'] = self.report_req_no
        self.df['trans_flow_src_type'] = np.where(self.df['trans_flow_src_type'].isin([2, 3]), 1, 0)
        self.df['trans_date'] = self.df['trans_time'].apply(lambda x: x.date())
        self.df['trans_time'] = self.df['trans_time'].apply(lambda x: format(x, '%H:%M:%S'))
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
            # for label_no in label_no_list:
            label_dict['label_no'] = label_no_list[0] if len(label_no_list) > 0 else 0
            loan_type_name_list = [i for i in getattr(row, 'loan_type').split(',')] if pd.notna(getattr(row, 'loan_type')) else []
            unusual_trans_type_name_list = [i for i in getattr(row, 'unusual_trans_type').split(';') if i] if pd.notna(
                getattr(row, 'unusual_trans_type')) else []
            usual_trans_type_name_list = [i for i in getattr(row, 'usual_trans_type').split(',')] if pd.notna(
                getattr(row, 'usual_trans_type')) else []
            label_name_join = ';'.join(
                ['#' + i + '#' for i in loan_type_name_list + unusual_trans_type_name_list + usual_trans_type_name_list if i])
            label_dict['label_name'] = label_name_join if label_name_join != '' else '#其他经营#'
            self.trans_label_list.append(label_dict.copy())
