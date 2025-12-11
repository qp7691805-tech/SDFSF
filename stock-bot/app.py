import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
import yfinance as yf

app = Flask(__name__)

# 讀取環境變數 (您的三把鑰匙會從這裡讀入)
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

@app.route("/")
def home():
    return "LINE Stock Bot is Running!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip().upper()

    # 簡單判斷：如果是數字，就當作股票代號處理
    if user_msg.isdigit():
        try:
            # 1. 抓取台股資料
            stock_id = f"{user_msg}.TW"
            stock = yf.Ticker(stock_id)
            info = stock.info

            # 如果找不到上市資料，嘗試上櫃 (.TWO)
            if 'regularMarketPrice' not in info and 'currentPrice' not in info:
                stock_id = f"{user_msg}.TWO"
                stock = yf.Ticker(stock_id)
                info = stock.info

            # 抓取近 5 天歷史股價
            history = stock.history(period="5d")

            if history.empty:
                reply_text = f"找不到代號 {user_msg}，請確認是否正確。"
            else:
                current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
                stock_name = info.get('longName', user_msg)

                # 2. 呼叫 Gemini AI 分析
                prompt = f"""
                你是專業分析師。請用繁體中文分析「{stock_name} ({user_msg})」：
                目前股價: {current_price}
                近五日收盤價: {history['Close'].to_list()}
                請給出100字以內的走勢簡評。
                """
                response = model.generate_content(prompt)
                ai_reply = response.text if response.text else "AI 暫時無法分析"

                reply_text = f"📊 {stock_name}\n股價：{current_price}\n\n🤖 AI 分析：\n{ai_reply}"

        except Exception as e:
            reply_text = "查詢發生錯誤，請稍後再試。"
    else:
        reply_text = "請輸入股票代號 (例如: 2330)"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run()