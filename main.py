import os
import json
import time
import sys
import requests
from openai import OpenAI

# ================= 配置区 =================
# 1. 验证 API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ 错误：未检测到 GEMINI_API_KEY，请在 GitHub Secrets 中配置！")
    sys.exit(1) # 强制退出，让 Action 显示红色失败

# 2. 配置客户端 (使用 Google 的 OpenAI 兼容接口)
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# ================= 核心函数 =================

def get_storyboard(novel_text):
    print(f"📖 正在分析小说，字数：{len(novel_text)}...")
    
    system_prompt = """
    你是一个专业的漫剧分镜导演。请将输入的小说片段拆解为3-5个关键镜头的分镜脚本。
    必须严格返回纯 JSON 格式，列表结构，不要包含 markdown 标记。
    JSON 格式示例：
    [
      {
        "id": 1,
        "narrator": "旁白内容",
        "sd_prompt": "highly detailed, anime style, 1boy, black hair, holding a sword, forest background, cinematic lighting, 8k"
      }
    ]
    注意：sd_prompt 必须是英文，且包含详细的画面描述。
    """

    try:
        response = client.chat.completions.create(
            # 修改点：使用 latest 版本，避免 404 错误
            model="gemini-1.5-flash-latest", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": novel_text},
            ]
        )
        content = response.choices[0].message.content
        # 清洗数据
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    
    except Exception as e:
        print(f"❌ 分镜生成失败: {e}")
        # 这里不退出，返回空列表，让主程序决定是否退出
        return []

def download_image(prompt, filename):
    # 强制加上动漫风格
    final_prompt = f"{prompt}, anime style, masterpiece, best quality"
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
    # 创建输出文件夹
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # === 修改这里：输入你的小说片段 ===
    novel = """
    林萧站在废弃的都市废墟之上，风吹动他破旧的红色斗篷。
    他手里紧紧握着那把断裂的合金长刀，眼神冷冽地注视着前方。
    远处，巨大的机甲残骸在夕阳下投射出长长的阴影。
    """

    # 1. 获取分镜
    scenes = get_storyboard(novel)
    
    # 如果分镜为空，强制报错退出
    if not scenes:
        print("❌ 致命错误：未能生成有效的分镜脚本。程序终止。")
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
        else:
            print(f"跳过场景 {idx}: 提示词为空")
            
    print("🎉 所有任务执行完毕！")
