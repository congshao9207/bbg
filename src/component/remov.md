---                                                                                                                     修改说明

  文件: src/component/trans_remover.py

  变更 1：分批删除 TransFlow（_batch_delete_flow 方法）

  _batch_delete_flow() 每次通过主键排序取 500 条 out_req_no 匹配的 ID，用 SELECT ... FOR UPDATE 只锁这 500 行，DELETE
  后立即 commit() 释放锁，循环直到删完。

  为什么用 ORDER BY id + LIMIT 500 + FOR UPDATE？
  - ORDER BY id：利用主键聚簇索引，避免全表扫描锁无关行
  - LIMIT 500：每批只锁 500 行，锁粒度可控
  - FOR UPDATE：确保同一批数据在 SELECT 和 DELETE 之间不被并发修改

  变更 2：拆分事务

  - 事务 1（第 1 步）：仅用于分批删除 TransFlow，每批提交一次
  - 事务 2（第 2 步）：删除 TransAccount、TransAttachment、OcrTask、TransParseTask

  这样 TransFlow 的长删除不再拖累其他表的锁释放，其他表数据量小（通常个位数行），事务 2 瞬间完成。

  变更 3：调整删除顺序

  TransFlow 从最后移到最先删除。这是最慢的操作，优先处理掉。

  ---
  补充建议（DBA 运维层面）

  1. 给 trans_flow.out_req_no 加索引（最有效的长期方案）

  ALTER TABLE trans_flow ADD INDEX idx_out_req_no (out_req_no);

  加上索引后，WHERE out_req_no = ?
  的删除将走索引直接定位目标行，不再全表扫描锁表。即使不用分批策略，也不会触发锁等待超时。

  同样建议给 trans_flow_original.out_req_no 也加索引（该表也未在删除逻辑中处理，如果后续也要删的话）。

  2. trans_flow_original 等关联表未删除

  当前 TransRemover 没有删除 TransFlowOriginal、TransFlowException、TransFlowPortrait、TransApply 等通过 account_id 或
  out_req_no 关联的表。这些表会留下孤儿数据。建议确认是否需要一并清理。