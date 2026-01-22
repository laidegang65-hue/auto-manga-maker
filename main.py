import os
import json
import time
import sys
import requests

# ================= 配置区 =================
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ 错误：未检测到 GEMINI_API_KEY，请在 GitHub Secrets 中配置！")
    sys.exit(1)

# ================= 核心函数 (纯 HTTP 请求版) =================

def get_storyboard(novel_text):
    print(f"📖 正在分析小说，字数：{len(novel_text)}...")
    
    # Google Gemini 的官方 API 地址
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    # 构造请求数据
    payload = {
        "contents": [{
            "parts": [{
                "text": f"""
                你是一个分镜导演。请将以下小说片段拆解为 3 个关键镜头的分镜脚本。
                必须返回纯 JSON 格式列表，不要包含 markdown 标记。
                每个镜头包含：id, narrator (中文旁白), sd_prompt (英文绘画提示词)。
                sd_prompt 必须包含：画面主体、环境描述、光影风格、"anime style"。
                
                【小说片段】：
                {novel_text}
                
                【JSON示例】：
                [
                    {{"id": 1, "narrator": "...", "sd_prompt": "..."}},
                    {{"id": 2, "narrator": "...", "sd_prompt": "..."}}
                ]
                """
            }]
        }]
    }
    
    headers = {'Content-Type': 'application/json'}

    try:
        # 直接发送 POST 请求，不依赖任何 Google 库
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # 检查是否成功
        if response.status_code != 200:
            print(f"❌ API 请求失败，状态码: {response.status_code}")
            print(f"错误详情: {response.text}")
            return []
            
        # 解析返回结果
        result = response.json()
        
        # 提取文本内容 (Gemini 的返回结构比较深)
        try:
            content = result['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            print("⚠️ 无法从返回结果中提取文本")
            print(result)
            return []

        # 清洗 JSON 字符串
        content = content.replace("```json", "").replace("```", "").strip()
        
        return json.loads(content)

    except Exception as e:
        print(f"❌ 分镜生成出错: {e}")
        return []

def download_image(prompt, filename):
    # 强制加上动漫风格
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = requests.utils.quote(final_prompt)
    
    # 使用 Pollinations 免费绘图
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
    print(f"🎨 正在绘图: {filename} ...")
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            with open(filename, "wb") as f:
                f.write(resp.content)
            print(f"✅ 保存成功: {filename}")
        else:
            print(f"⚠️ 图片下载失败，状态码: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ 图片请求错误: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    novel = """
    巨大的机甲残骸横亘在荒原之上，夕阳将其染成血红色。
    少年站在残骸顶端，风吹动他白色的衬衫。
    他摘下护目镜，露出一双金色的机械义眼，冷冷地注视着地平线上涌来的虫潮。
    """

    # 1. 获取分镜
    scenes = get_storyboard(novel)
    
    if not scenes:
        print("❌ 致命错误：未能生成有效的分镜。")
        sys.exit(1)

    # 保存分镜
    with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    # 2. 生成图片
    for scene in scenes:
        idx = scene.get("id", 0)
        prompt = scene.get("sd_prompt", "")
        if prompt:
            download_image(prompt, os.path.join(output_dir, f"scene_{idx:03d}.jpg"))
            time.sleep(1)

    print("🎉 任务完成！")
