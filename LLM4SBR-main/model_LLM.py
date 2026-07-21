import datetime
import math
import numpy as np
import torch
from torch import nn
from torch.nn import Module, Parameter
import torch.nn.functional as F
import os
from tqdm import tqdm
import re
import ast
import pandas as pd
import copy
import warnings
from math import log


# 本文件是推荐模型主体：
# - GNN：在每个 session 内构造的有向图上做消息传递；
# - SessionGraph：SR-GNN 风格的会话表示学习模型，并额外融合 LLM 语义 embedding；
# - train_test：完成一个 epoch 的训练和测试，返回 Recall/MRR/NDCG。

class GNN(Module):
    """会话图神经网络单元。

    每个会话会被转成一个小图：节点是该会话中出现过的 item，
    边表示 item 的点击转移关系。GNN 通过入边/出边邻接矩阵传播信息。
    """

    def __init__(self, hidden_size, step=1):
        super(GNN, self).__init__()
        # step 表示图神经网络传播轮数；hidden_size 是每个 item 的向量维度。
        self.step = step
        self.hidden_size = hidden_size
        self.input_size = hidden_size * 2
        self.gate_size = 3 * hidden_size
        # GRU 风格门控参数：reset gate、input/update gate、new gate 三组参数。
        self.w_ih = Parameter(torch.Tensor(self.gate_size, self.input_size))
        self.w_hh = Parameter(torch.Tensor(self.gate_size, self.hidden_size))
        self.b_ih = Parameter(torch.Tensor(self.gate_size))
        self.b_hh = Parameter(torch.Tensor(self.gate_size))
        self.b_iah = Parameter(torch.Tensor(self.hidden_size))
        self.b_oah = Parameter(torch.Tensor(self.hidden_size))

        self.linear_edge_in = nn.Linear(self.hidden_size, self.hidden_size, bias=True)
        self.linear_edge_out = nn.Linear(self.hidden_size, self.hidden_size, bias=True)
        self.linear_edge_f = nn.Linear(self.hidden_size, self.hidden_size, bias=True)

    def GNNCell(self, A, hidden):
        """执行一轮 GNN 消息传递。

        A 的前半部分是入边归一化邻接矩阵，后半部分是出边归一化邻接矩阵。
        hidden 是当前 batch 中每个 session 图节点的表示。
        """
        # 分别聚合入边和出边方向的邻居信息，再拼接成 GRU 输入。
        input_in = torch.matmul(A[:, :, :A.shape[1]], self.linear_edge_in(hidden)) + self.b_iah
        input_out = torch.matmul(A[:, :, A.shape[1]: 2 * A.shape[1]], self.linear_edge_out(hidden)) + self.b_oah
        inputs = torch.cat([input_in, input_out], 2)
        # gi 由图邻居消息产生，gh 由上一轮节点状态产生。
        gi = F.linear(inputs, self.w_ih, self.b_ih)
        gh = F.linear(hidden, self.w_hh, self.b_hh)
        # 拆成三组门控分量。
        i_r, i_i, i_n = gi.chunk(3, 2)
        h_r, h_i, h_n = gh.chunk(3, 2)
        resetgate = torch.sigmoid(i_r + h_r)
        inputgate = torch.sigmoid(i_i + h_i)
        newgate = torch.tanh(i_n + resetgate * h_n)
        # 使用 GRU 更新公式融合新消息和旧隐藏状态。
        hy = newgate + inputgate * (hidden - newgate)
        return hy

    def forward(self, A, hidden):
        # 多轮传播可以让 item 节点看到更远的点击转移上下文。
        for i in range(self.step):
            hidden = self.GNNCell(A, hidden)
        return hidden


class SessionGraph(Module):
    """融合行为序列和 LLM 语义意图的会话推荐模型。"""

    def __init__(self, opt, n_node):
        super(SessionGraph, self).__init__()
        self.hidden_size = opt.hiddenSize
        self.n_node = n_node
        self.batch_size = opt.batchSize
        self.nonhybrid = opt.nonhybrid
        # item embedding 表，索引 0 通常作为 padding，因此评分时会跳过第 0 行。
        self.embedding = nn.Embedding(self.n_node, self.hidden_size)
        self.gnn = GNN(self.hidden_size, step=opt.step)
        # 注意力聚合层：用于从 session 中所有 item 表示得到全局兴趣 a。
        self.linear_one = nn.Linear(self.hidden_size, self.hidden_size, bias=True)
        self.linear_two = nn.Linear(self.hidden_size, self.hidden_size, bias=True)
        self.linear_three = nn.Linear(self.hidden_size, 1, bias=False)
        # 将全局兴趣 a 与最后一次点击 ht 拼接后压回 hidden_size。
        self.linear_transform = nn.Linear(self.hidden_size * 2, self.hidden_size, bias=True)
        # LLM/BERT 语义向量通常是 768 维，这里映射到推荐模型 hidden_size。
        self.linear_text2seq = nn.Linear(768, self.hidden_size, bias=True)
        # 两个门控层分别控制长兴趣和短兴趣语义向量对行为表示的增强强度。
        self.linear_four = nn.Linear(self.hidden_size, 1, bias=False)
        self.linear_five = nn.Linear(self.hidden_size, 1, bias=False)
        self.loss_function = nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(self.parameters(), lr=opt.lr, weight_decay=opt.l2)
        self.scheduler = torch.optim.lr_scheduler.StepLR(self.optimizer, step_size=opt.lr_dc_step, gamma=opt.lr_dc)

        self.reset_parameters()

    def reset_parameters(self):
        """用均匀分布初始化所有可学习参数。"""
        stdv = 1.0 / math.sqrt(self.hidden_size)
        for weight in self.parameters():
            weight.data.uniform_(-stdv, stdv)

    def parse_embedding(self, embedding_str):
        """把 xlsx 中保存的字符串形式向量解析为 tensor。"""
        embedding_values = ast.literal_eval(embedding_str)
        embedding_tensor = trans_to_cuda(torch.tensor(embedding_values).float())
        return embedding_tensor
    def LLM_enhance(self, text_long_list):  # (b,d)
        """将一批 LLM 语义 embedding 转成推荐模型使用的 hidden_size 维表示。"""
        text_long_emb = [self.parse_embedding(text_long) for text_long in text_long_list]
        text_long_emb = torch.cat(text_long_emb, dim=0)
        text_long_emb = self.linear_text2seq(text_long_emb)

        return text_long_emb #[b,d]

    def alignment(self, x, y):
        """对齐损失：鼓励行为表示和语义表示在归一化空间里更接近。"""
        x, y = F.normalize(x, dim=-1), F.normalize(y, dim=-1)
        return (x - y).norm(p=2, dim=1).pow(2).mean()

    def uniformity(self, x):
        """均匀性约束：避免所有表示塌缩到同一个点。"""
        x = F.normalize(x, dim=-1)
        return torch.pdist(x, p=2).pow(2).mul(-2).exp().mean().log()

    def calculate_loss(self, emb_1, emb_2):
        """组合 alignment 和 uniformity，形成语义-行为表示的辅助损失。"""
        align = self.alignment(emb_1, emb_2)
        uniform = (self.uniformity(emb_1) + self.uniformity(emb_2)) / 2
        loss = align + uniform
        return loss

    def compute_scores(self, hidden, mask, text_long, text_short):
        """根据 session 表示计算所有候选 item 的打分。

        hidden: batch 内每条 session 每个位置的 GNN 表示。
        mask: padding 位置为 0，真实点击位置为 1。
        text_long/text_short: LLM 得到的长期/短期兴趣 embedding 字符串。
        """
        # ht 是每条 session 最后一个真实点击 item 的表示，常用于建模短期兴趣。
        ht = hidden[torch.arange(mask.shape[0]).long(), torch.sum(mask, 1) - 1]
        # 计算对 session 内每个位置的注意力权重 alpha。
        q1 = self.linear_one(ht).view(ht.shape[0], 1, ht.shape[1])
        q2 = self.linear_two(hidden)
        alpha = self.linear_three(torch.sigmoid(q1 + q2))
        alpha = F.softmax(alpha, 1)
        # a 是带 mask 的加权和，表示整条 session 的全局/长期行为兴趣。
        a = torch.sum(alpha * hidden * mask.view(mask.shape[0], -1, 1).float(), 1)

        # 将 LLM 语义兴趣映射到与行为表示相同的向量空间。
        long_text_emb = self.LLM_enhance(text_long)
        short_text_emb = self.LLM_enhance(text_short)

        # 辅助损失分别约束：全局行为兴趣 a 对齐长期语义兴趣，最后点击 ht 对齐短期语义兴趣。
        au_loss_1 = self.calculate_loss(a, long_text_emb)
        au_loss_2 = self.calculate_loss(ht, short_text_emb)

        # 根据行为表示和文本表示的匹配程度生成门控系数，动态增强行为表示。
        l_alpha = self.linear_four(torch.sigmoid(a + long_text_emb))
        s_alpha = self.linear_five(torch.sigmoid(ht + short_text_emb))
        a = a * l_alpha
        ht = ht * s_alpha

        # 拼接长期全局兴趣与短期最后点击兴趣，得到最终 session 向量。
        a = self.linear_transform(torch.cat([a, ht], 1))


        # 与所有 item embedding 做点积，得到候选 item 分数；跳过 padding item 0。
        b = self.embedding.weight[1:]
        scores = torch.matmul(a, b.transpose(1, 0))

        return scores, (au_loss_1 + au_loss_2) * 0.1

    def forward(self, inputs, A):
        # 先查 item embedding，再经过 session 图 GNN 更新节点表示。
        hidden = self.embedding(inputs)
        hidden = self.gnn(A, hidden)
        return hidden


def trans_to_cuda(variable):
    """CUDA 可用时把 tensor/model 放到 GPU，否则保持在 CPU。"""
    if torch.cuda.is_available():
        return variable.cuda()
    else:
        return variable


def trans_to_cpu(variable):
    """评估阶段需要转 numpy 时，先把 GPU tensor 搬回 CPU。"""
    if torch.cuda.is_available():
        return variable.cpu()
    else:
        return variable

def parse_embedding(embedding_str):
    """独立的 embedding 字符串解析函数；当前主要逻辑使用类方法版本。"""
    embedding_values = ast.literal_eval(embedding_str)
    embedding_tensor = trans_to_cuda(torch.tensor(embedding_values).float())
    return embedding_tensor


def forward(model, i, data):
    """取一个 batch，完成模型前向传播并返回 target、scores 和辅助损失。"""
    alias_inputs, A, items, mask, targets, text_long, text_short = data.get_slice(i)
    # numpy/list 数据转成 PyTorch tensor，并尽可能搬到 GPU。
    alias_inputs = trans_to_cuda(torch.Tensor(alias_inputs).long())
    items = trans_to_cuda(torch.Tensor(items).long())
    A = trans_to_cuda(torch.Tensor(A).float())
    mask = trans_to_cuda(torch.Tensor(mask).long())
    hidden = model(items, A)
    # hidden 是去重节点顺序下的表示；alias_inputs 把它还原成原始点击序列顺序。
    get = lambda i: hidden[i][alias_inputs[i]]
    seq_hidden = torch.stack([get(i) for i in torch.arange(len(alias_inputs)).long()])
    scores, au_loss = model.compute_scores(seq_hidden, mask, text_long, text_short)
    return targets, scores, au_loss


def train_test(model, train_data, test_data):
    """训练一个 epoch，并在测试集上计算 Recall、MRR、NDCG。"""
    print('start training: ', datetime.datetime.now())
    model.train()
    total_loss = 0.0
    slices = train_data.generate_batch(model.batch_size)
    for i, j in zip(slices, np.arange(len(slices))):
        # 标准训练流程：清梯度 -> 前向 -> 交叉熵 + 辅助损失 -> 反向传播 -> 更新参数。
        model.optimizer.zero_grad()
        targets, scores, au_loss = forward(model, i, train_data)
        targets = trans_to_cuda(torch.Tensor(targets).long())
        # targets 从 1 开始编号，而 scores 对应 embedding.weight[1:]，所以目标下标要减 1。
        loss = model.loss_function(scores, targets - 1)
        loss = loss + au_loss
        loss.backward()
        model.optimizer.step()
        total_loss += loss
        if j % int(len(slices) / 5 + 1) == 0:
            print('[%d/%d] Loss: %.4f, au_loss: %.4f' % (j, len(slices), loss.item(), au_loss.item()))
    print('\tLoss:\t%.3f' % total_loss)
    model.scheduler.step()

    print('start predicting: ', datetime.datetime.now())
    model.eval()
    hit_5, hit_10, hit_20 = [], [], []
    mrr_5, mrr_10, mrr_20 = [], [], []
    ndcg_5, ndcg_10, ndcg_20 = [], [], []

    slices = test_data.generate_batch(model.batch_size)

    for i in slices:
        targets, scores, au_loss= forward(model, i, test_data)
        # 只取 top-20 候选；top-5/top-10 指标从 top-20 结果中切片得到。
        sub_scores = scores.topk(20)[1]
        sub_scores = trans_to_cpu(sub_scores).detach().numpy()

        for score, target, mask in zip(sub_scores, targets, test_data.mask):
            # Recall@K：目标 item 是否出现在 top-K 推荐列表中。
            hit_5.append(np.isin(target - 1, score[:5]))
            hit_10.append(np.isin(target - 1, score[:10]))
            hit_20.append(np.isin(target - 1, score[:20]))

            if len(np.where(score == target - 1)[0]) == 0:
                # 如果 top-20 都没命中，MRR/NDCG 记为 0。
                mrr_5.append(0)
                mrr_10.append(0)
                mrr_20.append(0)
                ndcg_5.append(0)
                ndcg_10.append(0)
                ndcg_20.append(0)
            else:
                # rank 从 1 开始；MRR=1/rank，NDCG 使用 log2 折扣。
                rank = np.where(score == target - 1)[0][0] + 1
                if rank <= 5:
                    mrr_5.append(1 / rank)
                    ndcg_5.append(1 / log(rank + 1, 2))
                if rank <= 10:
                    mrr_10.append(1 / rank)
                    ndcg_10.append(1 / log(rank + 1, 2))
                if rank <= 20:
                    mrr_20.append(1 / rank)
                    ndcg_20.append(1 / log(rank + 1, 2))

    # 转成百分比形式输出，便于论文/实验表格对齐。
    hit_5 = np.mean(hit_5) * 100
    hit_10 = np.mean(hit_10) * 100
    hit_20 = np.mean(hit_20) * 100
    mrr_5 = np.mean(mrr_5) * 100
    mrr_10 = np.mean(mrr_10) * 100
    mrr_20 = np.mean(mrr_20) * 100
    ndcg_5 = np.mean(ndcg_5) * 100
    ndcg_10 = np.mean(ndcg_10) * 100
    ndcg_20 = np.mean(ndcg_20) * 100

    return hit_5, hit_10, hit_20, mrr_5, mrr_10, mrr_20, ndcg_5, ndcg_10, ndcg_20
