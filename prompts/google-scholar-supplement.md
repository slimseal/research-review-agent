# Google Scholar 人工补充检索

我的研究问题：[填写 RQ]
研究范围/已选数据库：[可留空，由 Agent 读取现有项目或询问必要范围]

请先读取项目规则和 docs/google-scholar-supplement.md，判断 Scholar 对我的问题
是否有补充价值，说明当前数据库的可能遗漏。不要联网搜索 Scholar。
如适合，请直接生成 3–5 条简短可复制检索式、各自目的、年份设置建议、检查上限、
停止规则和中文操作清单；由你准备 CLI 所需 JSON，不要求我写代码。
使用 scholar-prepare 保存独立登记模板，再生成 literature-coverage 报告。
我确认范围后自行操作浏览器。尚未操作时必须保持 not_performed，不能填假论文。
之后按我实际提供的记录汇总未核实身份、疑似重复和需筛选候选；保留 not_imported，
不自动修改 Registry、生成 SearchRun、调用 DOI API 或认定 Gate 通过。
