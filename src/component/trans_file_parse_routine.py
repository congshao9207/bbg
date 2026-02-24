# @Time : 2/23/22 9:42 AM 
# @Author : lixiaobo
# @File : trans_file_parse_routine.py 
# @Software: PyCharm
import os
import threading
import time
import traceback

from sqlalchemy.orm import sessionmaker, scoped_session

from component.task_ocr_scheduler import TaskOcrScheduler
from component.task_scheduler import TaskScheduler
from config.db_config import engine
from config.file_type import FileTypeEnum
from config.trans_config import WAITING_INTERVAL
from excepts.exceptions import ParseException
from logger.logger_util import LoggerUtil
from model.model import TransParseTask
from util.magfin_redis import trans_parse_queue

logger = LoggerUtil().logger(__name__)


class TransParseRouting(threading.Thread):

    def __init__(self):
        super().__init__()
        self.loop_count = 0
        self.session_factory = sessionmaker(bind=engine)
        self.pid = None

    def increment_loop_count(self):
        self.loop_count = self.loop_count + 1
        if self.loop_count % 40 == 0:
            logger.info("Routing-pid: %s, thread: %s, loop_count:%d", str(os.getpid()), threading.current_thread().getName(), self.loop_count)

    def run(self):
        self.pid = str(os.getpid())
        logger.info("Routine begin:pid: %s, thread: %s", str(self.pid), threading.current_thread().getName())
        try:
            while True:
                self.increment_loop_count()
                task_id = trans_parse_queue.dequeue()
                if not task_id:
                    time.sleep(WAITING_INTERVAL)
                    continue
                logger.info("Receive task id: %s, pid:%s, thread:%s", task_id, str(self.pid), threading.current_thread().getName())

                session = None
                try:
                    session = scoped_session(self.session_factory)
                    task = session.query(TransParseTask).filter(TransParseTask.id == int(task_id)).first()
                    logger.info("TaskInfo: task_id:%s, pid:%s, thread:%s", str(task.id), str(self.pid), threading.current_thread().getName())
                    if not task:
                        continue
                    scheduler = self.obtain_scheduler(task, session)

                    with scheduler as task_scheduler:
                        if task_scheduler:
                            task_scheduler()
                        else:
                            time.sleep(WAITING_INTERVAL)
                except Exception as e:
                    logger.error("TransParseRouting exception:%s, %s", str(e), traceback.format_exc())
                finally:
                    if session:
                        session.close()
        except Exception as e:
            trace_info = traceback.format_exc()
            logger.fatal("Routine exception, interrupted, run end....:%s, %s", str(e), trace_info)

    @staticmethod
    def obtain_scheduler(task, session):
        if task.result_attachment_id:
            return TaskScheduler(task, session)
        elif task.origin_file_type == FileTypeEnum.PDF.value:
            return TaskOcrScheduler(task, session)
        else:
            raise ParseException("no scheduler for file type:" + task.origin_file_type)
