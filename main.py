import os
import json
import time
import sys
import requests
from openai import OpenAI

# ================= 配置区 =================
print("🚀 初始化：正在连接 GitHub 本地 Ollama...")

client = OpenAI(
    api_key="ollama", 
    base_url="http://localhost:11434/v1" 
)

# ================= 核心函数 =================

def get_storyboard(novel_text):
    print(f"📖 正在通过本地 CPU 分析小说...")
    
    system_prompt = """
    你是一个分镜导演。请将小说片段拆解为 3 个关键镜头的分镜脚本。
    【强制要求】：
    1. 只返回纯 JSON 格式，严禁包含 markdown 标记。
    2. 字段：id, narrator (中文旁白), sd_prompt (英文绘画提示词)。
    3. sd_prompt 必须包含：画面主体, 动作, 环境, 光影, anime style, 8k。
    """

    try:
        start_time = time.time()
        response = client.chat.completions.create(
            model="qwen2:1.5b", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"处理这段文字:\n{novel_text}"},
            ],
            temperature=0.7,
        )
        print(f"✅ AI 思考耗时: {int(time.time() - start_time)} 秒")
        
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        if not content.endswith("]"): content += "]"
        
        return json.loads(content)
    
    except Exception as e:
        print(f"❌ 分镜生成失败: {e}")
        return []

def download_image(prompt, filename):
    # 强制加上动漫风格
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = requests.utils.quote(final_prompt)
    
    # === 🚨 关键修复点：这里的 URL 绝对不能有方括号 [] ===
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
    print(f"🎨 正在绘图: {filename} ...")
    try:
        # 增加 headers 伪装成浏览器，防止被拦截
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
            # 休息2秒，防止请求太快被封
            time.sleep(2)
            
    print("🎉 任务全部完成！")
