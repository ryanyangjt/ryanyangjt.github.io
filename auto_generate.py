import os
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime

# 1. 設定與初始化
SUBSTACK_FEED_URL = "https://mimivsjames2.substack.com/feed"

def is_already_processed(title):
    """檢查 index.html 是否已經有這篇文章"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            content = f.read()
            return title in content
    except FileNotFoundError:
        return False

def get_unprocessed_articles():
    """獲取所有尚未處理的 Substack 新文章列表 (加入反爬蟲偽裝)"""
    # 偽裝成一般 Windows 電腦的 Chrome 瀏覽器
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("正在發送偽裝請求獲取 RSS...")
    try:
        # 1. 先用 requests 帶上 headers 抓取網頁內容，繞過防火牆
        response = requests.get(SUBSTACK_FEED_URL, headers=headers, timeout=10)
        response.raise_for_status() # 如果被擋會拋出錯誤
        
        # 2. 把抓下來的純文字 XML 交給 feedparser 解析
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"抓取 RSS 失敗，可能是被防火牆阻擋: {e}")
        return []

    new_articles = []
    for entry in feed.entries:
        if is_already_processed(entry.title):
            break
            
        new_articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published_parsed
        })
        
    return new_articles

def generate_placeholder_html(title, link):
    """生成一個暫時的網頁佔位符"""
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 待處理</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; padding: 40px; text-align: center; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 600px; margin: auto; border-top: 5px solid #f39c12; }}
        h1 {{ color: #e67e22; }}
        a {{ color: #3498db; text-decoration: none; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚧 內容待補</h1>
        <p>系統已自動偵測到新文章：</p>
        <h2>{title}</h2>
        <p><a href="{link}" target="_blank">👉 點此前往 Substack 閱讀原文</a></p>
        <hr style="margin: 30px 0; border: 0; border-top: 1px dashed #ccc;">
        <p style="color: #7f8c8d; font-size: 0.9em; line-height: 1.6;">
            <strong>管理員請注意：</strong><br>
            請手動將原文複製給 AI 生成儀表板程式碼，<br>
            然後在 GitHub 上打開此檔案 (✏️Edit)，<br>
            <strong>將本檔案所有內容刪除，貼上新的 HTML 並儲存。</strong>
        </p>
    </div>
</body>
</html>"""
    return html

def update_index_html(file_name, title):
    """在 index.html 中自動插入新文章的連結 (標示待編輯)"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
            
        insert_point = html.find("<ul>") + 4
        new_list_item = f'\n        <li>\n            <a href="{file_name}">📝 {datetime.today().strftime("%Y%m%d")} - {title} <span style="color: #e67e22; font-size: 0.85em;">(待編輯)</span></a>\n        </li>'
        
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
        
    print(f"總共發現 {len(articles)} 篇新文章，開始建立待編輯檔案...")
    
    for article in reversed(articles):
        print(f"\n👉 正在建檔: {article['title']}")
        
        # 容錯處理：如果 RSS 沒有提供發布時間，則使用當下時間
        if article['published']:
            date_str = datetime(*article['published'][:6]).strftime("%Y%m%d")
        else:
            date_str = datetime.today().strftime("%Y%m%d")
            
        safe_title = re.sub(r'[\\/*?:"<>|]', "", article['title']).replace(" ", "_")
        file_name = f"{date_str}_{safe_title}.html"
        
        # 寫入佔位符 HTML
        html_content = generate_placeholder_html(article['title'], article['link'])
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ 已建立檔案: {file_name}")
        
        # 更新目錄
        update_index_html(file_name, article['title'])
        print(f"✅ 目錄 index.html 更新完成！")

if __name__ == "__main__":
    main()
