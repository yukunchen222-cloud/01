# AI短剧推广自动剪辑工作流 - 使用指南

## 一、本地环境准备

### 1. 创建素材库和成品库文件夹

在您的电脑桌面创建两个文件夹：

**Windows系统**:
```
C:\Users\您的用户名\Desktop\素材库
C:\Users\您的用户名\Desktop\成品库
```

**Mac系统**:
```
/Users/您的用户名/Desktop/素材库
/Users/您的用户名/Desktop/成品库
```

### 2. 配置工作流路径

编辑 `config/workflow_config.yaml` 文件，填入您的实际路径：

```yaml
# Windows示例
MATERIAL_LIBRARY: "C:/Users/张三/Desktop/素材库"
OUTPUT_LIBRARY: "C:/Users/张三/Desktop/成品库"

# Mac示例  
MATERIAL_LIBRARY: "/Users/zhangsan/Desktop/素材库"
OUTPUT_LIBRARY: "/Users/zhangsan/Desktop/成品库"
```

### 3. 安装FFmpeg (视频处理必需)

**Windows**:
1. 下载: https://ffmpeg.org/download.html
2. 解压到 `C:\ffmpeg`
3. 添加到系统环境变量 PATH: `C:\ffmpeg\bin`

**Mac**:
```bash
brew install ffmpeg
```

验证安装:
```bash
ffmpeg -version
```

## 二、使用流程

### 步骤1: 放入素材视频
将需要剪辑的短剧视频放入 **素材库** 文件夹

### 步骤2: 运行爆款Agent获取剪辑策略
```python
from src.graphs.graph import main_graph

result = main_graph.invoke({
    "material_video": {"url": "素材库/your_video.mp4", "file_type": "video"},
    "drama_type": "都市情感"  # 可选: 古装、悬疑、甜宠等
})

# 获取剪辑策略
strategy = result["edit_strategy"]
print(strategy)
```

### 步骤3: 确认剪辑策略
审核生成的剪辑策略文档，确认后继续

### 步骤4: 运行剪辑Agent
```python
from src.graphs.edit_graph import edit_graph
import json

result = edit_graph.invoke({
    "raw_strategy": json.dumps(strategy),
    "material_library": "您的素材库路径",
    "material_filename": "your_video.mp4",
    "output_library": "您的成品库路径"
})

print(f"成品输出: {result['final_output_path']}")
```

### 步骤5: 查看成品
剪辑完成的视频自动保存到 **成品库** 文件夹

## 三、支持的剪辑操作

| 操作类型 | 说明 |
|---------|------|
| 剪切 | 按时间戳裁剪视频片段 |
| 慢动作 | 0.5x / 0.25x 慢放效果 |
| 快进 | 1.5x / 2x 加速效果 |
| 画面震动 | 震动特效 |
| 渐变 | 淡入淡出效果 |
| 缩放 | 画面缩放效果 |
| 画中画 | 多视频叠加 |

## 四、返工机制

当剪辑出现错误时：
1. 系统自动记录错误类型
2. 分析错误模式，生成优化建议
3. 自动返工重新剪辑（最多3次）
4. 输出审核报告

## 五、后续开发

### 投放Agent (开发中)
- 自动爬取投放黄金时间
- 浏览器自动化发布到抖音
- 定时发布功能

### 剪映桌面版集成 (规划中)
- 替代FFmpeg，使用剪映专业版
- 支持更丰富的特效和转场
- GUI自动化控制

## 六、常见问题

**Q: 提示 "FFmpeg not found"**
A: 请确保已安装FFmpeg并添加到系统环境变量

**Q: 素材视频分析失败**
A: 检查视频格式，支持 mp4, mov, avi, mkv

**Q: 剪辑策略生成报错**
A: 可能是API资源不足，请检查DeepSeek API余额

---

如有问题，请查看 AGENTS.md 获取详细技术文档
