#!/usr/bin/env python
"""
完整流程测试脚本
测试爆款Agent + 剪辑Agent的完整流程
"""
import os
import sys
import json

# 添加项目路径
sys.path.insert(0, "/workspace/projects/src")

from graphs.edit_graph import edit_graph


# 模拟的剪辑策略（由于爆款Agent资源点不足，使用模拟数据）
MOCK_EDIT_STRATEGY = '''
{
    "overall_strategy": {
        "core_selling_point": "都市情感短剧，咖啡厅偶遇，眼神交汇的暧昧瞬间",
        "target_emotion": "心动",
        "suggested_duration": "30-45秒",
        "pace_style": "中速节奏"
    },
    "hook_strategy": {
        "type": "情绪共鸣式",
        "opening_3_seconds": {
            "timestamp": "00:00-00:03",
            "content": "男女主角眼神交汇的特写",
            "technique": "使用慢动作突出眼神交流，配合轻柔背景音乐",
            "expected_effect": "瞬间抓住观众注意力，引发共鸣"
        },
        "hook_strength": 8
    },
    "edit_points": [
        {
            "sequence": 1,
            "source_timestamp": "00:00-00:03",
            "content": "开场钩子：眼神交汇特写",
            "edit_reason": "黄金3秒，用最强情绪点开场",
            "suggested_effects": ["慢动作"],
            "duration": "3秒"
        },
        {
            "sequence": 2,
            "source_timestamp": "00:03-00:10",
            "content": "男主角主动走向女主角的中景镜头",
            "edit_reason": "展示男主角的主动，推进剧情",
            "suggested_effects": [],
            "duration": "7秒"
        },
        {
            "sequence": 3,
            "source_timestamp": "00:10-00:20",
            "content": "两人对话交流的近景切换",
            "edit_reason": "展示两人互动，加深情感连接",
            "suggested_effects": [],
            "duration": "10秒"
        },
        {
            "sequence": 4,
            "source_timestamp": "00:20-00:30",
            "content": "暧昧氛围高潮：微笑、眼神交流",
            "edit_reason": "情绪高潮点，强化心动感",
            "suggested_effects": ["慢动作", "BGM渐强"],
            "duration": "10秒"
        },
        {
            "sequence": 5,
            "source_timestamp": "00:30-00:40",
            "content": "结尾悬念：男主角伸手邀请",
            "edit_reason": "留下悬念，引发期待",
            "suggested_effects": ["定格"],
            "duration": "10秒"
        }
    ],
    "title_suggestions": [
        {
            "title": "咖啡厅偶遇，他一开口我就沦陷了💔#短剧推荐 #都市情感",
            "pattern_used": "场景+情绪共鸣+话题标签",
            "expected_ctr": "高"
        },
        {
            "title": "这是什么神仙偶遇？男主太会撩了！",
            "pattern_used": "疑问句+感叹",
            "expected_ctr": "中高"
        }
    ],
    "cover_design": {
        "main_visual": "男女主角眼神交汇的近景特写",
        "text_overlay": ""他说的第一句话，让我心跳加速"",
        "color_scheme": "暖色调，咖啡色系为主，营造温馨氛围"
    },
    "audio_strategy": {
        "bgm_style": "轻柔浪漫的钢琴曲或流行音乐",
        "bgm_mood": "甜蜜、心动、期待",
        "key_sound_effects": []
    }
}
'''


def test_edit_agent():
    """测试剪辑Agent工作流"""
    print("=" * 60)
    print("剪辑Agent工作流测试")
    print("=" * 60)
    
    # 准备输入
    input_data = {
        "raw_strategy": MOCK_EDIT_STRATEGY,
        "material_library": os.path.expanduser("~/Desktop/素材库"),
        "material_filename": "test_drama.mp4",
        "output_library": os.path.expanduser("~/Desktop/成品库")
    }
    
    print(f"\n输入配置:")
    print(f"  素材库: {input_data['material_library']}")
    print(f"  素材文件: {input_data['material_filename']}")
    print(f"  成品库: {input_data['output_library']}")
    
    print("\n开始执行剪辑工作流...")
    
    try:
        # 执行工作流
        result = edit_graph.invoke(input_data)
        
        print("\n" + "=" * 60)
        print("执行结果:")
        print("=" * 60)
        
        if result.get("export_success"):
            print(f"✓ 剪辑成功!")
            print(f"  输出文件: {result.get('final_output_path', '')}")
            print(f"  元数据: {json.dumps(result.get('metadata', {}), ensure_ascii=False, indent=2)[:500]}...")
        else:
            print(f"✗ 剪辑失败: {result.get('error_message', '未知错误')}")
        
        print(f"\n是否需要返工: {'是' if result.get('need_rework') else '否'}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ 执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("AI短剧推广自动剪辑 - 完整流程测试")
    print("=" * 60)
    
    # 检查素材库
    material_lib = os.path.expanduser("~/Desktop/素材库")
    if not os.path.exists(material_lib):
        print(f"\n创建素材库: {material_lib}")
        os.makedirs(material_lib, exist_ok=True)
    
    # 检查成品库
    output_lib = os.path.expanduser("~/Desktop/成品库")
    if not os.path.exists(output_lib):
        print(f"创建成品库: {output_lib}")
        os.makedirs(output_lib, exist_ok=True)
    
    # 检查素材文件
    material_file = os.path.join(material_lib, "test_drama.mp4")
    if not os.path.exists(material_file):
        print(f"\n⚠ 警告: 素材文件不存在: {material_file}")
        print("请先运行素材下载命令")
        return
    
    print(f"\n✓ 素材文件已就绪: {material_file}")
    
    # 执行剪辑测试
    result = test_edit_agent()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
