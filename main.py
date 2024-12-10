import os
from fastapi import FastAPI, HTTPException, Request
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd
import requests
from dotenv import load_dotenv
import logging
import uvicorn

# 環境変数をロード
load_dotenv()

# OpenAI APIキーを環境変数から取得
openai.api_key = os.getenv("OPENAI_API_KEY")

# チャットワークAPIキーとルームIDを環境変数から取得
CHATWORK_API_TOKEN = os.getenv("CHATWORK_API_TOKEN")
CHATWORK_ROOM_ID = os.getenv("CHATWORK_ROOM_ID")

# FastAPIアプリケーションの作成
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Welcome to the AI integration API"}


@app.get("/youtube_transcript/{video_id}")
async def get_youtube_transcript(video_id: str):
    """YouTube動画IDから字幕を取得する"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([entry['text'] for entry in transcript])
        return {"video_id": video_id, "transcript": transcript_text}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error fetching transcript: {e}"
        )


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
            status_code=400, detail=f"Error loading spreadsheet: {e}"
        )


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
            status_code=500, detail=f"Error generating response: {e}"
        )


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
            status_code=500, detail=f"Error processing request: {e}"
        )


def send_chatwork_message(message: str):
    """チャットワークにメッセージを送信"""
    url = f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages"
    headers = {"X-ChatWorkToken": CHATWORK_API_TOKEN}
    data = {"body": message}
    response = requests.post(url, headers=headers, data=data)

    if response.status_code != 200:
        logging.error(f"ChatWork API Error: {response.text}")
        raise HTTPException(
            status_code=response.status_code, detail="Failed to send message"
        )
    return response.json()


@app.post("/chatwork_webhook/")
async def chatwork_webhook(request: Request):
    """チャットワークのWebhookからメッセージを受信"""
    try:
        data = await request.json()
        message_body = data.get("webhook_event", {}).get("body", "")

        if not message_body:
            raise HTTPException(
                status_code=400, detail="No message body found"
            )

        # OpenAIに質問を送信
        prompt = f"以下の質問に回答してください:\n{message_body}"
        response = await generate_response(prompt)

        # チャットワークに返信
        send_chatwork_message(response["response"])

        return {"status": "Message processed"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing webhook: {e}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
