# Research Code Stewardship Lab：收口后的推进路线图

[English](DUAL_MODE_ROADMAP_EN.md) · [能力模型](COMPETENCY_MODEL.md) · [案例发布模型](CASE_RELEASE_MODEL.md)

## 目标与边界

RCSL 只保留两个核心用户结果：

- **Mode Audit**：帮助负责人审计真实研究代码，保存可追溯的证据和人工决定；
- **Mode Train**：训练人在 Coding Agent 时代识别、证明和处置研究代码风险的能力。

`export` / `package` 是案例发布辅助工具，不是第三种模式。展示层、托管平台和其他集成只有在核心工作流经过真实试点后才会重新评估。

## 防偏移准则

仓库最初以四级审计训练为主；后来将“帮助负责人完成真实研究代码审计并管理证据”明确加入目标。这是一次有意的双模式扩展，不是要求把仓库建设成通用安全平台、发布平台或展示平台。

一个新能力只有至少直接改善下面一个用户闭环，才允许进入核心：

1. 审计负责人能更准确地定位、保存、复核或交接一个真实项目的证据与人工决定；
2. 学习者和独立审阅者能围绕同一份冻结材料完成判断、举证、反馈和重做。

仅增加测试数量、文件系统防护、页面、Registry、集成或“平台感”，但没有解除上述闭环中的已观察阻塞，不构成立项理由。通用权限、同权限恶意本机进程防护、远程运营和托管能力必须由真实部署边界与负责人另行立项。

## 状态词必须严格区分

| 状态 | 含义 | 不能据此宣称 |
| --- | --- | --- |
| `implemented` | 对应代码、命令或文档已经存在 | 设计正确、用户可用或安全 |
| `internally verified` | 自动测试和受控合成场景通过 | 真实项目或真实学习者已经成功使用 |
| `field validated` | 外部真实用户在真实场景完成端到端任务，并留下观察证据 | 已具备生产级安全、恢复和运维能力 |
| `production ready` | 威胁模型、身份权限、恢复、迁移、监控、治理和维护责任均已闭环 | 超出明确部署边界的保证 |

今后不再单独使用含糊的“完成”。每个里程碑都要说明它处于以上哪一层。

## 当前诚实基线

| 工作面 | Implemented | Internally verified | Field validated | Production ready | 当前判断 |
| --- | --- | --- | --- | --- | --- |
| 四级公开训练案例 | 是 | 是 | 否 | 否 | 可作为公开实验性课程，不得宣称训练有效性 |
| Phase 1 Audit 生命周期 | 是 | 是 | 否 | 否 | Alpha；核心边界和恢复仍需收口 |
| Phase 2 Training progress | 是 | 是 | 否 | 否 | 实验性；人工审阅对象与案例版本绑定仍不完整 |
| Phase 3A 本地发布/分包 | 是 | 是 | 否 | 否 | 只验证本地文件与包契约 |
| Phase 3B 受控 Blind 运营 | 否 | 否 | 否 | 否 | 依赖真实私有案例、人员和基础设施，暂不推进代码扩张 |
| Phase 4 展示、Registry、托管 | 否 | 不适用 | 否 | 否 | 已从活跃产品剪除并延期 |

测试通过只支持 `internally verified`。它不是科学正确性、学习增益、独立审计成功或生产安全的证明。

## Phase 1：先关闭 Audit 核心风险

**当前状态：**`implemented` + `internally verified`，尚未 `field validated`。

保留的必要能力：clean Git baseline、外部 workspace、G0、finding/evidence 生命周期、本地事件链、preflight、rebaseline、verify 和人工复审报告。

必须先关闭的风险：

1. 每次读写都重新验证 workspace 仍在目标项目外，不能只在初始化时检查；
2. G0 只能有一个权威决定源，模板文字与机器状态不得互相矛盾；
3. 多文件变更要么原子提交，要么具备明确、可测试的恢复流程；
4. 在写入前执行大小和容量预检，拒绝“写入成功、随后无法验证”的状态；
5. 状态词已收口为 `g0-prerequisites-met`、`preflight-passed`、`local-records-consistent` 与 `preflight-current` 等精确范围，避免把流程状态误读为审计完成。

**下一退出门：**上述问题有回归测试，并由一个全新临时项目走通失败恢复；这仍只提升到更可靠的内部验证。

## Phase 2：让人工真的审到被冻结的材料

**当前状态：**`implemented` + `internally verified`，尚未 `field validated`。

保留的必要能力：外部学习工作区、结构检查、不可变 attempt、多审阅者记录、重做关系、四档人工 rubric、Capstone 和脱敏导出。

收口目标：

1. 提供 `attempt show` 或 reviewer packet，使审阅者看到系统实际绑定的冻结答案；
2. 用内容摘要绑定完整 learner-visible case，而不是只记录仓库 `HEAD`；
3. 合并竞争性的答题入口，明确 workspace worksheet 是唯一可提交入口；
4. 为 Capstone 提供可审查的 diff、日志、配置、审批或账本材料，而不只是一段叙述；
5. 保留人工判断边界，不用结构检查推断正确性或成熟度。

**下一退出门：**独立审阅者只依赖 reviewer packet 就能准确审阅指定 attempt，且修改题目材料会使 case binding 明确失效。

## Phase 3：保留发布契约，停止伪运营

### 3A 本地工具

**当前状态：**`implemented` + `internally verified`。

继续保留 Open Demo 导出、严格 manifest/checksum、三角色本地 staging 和 standalone verify。它们只证明保留字节与声明的包契约自洽，不提供 ACL、身份认证、保密、独立评测或科学结论。

### 3B 受控运营

**当前状态：**尚未 `implemented`，也不应通过继续堆叠本地代码伪装成完成。

只有同时具备以下外部条件才重新启动：全新且从未公开的案例、独立私有存储、最小权限、访问记录、冻结评分、独立 evaluator、受控执行、人工泄题复核、具名发布签署和撤回演练。

实验性的 readiness 工作不得进入核心基线，除非它直接服务一个已经确认的真实试点。

## Phase 4：已剪枝并延期

此前的离线展示原型虽然通过内部契约测试，但没有真实用户需求证据，而且会把没有共同 subject/case binding 的材料并列展示。它增加了大量重复 schema、文件系统防护和维护成本，却没有推进 Audit 或 Training 的核心闭环。

因此当前活跃产品不包含展示、Registry、Dashboard 或托管层。Git 历史保留设计过程；重新立项必须先满足：

1. 共享的 subject/case/artifact 身份模型已经稳定；
2. 至少一个真实 Audit 试点和一个真实 Training 试点完成；
3. 用户研究证明展示或协作是实际阻塞点；
4. 隐私、权限、无障碍、部署和维护责任有明确负责人。

## 新推进顺序

后续不再按“继续增加 Phase”推进，而按用户闭环和风险排序：

1. **剪枝与冻结基线**：移除旧训练目录、旧顶层别名和未验证的展示面；文档、CLI、测试和 CI 保持一致。
2. **Audit Core Closure**：关闭 Phase 1 的外置边界、G0 单一真源、事务恢复和写前容量问题。
3. **统一身份与证据模型**：定义 `subject → case → artifact → evidence → decision → review`，所有记录内容寻址并支持版本迁移。
4. **Audit 证据采集**：增加有摘要、命令、退出状态、环境和来源的 evidence import，而不是只保存自由文本引用。
5. **Training Reviewer Flow**：交付 reviewer packet、完整 case manifest 和 artifact-rich Capstone。
6. **真实公开审计试点**：选择一个公开研究仓库，让第二位人员只依赖导出材料完成复核，并记录完成时间、阻塞点和错误归因。
7. **真实学习者/审阅者试点**：观察是否能正确定位、证明和沟通问题；不以一次通过宣称学习增益。
8. **条件式恢复 Phase 3B**：只有真实私有案例、独立人员和基础设施到位后才启动。
9. **重新评估 Phase 4**：只根据试点暴露的真实导航或协作问题设计最小展示面。

任何步骤都不得因为测试数量增加而自动升级到 `field validated` 或 `production ready`。

## 进入下一步前的决策门

| 决策 | 必须回答的问题 |
| --- | --- |
| 修改 Audit schema | 是否保持旧 workspace 可识别、可迁移或明确拒绝？失败后如何恢复？ |
| 记录 evidence | 是否绑定真实 artifact 字节、生成方式、环境和责任人，而非只有文字描述？ |
| 记录人工 review | 审阅者看到的是否正是被签署的冻结对象？身份只是标签还是已认证主体？ |
| 宣称现场有效 | 是否有真实项目、真实人员、观察记录和失败案例？ |
| 发布 Blind Challenge | 未公开性、私有存储、最小权限、独立评测和撤回演练是否真实存在？ |
| 建设 UI/托管 | 核心 schema 是否稳定？试点是否证明它是当前最重要的阻塞？谁负责隐私、安全和运维？ |

当前最重要的里程碑不是新增功能，而是完成一次可由第二个人复核的真实 Audit。
