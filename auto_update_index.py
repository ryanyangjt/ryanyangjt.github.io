import os
import re
import glob
import json
import time
from bs4 import BeautifulSoup
from google import genai
from google.genai import errors

# 1. 設定與初始化
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def get_color_for_tag(tag):
    colors = [
        "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", 
        "#1abc9c", "#34495e", "#e67e22", "#27ae60", "#2980b9"
    ]
    color_index = sum(ord(c) for c in tag) % len(colors)
    return colors[color_index]

def get_targets_from_gemini(text_content):
    """呼叫 Gemini 閱讀內容。成功回傳 list (含 [])，API 失敗回傳 None"""
    prompt = f"""
    你是一位專業的投資分析師。請閱讀以下文章內容，萃取出文章中主要討論的「投資標的」（例如股票代號或公司簡稱，如 NVDA, QCOM, 台積電 等）。
    
    【文章內容】：
    {text_content[:15000]}
    
    【⚠️ 輸出格式嚴格要求】：
    請只輸出合法的 JSON 格式，包含一個 key "targets"，其值為字串陣列。若無提及具體標的，請給空陣列 []。
    範例：{{"targets": ["NVDA", "QCOM", "ASTS"]}}
    請不要輸出任何 Markdown 標記，只輸出純 JSON 字串。
    """
    
    max_retries = 3 
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=prompt,
            )
            raw_text = response.text
            
            raw_text = re.sub(r"^\x60\x60\x60(json|html)?\n", "", raw_text, flags=re.MULTILINE|re.IGNORECASE)
            raw_text = re.sub(r"\x60\x60\x60$", "", raw_text, flags=re.MULTILINE)
            
            data = json.loads(raw_text.strip())
            return data.get("targets", []) # 成功！即使是 [] 也是成功
            
        except Exception as e:
            # 同時捕捉 503(塞車) 與 429(額度耗盡) 等錯誤
            if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"⚠️ API 忙碌或額度限制，等待 30 秒後進行第 {attempt + 1}/{max_retries} 次重試... ({e})")
                time.sleep(30)
            else:
                print(f"❌ 發生未預期的解析或呼叫錯誤: {e}")
                return None # 失敗回傳 None
            
    print("❌ 伺服器持續忙碌或額度耗盡，重試次數已達上限。")
    return None # 徹底失敗回傳 None

def create_tags_html(targets):
    if not targets:
        return ""
    tags_list = "".join([f'<span data-symbol="{t}" class="stock-tag" style="display:inline-block; background-color:#7f8c8d; color:white; padding:4px 8px; border-radius:12px; font-size:0.75em; margin-right:6px; margin-top:8px; font-weight:bold; transition: background-color 0.4s ease;">{t} <span class="price-placeholder">...</span></span>' for t in targets])
    return f'<div style="margin-top: 5px;" class="stock-tags-container">{tags_list}</div>'

def main():
    print("正在掃描本地端的 HTML 檔案...")
    
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            index_html = f.read()
    except FileNotFoundError:
        print("找不到 index.html 大門！")
        return

    html_files = [f for f in glob.glob("*.html") if f != "index.html"]
    html_files.sort(reverse=True)

    updated = False

    for file_name in html_files:
        pattern = rf'(<a href="{re.escape(file_name)}"[^>]*>)(.*?)(</a>)'
        match = re.search(pattern, index_html, flags=re.DOTALL)
        
        if match:
            a_start, inner_html, a_end = match.groups()
            
            if 'class="stock-tag"' in inner_html or 'data-scanned="true"' in a_start:
                continue
                
            print(f"\n👉 發現舊文章尚未分析，準備處理: {file_name}")
            with open(file_name, "r", encoding="utf-8") as f:
                content = f.read()
            soup = BeautifulSoup(content, "html.parser")
            text_content = soup.get_text(separator='\n', strip=True)
            
            targets = get_targets_from_gemini(text_content)
            
            # 🌟 核心防護：如果是 None，代表 API 壞掉，直接跳過這篇，不貼已讀標記！
            if targets is None:
                print(f"⏩ 由於 API 錯誤，文章 {file_name} 將保留至下次掃描。")
                continue

            print(f"🎯 擷取到標的: {', '.join(targets) if targets else '無'}")
            
            tags_html = create_tags_html(targets)
            new_a_start = f'<a href="{file_name}" data-scanned="true">'
            new_a_tag = f'{new_a_start}{inner_html}{tags_html}{a_end}'
            
            index_html = index_html.replace(match.group(0), new_a_tag)
            updated = True
            
            print("⏳ 避免觸發 API 頻率限制，暫停 15 秒...")
            time.sleep(15)
                
        else:
            print(f"\n👉 發現全新文章: {file_name}")
            with open(file_name, "r", encoding="utf-8") as f:
                content = f.read()
            soup = BeautifulSoup(content, "html.parser")
            text_content = soup.get_text(separator='\n', strip=True)
            
            match_date = re.match(r"^(\d{8})_(.*)\.html$", file_name)
            if match_date:
                date_str, match_title = match_date.groups()
                match_title = match_title.replace("_", " ")
            else:
                date_str = "最新"
                match_title = file_name.replace(".html", "")
                
            targets = get_targets_from_gemini(text_content)
            
            # 🌟 核心防護：如果是全新文章且 API 壞掉，不要把它加入 index.html，下次它依然是「全新文章」！
            if targets is None:
                print(f"⏩ 由於 API 錯誤，全新文章 {file_name} 暫時不加入目錄，保留至下次掃描。")
                continue

            print(f"🎯 擷取到標的: {', '.join(targets) if targets else '無'}")
            
            tags_html = create_tags_html(targets)
            
            insert_point = index_html.find("<ul>") + 4
            new_list_item = f'\n        <li>\n            <a href="{file_name}" data-scanned="true">🆕 {date_str} - {match_title}{tags_html}</a>\n        </li>'
            
            index_html = index_html[:insert_point] + new_list_item + index_html[insert_point:]
            updated = True
            
            print("⏳ 避免觸發 API 頻率限制，暫停 15 秒...")
            time.sleep(15)

    if updated:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(index_html)
        print("\n✅ 目錄 index.html 更新完成！")
    else:
        print("\n✅ 所有文章皆已處理完畢 (或遇錯誤略過)，沒有發現需要更新的文章。")

if __name__ == "__main__":
    main()
