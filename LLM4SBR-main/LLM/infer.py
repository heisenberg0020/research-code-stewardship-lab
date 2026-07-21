from modelscope import AutoModelForCausalLM, AutoTokenizer
from modelscope import GenerationConfig
from nltk.chat import Chat
import json
import csv
from tqdm import tqdm
import openpyxl
import torch
import os

# LLM 批量推理脚本：
# 从 data/Ml-1M/{Process_File}.json 读取 prompt，
# 使用本地 Qwen-7B-Chat 生成长期/短期兴趣文本，
# 并把 prompt 与回复写入 xlsx，供 Intent_Localization.py 进一步转成 embedding。

# 模型路径：这里默认使用项目上级目录中的本地 Qwen-7B-Chat。
MODEL_PATH = "../Qwen-7B-Chat"
# Process_File 控制输入/输出文件名，例如 tra_session_short、tes_session_long。
Process_File = "tra_session_short"

# Note: The default behavior now has injection attack prevention off.
# trust_remote_code=True 允许加载 ModelScope 模型仓库中的自定义模型代码。
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)

# use fp16
# device_map="cuda:4" 表示将模型放到第 4 张 GPU；如果机器 GPU 编号不同，需要修改。
model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, device_map="cuda:4", trust_remote_code=True, fp16=True)
model.eval()

def batch_generator(data, batch_size):
    """按 batch_size 分块遍历 prompt，避免一次性处理过多文本。"""
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]


# 读取由数据预处理脚本生成的 prompt JSON。
json_file_path = "data/Ml-1M/"+Process_File+".json"

with open(json_file_path, 'r', encoding='utf-8') as json_file:
    data = json.load(json_file)
# 每条数据格式为 {"prompt": "..."}，这里只取 prompt 文本。
all_raw_text = [item['prompt'] for item in data]
all_raw_text = all_raw_text

xlsx_file_path = "data/Ml-1M/"+Process_File+".xlsx"
# 创建一个
workbook = openpyxl.Workbook()

# 选择默认的工作表（第一个工作表）
sheet = workbook.active

header = ['Key', 'Value']
sheet.append(header)

# 批量写入数据
# 每条 prompt 调用一次 model.chat，Value 列保存模型回答。
# 注意：batch_size 只是外层分块大小，并没有真正做张量级并行生成。
batch_size = 5000
for batch in batch_generator(all_raw_text, batch_size):
    for raw_text in tqdm(batch, total=len(batch)):
        response, history = model.chat(tokenizer, raw_text, history=None)
        print(response)

        # 将数据写入Excel文件
        # Key 保存原始 prompt，Value 保存 Qwen 生成的兴趣 item 名称。
        sheet.append([raw_text, response])

# 保存工作簿到xlsx文件
workbook.save(xlsx_file_path)

print(f"数据已成功写入到 {xlsx_file_path}")






