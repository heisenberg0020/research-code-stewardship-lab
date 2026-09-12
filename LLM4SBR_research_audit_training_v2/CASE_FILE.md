# LLM4SBR Research Audit v2 — Case File

[English](CASE_FILE_EN.md) · [课程主页](README.md) · [发布模型](../docs/CASE_RELEASE_MODEL.md)

| 字段 | 当前记录 |
| --- | --- |
| Case ID | `rcsl/llm4sbr-research-audit-v2` |
| 发布状态 | `current · Open Demo` |
| 版本依据 | 本仓库 Git commit；导出审计证据时记录准确 commit |
| 维护责任 | 本仓库维护者 |
| 教学目的 | 训练从算法语义到 Agent 治理的基于证据的人工判断 |

## 研究对象与来源

- 论文：[LLM4SBR: A Lightweight and Effective Framework for Integrating Large Language Models in Session-based Recommendation](https://arxiv.org/abs/2402.13840)
- 官方实现：[tsinghua-fib-lab/LLM4SBR](https://github.com/tsinghua-fib-lab/LLM4SBR)
- 本案例不重新分发论文 PDF、上游源码或原始数据；第三方边界见 [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。
- 训练候选、确定性小型 fixture、验证器和说明是独立的教育产物，不代表原作者实现中的问题。

## G0 研究契约摘要

- **允许主张：**本案例可用于练习识别可运行研究产物中的契约偏差，并评估学习者提交的证据链。
- **禁止外推：**公开检查不能证明论文结论、复现原论文结果、衡量真实生产安全性，或给出保密盲测成绩。
- **运行边界：**公开检查使用本地、小型、确定性材料；不需要网络、完整训练、原始数据或 GPU。
- **人类保留决策：**论文—代码冲突的解释、实验公平性、风险接受、最终 claim 与发布决定。
- **停止条件：**来源或许可不明、保护材料暴露、公开输出泄露教学判定，或上游协议发生实质变化。

## 覆盖范围

| Level | 首个失效契约 | 公开证据形态 |
| --- | --- | --- |
| L1 | 公式、算子、索引、loss 或梯度语义 | 候选实现、论文映射、极小 smoke path |
| L2 | 数据身份、切分、状态、checkpoint 或评估流 | 多文件流水线、冻结规格、运行产物 |
| L3 | 比较设计、证据总体、统计规则或 claim 范围 | planned/observed runs、aggregate、结构化 claim |
| L4 | 授权、审批、预算、记录或受保护证据边界 | 冻结协议、事件、审批、资源和报告账本 |
| Capstone | 多个层级信号交互时的分诊、委派、影响面与发布判断 | 公开合成事故 brief、跨层 response、具名人工复核 |

当前案例包含一个公开、合成的跨层 capstone，但不包含陌生私有项目 capstone、真实供应链审查、生产部署生命周期或访问受控的评测服务。它不应被描述为保密或未见测试。

## 本地学习进度与人工复核

`python scripts/rcsl.py train progress ...` 可以在仓库外创建学习者自有工作区，保存 L1–L4 与 Capstone worksheet、不可变提交快照、重做关系、人工反馈和脱敏导出。自动 `check` 只确认必需小节、非空内容和模板提示是否已处理；它不判断答案语义、科学正确性或成熟度。

Recognize / Prove / Direct / Steward 只能由具名人工审阅者声明。L1–L4 的人工 `pass` 要求审阅者把 Recognize 与 Prove 记录为 `demonstrated`；Capstone 的人工 `pass` 要求四档都记录为 `demonstrated`。CLI 只校验声明内部一致性，不验证判断本身。详见 [Mode Train 指南](../docs/TRAIN_MODE.md)。

## 公开验证

从仓库根目录运行：

```bash
python skills/research-code-audit-training/scripts/validate_training_package.py \
  LLM4SBR_research_audit_training_v2
python LLM4SBR_research_audit_training_v2/run_all_public_checks.py
```

预期的四行 `LEVEL n: PASS` 仅说明当前公开验证器的包契约通过。它不披露教学判定，也不替代人工审计。学习工作区显示的 `structure=complete` 同样不等于语义、科学或成熟度通过。

## 发布与隔离边界

本案例与教师侧相关的材料位于同一个公开 Git 仓库，因此隔离方式是 **honor isolation**，不是访问控制。它适合教学演示、流程练习和回归测试，但不应描述为安全的 Blind Challenge。真正盲测必须采用独立的公开 Challenge Package、受控 Evaluator Package 和受控 Maintainer Record。

## 复审触发条件

出现以下任一情况时，将本 Case File 标记为 `awaiting review`，再决定修订、替代或撤回：

- 论文、官方实现或相关数据协议发生实质变化；
- 发现不公平提示、教学判定暴露或第二个主要缺陷；
- 依赖、运行环境或公共接口改变；
- 来源、许可、安全、隐私或伦理边界改变；
- 公开验证器不再稳定复现其声明的包契约。
