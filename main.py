import os
import json
import time
import sys
import requests
import urllib.parse
import asyncio
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips

# ================= 配置区 =================
print("🚀 初始化：长文本 + 字幕最终版...")

# 指定中文字体路径 (Ubuntu下安装 fonts-wqy-microhei 后的默认位置)
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"

# ================= 1. 分镜生成模块 (支持长文) =================
def get_storyboard(novel_text):
    print(f"📖 [1/4] 正在分析剧本 (字数: {len(novel_text)})...")
    
    # 稍微放宽限制，但太长还是会超时，建议 2000 字以内
    if len(novel_text) > 2000: 
        print("⚠️ 提示：文本过长，已截取前2000字")
        novel_text = novel_text[:2000]
    
    # 提示词优化：要求覆盖完整剧情，分镜数量动态化
    prompt = f"""
    Role: Storyboard Director.
    Task: Convert the novel into a JSON storyboard covering the FULL PLOT.
    Requirements:
    1. Create 4 to 8 scenes depending on the length.
    2. Format: JSON ONLY. No markdown.
    3. Fields: "id", "narrator" (Chinese subtitles), "sd_prompt" (English visual description).
    Novel: {novel_text}
    """
    
    # === 升级：使用 POST 请求，解决 GET 请求无法发送长文的问题 ===
    url = "https://text.pollinations.ai/"
    payload = {
        "messages": [
            {"role": "system", "content": prompt}
        ],
        "model": "openai",
        "jsonMode": True 
    }

    try:
        # 增加超时时间到 90秒
        response = requests.post(url, json=payload, timeout=90)
        content = response.text
        
        # 清洗数据
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end != -1:
            data = json.loads(content[start:end])
            print(f"✅ 成功生成 {len(data)} 个分镜")
            return data
            
    except Exception as e:
        print(f"⚠️ 在线获取失败: {e}")

    # 兜底数据
    print("🔄 使用备用分镜...")
    return [{"id":1, "narrator":"AI繁忙，请稍后再试。", "sd_prompt":"error screen"}]

# ================= 2. 画图模块 =================
def download_image(prompt, filename):
    if not prompt: prompt = "anime scene"
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = urllib.parse.quote(final_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
    for i in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(filename, "wb") as f:
                    f.write(resp.content)
                return True
            time.sleep(2)
        except:
            pass
    return False

# ================= 3. 配音模块 =================
async def generate_audio(text, filename):
    try:
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save(filename)
    except:
        pass

# ================= 4. 字幕生成模块 (新功能) =================
def create_subtitle_clip(text, duration):
    try:
        # 创建字幕：白色字，黑色描边，底部居中，自动换行
        # size=(720, None) 表示宽度限制在720像素内，高度自动，实现自动换行
        txt_clip = TextClip(
            text, 
            font=FONT_PATH, 
            fontsize=35, 
            color='white', 
            stroke_color='black', 
            stroke_width=2, 
            method='caption', 
            size=(720, None) 
        )
        return txt_clip.set_position(('center', 0.85), relative=True).set_duration(duration)
    except Exception as e:
        print(f"      ⚠️ 字幕生成失败 (可能是缺少字体): {e}")
        return None

# ================= 主程序 =================
if __name__ == "__main__":
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    default_text = "林萧站在废墟顶端，红色的斗篷在风中猎猎作响。他拔出背后的长刀，刀锋在月光下闪着寒光。"
    novel = os.environ.get("USER_NOVEL", default_text)
    
    # 1. 获取分镜
    scenes = get_storyboard(novel)

    # 2. 生产素材
    video_clips = []
    print(f"🎬 [2/4] 开始生产素材 (共 {len(scenes)} 镜)...")
    
    for scene in scenes:
        idx = scene.get("id", 0)
        prompt = scene.get("sd_prompt") or "anime scene"
        narrator = scene.get("narrator") or "..."
        
        img_path = os.path.join(output_dir, f"scene_{idx}.jpg")
        audio_path = os.path.join(output_dir, f"scene_{idx}.mp3")
        
        print(f"   👉 第 {idx} 镜: 处理中...", end="")
        
        if download_image(prompt, img_path):
            asyncio.run(generate_audio(narrator, audio_path))
            
            if os.path.exists(img_path):
                try:
                    duration = 3
                    has_audio = False
                    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
                        audio_clip = AudioFileClip(audio_path)
                        duration = audio_clip.duration + 0.5
                        has_audio = True
                    
                    # 1. 基础画面
                    img_clip = ImageClip(img_path).set_duration(duration)
                    img_clip = img_clip.resize(height=1280)
                    if img_clip.w % 2 != 0: img_clip = img_clip.resize(width=img_clip.w - 1)
                    
                    # 2. 生成字幕
                    final_clip = img_clip
                    subtitle_clip = create_subtitle_clip(narrator, duration)
                    if subtitle_clip:
                        # 将字幕合成到画面上
                        final_clip = CompositeVideoClip([img_clip, subtitle_clip])
                    
                    # 3. 添加音频
                    if has_audio:
                        final_clip = final_clip.set_audio(audio_clip)
                    
                    final_clip.fps = 12
                    video_clips.append(final_clip)
                    print("完成")
                except Exception as e:
                    print(f"失败: {e}")
            
            time.sleep(3)
        else:
            print("画图失败")

    # 3. 合成视频
    if video_clips:
        print(f"🎞️ [3/4] 正在渲染...")
        try:
            final_path = os.path.join(output_dir, "final_video.mp4")
            final_video = concatenate_videoclips(video_clips, method="compose")
            
            final_video.write_videofile(
                final_path, 
                codec="libx264", 
                audio_codec="aac", 
                fps=12, 
                preset="ultrafast",
                threads=4,
                ffmpeg_params=['-pix_fmt', 'yuv420p']
            )
            print(f"✅ [4/4] 成功！")
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
            sys.exit(1)
    else:
        sys.exit(1)
