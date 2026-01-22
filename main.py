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
print("🚀 初始化：自定义剧本模式...")

# ================= 1. 分镜生成模块 =================
def get_storyboard(novel_text):
    print(f"📖 [1/4] 正在分析你的剧本...")
    # 限制字数，防止免费接口处理不过来
    if len(novel_text) > 1000:
        novel_text = novel_text[:1000]
        
    prompt = f"""
    Role: Storyboard Director.
    Task: Convert novel to JSON list of 3 to 5 scenes.
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
    try:
        # 使用微软超逼真语音 (晓晓)
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save(filename)
    except Exception as e:
        print(f"      ⚠️ 配音失败: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # === 关键修改：从 GitHub 输入框读取文字 ===
    # 如果没有输入（比如本地测试），就用默认的
    default_text = "一个孤独的剑客在沙漠中行走，夕阳西下。"
    novel = os.environ.get("USER_NOVEL", default_text)
    
    print(f"📝 收到剧本任务：\n{novel[:50]}...")

    # --- 步骤 1: 获取分镜 ---
    scenes = get_storyboard(novel)
    if not scenes:
        print("❌ 无法生成分镜，请检查剧本是否太长或含有特殊字符")
        sys.exit(1)

    # --- 步骤 2: 生产素材 ---
    video_clips = []
    print(f"🎬 [2/4] 开始生产素材 (共 {len(scenes)} 个镜头)...")
    
    for scene in scenes:
        idx = scene.get("id", 0)
        print(f"   👉 处理第 {idx} 镜...")
        
        img_path = os.path.join(output_dir, f"scene_{idx}.jpg")
        audio_path = os.path.join(output_dir, f"scene_{idx}.mp3")
        
        # A. 画图
        if download_image(scene.get("sd_prompt"), img_path):
            # B. 配音
            asyncio.run(generate_audio(scene.get("narrator"), audio_path))
            
            # C. 组装
            if os.path.exists(img_path) and os.path.exists(audio_path):
                try:
                    audio_clip = AudioFileClip(audio_path)
                    # 至少给图片 3 秒展示时间，如果语音很短
                    duration = max(audio_clip.duration, 3) 
                    
                    video_clip = ImageClip(img_path).set_duration(duration)
                    video_clip = video_clip.set_audio(audio_clip)
                    video_clip.fps = 24
                    video_clips.append(video_clip)
                except Exception as e:
                    print(f"      剪辑出错: {e}")
                
            time.sleep(10) # 休息防封
        else:
            print("      画图失败，跳过")

    # --- 步骤 3: 合成视频 ---
    if video_clips:
        print(f"🎞️ [3/4] 正在合成最终视频...")
        try:
            final_video = concatenate_videoclips(video_clips)
            final_path = os.path.join(output_dir, "final_video.mp4")
            final_video.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast")
            print(f"✅ [4/4] 视频制作完成！请下载 artifact")
        except Exception as e:
            print(f"❌ 合成失败: {e}")
    else:
        print("❌ 没有生成有效的视频片段")
