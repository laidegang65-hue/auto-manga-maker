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
print("🚀 初始化：稳定输出版 (防崩溃 + 防花屏)...")

# ================= 1. 分镜生成模块 =================
def get_storyboard(novel_text):
    print(f"📖 [1/4] 正在分析剧本...")
    if len(novel_text) > 800: novel_text = novel_text[:800]
    
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
        # 简单清洗
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
    
    for i in range(3): # 重试3次
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(filename, "wb") as f:
                    f.write(resp.content)
                return True
            else:
                time.sleep(2)
        except:
            pass
    return False

# ================= 3. 配音模块 =================
async def generate_audio(text, filename):
    try:
        # 使用微软晓晓
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save(filename)
    except Exception as e:
        print(f"      ⚠️ 配音生成出错: {e}")

# ================= 主程序 =================
if __name__ == "__main__":
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # 获取输入
    default_text = "林萧站在废墟顶端，红色的斗篷在风中猎猎作响。他拔出背后的长刀，刀锋在月光下闪着寒光。前方，一只巨大的机械巨兽正缓缓从阴影中浮现。"
    novel = os.environ.get("USER_NOVEL", default_text)
    
    # 1. 获取分镜
    scenes = get_storyboard(novel)
    if not scenes:
        print("❌ 分镜生成失败")
        sys.exit(1)

    # 2. 生产素材
    video_clips = []
    print(f"🎬 [2/4] 开始生产素材 (共 {len(scenes)} 镜)...")
    
    for scene in scenes:
        idx = scene.get("id", 0)
        print(f"   👉 第 {idx} 镜处理中...")
        
        img_path = os.path.join(output_dir, f"scene_{idx}.jpg")
        audio_path = os.path.join(output_dir, f"scene_{idx}.mp3")
        
        # A. 画图
        if download_image(scene.get("sd_prompt"), img_path):
            # B. 配音
            asyncio.run(generate_audio(scene.get("narrator"), audio_path))
            
            # C. 合成片段
            if os.path.exists(img_path):
                try:
                    duration = 3 # 默认时长
                    has_audio = False
                    
                    # 尝试加载音频
                    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
                        audio_clip = AudioFileClip(audio_path)
                        duration = audio_clip.duration + 0.5
                        has_audio = True
                    
                    # 创建图片片段
                    img_clip = ImageClip(img_path).set_duration(duration)
                    if has_audio:
                        img_clip = img_clip.set_audio(audio_clip)
                    
                    # 关键：统一尺寸，防止花屏
                    img_clip = img_clip.resize(height=1280) 
                    # 如果宽度是奇数，ffmpeg会报错，所以强制偶数
                    if img_clip.w % 2 != 0:
                        img_clip = img_clip.resize(width=img_clip.w - 1)

                    img_clip.fps = 12 # 降低帧率，减轻负载
                    video_clips.append(img_clip)
                    print(f"      ✅ 素材合成成功 (时长: {duration:.1f}s)")
                except Exception as e:
                    print(f"      ❌ 剪辑片段出错: {e}")
            
            time.sleep(5) # 休息防封
        else:
            print("      ❌ 画图失败，跳过")

    # 3. 合成视频
    if video_clips:
        print(f"🎞️ [3/4] 正在渲染最终视频...")
        try:
            final_video = concatenate_videoclips(video_clips, method="compose")
            final_path = os.path.join(output_dir, "final_video.mp4")
            
            # === 🚨 关键参数组合 ===
            # preset="ultrafast": 保证不超时，解决146字节空文件问题
            # pix_fmt="yuv420p": 保证兼容性，解决花屏问题
            # threads=4: 加速渲染
            final_video.write_videofile(
                final_path, 
                codec="libx264", 
                audio_codec="aac", 
                fps=12, 
                preset="ultrafast",
                threads=4,
                ffmpeg_params=['-pix_fmt', 'yuv420p']
            )
            print(f"✅ [4/4] 视频大功告成！文件大小: {os.path.getsize(final_path)/1024:.2f} KB")
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
    else:
        print("❌ 没有有效片段")
