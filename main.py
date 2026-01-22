import os
import json
import time
import sys
import requests
import urllib.parse
import asyncio
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# ================= 配置区 =================
print("🚀 初始化：全自动视频生成模式 (画图+配音+剪辑)...")

# ================= 1. 分镜生成模块 =================
def get_storyboard(novel_text):
    print(f"📖 [1/4] 正在分析小说生成分镜...")
    prompt = f"""
    Role: Storyboard Director.
    Task: Convert novel to JSON list of 3 scenes.
    Format: JSON ONLY. No markdown.
    Fields: "id", "narrator" (Chinese), "sd_prompt" (English, anime style).
    Novel: {novel_text}
    """
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai"

    try:
        response = requests.get(url, timeout=60)
        content = response.text
        # 清洗 JSON
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end != -1:
            return json.loads(content[start:end])
        return []
    except Exception as e:
        print(f"❌ 分镜错误: {e}")
        return []

# ================= 2. 画图模块 =================
def download_image(prompt, filename):
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = urllib.parse.quote(final_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code == 200:
            with open(filename, "wb") as f:
                f.write(resp.content)
            return True
    except:
        pass
    return False

# ================= 3. 配音模块 =================
async def generate_audio(text, filename):
    # 使用微软超逼真语音 (晓晓)
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
    await communicate.save(filename)

# ================= 主程序 =================
if __name__ == "__main__":
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    novel = """
    巨大的机甲残骸横亘在荒原之上，夕阳将其染成血红色。
    少年站在残骸顶端，风吹动他白色的衬衫。
    他摘下护目镜，露出一双金色的机械义眼，冷冷地注视着地平线上涌来的虫潮。
    """

    # --- 步骤 1: 获取分镜 ---
    scenes = get_storyboard(novel)
    if not scenes:
        sys.exit(1)

    # --- 步骤 2: 生产素材 (图+音) ---
    video_clips = []
    print(f"🎬 [2/4] 开始生产素材 (共 {len(scenes)} 个镜头)...")
    
    for scene in scenes:
        idx = scene.get("id", 0)
        print(f"   👉 处理第 {idx} 镜...")
        
        # 路径
        img_path = os.path.join(output_dir, f"scene_{idx}.jpg")
        audio_path = os.path.join(output_dir, f"scene_{idx}.mp3")
        
        # A. 画图
        if download_image(scene.get("sd_prompt"), img_path):
            # B. 配音 (异步运行)
            asyncio.run(generate_audio(scene.get("narrator"), audio_path))
            
            # C. 组装成视频片段
            if os.path.exists(img_path) and os.path.exists(audio_path):
                # 读取音频
                audio_clip = AudioFileClip(audio_path)
                # 创建图片片段，时长=音频时长
                video_clip = ImageClip(img_path).set_duration(audio_clip.duration)
                video_clip = video_clip.set_audio(audio_clip)
                # 设置FPS
                video_clip.fps = 24
                video_clips.append(video_clip)
                
            # 关键：休息10秒防止封号
            time.sleep(10)
        else:
            print("      画图失败，跳过此镜")

    # --- 步骤 3: 合成视频 ---
    if video_clips:
        print(f"🎞️ [3/4] 正在合成最终视频...")
        final_video = concatenate_videoclips(video_clips)
        final_path = os.path.join(output_dir, "final_video.mp4")
        
        # 写入文件 (使用 fast preset 加快速度)
        final_video.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast")
        print(f"✅ [4/4] 视频制作完成！请下载 final-video.mp4")
    else:
        print("❌ 没有生成有效的视频片段")
