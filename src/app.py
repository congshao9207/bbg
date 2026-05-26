import json
import os
import traceback

from flask import Flask, request, send_from_directory
from flask_sqlalchemy_session import current_session
from py_eureka_client import eureka_client
from sqlalchemy import text
from sqlalchemy.orm import Query

import ver_app
from component.attachment_file_compression import AttachmentFileCompression
from component.attachment_file_extractor import AttachmentFileExtractor
from component.preparser.pre_parse_scheduler import PreParseScheduler
from component.rectify_trans_download import RectifyTransDownload
from component.task_query_component import TaskQueryComponent
from component.trans_file_parse_routine import TransParseRouting
from component.trans_parse_component import TransParseComponent
from component.trans_remover import TransRemover
from config.db_config import init_connection, engine
from config.file_type import FileTypeEnum
from config.res_code import ResCodeEnum
from config.trans_config import MAX_WORKERS, EUREKA_SERVER, SPEC_OPT_TOKEN, DAFE_SERVER
from entity.resp_entity import RespEntity
from excepts.exceptions import ServerException
from job.trans_parser_jobs import init_ap_scheduler, init_register_dafe
from logger.logger_util import LoggerUtil
from model.model import SysInfo, TransFlow
from ocr.ocr_result_processor import OcrResultProcessor
from util import ObjectSerializer
from util.file_util import create_temp_file
from util.pagination import paginate
from util.pagination_serializer import PaginationSerializer
import socket

app = Flask(__name__)
logger = LoggerUtil().logger(__name__)
pps = PreParseScheduler()


def _init_system():
    """
    初始化系统并配置
    :return:
    """
    init_connection(app)
    # 注册蓝图
    app.register_blueprint(ver_app.ver_app, url_prefix='/ver')
    # 初始化eureka
    eureka_client.init(eureka_server=EUREKA_SERVER, app_name="TRANS-PARSER", instance_port=8011)
    logger.info("eureka client started. center: %s", EUREKA_SERVER)
    logger.info("开始注册请求到微服务中心...")
    # 获取客户端ip地址
    client_ip = socket.gethostbyname(socket.gethostname())
    logger.info("客户端地址：%s", client_ip)
    dafe_res = init_register_dafe(DAFE_SERVER, client_ip)
    if dafe_res != '':
        logger.info("注册微服务状态：%s", str(dafe_res.text))
    else:
        logger.info("注册微服务中心失败")

    # 初始化工作线程
    for i in range(MAX_WORKERS):
        routine = TransParseRouting()
        routine.start()
    # 初始化ApScheduler
    init_ap_scheduler(app)


@app.route('/')
def system_info():
    """
    SQLAlchemy testing.
    :return:
    """
    # trans_parse_queue.enqueue(7)
    infos = current_session.query(SysInfo).filter(SysInfo.id > 1).count()
    return json.dumps(infos, cls=ObjectSerializer.ObjectSerializer)


@app.route("/health", methods=['GET'])
def health_check():
    """
    检查当前应用的健康情况
        检查当前应用的健康情况
        :return:
        """
    msg = "Trans trans_parser is running!" + str(os.getpid())
    return RespEntity.response(0, msg)


@app.route("/info", methods=['GET'])
def info():
    """
    输出数据为连接池信息
    :return:
    """
    msg = "Db connect pool, engine:%d , status:%s" % (id(engine), engine.pool.status())
    return RespEntity.response(0, msg)


@app.route('/trans/upload', methods=["POST"])
def trans_upload():
    """
    文件上传接口， 以 `form-data`的方式提交
    :return:
    """
    logger.info("trans upload request has bee entered")
    file = request.files.get("file")
    app_id = request.form.get("appId")
    data = request.form.get("param")

    if not app_id:
        app_id = request.args.get("appId")

    if not data:
        data = request.args.get("param")
        logger.info("data from args: %s", data)

    tpc = TransParseComponent(app_id, data, file)
    have_exception = False
    try:
        if not tpc.pre_check():
            return tpc.get_last_resp()

        tpc.execute()
    except Exception as e:
        logger.error("trans upload exception:" + str(e))
        stack_trace = traceback.format_exc()
        logger.error(stack_trace)
        have_exception = True
    finally:
        tpc.teardown(have_exception)

    return tpc.get_last_resp()


@app.route("/trans/ocr/result", methods=["POST"])
def trans_ocr_result():
    """
    ocr解析后，主动通知接口
    :return:
    """
    logger.info("/trans/ocr/result request has bee entered")
    resp = request.get_json()
    if resp["resCode"] != 0:
        logger.info("/trans/ocr/result, msg: %s", str(resp["resCode"]))
    p = OcrResultProcessor(resp)
    cause = p.process()
    if cause:
        return RespEntity().with_res_enum(ResCodeEnum.FAILED, msg=cause)
    else:
        return RespEntity().with_res_enum(ResCodeEnum.SUCCESS)


@app.route('/trans/query', methods=["POST"])
def trans_query():
    """
    文件解析结果查询接口
    :return:
    """
    req_msg = request.get_json()
    out_req_no = req_msg["outReqNo"]
    tqc = TaskQueryComponent(out_req_no)
    res = tqc.analyze_task_res()
    return res


@app.route('/trans/excel/download', methods=["POST", "GET"])
def trans_excel_download():
    """
    识别后的excel文件下载
    {
        "appId": "客户端ID",
        "outReqNo":"流水解析编号",
        "attachmentId": "解析pdf后的excel文件ID"
    }
    :return:
    """
    req_msg = request.get_json()
    if req_msg:
        attachment_id = req_msg["attachmentId"]
    else:
        attachment_id = request.args.get("attachmentId")
    file_extractor = AttachmentFileExtractor(attachment_id)
    with file_extractor:
        directory, file_name = file_extractor.extract()
        return send_from_directory(directory, path=file_name, as_attachment=True)


@app.route('/trans/rectify/download', methods=["GET"])
def trans_rectify_download():
    """
    纠偏后的excel下载
    :return:
    """
    out_req_no = request.args.get("outReqNo")
    if not out_req_no:
        raise ServerException("outReqNo is required")

    with RectifyTransDownload(out_req_no) as rdt:
        directory, file_name = rdt.extract_to_file()
        return send_from_directory(directory, path=file_name, as_attachment=True)


@app.route('/trans/files')
def trans_files():
    file_extractor = AttachmentFileExtractor(None)
    with file_extractor:
        directory, zip_file_name = create_temp_file(FileTypeEnum.ZIP)
        file_extractor.pack_all_files(FileTypeEnum.XLSX, directory, zip_file_name)

        return send_from_directory(directory, path=zip_file_name, as_attachment=True)


@app.route('/trans/detail', methods=["GET"])
def trans_detail():
    out_req_no = request.args.get("out_req_no")
    page = request.args.get("page", 1, type=int)
    size = request.args.get("per_page", 20, type=int)
    logger.info("page:%d, size:%d, out_req_no:%s", page, size, out_req_no)
    if not out_req_no:
        return RespEntity.with_res_enum(ResCodeEnum.PARAM_ERROR)

    Query.paginate = paginate
    p = current_session\
        .query(TransFlow).filter(TransFlow.out_req_no == out_req_no)\
        .order_by(text("trans_time desc")).paginate(page, size, error_out=False)

    data = PaginationSerializer(p).to_json()
    return RespEntity().with_res_enum(ResCodeEnum.SUCCESS, msg="成功", data=data)


@app.route('/trans/delete', methods=['GET'])
def trans_delete():
    out_req_no = request.args.get("outReqNo")
    token = request.args.get("token")
    cause = ""
    res = None
    if not out_req_no:
        cause = "outReqNo is required"
    elif not token:
        cause = "token is required"
    logger.info('SPEC_OPT_TOKEN: %s', SPEC_OPT_TOKEN)
    logger.info('token: %s', token)
    if token != SPEC_OPT_TOKEN:
        logger.info('token 不同')
    else:
        logger.info('token 相同')
    if not cause:
        cause = "token incorrect" if token != SPEC_OPT_TOKEN else None

    if not cause:
        logger.info('test test test token: %s', token)
        res, cause = TransRemover(out_req_no).execute()

    if not res:
        res = ResCodeEnum.FAILED if cause else ResCodeEnum.SUCCESS
    return RespEntity().with_res_enum(res, cause)


@app.route('/trans/pre-parse', methods=["POST"])
def trans_pre_parse():
    """
    预解析接口，获取文件的信息如下:
    - passwdRequired 是否需要密码
    - rowCount 流水文件的条目数
    - startAt 开始时间
    - endAt 结束时间
    - bankName 机构名称
    - bankAccount 账号
    """
    file_pwd = request.form.get("filePwd")
    if not file_pwd:
        file_pwd = request.args.get("filePwd")

    file = request.files.get("file")

    res_code, res_msg, data = pps.dispatch_pre_parse(file, file_pwd)
    return RespEntity.response(res_code, res_msg, data)


# 初始化系统
_init_system()

if __name__ == '__main__':
    app.run()
