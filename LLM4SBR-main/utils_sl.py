#!/usr/bin/env python36
# -*- coding: utf-8 -*-
"""
Created on July, 2018

@author: Tangrizzly
"""

import networkx as nx
import numpy as np


# 工具函数文件：
# 负责把原始会话序列转成模型训练所需的 padded 序列、mask、batch 切片、
# 以及每个 session 内部的入边/出边归一化邻接矩阵。

def build_graph(train_data):
    """基于全部训练序列构建全局 item 转移图。

    这个函数保留自 SR-GNN 类代码，用于统计 item->item 的转移权重。
    当前主训练流程主要使用 Data.get_slice 中的“每个 session 局部图”。
    """
    graph = nx.DiGraph()
    for seq in train_data:
        # 遍历相邻点击，统计有向边出现次数。
        for i in range(len(seq) - 1):
            if graph.get_edge_data(seq[i], seq[i + 1]) is None:
                weight = 1
            else:
                weight = graph.get_edge_data(seq[i], seq[i + 1])['weight'] + 1
            graph.add_edge(seq[i], seq[i + 1], weight=weight)
    for node in graph.nodes:
        sum = 0
        # 对指向当前节点的入边权重求和，用于后续归一化。
        for j, i in graph.in_edges(node):
            sum += graph.get_edge_data(j, i)['weight']
        if sum != 0:
            # 将入边权重除以入边总和，使同一目标节点的入边权重可比较。
            for j, i in graph.in_edges(i):
                graph.add_edge(j, i, weight=graph.get_edge_data(j, i)['weight'] / sum)
    return graph


def data_masks(all_usr_pois, item_tail):
    """对变长 session 序列做 padding，并生成 mask。

    item_tail 通常为 [0]，表示用 0 补齐；mask 中真实 item 为 1，padding 为 0。
    """
    us_lens = [len(upois) for upois in all_usr_pois]
    len_max = max(us_lens)
    us_pois = [upois + item_tail * (len_max - le) for upois, le in zip(all_usr_pois, us_lens)]
    us_msks = [[1] * le + [0] * (len_max - le) for le in us_lens]
    return us_pois, us_msks, len_max


def split_validation(train_set, valid_portion):
    """随机打乱训练集，并按比例切分出验证集。"""
    train_set_x, train_set_y = train_set
    n_samples = len(train_set_x)
    sidx = np.arange(n_samples, dtype='int32')
    np.random.shuffle(sidx)
    n_train = int(np.round(n_samples * (1. - valid_portion)))
    valid_set_x = [train_set_x[s] for s in sidx[n_train:]]
    valid_set_y = [train_set_y[s] for s in sidx[n_train:]]
    train_set_x = [train_set_x[s] for s in sidx[:n_train]]
    train_set_y = [train_set_y[s] for s in sidx[:n_train]]

    return (train_set_x, train_set_y), (valid_set_x, valid_set_y)


class Data():
    """模型训练/评估数据包装器。

    它把 pickle 中的 (输入序列, 标签) 与 LLM embedding 对齐保存，
    并在 get_slice 时即时构造 batch 内每条 session 的图结构。
    """

    def __init__(self, data, text_long, text_short, shuffle=False, graph=None):
        inputs = data[0]
        # 先把所有输入序列 padding 到同一长度，方便组成 batch tensor。
        inputs, mask, len_max = data_masks(inputs, [0])
        # text_long/text_short 是与每条输入序列一一对应的语义 embedding 字符串。
        self.text_long = np.asarray(text_long)
        self.text_short = np.asarray(text_short)
        self.inputs = np.asarray(inputs)
        self.mask = np.asarray(mask)
        self.len_max = len_max
        self.targets = np.asarray(data[1])
        self.length = len(inputs)
        self.shuffle = shuffle
        self.graph = graph

    def generate_batch(self, batch_size):
        """生成 batch 索引切片；训练时可先整体打乱样本顺序。"""
        if self.shuffle:
            shuffled_arg = np.arange(self.length)
            np.random.shuffle(shuffled_arg)
            # 输入序列、长短期文本向量、mask、标签必须使用同一个乱序索引。
            self.inputs = self.inputs[shuffled_arg]
            self.text_long = self.text_long[shuffled_arg]
            self.text_short = self.text_short[shuffled_arg]
            self.mask = self.mask[shuffled_arg]
            self.targets = self.targets[shuffled_arg]
        n_batch = int(self.length / batch_size)
        if self.length % batch_size != 0:
            n_batch += 1
        slices = np.split(np.arange(n_batch * batch_size), n_batch)
        slices[-1] = slices[-1][:(self.length - batch_size * (n_batch - 1))]
        return slices

    def get_slice(self, i):
        """根据 batch 索引 i 构造模型前向传播需要的全部输入。

        返回：
        - alias_inputs：原始序列位置到去重节点列表的映射；
        - A：每条 session 的入边/出边归一化邻接矩阵；
        - items：每条 session 去重后的节点列表；
        - mask/targets/text_long/text_short：训练标签和语义特征。
        """
        inputs, mask, targets = self.inputs[i], self.mask[i], self.targets[i]
        text_long = self.text_long[i]
        text_short = self.text_short[i]
        items, n_node, A, alias_inputs = [], [], [], []
        # 每条 session 先统计去重 item 数，batch 内统一 padding 到 max_n_node。
        for u_input in inputs:
            n_node.append(len(np.unique(u_input)))
        max_n_node = np.max(n_node)
        for u_input in inputs:
            node = np.unique(u_input)
            items.append(node.tolist() + (max_n_node - len(node)) * [0])
            u_A = np.zeros((max_n_node, max_n_node))
            # 按原始点击顺序建立 item_i -> item_{i+1} 的有向边。
            for i in np.arange(len(u_input) - 1):
                if u_input[i + 1] == 0:
                    break
                u = np.where(node == u_input[i])[0][0]
                v = np.where(node == u_input[i + 1])[0][0]
                u_A[u][v] = 1
            # 入边方向按列归一化。
            u_sum_in = np.sum(u_A, 0)
            u_sum_in[np.where(u_sum_in == 0)] = 1
            u_A_in = np.divide(u_A, u_sum_in)
            # 出边方向按行归一化后转置，使维度与入边矩阵对齐。
            u_sum_out = np.sum(u_A, 1)
            u_sum_out[np.where(u_sum_out == 0)] = 1
            u_A_out = np.divide(u_A.transpose(), u_sum_out)
            # 拼接入边和出边邻接矩阵，GNNCell 会按前后两半分别读取。
            u_A = np.concatenate([u_A_in, u_A_out]).transpose()
            A.append(u_A)
            # alias_inputs 用于把去重节点表示还原回原始点击序列位置。
            alias_inputs.append([np.where(node == i)[0][0] for i in u_input])
        return alias_inputs, A, items, mask, targets, text_long, text_short
