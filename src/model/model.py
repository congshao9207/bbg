# coding: utf-8
from sqlalchemy import Column, DECIMAL, DateTime, String, Date, Time
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGBLOB
from sqlalchemy.ext.declarative import declarative_base
import pandas as pd
import re

Base = declarative_base()
metadata = Base.metadata


def transform_class_str(params, class_name):
    func_str = class_name + '('
    for k, v in params.items():
        if v is not None and v != '':
            func_str += k + "='" + re.sub(r'[\'"]', '', str(v)) + "',"
    func_str = func_str[:-1]
    func_str += ')'
    value = eval(func_str)
    return value


def transform_flow_str(session, params, class_name):
    f = eval(class_name + "()")
    col_list = [x for x in dir(f) if not x.startswith("_") and x not in ['id', 'metadata', 'registry']]
    start = f"insert into {f.__tablename__}({','.join(col_list)}) values "

    def sql_values(col_val):
        vals = []
        for col in col_list:
            if col in col_val and pd.notna(col_val[col]) and col_val[col] != '':
                vals.append(re.sub(r"(?<![\da-zA-Z]):", '-', f"'{col_val[col]}'"))
            else:
                vals.append('null')
        return f"({','.join(vals)})"
    insert_list = [start + ','.join([sql_values(params[j]) for j in range(i, min(i + 1000, len(params)))])
                   for i in range(0, len(params), 1000)]
    try:
        for ins in insert_list:
            session.execute(ins)
        session.commit()
    except Exception as e:
        session.rollback()
        return e


class OcrTask(Base):
    __tablename__ = 'ocr_task'
    __table_args__ = {'comment': 'OCR识别'}

    id = Column(BIGINT(20), primary_key=True)
    out_req_no = Column(String(32), comment='关联外部请求编号')
    parse_no = Column(String(32), comment='识别任务编号')
    origin_attachment_id = Column(BIGINT(20), comment='源文件ID')
    origin_file_type = Column(String(255), comment='源文件类型')
    result_attachment_id = Column(BIGINT(20), comment='结果文件附件ID')
    result_file_type = Column(String(255), comment='结果文件类型')
    process_status = Column(String(255), comment='处理状态')
    memo = Column(String(128), comment='备注')
    created_date = Column(DateTime, comment='创建时间')
    last_modified_date = Column(DateTime, comment='最后修改时间')

    def set_memo(self, memo):
        if not memo:
            return
        self.memo = memo[0:128]


class SysInfo(Base):
    __tablename__ = 'sys_info'

    id = Column(BIGINT(20), primary_key=True, comment='主键')
    info = Column(String(128))


class TransAccount(Base):
    __tablename__ = 'trans_account'
    __table_args__ = {'comment': '流水账户表'}

    id = Column(BIGINT(20), primary_key=True)
    out_req_no = Column(String(32), comment='外部系请求编号')
    account_name = Column(String(32), comment='主体姓名')
    id_card_no = Column(String(32), comment='主体身份证号')
    id_type = Column(String(32), comment='证件类型ID_CARD_NO, CREDIT_CODE, REG_NO, OTHER')
    bank = Column(String(32), comment='银行名称')
    account_no = Column(String(64), comment='账户号')
    start_time = Column(DateTime, comment='开始时间')
    end_time = Column(DateTime, comment='结束时间')
    trans_flow_type = Column(INTEGER(11), comment='流水类型 1个人；2企业')
    update_time = Column(DateTime, comment='导入时间')
    account_state = Column(INTEGER(11), comment='账户状态 0-作废；1-正常')
    create_time = Column(DateTime, comment='创建时间')
    task_no = Column(String(32), comment='任务编号')
    

class TransAttachment(Base):
    __tablename__ = 'trans_attachment'
    __table_args__ = {'comment': '流水文件内容'}

    id = Column(BIGINT(20), primary_key=True)
    file_type = Column(String(255), comment='文件类型')
    file_md_5 = Column(String(128), comment='文件内容的md5')
    trans_data = Column(LONGBLOB, comment='文件类型')
    trans_data_content_type = Column(String(255))


class TransCallBack(Base):
    __tablename__ = 'trans_call_back'
    __table_args__ = {'comment': '回调记录'}

    id = Column(BIGINT(20), primary_key=True)
    out_req_no = Column(String(32), comment='外部请求编号')
    try_times = Column(INTEGER(11), comment='重试次数')
    process_status = Column(String(255), comment='处理状态')
    memo = Column(String(64), comment='备注')
    created_date = Column(DateTime, comment='创建时间')
    last_modified_date = Column(DateTime, comment='更新时间')


class TransFlow(Base):
    __tablename__ = 'trans_flow'
    __table_args__ = {'comment': '流水明细信息表'}

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20), comment='关联trans_account的id字段')
    out_req_no = Column(String(32), comment='外部系请求编号')
    trans_time = Column(DateTime, comment='交易时间')
    opponent_name = Column(String(255), comment='对方户名')
    trans_amt = Column(DECIMAL(10, 2), comment='交易金额 “+”、“-”代表进账、出账')
    account_balance = Column(DECIMAL(10, 2), comment='账户余额')
    currency = Column(String(16), comment='币种')
    opponent_account_no = Column(String(64), comment='对方账户')
    opponent_account_bank = Column(String(64), comment='对方开户行')
    trans_channel = Column(String(64), comment='交易渠道')
    trans_type = Column(String(64), comment='交易类型')
    file_id = Column(BIGINT(20), comment='关联的⽂件ID')
    trans_use = Column(String(255), comment='交易用途')
    remark = Column(String(255), comment='备注')
    repeated = Column(INTEGER(11), comment='去重标识：1：重复， 0 不重复')
    verif_label = Column(String(64), comment='验证结果 VerifyLabelEnum')
    rel_attachment_id = Column(BIGINT(20), comment='关联的流水文件ID')
    rel_line_num = Column(BIGINT(20), comment='行号')
    create_time = Column(DateTime, comment='创建时间')
    update_time = Column(DateTime, comment='更新时间')


class TransFlowOriginal(Base):
    __tablename__ = 'trans_flow_original'
    __table_args__ = {'comment': '流水明细原始表'}

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20), comment='关联trans_account的id字段')
    out_req_no = Column(String(32), comment='外部系请求编号')
    trans_time = Column(DateTime, comment='交易时间')
    opponent_name = Column(String(255), comment='对方户名')
    trans_amt = Column(DECIMAL(10, 2), comment='交易金额 “+”、“-”代表进账、出账')
    account_balance = Column(DECIMAL(10, 2), comment='账户余额')
    currency = Column(String(16), comment='币种')
    opponent_account_no = Column(String(64), comment='对方账户')
    opponent_account_bank = Column(String(64), comment='对方开户行')
    trans_channel = Column(String(64), comment='交易渠道')
    trans_type = Column(String(64), comment='交易类型')
    trans_use = Column(String(255), comment='交易用途')
    remark = Column(String(255), comment='备注')
    repeated = Column(INTEGER(11), comment='去重标识：1：重复， 0 不重复')
    verif_label = Column(String(64), comment='验证结果 VerifyLabelEnum')
    rel_attachment_id = Column(BIGINT(20), comment='关联的流水文件ID')
    rel_line_num = Column(BIGINT(20), comment='行号')
    create_time = Column(DateTime, comment='创建时间')
    update_time = Column(DateTime, comment='更新时间')


class TransOpenCfg(Base):
    __tablename__ = 'trans_open_cfg'
    __table_args__ = {'comment': '流水开放接口配置'}

    id = Column(BIGINT(20), primary_key=True)
    app_id = Column(String(32), comment='调用方编号')
    call_back_url = Column(String(128), comment='回调URL')
    max_try_times = Column(INTEGER(11), comment='重试次数')
    created_date = Column(DateTime, comment='创建时间')


class TransParseTask(Base):
    __tablename__ = 'trans_parse_task'
    __table_args__ = {'comment': '流水解析任务'}

    id = Column(BIGINT(20), primary_key=True)
    out_apply_no = Column(String(32), comment='关联业务编号')
    group_no = Column(String(32), comment='组编号')
    out_req_no = Column(String(32), comment='外部请求编号')
    account_id = Column(BIGINT(20), comment='账号ID， 关联表 trans_account 表')
    origin_file_name = Column(String(128), comment='原文件名')
    origin_attachment_id = Column(BIGINT(20), comment='文件编号')
    origin_file_type = Column(String(255), comment='文件类型')
    file_hash = Column(String(128), comment='文件hash 由文件内容_客户证件号_银行卡号 计算而来')
    ocr_task_id = Column(BIGINT(20), comment='ocr识别任务ID')
    result_attachment_id = Column(BIGINT(20), comment='ocr处理结果文件')
    trans_flow_src_type = Column(INTEGER(11), comment='文件类型 1: 普通流水文件， 2：支付宝流水文件， 3：微信流水文件"')
    ocr_post_attachment_id = Column(BIGINT(20), comment='pdf对应的excel文件id')
    result_file_type = Column(String(255), comment='结果文件类型')
    rectify = Column(INTEGER(11), comment='是否纠偏: 0: 不纠偏， 1： 纠偏')
    verify_res = Column(String(255), comment='验证结果')
    process_status = Column(String(255), comment='处理状态')
    req_raw_data = Column(String(1024), comment='原始请求报文')
    resp_msg = Column(String(512), comment='处理最终结果应答报文')
    memo = Column(String(128), comment='备注')
    process_memo = Column(String(128), comment='处理备注')
    created_date = Column(DateTime, comment='创建时间')
    last_modified_date = Column(DateTime, comment='最后修改时间')

    def set_memo(self, memo):
        if not memo:
            return
        self.memo = memo[0:128]


class TransApply(Base):
    __tablename__ = 'trans_apply'

    id = Column(BIGINT(20), primary_key=True)
    out_req_no = Column(String(32))
    report_req_no = Column(String(32))
    apply_no = Column(String(32))
    cus_name = Column(String(32))
    related_name = Column(String(32))
    relationship = Column(String(32))
    account_id = Column(BIGINT(20))
    industry = Column(String(32))
    id_card_no = Column(String(32))
    id_type = Column(String(32))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransFlowException(Base):
    __tablename__ = 'trans_flow_exception'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    out_req_no = Column(String(32))
    trans_time = Column(DateTime)
    opponent_name = Column(String(255))
    trans_amt = Column(DECIMAL(16, 4))
    account_balance = Column(DECIMAL(16, 4))
    currency = Column(String(16))
    opponent_account_no = Column(String(32))
    opponent_account_bank = Column(String(16))
    trans_channel = Column(String(16))
    trans_type = Column(String(16))
    trans_use = Column(String(16))
    remark = Column(String(32))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransFlowPortrait(Base):
    __tablename__ = 'trans_flow_portrait'

    id = Column(BIGINT(20), primary_key=True)
    flow_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    account_id = Column(BIGINT(20))
    trans_date = Column(Date)
    trans_time = Column(Time)
    trans_amt = Column(DECIMAL(16, 4))
    account_balance = Column(DECIMAL(16, 4))
    opponent_name = Column(String(64))
    opponent_type = Column(INTEGER(11))
    opponent_account_no = Column(String(32))
    opponent_account_bank = Column(String(32))
    trans_channel = Column(String(64))
    trans_type = Column(String(64))
    trans_use = Column(String(64))
    remark = Column(String(255))
    currency = Column(String(16))
    phone = Column(String(32))
    relationship = Column(String(32))
    is_financing = Column(INTEGER(11))
    is_interest = Column(INTEGER(11))
    loan_type = Column(String(32))
    is_repay = Column(INTEGER(11))
    is_before_interest_repay = Column(INTEGER(11))
    unusual_trans_type = Column(String(16))
    is_sensitive = Column(INTEGER(11))
    cost_type = Column(String(16))
    remark_type = Column(String(255))
    income_cnt_order = Column(INTEGER(11))
    expense_cnt_order = Column(INTEGER(11))
    income_amt_order = Column(INTEGER(11))
    expense_amt_order = Column(INTEGER(11))
    create_time = Column(DateTime)
    update_time = Column(DateTime)
    trans_flow_src_type = Column(INTEGER(11))
    usual_trans_type = Column(String(256))


class TransSingleAbnormalRecovery(Base):
    __tablename__ = 'trans_single_abnormal_recovery'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    flow_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    opponent_name = Column(String(32))
    account_no = Column(String(64))
    abnormal_recovery_id = Column(BIGINT(20))
    abnormal_recovery_label = Column(String(32))
    trans_amt = Column(DECIMAL(16, 4))
    trans_datetime = Column(DateTime)
    remark = Column(String(32))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransSingleCounterpartyPortrait(Base):
    __tablename__ = 'trans_single_counterparty_portrait'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    month = Column(String(16))
    opponent_name = Column(String(32))
    income_amt_order = Column(String(16))
    expense_amt_order = Column(String(16))
    trans_amt = Column(DECIMAL(16, 4))
    trans_month_cnt = Column(INTEGER(11))
    trans_cnt = Column(INTEGER(11))
    trans_mean = Column(DECIMAL(16, 4))
    trans_amt_proportion = Column(DECIMAL(16, 4))
    trans_gap_avg = Column(DECIMAL(16, 4))
    income_amt_proportion = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransSingleLoanPortrait(Base):
    __tablename__ = 'trans_single_loan_portrait'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    loan_type = Column(String(16))
    month = Column(String(16))
    loan_amt = Column(DECIMAL(16, 4))
    loan_cnt = Column(INTEGER(11))
    loan_mean = Column(DECIMAL(16, 4))
    repay_amt = Column(DECIMAL(16, 4))
    repay_cnt = Column(INTEGER(11))
    repay_mean = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransSinglePortrait(Base):
    __tablename__ = 'trans_single_portrait'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    analyse_start_time = Column(DateTime)
    analyse_end_time = Column(DateTime)
    not_full_month = Column(String(16))
    normal_income_amt = Column(DECIMAL(16, 4))
    normal_income_cnt = Column(INTEGER(11))
    normal_income_mean = Column(INTEGER(11))
    normal_income_d_mean = Column(INTEGER(11))
    normal_income_m_mean = Column(INTEGER(11))
    normal_income_m_std = Column(INTEGER(11))
    normal_expense_amt = Column(DECIMAL(16, 4))
    normal_expense_cnt = Column(INTEGER(11))
    income_amt_y_pred = Column(DECIMAL(16, 4))
    relationship_risk = Column(INTEGER(11))
    income_0_to_5_cnt = Column(INTEGER(11))
    income_5_to_10_cnt = Column(INTEGER(11))
    income_10_to_30_cnt = Column(INTEGER(11))
    income_30_to_50_cnt = Column(INTEGER(11))
    income_50_to_100_cnt = Column(INTEGER(11))
    income_100_to_200_cnt = Column(INTEGER(11))
    income_above_200_cnt = Column(INTEGER(11))
    balance_0_to_5_day = Column(INTEGER(11))
    balance_5_to_10_day = Column(INTEGER(11))
    balance_10_to_30_day = Column(INTEGER(11))
    balance_30_to_50_day = Column(INTEGER(11))
    balance_50_to_100_day = Column(INTEGER(11))
    balance_100_to_200_day = Column(INTEGER(11))
    balance_above_200_day = Column(INTEGER(11))
    income_weight_max = Column(DECIMAL(16, 4))
    income_weight_min = Column(DECIMAL(16, 4))
    balance_weight_max = Column(DECIMAL(16, 4))
    balance_weight_min = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransSingleRelatedPortrait(Base):
    __tablename__ = 'trans_single_related_portrait'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    opponent_name = Column(String(32))
    relationship = Column(String(32))
    income_cnt_order = Column(INTEGER(11))
    income_cnt = Column(INTEGER(11))
    income_amt_order = Column(INTEGER(11))
    income_amt = Column(DECIMAL(16, 4))
    income_amt_proportion = Column(DECIMAL(16, 4))
    expense_cnt_order = Column(INTEGER(11))
    expense_cnt = Column(INTEGER(11))
    expense_amt_order = Column(INTEGER(11))
    expense_amt = Column(DECIMAL(16, 4))
    expense_amt_proportion = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)
    opponent_account_no = Column(String(64))


class TransSingleRemarkPortrait(Base):
    __tablename__ = 'trans_single_remark_portrait'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    remark_type = Column(String(32))
    remark_income_amt_order = Column(INTEGER(11))
    remark_expense_amt_order = Column(INTEGER(11))
    remark_trans_cnt = Column(INTEGER(11))
    remark_trans_amt = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransSingleSummaryPortrait(Base):
    __tablename__ = 'trans_single_summary_portrait'

    id = Column(BIGINT(20), primary_key=True)
    account_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    month = Column(String(16))
    q_1_year = Column(INTEGER(11))
    q_2_year = Column(INTEGER(11))
    q_3_year = Column(INTEGER(11))
    q_4_year = Column(INTEGER(11))
    normal_income_amt = Column(DECIMAL(16, 4))
    normal_expense_amt = Column(DECIMAL(16, 4))
    net_income_amt = Column(DECIMAL(16, 4))
    salary_cost_amt = Column(DECIMAL(16, 4))
    living_cost_amt = Column(DECIMAL(16, 4))
    tax_cost_amt = Column(DECIMAL(16, 4))
    rent_cost_amt = Column(DECIMAL(16, 4))
    insurance_cost_amt = Column(DECIMAL(16, 4))
    loan_cost_amt = Column(DECIMAL(16, 4))
    interest_amt = Column(DECIMAL(16, 4))
    balance_amt = Column(DECIMAL(16, 4))
    interest_balance_proportion = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)
    variable_cost_amt = Column(DECIMAL(16, 4))


class TransUAbnormalRecovery(Base):
    __tablename__ = 'trans_u_abnormal_recovery'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(255))
    account_id = Column(BIGINT(20))
    flow_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    opponent_name = Column(String(64))
    account_no = Column(String(64))
    abnormal_recovery_id = Column(BIGINT(20))
    abnormal_recovery_label = Column(String(32))
    trans_amt = Column(DECIMAL(16, 4))
    trans_datetime = Column(DateTime)
    remark = Column(String(64))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransUCounterpartyPortrait(Base):
    __tablename__ = 'trans_u_counterparty_portrait'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(32))
    report_req_no = Column(String(32))
    month = Column(String(16))
    opponent_name = Column(String(64))
    income_amt_order = Column(String(16))
    expense_amt_order = Column(String(16))
    trans_amt = Column(DECIMAL(16, 4))
    trans_month_cnt = Column(INTEGER(11))
    trans_cnt = Column(INTEGER(11))
    trans_mean = Column(DECIMAL(16, 4))
    trans_amt_proportion = Column(DECIMAL(16, 4))
    trans_gap_avg = Column(DECIMAL(16, 4))
    income_amt_proportion = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransUFlowPortrait(Base):
    __tablename__ = 'trans_u_flow_portrait'

    id = Column(BIGINT(20), primary_key=True)
    flow_id = Column(BIGINT(20))
    apply_no = Column(String(32))
    account_id = Column(BIGINT(20))
    report_req_no = Column(String(32))
    trans_date = Column(DateTime)
    trans_time = Column(DateTime)
    trans_amt = Column(DECIMAL(16, 4))
    account_balance = Column(DECIMAL(16, 4))
    bank = Column(String(64))
    account_no = Column(String(64))
    opponent_name = Column(String(64))
    opponent_type = Column(INTEGER(11))
    opponent_account_no = Column(String(64))
    opponent_account_bank = Column(String(64))
    trans_channel = Column(String(64))
    trans_type = Column(String(32))
    trans_use = Column(String(64))
    remark = Column(String(64))
    currency = Column(String(16))
    phone = Column(String(16))
    relationship = Column(String(32))
    is_financing = Column(INTEGER(11))
    is_interest = Column(INTEGER(11))
    is_repay = Column(INTEGER(11))
    is_before_interest_repay = Column(INTEGER(11))
    loan_type = Column(String(16))
    unusual_trans_type = Column(String(16))
    is_sensitive = Column(INTEGER(11))
    cost_type = Column(String(16))
    remark_type = Column(String(64))
    income_cnt_order = Column(INTEGER(11))
    expense_cnt_order = Column(INTEGER(11))
    income_amt_order = Column(INTEGER(11))
    expense_amt_order = Column(INTEGER(11))
    create_time = Column(DateTime)
    update_time = Column(DateTime)
    trans_flow_src_type = Column(INTEGER(11))
    usual_trans_type = Column(String(256))


class TransULoanPortrait(Base):
    __tablename__ = 'trans_u_loan_portrait'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(32))
    report_req_no = Column(String(32))
    loan_type = Column(String(32))
    month = Column(String(16))
    loan_amt = Column(DECIMAL(16, 4))
    loan_cnt = Column(INTEGER(11))
    loan_mean = Column(DECIMAL(16, 4))
    repay_amt = Column(DECIMAL(16, 4))
    repay_cnt = Column(INTEGER(11))
    repay_mean = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransUModelling(Base):
    __tablename__ = 'trans_u_modelling'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(32))
    report_req_no = Column(String(32))
    apply_amt = Column(DECIMAL(16, 4))
    pawn_cnt = Column(INTEGER(11))
    medical_cnt = Column(INTEGER(11))
    court_cnt = Column(INTEGER(11))
    insure_cnt = Column(INTEGER(11))
    night_trans_cnt = Column(INTEGER(11))
    fam_unstab_cnt = Column(INTEGER(11))
    balance_mean = Column(DECIMAL(16, 4))
    balance_max = Column(DECIMAL(16, 4))
    balance_max_0_to_5 = Column(DECIMAL(16, 4))
    balance_0_to_5_prop = Column(DECIMAL(16, 4))
    income_0_to_5_prop = Column(DECIMAL(16, 4))
    balance_min_weight = Column(DECIMAL(16, 4))
    balance_max_weight = Column(DECIMAL(16, 4))
    income_max_weight = Column(DECIMAL(16, 4))
    half_year_interest_amt = Column(DECIMAL(16, 4))
    half_year_balance_amt = Column(DECIMAL(16, 4))
    year_interest_amt = Column(DECIMAL(16, 4))
    q_2_balance_amt = Column(DECIMAL(16, 4))
    q_3_balance_amt = Column(DECIMAL(16, 4))
    year_interest_balance_prop = Column(DECIMAL(16, 4))
    q_4_interest_balance_prop = Column(DECIMAL(16, 4))
    income_mean = Column(DECIMAL(16, 4))
    mean_sigma_left = Column(DECIMAL(16, 4))
    mean_sigma_right = Column(DECIMAL(16, 4))
    mean_2_sigma_left = Column(DECIMAL(16, 4))
    mean_2_sigma_right = Column(DECIMAL(16, 4))
    normal_income_mean = Column(DECIMAL(16, 4))
    normal_income_amt_d_mean = Column(DECIMAL(16, 4))
    normal_income_amt_m_mean = Column(DECIMAL(16, 4))
    normal_expense_amt_m_std = Column(DECIMAL(16, 4))
    opponent_cnt = Column(INTEGER(11))
    income_rank_1_amt = Column(DECIMAL(16, 4))
    income_rank_2_amt = Column(DECIMAL(16, 4))
    income_rank_3_amt = Column(DECIMAL(16, 4))
    income_rank_4_amt = Column(DECIMAL(16, 4))
    income_rank_2_cnt_prop = Column(DECIMAL(16, 4))
    expense_rank_6_avg_gap = Column(DECIMAL(16, 4))
    income_rank_9_avg_gap = Column(DECIMAL(16, 4))
    expense_rank_10_avg_gap = Column(DECIMAL(16, 4))
    relationship_risk = Column(INTEGER(11))
    enterprise_3_income_amt = Column(DECIMAL(16, 4))
    enterprise_3_expense_cnt_prop = Column(DECIMAL(16, 4))
    all_relations_expense_cnt_prop = Column(DECIMAL(16, 4))
    hit_loan_type_cnt_6_cm = Column(INTEGER(11))
    private_income_amt_12_cm = Column(DECIMAL(16, 4))
    private_income_mean_12_cm = Column(DECIMAL(16, 4))
    pettyloan_income_amt_12_cm = Column(DECIMAL(16, 4))
    pettyloan_income_mean_12_cm = Column(DECIMAL(16, 4))
    finlease_expense_cnt_6_cm = Column(INTEGER(11))
    otherfin_income_mean_3_cm = Column(DECIMAL(16, 4))
    all_loan_expense_cnt_3_cm = Column(DECIMAL(16, 4))
    income_net_rate_compare_2 = Column(DECIMAL(16, 4))
    cus_apply_amt_pred = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransUPortrait(Base):
    __tablename__ = 'trans_u_portrait'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(255))
    report_req_no = Column(String(32))
    analyse_start_time = Column(DateTime)
    analyse_end_time = Column(DateTime)
    not_full_month = Column(String(16))
    normal_income_amt = Column(DECIMAL(16, 4))
    normal_income_cnt = Column(INTEGER(11))
    normal_income_mean = Column(DECIMAL(16, 4))
    normal_income_d_mean = Column(DECIMAL(16, 4))
    normal_income_m_mean = Column(DECIMAL(16, 4))
    normal_income_m_std = Column(DECIMAL(16, 4))
    normal_expense_amt = Column(DECIMAL(16, 4))
    normal_expense_cnt = Column(INTEGER(11))
    income_amt_y_pred = Column(DECIMAL(16, 4))
    relationship_risk = Column(INTEGER(11))
    income_0_to_5_cnt = Column(INTEGER(11))
    income_5_to_10_cnt = Column(INTEGER(11))
    income_10_to_30_cnt = Column(INTEGER(11))
    income_30_to_50_cnt = Column(INTEGER(11))
    income_50_to_100_cnt = Column(INTEGER(11))
    income_100_to_200_cnt = Column(INTEGER(11))
    income_above_200_cnt = Column(INTEGER(11))
    balance_0_to_5_day = Column(INTEGER(11))
    balance_5_to_10_day = Column(INTEGER(11))
    balance_10_to_30_day = Column(INTEGER(11))
    balance_30_to_50_day = Column(INTEGER(11))
    balance_50_to_100_day = Column(INTEGER(11))
    balance_100_to_200_day = Column(INTEGER(11))
    balance_above_200_day = Column(INTEGER(11))
    income_weight_max = Column(DECIMAL(16, 4))
    income_weight_min = Column(DECIMAL(16, 4))
    balance_weight_max = Column(DECIMAL(16, 4))
    balance_weight_min = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransURelatedPortrait(Base):
    __tablename__ = 'trans_u_related_portrait'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(32))
    report_req_no = Column(String(32))
    opponent_name = Column(String(64))
    relationship = Column(String(16))
    income_cnt_order = Column(INTEGER(11))
    income_cnt = Column(INTEGER(11))
    income_amt_order = Column(INTEGER(11))
    income_amt = Column(DECIMAL(16, 4))
    income_amt_proportion = Column(DECIMAL(16, 4))
    expense_cnt_order = Column(INTEGER(11))
    expense_cnt = Column(INTEGER(11))
    expense_amt_order = Column(INTEGER(11))
    expense_amt = Column(DECIMAL(16, 4))
    expense_amt_proportion = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)
    opponent_account_no = Column(String(64))


class TransURemarkPortrait(Base):
    __tablename__ = 'trans_u_remark_portrait'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(32))
    report_req_no = Column(String(32))
    remark_type = Column(String(64))
    remark_income_amt_order = Column(INTEGER(11))
    remark_expense_amt_order = Column(INTEGER(11))
    remark_trans_cnt = Column(INTEGER(11))
    remark_trans_amt = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class TransUSummaryPortrait(Base):
    __tablename__ = 'trans_u_summary_portrait'

    id = Column(BIGINT(20), primary_key=True)
    apply_no = Column(String(255))
    report_req_no = Column(String(32))
    month = Column(String(16))
    q_1_year = Column(INTEGER(11))
    q_2_year = Column(INTEGER(11))
    q_3_year = Column(INTEGER(11))
    q_4_year = Column(INTEGER(11))
    normal_income_amt = Column(DECIMAL(16, 4))
    normal_expense_amt = Column(DECIMAL(16, 4))
    net_income_amt = Column(DECIMAL(16, 4))
    salary_cost_amt = Column(DECIMAL(16, 4))
    living_cost_amt = Column(DECIMAL(16, 4))
    tax_cost_amt = Column(DECIMAL(16, 4))
    rent_cost_amt = Column(DECIMAL(16, 4))
    insurance_cost_amt = Column(DECIMAL(16, 4))
    loan_cost_amt = Column(DECIMAL(16, 4))
    interest_amt = Column(DECIMAL(16, 4))
    balance_amt = Column(DECIMAL(16, 4))
    interest_balance_proportion = Column(DECIMAL(16, 4))
    create_time = Column(DateTime)
    update_time = Column(DateTime)
    variable_cost_amt = Column(DECIMAL(16, 4))


class TransFlowLabel(Base):
    __tablename__ = 'trans_flow_label'

    id = Column(BIGINT(20), primary_key=True)
    trans_flow_id = Column(BIGINT(20))
    label_no = Column(String(8))
    label_name = Column(String(64))
    created_date = Column(DateTime)
