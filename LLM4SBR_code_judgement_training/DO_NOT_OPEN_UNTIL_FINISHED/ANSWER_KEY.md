# 答案与错误解析

先确认你已经填写 `ANSWER_SHEET.md`。

## 正确候选

正确的是 **Candidate C**。

它按论文公式 (4)–(15) 保持了四个关键语义：Top-r 索引与相似度权重一一对应；
padding 不参与 global attention 的归一化；long/global 与 short/local 正确配对；
uniformity 使用 batch 分布中的全部无序样本对。

## Candidate A：在 softmax 之后才屏蔽 padding，且没有重新归一化

位置：`global_preference`。

它先让真实位置和 padding 一起进入 softmax，再把 padding 权重乘成 0。这样真实位置
权重之和小于 1，global 表示会被按 padding 数量缩小。它最后除以一个恒为 1 的
`normalizer`，看起来像归一化，实际没有恢复真实位置的权重和。

为什么隐蔽：shape、前向、反向都正确；同长度 session 上甚至可能看不出问题。
损害：global 向量尺度与 batch padding/序列长度耦合，long-term 对齐、门控和预测均受影响。

最小反例：给同一真实 session 追加一个 mask=0 的位置。正确实现的 global 输出不变；
A 的输出会变。正确做法是在 softmax 前把无效 logits 设为负无穷，或在乘 mask 后按
真实权重和重新归一化。

## Candidate B：Top-r item 与错误的相似度权重配对

位置：`localize_intent`。

代码用 `topk` 得到了正确 item 索引，却用 `similarities[:, :topk]` 作为权重。这些是
item 表前 r 行的分数，不是被选中 Top-r item 的分数；随后又除以 `topk`，而论文
公式 (5) 是对应相似度加权后求和，没有这个平均。

这对应原仓库 `Intent_Localization.py` 中一个非常值得警惕的细节：原代码把 top-5
embedding 与完整 similarity tensor 的前五项 zip。训练题的正确基线依据论文公式
修正了这个问题，因此没有把上游已有缺陷伪装成正确答案。

为什么隐蔽：索引和权重的 shape 都是 `[batch, r]`，广播完全合法；若真正 Top-r
刚好位于表前 r 行，小样本还会偶然通过。

最小反例：构造 query，使最相似 item 位于表末尾，并让前 r 个 item 相似度接近 0。
检查输出是否使用末尾 item 自己的 top-k score。

## Candidate D：把 long/short view 与 local/global 行为表示交叉接错

位置：`forward` 中 DirectAU、gate 和 fusion 段。

论文公式 (10)–(12) 明确规定 long-term inference 对应 global behavior，short-term
inference 对应 local behavior。D 却让 long 对齐/门控 local，让 short 对齐/门控
global，并把错误分支继续送入 fusion。

为什么隐蔽：四种表示都是 `[batch, hidden_dim]`，所有加法、loss 和拼接都合法。
损害：辅助目标会把稳定兴趣拉向最后一次点击，把即时意图拉向全局历史；门控也会
强化错误的行为分支，长短期差异明显的数据上尤其伤性能。

最小反例：令 long/short 语义向量正交，令 local/global 行为向量分别只在对应维度
非零，固定线性层为单位/选择矩阵后追踪两个分支。

## Candidate E：uniformity 只比较环上相邻样本

位置：`uniformity_loss`。

论文公式 (9) / DirectAU 期望来自同一分布的样本对距离。正确实现用 `torch.pdist`
覆盖全部无序对。E 只比较每个样本与 `roll(1)` 后的邻居，结果取决于 batch 内排列，
且只覆盖 O(B) 对而不是 O(B²) 对。

为什么隐蔽：loss 标量有限、可微，复杂度还更低；随机 batch 上曲线看起来也可能正常。
损害：同一 batch 仅仅重排顺序就会改变目标和梯度，表示空间受到有偏、方差更大的
排斥力，可能形成局部结构或不稳定训练。

最小反例：固定一组 4 个不等距向量，计算 loss；打乱 batch 顺序再算并比较。正确
all-pairs uniformity 不变，E 通常会变化。

## 改动比例

以 Candidate C 的 88 条非空、非注释逻辑行为基准，用行级序列 diff 计算：

- A：5 行，5.68%
- B：4 行，4.55%
- D：5 行，5.68%
- E：4 行，4.55%

这比追求恰好 5.00% 更接近真实代码审查：每个候选只有一个集中、连贯的算法错误，
没有为了凑行数加入无关噪声。
