import os
from fastapi import FastAPI, HTTPException, Request
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()  # 環境変数をロード

app = FastAPI()

# OpenAI APIキー
openai.api_key = os.getenv(
    "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")

# チャットワークAPIキーとルームID
CHATWORK_API_TOKEN = os.getenv(
    "d884411846999c80c15e63bef1be44c3")
CHATWORK_ROOM_ID = os.getenv("379360519")


@app.get("/")
async def root():
    return {"message": "Welcome to the AI integration API"}

# YouTube字幕の取得エンドポイント


@app.get("/youtube_transcript/{video_id}")
async def get_youtube_transcript(video_id: str):
    """YouTube動画IDから字幕を取得する"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([entry['text'] for entry in transcript])
        return {"video_id": video_id, "transcript": transcript_text}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error fetching transcript: {e}")

# スプレッドシートからデータをロード


@app.post("/load_spreadsheet/")
async def load_spreadsheet(file_path: str):
    """スプレッドシート（Excelファイル）からQ&Aデータをロードする"""
    try:
        df = pd.read_excel(file_path)
        if "質問" not in df.columns or "回答" not in df.columns:
            raise ValueError("スプレッドシートに'質問'または'回答'列がありません")
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error loading spreadsheet: {e}")

# OpenAIを使った応答生成


@app.post("/generate_response/")
async def generate_response(prompt: str):
    """OpenAI APIを使って応答を生成"""
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=200,
            n=1,
            stop=None,
            temperature=0.7,
        )
        return {"response": response.choices[0].text.strip()}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating response: {e}")

# 動画字幕 + OpenAI連携のデモ


@app.post("/youtube_to_response/")
async def youtube_to_response(video_id: str, user_question: str):
    """YouTube動画の字幕を解析し、質問に回答"""
    try:
        # 字幕を取得
        transcript = await get_youtube_transcript(video_id)
        transcript_text = transcript["transcript"]

        # OpenAIに質問を投げる
        prompt = f"以下の内容を基に質問に回答してください:\n{transcript_text}\n質問: {user_question}"
        response = await generate_response(prompt)

        return {"video_id": video_id, "response": response["response"]}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {e}")

# チャットワークAPIからメッセージを送信


def send_chatwork_message(message: str):
    """チャットワークにメッセージを送信"""
    url = f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages"
    headers = {"X-ChatWorkToken": CHATWORK_API_TOKEN}
    data = {"body": message}
    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code,
                            detail="Failed to send message")
    return response.json()

# チャットワークWebhookでメッセージを受信


@app.post("/chatwork_webhook/")
async def chatwork_webhook(request: Request):
    """チャットワークのWebhookからメッセージを受信"""
    try:
        data = await request.json()
        message_body = data.get("webhook_event", {}).get("body", "")

        if not message_body:
            raise HTTPException(
                status_code=400, detail="No message body found")

        # OpenAIに質問を送信
        prompt = f"以下の質問に回答してください:\n{message_body}"
        response = await generate_response(prompt)

        # チャットワークに返信
        send_chatwork_message(response["response"])

        return {"status": "Message processed"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing webhook: {e}")
