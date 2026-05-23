#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI短剧推广自动剪辑工作流 - 启动脚本
功能：
1. 自动扫描素材库内所有视频
2. 自动识别视频内容并分类
3. 批量处理所有视频（可选）
4. 输出到指定成品库
"""

import os
import sys
import json
import yaml
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "workflow_config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def check_ffmpeg() -> bool:
    """检查FFmpeg是否安装"""
    import subprocess
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def scan_material_library(material_library: str) -> List[Dict[str, Any]]:
    """扫描素材库中的所有视频文件"""
    if not os.path.exists(material_library):
        print(f"❌ 素材库路径不存在: {material_library}")
        return []
    
    video_extensions = [".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv"]
    videos = []
    
    # 递归扫描所有子目录
    for root, dirs, files in os.walk(material_library):
        for f in files:
            if any(f.lower().endswith(ext) for ext in video_extensions):
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath) / 1024 / 1024  # MB
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
                videos.append({
                    "name": f,
                    "path": fpath,
                    "size_mb": round(size, 2),
                    "modified": mtime,
                    "relative_path": os.path.relpath(fpath, material_library)
                })
    
    return videos


def upload_to_storage(file_path: str) -> str:
    """上传本地文件到对象存储，返回URL"""
    print(f"   📤 正在上传到云端...")
    
    try:
        from coze_coding_dev_sdk import StorageClient
        
        client = StorageClient()
        
        with open(file_path, 'rb') as f:
            result = client.upload(
                file=f,
                file_name=os.path.basename(file_path),
                content_type="video/mp4"
            )
        
        url = result.get("url", "")
        if url:
            print(f"   ✅ 上传成功")
        return url
        
    except Exception as e:
        print(f"   ⚠️ 上传失败: {e}")
        return ""


def auto_classify_video(video_url: str) -> Dict[str, Any]:
    """自动识别视频内容并分类"""
    try:
        from graphs.nodes.video_classify_node import video_classify_node
        from graphs.state import VideoClassifyInput
        from langchain_core.runnables import RunnableConfig
        
        classify_input = VideoClassifyInput(
            video_path="",
            video_url=video_url
        )
        
        class MockRuntime:
            context = None
        
        result = video_classify_node(
            classify_input,
            RunnableConfig(),
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
        print(f"   ⚠️ 自动识别失败: {e}")
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
    from graphs.graph import main_graph
    
    result = main_graph.invoke({
        "material_video": {"url": video_url, "file_type": "video"},
        "drama_type": drama_type
    })
    
    return result


def run_edit_agent(strategy: dict, material_library: str, video_name: str, output_library: str) -> Dict[str, Any]:
    """运行剪辑Agent执行剪辑"""
    from graphs.edit_graph import edit_graph
    
    result = edit_graph.invoke({
        "raw_strategy": json.dumps(strategy, ensure_ascii=False),
        "material_library": material_library,
        "material_filename": video_name,
        "output_library": output_library
    })
    
    return result


def process_single_video(
    video: Dict[str, Any],
    material_library: str,
    output_library: str,
    auto_mode: bool = False,
    skip_confirm: bool = False
) -> Dict[str, Any]:
    """处理单个视频"""
    print(f"\n{'='*60}")
    print(f"🎯 处理视频: {video['name']}")
    print(f"   大小: {video['size_mb']}MB | 修改时间: {video['modified']}")
    print(f"{'='*60}")
    
    result = {
        "video": video['name'],
        "status": "pending",
        "drama_type": "",
        "output_file": "",
        "error": ""
    }
    
    # 1. 上传视频获取URL
    video_url = upload_to_storage(video['path'])
    if not video_url:
        if video['path'].startswith("http"):
            video_url = video['path']
        else:
            result["status"] = "failed"
            result["error"] = "无法获取视频URL"
            print(f"❌ 跳过: 无法获取视频URL")
            return result
    
    # 2. 自动识别视频内容
    print(f"   🔍 正在识别视频内容...")
    classify_result = auto_classify_video(video_url)
    drama_type = classify_result['drama_type']
    
    print(f"   📊 识别结果: {drama_type} (置信度: {classify_result['confidence']:.0%})")
    print(f"   📝 摘要: {classify_result['content_summary'][:80]}...")
    
    result["drama_type"] = drama_type
    
    # 3. 确认类型（非自动模式）
    if not auto_mode and not skip_confirm:
        confirm = input(f"\n   确认使用 [{drama_type}] 类型? (Y/n): ").strip().lower()
        if confirm == 'n':
            new_type = input("   请输入新的短剧类型: ").strip()
            if new_type:
                drama_type = new_type
                result["drama_type"] = drama_type
    
    # 4. 运行爆款Agent
    print(f"\n   🎬 运行爆款Agent生成剪辑策略...")
    try:
        viral_result = run_viral_agent(video_url, drama_type)
        strategy = viral_result.get("edit_strategy", {})
        if isinstance(strategy, str):
            try:
                strategy = json.loads(strategy)
            except:
                strategy = {"overall_strategy": {}, "edit_points": []}
        
        print(f"   ✅ 策略生成完成，共 {len(strategy.get('edit_points', []))} 个剪辑点")
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"爆款Agent失败: {str(e)}"
        print(f"   ❌ 策略生成失败: {e}")
        return result
    
    # 5. 确认剪辑（非自动模式）
    if not auto_mode and not skip_confirm:
        confirm_edit = input(f"\n   确认开始剪辑? (Y/n): ").strip().lower()
        if confirm_edit == 'n':
            result["status"] = "skipped"
            print(f"   ⏭️ 跳过剪辑")
            return result
    
    # 6. 运行剪辑Agent
    print(f"\n   ✂️ 运行剪辑Agent执行剪辑...")
    try:
        edit_result = run_edit_agent(strategy, material_library, video['name'], output_library)
        
        output_file = edit_result.get("final_output_path", "")
        if output_file and os.path.exists(output_file):
            result["status"] = "success"
            result["output_file"] = output_file
            print(f"   ✅ 剪辑完成: {os.path.basename(output_file)}")
        else:
            result["status"] = "partial"
            result["error"] = "剪辑输出可能不完整"
            print(f"   ⚠️ 剪辑可能不完整")
            
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"剪辑失败: {str(e)}"
        print(f"   ❌ 剪辑失败: {e}")
    
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
    print(f"\n🔍 正在扫描素材库...")
    videos = scan_material_library(material_library)
    
    if not videos:
        print(f"\n❌ 素材库中没有找到视频文件!")
        print(f"   请将视频文件放入: {material_library}")
        print(f"   支持格式: MP4, MOV, AVI, MKV, FLV, WMV")
        return
    
    print(f"\n📹 找到 {len(videos)} 个视频文件:")
    for i, v in enumerate(videos, 1):
        print(f"   {i}. {v['name']} ({v['size_mb']}MB)")
    
    # 选择处理模式
    print(f"\n" + "-"*60)
    print("请选择处理模式:")
    print("  1. 全部自动处理 (自动识别、自动剪辑，无需确认)")
    print("  2. 逐个处理 (每个视频需要确认)")
    print("  3. 选择单个视频处理")
    print("  4. 测试模式 (使用测试视频)")
    print("-"*60)
    
    try:
        mode = int(input("\n请输入序号 (默认1): ") or "1")
    except ValueError:
        mode = 1
    
    results = []
    
    if mode == 1:
        # 全部自动处理
        print(f"\n🚀 开始批量自动处理 {len(videos)} 个视频...")
        for video in videos:
            result = process_single_video(
                video, 
                material_library, 
                output_library,
                auto_mode=True,
                skip_confirm=True
            )
            results.append(result)
            
    elif mode == 2:
        # 逐个处理
        for video in videos:
            result = process_single_video(
                video,
                material_library,
                output_library,
                auto_mode=False
            )
            results.append(result)
            
    elif mode == 3:
        # 选择单个视频
        for i, v in enumerate(videos, 1):
            print(f"  {i}. {v['name']}")
        
        try:
            choice = int(input(f"\n请输入序号 (1-{len(videos)}): "))
            if 1 <= choice <= len(videos):
                result = process_single_video(
                    videos[choice - 1],
                    material_library,
                    output_library,
                    auto_mode=False
                )
                results.append(result)
        except ValueError:
            print("❌ 无效选择")
            
    elif mode == 4:
        # 测试模式 - 使用在线测试视频
        print(f"\n🧪 测试模式: 使用在线测试视频")
        test_url = "https://coze-coding-mockdata.tos-cn-beijing.volces.com/video_bkarsr.mp4"
        
        test_video = {
            "name": "test_drama.mp4",
            "path": test_url,
            "size_mb": 0,
            "modified": "测试"
        }
        
        result = process_single_video(
            test_video,
            material_library,
            output_library,
            auto_mode=True,
            skip_confirm=True
        )
        results.append(result)
    
    # 输出汇总报告
    print(f"\n" + "="*60)
    print("📊 处理结果汇总")
    print("="*60)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    
    for r in results:
        status_icon = "✅" if r["status"] == "success" else "❌" if r["status"] == "failed" else "⏭️"
        print(f"   {status_icon} {r['video']}: {r['status']} - {r.get('drama_type', '-')}")
    
    print(f"\n📈 统计: 成功 {success_count}, 失败 {failed_count}, 跳过 {skipped_count}")
    print(f"📂 输出目录: {output_library}")
    
    # 保存处理报告
    report_file = os.path.join(output_library, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "material_library": material_library,
            "output_library": output_library,
            "total_videos": len(videos),
            "processed": len(results),
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"📄 处理报告已保存: {report_file}")


if __name__ == "__main__":
    main()
