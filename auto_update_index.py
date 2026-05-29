import os
import re
import glob
import json
from bs4 import BeautifulSoup
from google import genai

# 1. 設定與初始化
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 定義標籤的調色盤
def get_color_for_tag(tag):
    """根據標的名稱的字元產生固定的顏色，讓同一個標的永遠是同一個顏色"""
    colors = [
        "#e74c3c", # 紅色
        "#3498db", # 藍色
        "#2ecc71", # 綠色
        "#f39c12", # 橘黃色
        "#9b59b6", # 紫色
        "#1abc9c", # 藍綠色
        "#34495e", # 深鐵灰
        "#e67e22", # 橙色
        "#27ae60", # 深綠色
        "#2980b9"  # 深藍色
    ]
    # 利用 ASCII 碼加總來決定顏色索引
    color_index = sum(ord(c) for c in tag) % len(colors)
    return colors[color_index]

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
    
    response = client.models.generate_content(
        model='gemini-2.5-flash', # 使用最新且速度最快的模型
        contents=prompt,
    )
    raw_text = response.text
    
    # 清理殘留的 Markdown 標記
    raw_text = re.sub(r"^\x60\x60\x60(json|html)?\n", "", raw_text, flags=re.MULTILINE|re.IGNORECASE)
    raw_text = re.sub(r"\x60\x60\x60$", "", raw_text, flags=re.MULTILINE)
    
    try:
        data = json.loads(raw_text.strip())
        return data.get("targets", [])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失敗: {e}")
        return []

def create_tags_html(targets):
    """將標的陣列轉換成彩色 CSS 標籤的 HTML"""
    if not targets:
        return ""
    tags_list = "".join([f'<span style="display:inline-block; background-color:{get_color_for_tag(t)}; color:white; padding:2px 8px; border-radius:12px; font-size:0.75em; margin-right:6px; margin-top:8px;" class="stock-tag">{t}</span>' for t in targets])
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
        # 1. 使用正規表達式尋找 index.html 裡面是否已經有這篇文章的 <a> 標籤
        pattern = rf'(<a href="{re.escape(file_name)}">)(.*?)(</a>)'
        match = re.search(pattern, index_html, flags=re.DOTALL)
        
        if match:
            a_start, inner_html, a_end = match.groups()
            
            # 檢查這行裡面是不是已經有標籤了 (避免重複生成)
            if 'class="stock-tag"' in inner_html or 'margin-top: 5px;' in inner_html:
                print(f"⏩ {file_name} 已有標籤，跳過。")
                continue
                
            # 【回溯補齊邏輯】：文章在目錄裡，但還沒有標籤
            print(f"\n👉 發現舊文章缺標籤，準備補齊: {file_name}")
            with open(file_name, "r", encoding="utf-8") as f:
                content = f.read()
            soup = BeautifulSoup(content, "html.parser")
            text_content = soup.get_text(separator='\n', strip=True)
            
            targets = get_targets_from_gemini(text_content)
            print(f"🎯 擷取到標的: {', '.join(targets) if targets else '無'}")
            
            if targets:
                tags_html = create_tags_html(targets)
                # 將新標籤安插進原本的 <a> 裡面
                new_a_tag = f'{a_start}{inner_html}{tags_html}{a_end}'
                index_html = index_html.replace(match.group(0), new_a_tag)
                updated = True
                
        else:
            # 【新文章邏輯】：文章根本不在目錄裡
            print(f"\n👉 發現全新文章: {file_name}")
            with open(file_name, "r", encoding="utf-8") as f:
                content = f.read()
            soup = BeautifulSoup(content, "html.parser")
            text_content = soup.get_text(separator='\n', strip=True)
            
            match_date = re.match(r"^(\d{8})_(.*)\.html$", file_name)
            if match_date:
                date_str, title = match_date.groups()
                title = title.replace("_", " ")
            else:
                date_str = "最新"
                title = file_name.replace(".html", "")
                
            targets = get_targets_from_gemini(text_content)
            print(f"🎯 擷取到標的: {', '.join(targets) if targets else '無'}")
            
            tags_html = create_tags_html(targets)
            
            insert_point = index_html.find("<ul>") + 4
            new_list_item = f'\n        <li>\n            <a href="{file_name}">🆕 {date_str} - {title}{tags_html}</a>\n        </li>'
            
            index_html = index_html[:insert_point] + new_list_item + index_html[insert_point:]
            updated = True

    if updated:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(index_html)
        print("\n✅ 目錄 index.html 更新完成！")
    else:
        print("\n沒有發現需要更新的文章。")

if __name__ == "__main__":
    main()
