# V1.1 整合验收与发布准备

日期：2026-10-22。分支：`codex/v1.1-database-access`。
本文件保留整合验收时的历史记录。负责人随后已授权 MIT 与 GitHub 发布；当前许可见
[LICENSE](../LICENSE)，当前发布说明见 [Release Notes](V1_1_RELEASE_NOTES.md)。
下文“许可待定/尚未发布”仅描述当时检查点，不代表现行许可。
结论：**可准备受限声明的 Experimental 源码提交；不应宣称全部验收通过或无条件 Release-ready。**
本轮仅整合文档与验收，没有新增接口、修改实现/测试、科研审批、检索或下载。

**后续 Final Release Gate 更新：**标准联网安装已在两个全新、不继承系统/用户包的
虚拟环境通过，含普通 wheel 安装与 PDF 依赖；安装阻碍已解除。
下文保留上一轮离线验收的历史结论，不代表当前仍然安装失败。最新发布判断见
[最终发布门禁](V1_1_FINAL_RELEASE_GATE.md)。Scholar 等功能限制原样保留，不作为
本轮新增开发事项；可在明确披露限制、等待负责人确认后提交 Experimental 源码。

## 新手完整路径核查

| 用户步骤 | 实际情况与验证依据 |
|---|---|
| 1. 下载、安装、在 Codex 打开 | GitHub 目前只有 V1 main，V1.1 还在本地。干净源码副本可运行；离线 wheel 构建因缺 setuptools 后端失败，首次安装不能记为通过。没有实际新手用户可用性测试。 |
| 2. 输入 RQ | 已有 init 及 Codex Protocol 工作流；本轮干净源码副本重新运行 init/next/phase-context 成功。空模板不等于完成研究方案。 |
| 3. 推荐来源 | source-plan 离线运行成功，Codex 按领域修订启发式建议。Standard/Comprehensive 是操作约定，不是新 CLI 功能。 |
| 4. 查看访问条件 | provider-status 离线检查成功；六个来源有保存的真实联网成功证据。状态是端点/时间特定，不重新探测就不能声称此刻可用。 |
| 5. 一次确认来源与预算 | 文档/Prompt 约定一次确认具体技术范围；每次运行有请求硬上限。全计划跨库总额仍靠 Agent 分配，没有事务式总预算执行器。科研批准不能合并代签。 |
| 6. 自动查询 | Batch 1–2 已有真实小规模查询；本轮只复核保存响应，未重新联网。正常正式入口仍需 Protocol 与 Phase 1–2 等前置条件。 |
| 7. 汇总/去重 | 保存的主语料 51 条观察、47 个规范候选、1 条重复、3 条身份未解；独立 arXiv 10 条。真实干净跨库重叠为中等置信度题名/作者/年份匹配；DOI/PMID/PMCID 精确匹配也有离线合同测试，不能冒充干净的真实跨库验证。 |
| 8. Coverage Report | 两套真实保存语料只读重算，各 API 计数/重叠与原报告一致；来源原始 SHA/provenance 校验无问题。未评价相关性。 |
| 9. Scholar 方案/中文说明 | 独立练习已生成四条检索式及清单；干净副本运行 scholar-prepare 也成功，无网页抓取或检索。 |
| 10. 人工发现/状态 | 空清单保持 not_performed；人工记录与 Registry 分离测试通过。completed/incomplete 自动判定未实现，performed_as_reported 不能等同完成；此验收项部分满足。 |
| 11. Screening → Reading → Evidence | 原有正式接口/Gate 与回归测试保留。真实单篇 PDF 下游演示在隔离环境完成过，不能拼接成多库语料已通过全部人工 Gate 的正式端到端研究。 |

## 实际数据库分级

- **已保存真实成功：** Crossref、PubMed、Europe PMC、ERIC、arXiv、OpenAIRE Graph v3。
- **已实现但当前保存的测试失败：** OpenAlex 额度耗尽；Semantic Scholar 429 限流。配置免费 Key 不是成功保障。
- **机构授权且没有实现：** Scopus、Web of Science、PsycINFO；必须区分缺代码、缺凭证和缺 entitlement。
- **人工补充：** Google Scholar 方案/记录；其他专科来源仅可明确记录人工补查缺口。Button 是浏览器扩展，不是连接器。
- **未来/未交付：** CORE、DataCite、新的 Unpaywall 集成、个人文献库/批量导入；既有 OpenCitations 是引用追踪，不是关键词发现。

## 本轮实际验证

- `scripts/run_tests.sh`：**436 项通过，348.123 秒**；编译、19 阶段 Registry/Procedure 校验通过。无新增测试，无真实科研审批。
- 对保存的主语料与独立 arXiv 语料运行真实来源校验，无问题；新旧 API coverage 关键统计相同。
- Scholar 练习：4 条查询全部 not_performed；0 条人工候选，0 次正式导入；completed_scope=not_assessed。不是成功零结果检索。
- 干净候选源码副本：init、next、phase-context、provider-status、source-plan、scholar-prepare 成功，socket 入口禁用；不依赖全局 Skills。
- wheel 构建失败：现有测试虚拟环境没有 `setuptools.build_meta`。后续安装也没有可用 wheel，不能记为安装通过。本轮未联网补装，不诊断成产品运行代码 Bug；Python 构建后端已在安装要求声明。
- 发布范围隐私、链接及历史项目保存检查结果见下方最终核对。日志留在仓库外，不作为发布附件。

## 新手最短操作

等待明确发布的 V1.1 源码版本 → 在 Codex 打开仓库根目录 → 按
[新手指南](beginner-quick-start.md)完成一次 Python/虚拟环境设置 → 输入 RQ 与范围 →
审阅 Protocol 和一次来源/查询/预算计划 → 授权的技术请求由 Codex 执行 →
查看 Coverage、按需手动 Scholar → 按提示完成真实科研审核后继续。
不需要先学全部阶段/API；也不能跳过人工科研判断。

## 发布判断

适合发布：现有源码、19 阶段/Procedures、Schemas、CLI、436 项测试、英文 README、
安装与新手教程、数据库状态说明、两种规划方式、Scholar 指南/模板生成器、Prompt、
Known Issues、经过筛选的 V1 演示摘要。保留原有未提交成果。

不能发布：私人科研目录、全文 PDF、原始 API 响应、真实审批身份、Key、私人路径、
环境/缓存、恢复快照和测试日志。GitHub 实际可见性当前是 **Public**，本轮没有改变；
不能继续按“仍是 Private”处理上传风险。公开可见不等于开源许可，未选择 LICENSE。

可以在负责人认可限制后创建 **V1.1 Experimental 源码快照提交**。
尚不具备“全部目标通过、首次安装已验证、正式学术系统综述工具”的 Release 条件：
Scholar 完成状态验收缺口和安装验证失败必须保留，不能改数据制造通过。
如仍选择带这些限制的 Experimental Release，需要负责人明确接受公开范围、限制、
版本/Tag 与许可表述；本轮没有执行，也没有开始下一轮开发。

## 最终核对

- 当前候选共 **324 个文件**（已跟踪 + 未忽略的新文件），本轮不暂存。新增/调整文档的 92 个本地链接通过，`git diff --check` 通过。
- 候选文件未发现 PDF、日志、审批 JSONL、私钥/凭证文件或 >1 MB 文件；常见凭证及本机身份/绝对路径模式扫描无真实敏感信息命中。唯一主目录前缀命中是既有隐私检测脚本的通用检测字符串，不含个人目录。
- 现有 Git 历史扫描 248 个唯一 blob，同样只有上述检测字符串命中；未发现匹配的凭证或个人路径。这是有边界的模式扫描与内容复核，不是绝对无泄露保证。
- 私人试点目录 **11,657 个文件**的路径/大小/修改时间清单摘要前后一致；其中 **304 个 Protocol、状态、Registry、Coverage 与 Scholar 关键文件**的内容 SHA 摘要也一致。大型原始日志未逐字节重新散列，不把元数据清单检查夸大成全部内容哈希认证。
- 对照本轮开始前可恢复快照：已有文件只变更 9 个 Markdown 文档/Prompt/AGENTS；另新增 5 个 Markdown 文档。核心源码、全部测试、19 阶段 Registry、Procedure、Gate 与 Batch 1–2 实现逐文件未变。
- 本地 HEAD/main 与远端 main 都仍为 `09a728015081c300ad653f987e725f627741f876`；远端 API 当次读取仅 main 分支、仓库 Public、当前账号具备 push 权限。未创建 commit、merge、tag、Release，也未 push。
- 关键未通过项：干净安装/wheel 验收未完成；Scholar completed/incomplete 自动状态不具备。代码回归通过不能消除这两项限制。
