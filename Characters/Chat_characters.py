import google.generativeai as genai
import os
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import yaml
import re
import sys
now_dir = os.getcwd()
sys.path.append(now_dir)
sys.path.append("%s/TTS" % (now_dir))
from TTS.GPTSoVITS import Sovits_audio_generator, save_audio

class Momotalk(genai.GenerativeModel):
    def __init__(self, character):
        api_key = os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        with open(f"Characters/characters_config/{character}.yaml", "r") as f:
            self.character = yaml.safe_load(f)
        self.promt = self.get_prompt(self.character)
        super(Momotalk, self).__init__(
            model_name="models/gemini-1.5-flash",
            system_instruction=self.promt,
        )
        sovits_config = "/home/yumio/Code/MHCP_Momotalk/TTS/config.yaml"
        self.gsv = Sovits_audio_generator(sovits_config)
    
    def get_prompt(self, character):
        '''
        从yaml文件中获取设定和台词，组成prompt
        '''
        common_prompt = "接下来我会提供一些设定和台词，请你遵照这些设定、模仿这些台词来扮演角色并用日文与我对话、回答我的问题。注意使用日文。"
        character_prompt = f'''你的名字是{character['name']}，来自学园都市基沃托斯的{character['school']}，是{character['school']}的{character['grade']}学生。我是你的老师。
                            年龄是{character['age']}岁，身高是{character['height']}cm，爱好是{character['hobby']}，生日是{character['birthday']}。'''\
                            + character["intro"]

        feature_prompt = "你的萌点是："
        for i in range(len(character['features'])):
            feature_prompt += character['features'][i]
            feature_prompt += "、" if i < len(character['features']) - 1 else ","
        experience_prompt = "你的经历是：" + character["experience"]
        quote_prompt = "日文台词参考："
        for i in range(len(character["quotes_jp"])):
            quote_prompt += f'''\"{character["quotes_jp"][i]}\"'''
            quote_prompt += "、" if i < len(character["quotes_jp"]) - 1 else "，"
        prompt = common_prompt + character_prompt + feature_prompt + experience_prompt + quote_prompt + \
            "\n以上是我提供的设定和台词，请你遵照这些设定、萌点，重点是模仿这些台词来扮演角色并用日文与我对话、回答我的问题。注意使用日文！注意使用日文！注意使用日文！回复不要有太多省略号。不要太过标签化。" + \
            "同时，如果你的回答里面有数学符号，请用日文表达。"
        return prompt
    
    def clean_response(self, response):
        '''
        去掉心理活动和多余的空格，生成干净整洁的响应，主要用于TTS
        '''
        response_cleaned = re.sub(r'[\(\（].*?[\)\）]', "", response.text)
        # 把'’……'替换为'、'，防止在TTS时出现问题
        response_cleaned = re.sub(r'\…\…', '、', response_cleaned)
        response_cleaned = re.sub(r'\…', '、', response_cleaned)
        response_cleaned = re.sub(r'\s+', '', response_cleaned).strip()
        return response_cleaned
    
    def speech(self, text):
        '''
        语音合成
        '''
        audio_data = self.gsv.generate_audio(text)
        save_audio(audio_data, f"/home/yumio/Code/MHCP_Momotalk/TTS/TTS_output/hina/hina.wav")
        return audio_data
    
    # todo
    def get_emotion(self):
        pass

    def get_memory(self):
        pass

    def change_language(self, language):
        pass