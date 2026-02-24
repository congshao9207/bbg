# @Time : 2/22/22 10:34 AM 
# @Author : lixiaobo
# @File : task_receiver.py 
# @Software: PyCharm
from datetime import datetime

from flask_sqlalchemy_session import current_session
from json2obj import JSONObjectMapper

from component.attachment_file_compression import AttachmentFileCompression
from config.file_type import FileTypeEnum
from config.process_status import ProcessStatusEnum
from model.model import TransParseTask
from util.common_util import calc_md5


class TaskReceiver(object):
    def __init__(self, ocr_required, param, origin_file_name, ext, file_hash, file_path, post_file_path):
        self.ocr_required = ocr_required
        self.param = param
        self.origin_file_name = origin_file_name
        self.ext = ext
        self.file_hash = file_hash
        self.file_path = file_path
        self.post_file_path = post_file_path

    def receive_task(self):
        param_obj = JSONObjectMapper(self.param)
        post_ext = self.ext if self.ocr_required else FileTypeEnum.XLSX.value
        afc = AttachmentFileCompression()
        origin_attachment_id = afc.persistence_file(self.file_path, self.file_hash, self.ext)
        post_attachment_id = None
        if not self.ocr_required:
            post_attachment_id = afc.persistence_file(self.post_file_path, None, post_ext)

        tpt = TransParseTask()
        tpt.req_raw_data = self.param
        tpt.out_apply_no = param_obj.outApplyNo
        tpt.out_req_no = param_obj.outReqNo
        tpt.file_hash = self.file_hash
        tpt.process_status = ProcessStatusEnum.PENDING.name
        # 原文件
        tpt.origin_file_type = self.ext
        tpt.origin_attachment_id = origin_attachment_id
        tpt.origin_file_name = self.origin_file_name
        # 处理后文件
        if not self.ocr_required:
            tpt.result_file_type = post_ext
            tpt.result_attachment_id = post_attachment_id

        group_no_info = param_obj.idNo + param_obj.bankAccount + param_obj.bankName
        group_no = calc_md5(group_no_info)
        tpt.group_no = group_no

        if self.ext == FileTypeEnum.PDF.value:
            tpt.rectify = 1
        else:
            tpt.rectify = param_obj.rectify
        tpt.created_date = datetime.now()
        tpt.last_modified_date = datetime.now()
        current_session.add(tpt)
        current_session.commit()
        return tpt.id


