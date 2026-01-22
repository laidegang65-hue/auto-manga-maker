import os
import json
import time
import sys
import requests
from openai import OpenAI

# ================= 配置区 =================
# 读取你刚才设置的 Secret
api_key = os.environ.get("GROQ_API_KEY") 
if not api_key:
    # 尝试读取旧名字，防止你没改名
    api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("❌ 错误：未检测到 Key！请在 GitHub Secrets 中添加 GROQ_API_KEY")
    sys.exit(1)

# 配置 Groq (完全兼容 OpenAI 写法)
client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

# ================= 核心函数 =================

def get_storyboard(novel_text):
    print(f"📖 正在通过 Groq 分析小说，字数：{len(novel_text)}...")
    
    system_prompt = """
    You are a professional storyboard director. 
    Task: Convert the user's Chinese novel text into a standard storyboard JSON list.
    
    Requirements:
    1. Output MUST be valid JSON only. NO markdown blocks (no ```json).
    2. Fields per shot: 
       - "id": integer index
       - "narrator": (Keep in Chinese) The narration text.
       - "sd_prompt": (In English) Stable Diffusion prompt describing the scene visually.
    3. sd_prompt format: "subject description, action, environment, lighting, anime style, 8k, masterpiece"
    
    Example Output:
    [
      {"id": 1, "narrator": "午夜时分，钟声响起。", "sd_prompt": "1girl, cinderella, running on stairs, glass shoe left behind, castle background, night, moonlight, anime style, 8k"}
    ]
    """

    try:
        response = client.chat.completions.create(
            # 使用 Llama3-70b，目前地表最强开源模型之一，且在Groq上免费
            model="llama3-70b-8192", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this text:\n{novel_text}"},
            ],
            temperature=0.5,
            max_tokens=2048
        )
        
        content = response.choices[0].message.content
        # 清洗数据，防止模型返回 ```json
        content = content.replace("```json", "").replace("```", "").strip()
        
        print("✅ 分镜生成成功！")
        return json.loads(content)
    
    except Exception as e:
        print(f"❌ 分镜生成失败: {e}")
        # 打印原始返回以便调试
        if 'content' in locals():
            print(f"原始返回内容: {content}")
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

    # === 测试小说片段 ===
    novel = """
    林萧站在废弃的机甲残骸上，夕阳将他的影子拉得很长。
    风吹乱了他银色的头发，他按住腰间的断刀，眼神冷冽。
    远处的地平线上，黑压压的虫潮正在逼近，空气中弥漫着硝烟的味道。
    """

    # 1. 获取分镜
    scenes = get_storyboard(novel)
    
    if not scenes:
        print("❌ 致命错误：分镜列表为空。")
        sys.exit(1)

    # 保存脚本
    with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    # 2. 生成图片
    print(f"🚀 开始生成 {len(scenes)} 张图片...")
    for scene in scenes:
        idx = scene.get("id", 0)
        prompt = scene.get("sd_prompt", "")
        
        if prompt:
            download_image(prompt, os.path.join(output_dir, f"scene_{idx:03d}.jpg"))
            time.sleep(1) 
        
    print("🎉 任务完成！请去 Artifacts 下载结果！")
