import os
import re
import glob
import json
from bs4 import BeautifulSoup
from google import genai

# 1. 設定與初始化
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def get_targets_from_gemini(text_content):
    """呼叫 Gemini 閱讀純文字內容，只萃取投資標的"""
    prompt = f"""
    你是一位專業的投資分析師。請閱讀以下文章內容，萃取出文章中主要討論的「投資標的」（例如股票代號或公司簡稱，如 NVDA, QCOM, 台積電 等）。
    
    【文章內容】：
    {text_content[:15000]}
    
    【⚠️ 輸出格式嚴格要求】：
    請只輸出合法的 JSON 格式，包含一個 key "targets"，其值為字串陣列。若無提及具體標的，請給空陣列 []。
    範例：{{"targets": ["NVDA", "QCOM", "ASTS"]}}
    請不要輸出任何 Markdown 標記，只輸出純 JSON 字串。
    """
    
    # 🌟 這裡已經換成支援最新 API 版本的模型代號
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    raw_text = response.text
    
    # 清理殘留的 Markdown 標記，避免 SyntaxError
    raw_text = re.sub(r"^\x60\x60\x60(json|html)?\n", "", raw_text, flags=re.MULTILINE|re.IGNORECASE)
    raw_text = re.sub(r"\x60\x60\x60$", "", raw_text, flags=re.MULTILINE)
    
    try:
        data = json.loads(raw_text.strip())
        return data.get("targets", [])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失敗: {e}")
        return []

def main():
    print("正在掃描本地端的 HTML 檔案...")
    
    # 讀取現有目錄
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            index_html = f.read()
    except FileNotFoundError:
        print("找不到 index.html 大門！")
        return

    # 找出所有 .html 檔案，並排除 index.html 本身
    html_files = [f for f in glob.glob("*.html") if f != "index.html"]
    # 按照檔名排序 (假設檔名是 20260528_xxx.html，這樣能確保由新到舊排)
    html_files.sort(reverse=True)

    updated = False

    for file_name in html_files:
        # 如果檔案名稱已經存在於 index.html 中，代表處理過了，跳過
        if file_name in index_html:
            continue
            
        print(f"\n👉 發現新文章: {file_name}")
        
        # 讀取新文章內容
        with open(file_name, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 拔除 HTML 標籤，只留純文字給 Gemini 分析以節省 Token
        soup = BeautifulSoup(content, "html.parser")
        text_content = soup.get_text(separator='\n', strip=True)
        
        # 嘗試從檔名拆解出「日期」與「標題」 (格式: YYYYMMDD_標題.html)
        match = re.match(r"^(\d{8})_(.*)\.html$", file_name)
        if match:
            date_str, title = match.groups()
            title = title.replace("_", " ") # 替換掉可能存在的底線
        else:
            date_str = "最新"
            title = file_name.replace(".html", "")
            
        # 呼叫 AI 萃取標的
        print("🧠 正在請 Gemini 萃取標的...")
        targets = get_targets_from_gemini(text_content)
        print(f"🎯 擷取到標的: {', '.join(targets) if targets else '無'}")
        
        # 製作標籤的 CSS UI
        tags_html = ""
        if targets:
            tags_list = "".join([f'<span style="display:inline-block; background-color:#e74c3c; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; margin-right:6px; margin-top:8px;">{t}</span>' for t in targets])
            tags_html = f'<div style="margin-top: 5px;">{tags_list}</div>'
            
        # 插入到 index.html
        insert_point = index_html.find("<ul>") + 4
        new_list_item = f'\n        <li>\n            <a href="{file_name}">🆕 {date_str} - {title}{tags_html}</a>\n        </li>'
        
        index_html = index_html[:insert_point] + new_list_item + index_html[insert_point:]
        updated = True

    # 如果有更新，就覆寫回 index.html
    if updated:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(index_html)
        print("\n✅ 目錄 index.html 更新完成！")
    else:
        print("\n沒有發現新文章，目錄無需更新。")

if __name__ == "__main__":
    main()
