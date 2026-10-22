# Beginner Quick Start / 新手入门

不用先学习数据库 API、命令行或全部 19 个阶段。你负责研究问题、范围和真实科研判断；
Codex 按项目规则操作工具，不能代替你签署审批。

## 1. 下载并打开

从 [GitHub 项目](https://github.com/slimseal/research-review-agent) 下载已发布的版本
（Code → Download ZIP，解压；会使用 Git 也可 clone）。在 Codex 打开包含
`AGENTS.md`、`README.md` 和 `research_review_agent/` 的根目录，不要只打开一个 PDF。

建议从 [v1.1-experimental 预发布页面](https://github.com/slimseal/research-review-agent/releases/tag/v1.1-experimental)
下载 **Source code (zip)**，以固定版本开始；main 后续可能变化。此为 MIT 许可的
Experimental 源码，不是稳定产品或已通过完整学术验收的系统综述工具。

## 2. 一次环境准备

需要 Python 3.11+，以及你正常可用的 Codex 环境。把以下话发给 Codex：

> 请读取 AGENTS.md，检查 Python 和项目安装状态，解释需要的本地环境设置。
> 经我允许后在项目虚拟环境安装此包。先不联网检索、不配置可选数据库 Key。

具体安装见 [安装说明](installation.md)。后续需要 PDF 解析时再安装已声明的
`pdf` 可选依赖，并使用本地查看器核查表格和特殊字符。安装可能联网下载依赖，
与检索预算是不同操作。没有模型 SDK 或个人 Skill 依赖；Codex 本身的使用条件仍适用。

## 3. 输入研究问题

复制 [完整起始 Prompt](../prompts/start-review.md)，或直接说：

> 我的研究问题是：[填写 RQ]。领域和用途：[填写]。必须遵守的范围：[如年份/语言]。
> 请按 AGENTS.md 开始 Standard 模式，推荐互补且合法可访问的数据库。
> 在仓库外建立独立研究文件夹，起草研究方案，列明未知信息，不自动审批。
> 向我展示一份检索来源、实际检索式和总预算，确认后才执行。

数据库名称可不填；你明确要求或排除的来源优先。Codex 会解释可用情况，而不是
要求你首先申请一串 Key。离线配置检测不证明网站当前可用。

## 4. 读两类不同的确认

- **研究方案与科研判断：**审阅 Protocol；在你实际同意时，由你按工具要求执行审批。
- **技术操作范围：**一次确认选定来源、检索式、页数、记录数、请求/重试总预算、
  是否允许验证访问状态及凭证模式。范围内无需逐个 HTTP 请求再确认。

确认来源不等于批准所有后续科研判断。扩大预算、更换来源、注册账号或收费都要另行确认。
可选来源失败不阻止其他已授权来源；失败和未执行不能被写成成功零结果。

## 5. 查看结果和缺口

Codex 按现有流程保存 SearchRun、原始响应与哈希，协调多数据库元数据，保留重复和
身份冲突，再生成 Literature Coverage Report。看“独有候选、重复、摘要缺失、失败和遗漏”，
不要只看总数量；预印本和综述等类型仍需筛选。

需要更广的探索时可选择 [Comprehensive](search-modes.md)，但这不是“保证全覆盖”。
Google Scholar 是 [人工补充](google-scholar-supplement.md)：Codex 提供检索式和中文
操作清单，你自行浏览并给出真实记录。未操作保持 not_performed；人工候选不自动导入 Registry。

## 6. 按提示继续科研

依次完成引用扩展的停止/覆盖审核、合法全文获取处置、正式 Screening，随后才是
Reading Notes 和 Evidence Matrix。可以请 Codex 解释下一项最少必要操作，不需要背阶段号。
缺摘要、缺 PDF 或 API 失败都不自动意味着排除。不能为了演示而伪造 Gate 通过。

目前没有经过真实多篇文献、全部人工 Gate 的全流程学术验收；单篇实证演示与隔离
工程测试是不同运行，不能合称正式端到端综述。

[数据库配置](database-access.md) · [常见问题](troubleshooting.md) ·
[已知限制](KNOWN_ISSUES.md) · [技术用户教程](tutorial.md)
