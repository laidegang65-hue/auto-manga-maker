import os
import json
import time
import sys
import requests
import urllib.parse

# ================= 核心配置 =================
print("🚀 初始化：使用 Pollinations 免费直连模式 (无Key版)...")

def get_storyboard(novel_text):
    print(f"📖 正在通过免费接口分析小说...")
    
    # 精简提示词，防止URL过长报错
    prompt = f"""
    Role: Storyboard Director.
    Task: Convert the novel into a JSON list of 3 scenes.
    Format: JSON ONLY. No markdown.
    Fields: "id", "narrator" (Chinese), "sd_prompt" (English, anime style, visual details).
    Novel: {novel_text}
    """
    
    # URL 编码
    encoded_prompt = urllib.parse.quote(prompt)
    # 使用 GET 请求直连，强制指定 model=openai
    url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai"

    try:
        start_time = time.time()
        # 发送请求
        response = requests.get(url, timeout=60)
        
        # 检查是否是 HTML 报错 (你刚才遇到的问题)
        if "<!DOCTYPE html>" in response.text:
            print("⚠️ 接口返回了网页而非数据，尝试备用清洗...")
        
        content = response.text
        print(f"✅ AI 响应耗时: {int(time.time() - start_time)} 秒")
        
        # === 暴力清洗数据 ===
        # 免费接口有时候会返回 "Here is the JSON: [ ... ]"，我们需要提取 [ ... ]
        start = content.find("[")
        end = content.rfind("]") + 1
        
        if start != -1 and end != -1:
            clean_content = content[start:end]
            return json.loads(clean_content)
        else:
            print("❌ 未在返回结果中找到 JSON 列表符号 []")
            print(f"原始内容片段: {content[:100]}...")
            return []
    
    except Exception as e:
        print(f"❌ 分镜生成失败: {e}")
        return []

def download_image(prompt, filename):
    # 强制加上动漫风格
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = urllib.parse.quote(final_prompt)
    
    # Pollinations 画图接口 (这个一直很稳)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
    print(f"🎨 正在绘图: {filename} ...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=60)
        
        if resp.status_code == 200:
            with open(filename, "wb") as f:
                f.write(resp.content)
            print(f"✅ 保存成功")
        else:
            print(f"⚠️ 下载失败: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ 请求错误: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # === 小说片段 ===
    novel = """
    巨大的机甲残骸横亘在荒原之上，夕阳将其染成血红色。
    少年站在残骸顶端，风吹动他白色的衬衫。
    他摘下护目镜，露出一双金色的机械义眼，冷冷地注视着地平线上涌来的虫潮。
    """

    # 1. 获取分镜
    scenes = get_storyboard(novel)
    
    if not scenes:
        print("❌ 致命错误：未能生成有效的分镜。可能是免费接口繁忙，请过几分钟再试。")
        sys.exit(1)

    # 保存脚本
    with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    # 2. 生成图片
    print(f"🚀 开始生成图片 (共 {len(scenes)} 张)...")
    for scene in scenes:
        idx = scene.get("id", 0)
        prompt = scene.get("sd_prompt", "")
        if prompt:
            download_image(prompt, os.path.join(output_dir, f"scene_{idx:03d}.jpg"))
            # 免费接口要温柔一点，休息2秒
            time.sleep(2)
            
    print("🎉 任务全部完成！")
