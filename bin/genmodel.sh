sqlacodegen --tables \
\
ocr_task,sys_info,trans_account,trans_attachment,trans_call_back,trans_flow,trans_flow_original,trans_open_cfg,trans_parse_task \
\
mysql+pymysql://root:'ysyhl9t!'@127.0.0.1:3306/trans_parser > ../src/model/model.py