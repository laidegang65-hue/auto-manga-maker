import os
import json
import time
import sys
import requests
import google.generativeai as genai # 换成官方库

# ================= 配置区 =================
# 1. 验证 API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ 错误：未检测到 GEMINI_API_KEY，请在 GitHub Secrets 中配置！")
    sys.exit(1)

# 2. 配置 Google 官方客户端
try:
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"❌ API配置失败: {e}")
    sys.exit(1)

# ================= 核心函数 =================

def get_storyboard(novel_text):
    print(f"📖 正在分析小说，字数：{len(novel_text)}...")
    
    # 这里的 Prompt 稍微调整一下，让它更听话
    prompt = f"""
    你是一个分镜导演。请将以下小说片段拆解为 3 个关键镜头的分镜脚本。
    
    【小说片段】：
    {novel_text}
    
    【要求】：
    1. 必须返回纯 JSON 格式列表。
    2. 不要使用 markdown 格式（不要用 ```json 包裹）。
    3. 每个镜头包含：id, narrator (中文旁白), sd_prompt (英文绘画提示词)。
    4. sd_prompt 必须包含：画面主体、环境描述、光影风格、"anime style"。
    
    【JSON示例】：
    [
        {{"id": 1, "narrator": "...", "sd_prompt": "..."}},
        {{"id": 2, "narrator": "...", "sd_prompt": "..."}}
    ]
    """

    try:
        # 使用官方定义的模型名称，这个最稳
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 发送请求
        response = model.generate_content(prompt)
        
        # 获取文本
        content = response.text
        
        # 清洗数据 (去掉可能存在的 markdown 符号)
        content = content.replace("```json", "").replace("```", "").strip()
        
        # 尝试解析 JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 如果 AI 返回的不是标准 JSON，尝试强行修复或打印错误
            print("⚠️ AI 返回的格式不标准，正在打印原始内容：")
            print(content)
            return []
            
    except Exception as e:
        print(f"❌ 分镜生成失败: {e}")
        return []

def download_image(prompt, filename):
    # 强制加上动漫风格
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = requests.utils.quote(final_prompt)
    
    # 使用 Pollinations 免费绘图
    url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
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
    # 创建输出文件夹
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
    
    # 如果分镜为空，强制报错退出
    if not scenes:
        print("❌ 致命错误：未能生成有效的分镜脚本。可能是 API 连接问题或 AI 没听懂。")
        sys.exit(1) 

    # 保存分镜脚本
    script_path = os.path.join(output_dir, "script.json")
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)
    print("📝 分镜脚本已保存。")

    # 2. 遍历生成图片
    print(f"🚀 开始生成 {len(scenes)} 张图片...")
    for scene in scenes:
        idx = scene.get("id", 0)
        prompt = scene.get("sd_prompt", "")
        img_filename = os.path.join(output_dir, f"scene_{idx:03d}.jpg")
        
        if prompt:
            download_image(prompt, img_filename)
            # 休息1秒，防止请求太快
            time.sleep(1)
        else:
            print(f"跳过场景 {idx}: 提示词为空")
            
    print("🎉 所有任务执行完毕！")
