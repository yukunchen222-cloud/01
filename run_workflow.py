#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI短剧推广自动剪辑工作流 - 启动脚本
使用方法: python run_workflow.py
"""

import os
import sys
import json
import yaml
from pathlib import Path

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

def list_materials(material_library: str):
    """列出素材库中的视频文件"""
    if not os.path.exists(material_library):
        print(f"❌ 素材库路径不存在: {material_library}")
        return []
    
    video_extensions = [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv"]
    videos = []
    for f in os.listdir(material_library):
        if any(f.lower().endswith(ext) for ext in video_extensions):
            videos.append(f)
    return videos

def run_viral_agent(video_path: str, drama_type: str = "都市情感"):
    """运行爆款Agent获取剪辑策略"""
    print("\n" + "="*50)
    print("🎬 第一步: 运行爆款Agent分析素材...")
    print("="*50)
    
    from src.graphs.graph import main_graph
    from utils.file.file import File
    
    # 构建输入
    video_url = video_path
    if os.path.exists(video_path):
        video_url = video_path
    
    result = main_graph.invoke({
        "material_video": {"url": video_url, "file_type": "video"},
        "drama_type": drama_type
    })
    
    return result

def run_edit_agent(strategy: dict, material_library: str, video_name: str, output_library: str):
    """运行剪辑Agent执行剪辑"""
    print("\n" + "="*50)
    print("✂️ 第二步: 运行剪辑Agent执行剪辑...")
    print("="*50)
    
    from src.graphs.edit_graph import edit_graph
    
    result = edit_graph.invoke({
        "raw_strategy": json.dumps(strategy, ensure_ascii=False),
        "material_library": material_library,
        "material_filename": video_name,
        "output_library": output_library
    })
    
    return result

def main():
    """主函数"""
    print("\n" + "="*60)
    print("🎭 AI短剧推广自动剪辑工作流")
    print("="*60)
    
    # 检查FFmpeg
    if not check_ffmpeg():
        print("\n⚠️ 警告: FFmpeg未安装，部分功能可能无法使用")
        print("请安装FFmpeg: https://ffmpeg.org/download.html")
    else:
        print("✅ FFmpeg已安装")
    
    # 加载配置
    config = load_config()
    material_library = config.get("MATERIAL_LIBRARY", "")
    output_library = config.get("OUTPUT_LIBRARY", "")
    
    # 检查路径配置
    if not material_library or not output_library:
        print("\n⚠️ 请先配置素材库和成品库路径!")
        print("编辑 config/workflow_config.yaml 文件")
        
        # 提示用户输入
        print("\n请输入素材库路径 (例如: C:/Users/张三/Desktop/素材库):")
        material_library = input().strip().strip('"').strip("'")
        
        print("请输入成品库路径 (例如: C:/Users/张三/Desktop/成品库):")
        output_library = input().strip().strip('"').strip("'")
        
        # 创建文件夹
        os.makedirs(material_library, exist_ok=True)
        os.makedirs(output_library, exist_ok=True)
        print(f"✅ 已创建文件夹")
    
    # 列出素材
    videos = list_materials(material_library)
    if not videos:
        print(f"\n⚠️ 素材库中没有视频文件")
        print(f"请将视频放入: {material_library}")
        return
    
    print(f"\n📁 素材库中的视频 ({len(videos)}个):")
    for i, v in enumerate(videos, 1):
        print(f"  {i}. {v}")
    
    # 选择视频
    print("\n请输入要剪辑的视频序号 (输入数字):")
    try:
        idx = int(input().strip())
        if idx < 1 or idx > len(videos):
            print("❌ 无效的序号")
            return
        video_name = videos[idx - 1]
    except ValueError:
        print("❌ 请输入数字")
        return
    
    video_path = os.path.join(material_library, video_name)
    print(f"\n已选择: {video_name}")
    
    # 选择短剧类型
    print("\n请选择短剧类型:")
    print("1. 都市情感")
    print("2. 古装穿越")
    print("3. 悬疑推理")
    print("4. 甜宠恋爱")
    print("5. 其他")
    
    drama_types = {
        "1": "都市情感",
        "2": "古装穿越", 
        "3": "悬疑推理",
        "4": "甜宠恋爱",
        "5": "其他"
    }
    
    print("请输入序号 (默认1):")
    type_idx = input().strip() or "1"
    drama_type = drama_types.get(type_idx, "都市情感")
    
    print(f"\n短剧类型: {drama_type}")
    
    # 运行爆款Agent
    try:
        viral_result = run_viral_agent(video_path, drama_type)
        
        if "error" in viral_result.get("edit_strategy", {}):
            print(f"\n❌ 爆款Agent运行失败: {viral_result['edit_strategy']['error']}")
            print("可能是API资源不足，请检查DeepSeek API余额")
            return
        
        strategy = viral_result.get("edit_strategy", {})
        if isinstance(strategy, str):
            # 解析JSON字符串
            strategy = json.loads(strategy)
        
        print("\n✅ 爆款Agent分析完成!")
        print(f"\n📋 剪辑策略预览:")
        if "overall_strategy" in strategy:
            print(f"   核心卖点: {strategy['overall_strategy'].get('core_selling_point', '')}")
            print(f"   目标情绪: {strategy['overall_strategy'].get('target_emotion', '')}")
            print(f"   建议时长: {strategy['overall_strategy'].get('suggested_duration', '')}")
        
        # 确认是否继续
        print("\n是否继续执行剪辑? (y/n):")
        confirm = input().strip().lower()
        if confirm != "y":
            print("已取消")
            return
        
    except Exception as e:
        print(f"\n❌ 爆款Agent运行出错: {e}")
        return
    
    # 运行剪辑Agent
    try:
        edit_result = run_edit_agent(strategy, material_library, video_name, output_library)
        
        output_path = edit_result.get("final_output_path", "")
        if output_path and os.path.exists(output_path):
            print(f"\n✅ 剪辑完成!")
            print(f"📁 成品路径: {output_path}")
            
            # 列出成品库文件
            print(f"\n📦 成品库文件:")
            for f in os.listdir(output_library):
                if f.endswith((".mp4", ".json", ".txt")):
                    fpath = os.path.join(output_library, f)
                    size = os.path.getsize(fpath) / 1024 / 1024
                    print(f"   {f} ({size:.2f} MB)")
        else:
            print("\n❌ 剪辑失败")
            
    except Exception as e:
        print(f"\n❌ 剪辑Agent运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
