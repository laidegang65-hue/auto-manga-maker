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
print("🚀 初始化：防花屏 + 强力配音版...")

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
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end != -1:
            return json.loads(content[start:end])
        return []
    except Exception as e:
        print(f"❌ 分镜错误: {e}")
        return []

# ================= 2. 画图模块 (带重试) =================
def download_image(prompt, filename):
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = urllib.parse.quote(final_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
    # 尝试下载 3 次，防止网络波动导致花屏
    for i in range(3):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 1024: # 确保文件大于1KB
                with open(filename, "wb") as f:
                    f.write(resp.content)
                return True
            else:
                print(f"      ⚠️ 图片下载失败 (尝试 {i+1}/3)...")
                time.sleep(2)
        except:
            pass
    return False

# ================= 3. 配音模块 =================
async def generate_audio(text, filename):
    try:
        # 使用微软晓晓 (zh-CN-XiaoxiaoNeural)
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
            
            # C. 严格检查素材完整性
            if os.path.exists(img_path) and os.path.exists(audio_path):
                # 检查文件大小，防止空文件导致无声/花屏
                if os.path.getsize(audio_path) > 100: 
                    try:
                        audio_clip = AudioFileClip(audio_path)
                        duration = audio_clip.duration + 0.5 # 多给0.5秒余量
                        
                        img_clip = ImageClip(img_path).set_duration(duration)
                        img_clip = img_clip.set_audio(audio_clip)
                        img_clip.fps = 24
                        video_clips.append(img_clip)
                        print(f"      ✅ 素材合成成功 (时长: {duration:.1f}s)")
                    except Exception as e:
                        print(f"      ❌ 剪辑片段出错: {e}")
                else:
                    print("      ❌ 音频文件过小，可能是生成失败")
            else:
                print("      ❌ 素材文件缺失")
                
            time.sleep(5) # 休息防封
        else:
            print("      ❌ 画图彻底失败，跳过")

    # 3. 合成视频
    if video_clips:
        print(f"🎞️ [3/4] 正在渲染最终视频...")
        try:
            final_video = concatenate_videoclips(video_clips)
            final_path = os.path.join(output_dir, "final_video.mp4")
            
            # === 🚨 关键修复：强制使用 yuv420p 修复花屏，使用 aac 修复无声 ===
            final_video.write_videofile(
                final_path, 
                codec="libx264", 
                audio_codec="aac", 
                fps=24, 
                preset="medium", # 牺牲一点速度换取稳定性
                ffmpeg_params=['-pix_fmt', 'yuv420p'] # <--- 这句是修复花屏的神器！
            )
            print(f"✅ [4/4] 视频大功告成！")
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
    else:
        print("❌ 没有有效片段，无法合成")
