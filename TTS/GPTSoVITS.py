from GPT_SoVITS.TTS_infer_pack.TTS import TTS_Config, TTS
from tools.i18n.i18n import I18nAuto, scan_language_list
import sys
import os
import torch
import argparse
import yaml
from GPT_SoVITS.inference_webui_fast import inference
from io import BytesIO
import time
import numpy as np
import subprocess
import soundfile as sf


def save_audio(audio_data, filename):
    # 使用二进制模式打开文件，保存音频数据
    with open(filename, "wb") as audio_file:
        audio_file.write(audio_data)

def pack_ogg(io_buffer:BytesIO, data:np.ndarray, rate:int):
    with sf.SoundFile(io_buffer, mode='w', samplerate=rate, channels=1, format='ogg') as audio_file:
        audio_file.write(data)
    return io_buffer

def pack_raw(io_buffer:BytesIO, data:np.ndarray, rate:int):
    io_buffer.write(data.tobytes())
    return io_buffer


def pack_wav(io_buffer:BytesIO, data:np.ndarray, rate:int):
    io_buffer = BytesIO()
    sf.write(io_buffer, data, rate, format='wav')
    return io_buffer

def pack_aac(io_buffer:BytesIO, data:np.ndarray, rate:int):
    process = subprocess.Popen([
        'ffmpeg',
        '-f', 's16le',  # 输入16位有符号小端整数PCM
        '-ar', str(rate),  # 设置采样率
        '-ac', '1',  # 单声道
        '-i', 'pipe:0',  # 从管道读取输入
        '-c:a', 'aac',  # 音频编码器为AAC
        '-b:a', '192k',  # 比特率
        '-vn',  # 不包含视频
        '-f', 'adts',  # 输出AAC数据流格式
        'pipe:1'  # 将输出写入管道
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = process.communicate(input=data.tobytes())
    io_buffer.write(out)
    return io_buffer

def pack_audio(io_buffer:BytesIO, data:np.ndarray, rate:int, media_type:str):
    if media_type == "ogg":
        io_buffer = pack_ogg(io_buffer, data, rate)
    elif media_type == "aac":
        io_buffer = pack_aac(io_buffer, data, rate)
    elif media_type == "wav":
        io_buffer = pack_wav(io_buffer, data, rate)
    else:
        io_buffer = pack_raw(io_buffer, data, rate)
    io_buffer.seek(0)
    return io_buffer

class Sovits_audio_generator():
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        is_half = eval(self.config["is_half"]) and torch.cuda.is_available()
        gpt_path = self.config["gpt_path"]
        sovits_path = self.config["sovits_path"]
        cnhubert_base_path = self.config["cnhubert_base_path"]
        bert_path = self.config["bert_path"]
        language = self.config["language"]
        version = self.config["version"]

        i18n = I18nAuto(language=language)

        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

        dict_language = {
            "中文": "all_zh",#全部按中文识别
            "英文": "en",#全部按英文识别#######不变
            "日文": "all_ja",#全部按日文识别
            "粤语": "all_yue",#全部按中文识别
            "韩文": "all_ko",#全部按韩文识别
            "中英混合": "zh",#按中英混合识别####不变
            "日英混合": "ja",#按日英混合识别####不变
            "粤英混合": "yue",#按粤英混合识别####不变
            "韩英混合": "ko",#按韩英混合识别####不变
            "多语种混合": "auto",#多语种启动切分识别语种
            "多语种混合(粤语)": "auto_yue",#多语种启动切分识别语种
        }

        cut_method = {
            "不切":"cut0",
            "凑四句一切": "cut1",
            "凑50字一切": "cut2",
            "按中文句号。切": "cut3",
            "按英文句号.切": "cut4",
            "按标点符号切": "cut5",
        }

        tts_config = TTS_Config("TTS/GPT_SoVITS/configs/tts_infer.yaml")
        tts_config.device = device
        tts_config.is_half = is_half
        tts_config.version = version
        if gpt_path is not None:
            tts_config.t2s_weights_path = gpt_path
        if sovits_path is not None:
            tts_config.vits_weights_path = sovits_path
        if cnhubert_base_path is not None:
            tts_config.cnhuhbert_base_path = cnhubert_base_path
        if bert_path is not None:
            tts_config.bert_base_path = bert_path

        self.tts_pipeline = TTS(tts_config)

        self.text_language = self.config["text_language"] # 需要合成的文本的语种
        self.input_ref = self.config['ref_audio'] # 主参考音频文件路径
        self.input_refs = self.config['ref_audio_list'] # 辅助参考音频，可选
        self.prompt_text = self.config['prompt_text'] # 主参考音频的文本
        self.prompt_language = self.config['prompt_language'] # 主参考音频的语种
        self.top_k = self.config['top_k'] # [1, 1, 100]
        self.top_p = self.config['top_p'] # [0, 0.05, 1]
        self.temperature = self.config['temperature'] # [0, 0.05, 1]
        self.how_to_cut = self.config["how_to_cut"]
        self.batch_size = self.config['batch_size'] # [1, 1, 200]
        self.speed_factor = self.config["speed_factor"]  # [0.6, 0.05, 1.65]
        self.ref_text_free = self.config["ref_text_free"] # True or False
        self.split_bucket = self.config["split_bucket"] # True or False
        self.fragment_interval = self.config["fragment_interval"] # [0.01, 0.01, 1] 分割时间
        self.seed = self.config["seed"] # 随机种子
        self.keep_random = self.config["keep_random"] # 保持随机 True or False
        self.parallel_infer = self.config["parallel_infer"] # 并行推理 True or False
        self.repetition_penalty = self.config["repetition_penalty"] # [0, 0.05, 2] 重复惩罚

    def generate_audio(self, text):
        [output, seed] = next(inference(
            self.tts_pipeline,
            text, self.text_language, self.input_ref, self.input_refs,
            self.prompt_text, self.prompt_language, 
            self.top_k, self.top_p, self.temperature, 
            self.how_to_cut, self.batch_size, 
            self.speed_factor, self.ref_text_free,
            self.split_bucket, self.fragment_interval,
            self.seed, self.keep_random, self.parallel_infer,
            self.repetition_penalty
        ))
        media_type = self.config["media_type"]
        sr, audio_data = output[0], output[1]
        audio_data = pack_audio(BytesIO(), audio_data, sr, media_type).getvalue()
        return audio_data
