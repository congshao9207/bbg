# @Time : 4/14/22 10:21 AM 
# @Author : lixiaobo
# @File : trans_file_downloader.py 
# @Software: PyCharm
import os
import zipfile

from flask_sqlalchemy_session import current_session

from model.model import TransAttachment
from util.file_util import create_temp_file


class AttachmentFileExtractor(object):
    def __init__(self, attachment_id):
        if type(attachment_id) == str:
            self.attachment_id = int(attachment_id)
        else:
            self.attachment_id = attachment_id
        self.file_full_path = []

    def __enter__(self):
        pass

    def extract(self):
        attachment = current_session.query(TransAttachment).filter(TransAttachment.id == self.attachment_id).first()
        from config.trans_config import NAS_STORAGE_PATH
        full_path = os.path.join(NAS_STORAGE_PATH, attachment.trans_data.decode('utf-8'))
        # directory, file_name = create_temp_file(attachment.file_type, attachment.id)
        # full_path = directory + os.path.sep + file_name

        # 创建临时文件链接
        directory, file_name = create_temp_file(attachment.file_type, attachment.id)
        temp_path = os.path.join(directory, file_name)
        os.symlink(full_path, temp_path)  # 创建符号链接
        self.file_full_path.append(temp_path)
        return directory, file_name
        # self.file_full_path.append(full_path)
        # with open(full_path, "wb") as f:
        #     f.write(attachment.trans_data)
        #
        # return directory, file_name

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_full_path:
            for path in self.file_full_path:
                os.remove(path)

    def pack_all_files(self, file_type_enum, zip_file_dir, zip_file_name):
        page = 1
        size = 10
        while True:
            if file_type_enum:
                attachments = current_session.query(TransAttachment) \
                    .filter(TransAttachment.file_type == file_type_enum.value).offset((page - 1) * size).limit(
                    size).all()
            else:
                attachments = current_session.query(TransAttachment).offset((page - 1) * size).limit(size).all()
            page = page + 1
            if not attachments or len(attachments) == 0:
                break
            for attachment in attachments:
                directory, file_name = create_temp_file(attachment.file_type, attachment.id)
                file_full_path = directory + os.path.sep + file_name
                with open(file_full_path, "wb") as f:
                    f.write(attachment.trans_data)
                self.file_full_path.append(file_full_path)

        zip_file_path = zip_file_dir + os.path.sep + zip_file_name
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in self.file_full_path:
                zf.write(f, os.path.basename(f))

        self.file_full_path.append(zip_file_path)
