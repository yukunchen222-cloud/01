#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI短剧推广自动剪辑工作流 - 启动脚本
功能：
1. 自动识别素材库视频内容
2. 自动判断短剧类型
3. 批量处理或单个处理
4. 输出到指定成品库
"""

import os
import sys
import json
import yaml
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "workflow_config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def check_ffmpeg():
    """检查FFmpeg是否安装"""
    import subprocess
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def list_materials(material_library: str) -> List[Dict[str, Any]]:
    """列出素材库中的视频文件及其信息"""
    if not os.path.exists(material_library):
        print(f"❌ 素材库路径不存在: {material_library}")
        return []
    
    video_extensions = [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv"]
    videos = []
    for f in os.listdir(material_library):
        if any(f.lower().endswith(ext) for ext in video_extensions):
            fpath = os.path.join(material_library, f)
            size = os.path.getsize(fpath) / 1024 / 1024  # MB
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
            videos.append({
                "name": f,
                "path": fpath,
                "size_mb": round(size, 2),
                "modified": mtime
            })
    return videos


def upload_to_storage(file_path: str) -> str:
    """上传本地文件到对象存储，返回URL"""
    print(f"📤 正在上传文件到云端...")
    
    try:
        from coze_coding_dev_sdk import StorageClient
        
        client = StorageClient()
        
        # 上传文件
        with open(file_path, 'rb') as f:
            result = client.upload(
                file=f,
                file_name=os.path.basename(file_path),
                content_type="video/mp4"
            )
        
        url = result.get("url", "")
        print(f"✅ 上传成功: {url[:50]}...")
        return url
        
    except Exception as e:
        print(f"⚠️ 上传失败: {e}")
        # 如果上传失败，返回空字符串
        return ""


def auto_classify_video(video_path: str, video_url: str = "") -> Dict[str, Any]:
    """自动识别视频内容并分类"""
    print(f"\n🔍 正在识别视频内容...")
    
    # 优先使用URL，因为模型不支持本地路径
    input_url = video_url
    if not input_url and video_path.startswith("http"):
        input_url = video_path
    
    if not input_url and os.path.exists(video_path):
        # 本地文件需要先上传
        input_url = upload_to_storage(video_path)
    
    if not input_url:
        print("⚠️ 无法获取视频URL，使用默认分类")
        return {
            "drama_type": "都市情感",
            "confidence": 0.5,
            "content_summary": "无法获取视频URL",
            "key_elements": [],
            "emotion_tone": "未知",
            "suggested_style": "标准剪辑"
        }
    
    try:
        from graphs.nodes.video_classify_node import video_classify_node
        from graphs.state import VideoClassifyInput
        from langchain_core.runnables import RunnableConfig
        from langgraph.runtime import Runtime
        from coze_coding_utils.runtime_ctx.context import Context
        
        # 构建输入
        classify_input = VideoClassifyInput(
            video_path="",
            video_url=input_url
        )
        
        # 创建模拟的config和runtime
        config = RunnableConfig()
        
        # 创建模拟Runtime
        class MockRuntime:
            context = None
        
        # 调用分类节点
        result = video_classify_node(
            classify_input,
            config,
            MockRuntime()
        )
        
        return {
            "drama_type": result.drama_type,
            "confidence": result.drama_type_confidence,
            "content_summary": result.content_summary,
            "key_elements": result.key_elements,
            "emotion_tone": result.emotion_tone,
            "suggested_style": result.suggested_style
        }
        
    except Exception as e:
        print(f"⚠️ 自动识别失败: {e}")
        print("   将使用默认分类: 都市情感")
        return {
            "drama_type": "都市情感",
            "confidence": 0.5,
            "content_summary": f"识别失败: {str(e)}",
            "key_elements": [],
            "emotion_tone": "未知",
            "suggested_style": "标准剪辑"
        }


def run_viral_agent(video_url: str, drama_type: str) -> Dict[str, Any]:
    """运行爆款Agent获取剪辑策略"""
    print("\n" + "="*50)
    print("🎬 第一步: 运行爆款Agent分析素材...")
    print("="*50)
    
    from graphs.graph import main_graph
    from utils.file.file import File
    
    # 构建输入
    result = main_graph.invoke({
        "material_video": {"url": video_url, "file_type": "video"},
        "drama_type": drama_type
    })
    
    return result


def run_edit_agent(strategy: dict, material_library: str, video_name: str, output_library: str) -> Dict[str, Any]:
    """运行剪辑Agent执行剪辑"""
    print("\n" + "="*50)
    print("✂️ 第二步: 运行剪辑Agent执行剪辑...")
    print("="*50)
    
    from graphs.edit_graph import edit_graph
    
    result = edit_graph.invoke({
        "raw_strategy": json.dumps(strategy, ensure_ascii=False),
        "material_library": material_library,
        "material_filename": video_name,
        "output_library": output_library
    })
    
    return result


def main():
    """主函数"""
    print("="*60)
    print("🎬 AI短剧推广自动剪辑工作流")
    print("="*60)
    
    # 检查FFmpeg
    if not check_ffmpeg():
        print("\n⚠️ 警告: FFmpeg未安装，视频剪辑功能可能无法正常工作")
        print("   请安装FFmpeg: https://ffmpeg.org/download.html")
    else:
        print("✅ FFmpeg已安装")
    
    # 加载配置
    config = load_config()
    material_library = config.get("MATERIAL_LIBRARY", "C:/Users/lonel/Desktop/素材库")
    output_library = config.get("OUTPUT_LIBRARY", "C:/Users/lonel/Desktop/成品库")
    
    print(f"\n📂 素材库: {material_library}")
    print(f"📂 成品库: {output_library}")
    
    # 创建输出目录
    os.makedirs(output_library, exist_ok=True)
    
    # 扫描素材库
    videos = list_materials(material_library)
    
    if not videos:
        print(f"\n❌ 素材库中没有找到视频文件!")
        print(f"   请将视频文件放入: {material_library}")
        print(f"   支持格式: MP4, MOV, AVI, MKV, FLV, WMV")
        return
    
    print(f"\n📹 找到 {len(videos)} 个视频文件:")
    for i, v in enumerate(videos, 1):
        print(f"   {i}. {v['name']} ({v['size_mb']}MB, {v['modified']})")
    
    # 选择要处理的视频
    if len(videos) == 1:
        selected = videos[0]
        print(f"\n✅ 自动选择唯一视频: {selected['name']}")
    else:
        print("\n请选择要处理的视频:")
        print("  0. 全部处理")
        for i, v in enumerate(videos, 1):
            print(f"  {i}. {v['name']}")
        
        try:
            choice = int(input("\n请输入序号 (默认1): ") or "1")
        except ValueError:
            choice = 1
        
        if choice == 0:
            selected_videos = videos
        else:
            selected_videos = [videos[choice - 1]] if 1 <= choice <= len(videos) else [videos[0]]
    
    # 处理选中的视频
    for video in selected_videos if isinstance(selected_videos, list) else [selected_videos]:
        print("\n" + "="*60)
        print(f"🎯 开始处理: {video['name']}")
        print("="*60)
        
        # 1. 上传视频获取URL
        video_url = upload_to_storage(video['path'])
        if not video_url:
            # 如果上传失败，尝试直接使用路径（可能是在沙箱环境）
            if video['path'].startswith("http"):
                video_url = video['path']
            else:
                print(f"❌ 跳过 {video['name']}: 无法获取视频URL")
                continue
        
        # 2. 自动识别视频内容
        classify_result = auto_classify_video(video['path'], video_url)
        drama_type = classify_result['drama_type']
        
        print(f"\n📊 视频分析结果:")
        print(f"   类型: {drama_type} (置信度: {classify_result['confidence']:.0%})")
        print(f"   摘要: {classify_result['content_summary'][:100]}...")
        print(f"   情感: {classify_result['emotion_tone']}")
        print(f"   建议: {classify_result['suggested_style']}")
        
        # 确认是否继续
        confirm = input(f"\n确认使用 [{drama_type}] 类型进行剪辑? (Y/n): ").strip().lower()
        if confirm == 'n':
            new_type = input("请输入新的短剧类型: ").strip()
            if new_type:
                drama_type = new_type
        
        # 3. 运行爆款Agent
        viral_result = run_viral_agent(video_url, drama_type)
        
        strategy = viral_result.get("edit_strategy", {})
        if isinstance(strategy, str):
            try:
                strategy = json.loads(strategy)
            except:
                strategy = {"overall_strategy": {}, "edit_points": []}
        
        print(f"\n📋 剪辑策略生成完成:")
        print(f"   核心卖点: {strategy.get('overall_strategy', {}).get('core_selling_point', '无')[:50]}...")
        print(f"   剪辑点数: {len(strategy.get('edit_points', []))}")
        
        # 确认剪辑思路
        confirm_edit = input("\n确认开始剪辑? (Y/n): ").strip().lower()
        if confirm_edit == 'n':
            print("⏭️ 跳过剪辑，保存策略...")
            # 保存策略
            strategy_file = os.path.join(output_library, f"{video['name']}_strategy.json")
            with open(strategy_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "video": video['name'],
                    "drama_type": drama_type,
                    "classify": classify_result,
                    "strategy": strategy
                }, f, ensure_ascii=False, indent=2)
            print(f"✅ 策略已保存: {strategy_file}")
            continue
        
        # 4. 运行剪辑Agent
        edit_result = run_edit_agent(strategy, material_library, video['name'], output_library)
        
        # 5. 显示结果
        output_file = edit_result.get("output_file", "")
        if output_file and os.path.exists(output_file):
            print(f"\n✅ 剪辑完成!")
            print(f"   输出文件: {output_file}")
            print(f"   文件大小: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")
        else:
            print(f"\n⚠️ 剪辑可能未完成，请检查成品库")
        
        print(f"\n{'='*60}")
        print(f"✅ {video['name']} 处理完成!")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
