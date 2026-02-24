# @Time : 4/20/22 8:27 PM 
# @Author : lixiaobo
# @File : ocr_result_check_job.py 
# @Software: PyCharm
import json
import os
import threading
import requests

from flask_apscheduler import APScheduler
from flask_sqlalchemy_session import current_session

from job.executor.ocr_result_query_job_executor import OcrResultQueryJobExecutor
from logger.logger_util import LoggerUtil
from util.distributed_lock_proxy import DistributedLockProxy
from util.magfin_redis import redis_conn

logger = LoggerUtil().logger(__name__)
scheduler = APScheduler()


def init_ap_scheduler(app):
    distributed_lock = DistributedLockProxy(redis_conn, timeout=60, resource_key="ap_scheduler_lock_init")
    locked = distributed_lock.acquire_no_block()
    # 该lock不需要显式释放, 10minutes auto unlock.
    if not locked:
        logger.info("init_ap_scheduler acquired lock: false. nothing to do. %s, %s",
                    os.getpid(), threading.current_thread().getName())
        return
    if locked:
        logger.info("acquired lock, begin init ap scheduler...")
        # 初始化job
        scheduler.init_app(app)
        scheduler.start()


def init_register_dafe(root_url, client_ip):
    """
    注册到微服务中心
    :param root_url:
    :param client_ip:
    :return:
    """
    # requests
    param = {
        "datacenter": "default",
        "namespace": "default",
        "appCode": "60064003",
        "version": "1.0.0",
        "ip": client_ip,
        "port": 8011,
        "services": [
            {
                "funcIntfCode": "600640030001",
                "funcIntfName": "文件解析结果查询接口",
                "serviceCode": "6006400300",
                "uri": "/trans/query"
            },
            {
                "funcIntfCode": "600640030002",
                "funcIntfName": "识别后的excel文件下载",
                "serviceCode": "6006400300",
                "uri": "/trans/excel/download"
            },
            {
                "funcIntfCode": "600640030003",
                "funcIntfName": "纠偏后的excel下载",
                "serviceCode": "6006400300",
                "uri": "/trans/rectify/download"
            },
            {
                "funcIntfCode": "600640030004",
                "funcIntfName": "流水明细",
                "serviceCode": "6006400300",
                "uri": "/trans/detail"
            },
            {
                "funcIntfCode": "600640030005",
                "funcIntfName": "流水数据删除",
                "serviceCode": "6006400300",
                "uri": "/trans/delete"
            }
        ]
    }
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        res = requests.post(url=root_url, data=json.dumps(param), headers=headers)
        return res
    except Exception as e:
        logger.info('注册微服务平台请求错误：%s', str(e))
        return ''


@scheduler.task('interval', id='job_ocr_result_query', seconds=60, misfire_grace_time=900)
def job_ocr_result_query():
    distributed_lock = DistributedLockProxy(redis_conn, timeout=60, resource_key="ap_scheduler_executor_lock")
    locked = distributed_lock.acquire_no_block()
    try:
        if not locked:
            logger.info("job_ocr_result_query acquired lock false, task executor returning...")
            return
        logger.info('job_ocr_result_query 1 executed, pid:%s, threading:%s',
                    str(os.getpid()), threading.current_thread().getName())
        with scheduler.app.app_context():
            OcrResultQueryJobExecutor(current_session).execute()
        logger.info("job_ocr_result_query end.")
    finally:
        if distributed_lock and locked:
            distributed_lock.release()
