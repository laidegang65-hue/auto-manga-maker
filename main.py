import os
import json
import time
import sys
import requests
import urllib.parse
import asyncio
import edge_tts
# 确保导入旧版 moviepy
try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    print("❌ 严重错误: moviepy 版本不对，请检查 requirements.txt 是否写了 moviepy==1.0.3")
    sys.exit(1)

# ================= 配置区 =================
print("🚀 初始化：强制生成版 (含兜底机制)...")

# ================= 1. 分镜生成模块 (带兜底) =================
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
        # 尝试清洗 JSON
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end != -1:
            data = json.loads(content[start:end])
            # 简单校验数据格式
            if isinstance(data, list) and len(data) > 0 and "sd_prompt" in data[0]:
                print(f"✅ AI 剧本生成成功 (共 {len(data)} 镜)")
                return data
    except Exception as e:
        print(f"⚠️ 在线获取分镜失败: {e}")
    
    # === 🚨 兜底机制：如果AI挂了，使用备用分镜，保证程序不中断 ===
    print("🔄 启动备用分镜 (Fallback Mode)...")
    return [
        {
            "id": 1, 
            "narrator": "由于网络波动，AI无法实时生成，正在使用备用画面。", 
            "sd_prompt": "1boy, standing in cyber city, neon lights, back view, anime style, 8k"
        },
        {
            "id": 2, 
            "narrator": "但这并不影响我们生成视频的流程。", 
            "sd_prompt": "close up of mechanical eye, glowing blue, highly detailed, anime style"
        },
        {
            "id": 3, 
            "narrator": "请检查网络或稍后再试，自动化系统依然正常运转。", 
            "sd_prompt": "sunset over ruins, melancholic atmosphere, lens flare, anime style"
        }
    ]

# ================= 2. 画图模块 =================
def download_image(prompt, filename):
    # 智能修正 key，防止 AI 乱写 key 名字
    if not prompt: prompt = "anime style scene, high quality"
    
    final_prompt = f"{prompt}, anime style, masterpiece, best quality, 8k"
    encoded_prompt = urllib.parse.quote(final_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1344&model=flux&seed={int(time.time())}"
    
    for i in range(3): 
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=30)
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
        pass # 配音失败不阻断流程

# ================= 主程序 =================
if __name__ == "__main__":
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    default_text = "林萧站在废墟顶端，红色的斗篷在风中猎猎作响。他拔出背后的长刀，刀锋在月光下闪着寒光。"
    novel = os.environ.get("USER_NOVEL", default_text)
    
    # 1. 获取分镜 (含兜底)
    scenes = get_storyboard(novel)

    # 2. 生产素材
    video_clips = []
    print(f"🎬 [2/4] 开始生产素材 (共 {len(scenes)} 镜)...")
    
    for scene in scenes:
        idx = scene.get("id", 0)
        # 兼容不同的 Key 写法
        prompt = scene.get("sd_prompt") or scene.get("image_prompt") or scene.get("description")
        narrator = scene.get("narrator") or "..."
        
        img_path = os.path.join(output_dir, f"scene_{idx}.jpg")
        audio_path = os.path.join(output_dir, f"scene_{idx}.mp3")
        
        print(f"   👉 第 {idx} 镜: 画图...", end="")
        if download_image(prompt, img_path):
            print("成功 | 配音...", end="")
            asyncio.run(generate_audio(narrator, audio_path))
            print("完成")
            
            if os.path.exists(img_path):
                try:
                    duration = 3
                    has_audio = False
                    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
                        audio_clip = AudioFileClip(audio_path)
                        duration = audio_clip.duration + 0.5
                        has_audio = True
                    
                    img_clip = ImageClip(img_path).set_duration(duration)
                    if has_audio:
                        img_clip = img_clip.set_audio(audio_clip)
                    
                    # 统一尺寸
                    img_clip = img_clip.resize(height=1280) 
                    if img_clip.w % 2 != 0: img_clip = img_clip.resize(width=img_clip.w - 1)
                    img_clip.fps = 12 
                    
                    video_clips.append(img_clip)
                except Exception as e:
                    print(f"      ❌ 剪辑出错: {e}")
            
            time.sleep(3)
        else:
            print("失败 (跳过)")

    # 3. 合成视频
    if video_clips:
        print(f"🎞️ [3/4] 正在渲染最终视频...")
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
            
            if os.path.exists(final_path) and os.path.getsize(final_path) > 1000:
                print(f"✅ [4/4] 视频制作完成！文件大小: {os.path.getsize(final_path)/1024:.2f} KB")
            else:
                print("❌ 视频文件生成失败或为空")
                sys.exit(1) # 强制报错
                
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
            sys.exit(1)
    else:
        print("❌ 没有任何有效片段生成！")
        sys.exit(1) # 强制报错，让 Action 变红
