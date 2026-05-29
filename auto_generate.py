import os
import re
import json
import feedparser
from google import genai
from bs4 import BeautifulSoup
from datetime import datetime

# 1. 設定與初始化
SUBSTACK_FEED_URL = "https://mimivsjames2.substack.com/feed"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 使用 Google 全新世代的 SDK 初始化寫法
client = genai.Client(api_key=GEMINI_API_KEY)

def is_already_processed(title):
    """檢查 index.html 是否已經有這篇文章"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            content = f.read()
            return title in content
    except FileNotFoundError:
        return False

def get_unprocessed_articles():
    """獲取所有尚未處理的 Substack 新文章列表"""
    feed = feedparser.parse(SUBSTACK_FEED_URL)
    new_articles = []
    
    for entry in feed.entries:
        if is_already_processed(entry.title):
            break
            
        soup = BeautifulSoup(entry.content[0].value, "html.parser")
        clean_text = soup.get_text(separator='\n', strip=True)
        
        new_articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published_parsed,
            "content": clean_text
        })
        
    return new_articles

def generate_data_with_gemini(article):
    """呼叫 Gemini 同時生成 HTML 與標的清單"""
    prompt = f"""
    你現在是一位專業的科技與投資分析師。
    請閱讀以下文章內容，並將其重點整理成一個「投資研究儀表板」的 HTML。
    
    【文章標題】：{article['title']}
    【文章內容】：
    {article['content'][:15000]}
    
    【⚠️ 輸出格式嚴格要求】：
    請務必只輸出合法的 JSON 格式，包含兩個 key：
    1. "targets": 一個陣列，包含文章中主要提到的投資標的（如股票代號 "NVDA" 或公司名稱）。若無提及具體標的，請給空陣列 []。
    2. "html": 完整的 HTML 程式碼字串（需包含 <!DOCTYPE html>, <html>, <head>, <body>）。
       - HTML 設計要求：背景色 #f4f7f6，使用 Cards 排版，適度加上顏色標籤。
       - 若有數據，請用 Chart.js 畫圖。
       
    請不要輸出任何 Markdown 標記 (例如 ```json )，只輸出純 JSON 字串。
    """
    
    # 新版 SDK 的呼叫語法
    response = client.models.generate_content(
        model='gemini-1.5-pro',
        contents=prompt,
    )
    raw_text = response.text
    
    raw_text = re.sub(r"^\x60\x60\x60(json|html)?\n", "", raw_text, flags=re.MULTILINE|re.IGNORECASE)
    raw_text = re.sub(r"\x60\x60\x60$", "", raw_text, flags=re.MULTILINE)
    
    try:
        data = json.loads(raw_text.strip())
        return data.get("html", ""), data.get("targets", [])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失敗: {e}")
        return raw_text, []

def update_index_html(file_name, title, targets):
    """在 index.html 中自動插入新文章的連結與標的標籤"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
            
        tags_html = ""
        if targets:
            tags_list = "".join([f'<span style="display:inline-block; background-color:#e74c3c; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; margin-right:6px; margin-top:8px;">{t}</span>' for t in targets])
            tags_html = f'<div style="margin-top: 5px;">{tags_list}</div>'
            
        insert_point = html.find("<ul>") + 4
        new_list_item = f'\n        <li>\n            <a href="{file_name}">🆕 {datetime.today().strftime("%Y%m%d")} - {title}{tags_html}</a>\n        </li>'
        
        new_html = html[:insert_point] + new_list_item + html[insert_point:]
        
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(new_html)
            
    except Exception as e:
        print(f"更新 index.html 失敗: {e}")

def main():
    print("正在檢查 Substack 新文章...")
    articles = get_unprocessed_articles()
    
    if not articles:
        print("目前沒有新文章。")
        return
        
    print(f"總共發現 {len(articles)} 篇新文章，開始依序處理...")
    
    for article in reversed(articles):
        print(f"\n👉 正在處理: {article['title']}")
        
        date_str = datetime(*article['published'][:6]).strftime("%Y%m%d")
        safe_title = re.sub(r'[\\/*?:"<>|]', "", article['title']).replace(" ", "_")
        file_name = f"{date_str}_{safe_title}.html"
        
        html_content, targets = generate_data_with_gemini(article)
        
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ 已生成 HTML 檔案: {file_name}")
        print(f"🎯 擷取到標的: {', '.join(targets) if targets else '無'}")
        
        update_index_html(file_name, article['title'], targets)
        print(f"✅ 目錄 index.html 更新完成！")

if __name__ == "__main__":
    main()
