from Characters.Chat_characters import Momotalk
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import warnings
warnings.simplefilter("ignore")
role = "hina"

chat_language = "zh"
speech_language = "jp"

momotalk = Momotalk(role)
chat = momotalk.start_chat()

while True:
    content = input("input: ")
    if content == "quit":
        break
    if content == "":
        warnings.warn("输入不能为空")
        continue
    response = chat.send_message(
        content=content,
        safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
        },
    )
    # print(response.text)
    response_cleaned = momotalk.clean_response(response)
    print(response_cleaned)

    momotalk.speech(response_cleaned)