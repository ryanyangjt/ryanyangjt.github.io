import os
import re
import feedparser
import google.generativeai as genai
from bs4 import BeautifulSoup
from datetime import datetime

# 1. 設定與初始化
SUBSTACK_FEED_URL = "https://mimivsjames2.substack.com/feed"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

def is_already_processed(title):
    """檢查 index.html 是否已經有這篇文章，避免重複生成"""
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
    
    # 遍歷 RSS 裡的文章 (由新到舊)
    for entry in feed.entries:
        # 如果這篇文章已經在目錄裡，代表更舊的文章也都處理過了，直接中斷迴圈
        if is_already_processed(entry.title):
            break
            
        # 提取純文字內容
        soup = BeautifulSoup(entry.content[0].value, "html.parser")
        clean_text = soup.get_text(separator='\n', strip=True)
        
        new_articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published_parsed,
            "content": clean_text
        })
        
    return new_articles

def generate_html_with_gemini(article):
    """呼叫 Gemini 生成投資儀表板 HTML"""
    prompt = f"""
    你現在是一位專業的科技與投資分析師。
    請閱讀以下來自 Substack 的最新文章內容，並將其重點整理成一個「投資研究儀表板」的單頁 HTML。
    
    【文章標題】：{article['title']}
    【文章內容】：
    {article['content'][:15000]}
    
    【HTML 輸出要求】：
    1. 必須是完整的 HTML 程式碼（包含 <!DOCTYPE html>, <html>, <head>, <body>）。
    2. 請模仿我先前的設計風格：
       - 背景顏色使用 #f4f7f6 或 #f8f9fa。
       - 使用區塊 (Cards) 來排版不同的重點。
       - 適度加上顏色標籤 (Tags) 來標示產業或操作建議 (例如: <span class="tag">逢低佈局</span>)。
    3. 如果文章內容有提到比較、數據或趨勢，請務必使用 Chart.js (CDN: https://cdn.jsdelivr.net/npm/chart.js) 在網頁中畫出一個對應的圖表。
    4. 內容必須專業、精煉，並保留原本的投資洞見。
    5. 不要輸出任何 Markdown 語法 (如 ```html )，只輸出純 HTML 字串。
    """
    
    response = model.generate_content(prompt)
    raw_html = response.text
    
    raw_html = re.sub(r"^
```html\n", "", raw_html, flags=re.MULTILINE)
    raw_html = re.sub(r"```$", "", raw_html, flags=re.MULTILINE)
    
    return raw_html.strip()

def update_index_html(file_name, title):
    """在 index.html 中自動插入新文章的連結"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
            
        insert_point = html.find("<ul>") + 4
        new_list_item = f'\n        <li><a href="{file_name}">🆕 {datetime.today().strftime("%Y%m%d")} - {title}</a></li>'
        
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
    
    # 使用 reversed() 讓處理順序變成「從舊到新」
    # 這樣在寫入 index.html 目錄時，最新的一篇才會被堆疊在最上面
    for article in reversed(articles):
        print(f"\n👉 正在處理: {article['title']}")
        
        date_str = datetime(*article['published'][:6]).strftime("%Y%m%d")
        safe_title = re.sub(r'[\\/*?:"<>|]', "", article['title']).replace(" ", "_")
        file_name = f"{date_str}_{safe_title}.html"
        
        html_content = generate_html_with_gemini(article)
        
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ 已生成 HTML 檔案: {file_name}")
        
        update_index_html(file_name, article['title'])
        print(f"✅ 目錄 index.html 更新完成！")

if __name__ == "__main__":
    main()
