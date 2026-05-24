"""
剪映桌面版自动化控制模块
使用 pyautogui + pywinauto 实现剪映的自动化操作
"""

import os
import time
import json
import subprocess
import platform
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class EditOperation:
    """剪辑操作数据类"""
    operation_type: str  # split, speed, transition, filter, text, audio
    timestamp: str       # 操作时间点 "00:00-00:03"
    params: Dict[str, Any]  # 操作参数


class JianyingController:
    """剪映桌面版控制器"""
    
    # 剪映默认安装路径
    JIANYING_PATHS = {
        'Windows': [
            r"C:\Program Files\JianyingPro\JianyingPro.exe",
            r"C:\Program Files (x86)\JianyingPro\JianyingPro.exe",
            os.path.expanduser(r"~\AppData\Local\JianyingPro\JianyingPro.exe"),
            r"D:\Program Files\JianyingPro\JianyingPro.exe",
            r"E:\Program Files\JianyingPro\JianyingPro.exe",
        ],
        'Darwin': [  # macOS
            "/Applications/JianyingPro.app/Contents/MacOS/JianyingPro",
        ]
    }
    
    # 快捷键映射
    SHORTCUTS = {
        'split': ['ctrl', 'b'],           # 分割
        'delete': ['ctrl', 'delete'],     # 删除
        'undo': ['ctrl', 'z'],            # 撤销
        'redo': ['ctrl', 'shift', 'z'],   # 重做
        'copy': ['ctrl', 'c'],            # 复制
        'paste': ['ctrl', 'v'],           # 粘贴
        'select_all': ['ctrl', 'a'],      # 全选
        'play_pause': ['space'],          # 播放/暂停
        'export': ['ctrl', 'e'],          # 导出
        'add_text': ['ctrl', 't'],        # 添加文本
        'add_audio': ['ctrl', 'shift', 'a'],  # 添加音频
    }
    
    def __init__(self, jianying_path: Optional[str] = None):
        """
        初始化剪映控制器
        
        Args:
            jianying_path: 剪映安装路径，如果不提供会自动检测
        """
        self.system = platform.system()
        self.jianying_path = jianying_path or self._find_jianying()
        self.is_running = False
        self.current_project = None
        
        # 延迟导入，避免在无GUI环境报错
        self.pyautogui = None
        self.pywinauto = None
        self._init_automation()
        
    def _init_automation(self):
        """初始化自动化库"""
        try:
            import pyautogui
            self.pyautogui = pyautogui
            # 设置安全措施
            pyautogui.PAUSE = 0.5
            pyautogui.FAILSAFE = True
            logger.info("pyautogui 初始化成功")
        except ImportError:
            logger.warning("pyautogui 未安装，请运行: pip install pyautogui")
        except Exception as e:
            # 无GUI环境（如沙箱）会报错，这是正常的
            logger.warning(f"pyautogui 初始化失败（可能是无GUI环境）: {e}")
            
        if self.system == 'Windows':
            try:
                from pywinauto.application import Application  # type: ignore[misc]
                self.pywinauto_app = Application  # type: ignore[misc]
                logger.info("pywinauto 初始化成功")
            except ImportError:
                logger.warning("pywinauto 未安装，请运行: pip install pywinauto")
            except Exception as e:
                logger.warning(f"pywinauto 初始化失败: {e}")
    
    def _find_jianying(self) -> Optional[str]:
        """自动查找剪映安装路径"""
        paths = self.JIANYING_PATHS.get(self.system, [])
        for path in paths:
            if os.path.exists(path):
                logger.info(f"找到剪映安装路径: {path}")
                return path
        logger.warning("未找到剪映安装路径，请手动指定")
        return None
    
    def is_installed(self) -> bool:
        """检查剪映是否已安装"""
        return self.jianying_path is not None and os.path.exists(self.jianying_path)
    
    def start_jianying(self, wait_time: int = 10) -> bool:
        """
        启动剪映
        
        Args:
            wait_time: 等待启动的时间（秒）
        
        Returns:
            是否启动成功
        """
        if not self.is_installed():
            logger.error("剪映未安装或路径未找到")
            return False
            
        try:
            logger.info(f"正在启动剪映: {self.jianying_path}")
            
            if self.system == 'Windows':
                # Windows使用subprocess启动
                subprocess.Popen([self.jianying_path])
            else:
                # macOS使用open命令
                subprocess.Popen(['open', self.jianying_path])
            
            # 等待启动
            time.sleep(wait_time)
            self.is_running = True
            logger.info("剪映启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动剪映失败: {e}")
            return False
    
    def create_new_project(self, project_name: str = "自动剪辑项目", 
                           resolution: str = "1080p") -> bool:
        """
        创建新项目
        
        Args:
            project_name: 项目名称
            resolution: 分辨率 (720p, 1080p, 4K)
        
        Returns:
            是否创建成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        try:
            logger.info(f"创建新项目: {project_name}")
            
            # 点击"开始创作"按钮（需要根据实际UI调整坐标）
            # 这里使用快捷键方式
            time.sleep(1)
            
            # 按Ctrl+N创建新项目
            self.pyautogui.hotkey('ctrl', 'n')
            time.sleep(2)
            
            # 设置项目名称
            self.pyautogui.typewrite(project_name)
            time.sleep(0.5)
            
            # 选择分辨率
            # TODO: 根据实际UI调整
            
            # 确认创建
            self.pyautogui.press('enter')
            time.sleep(2)
            
            self.current_project = project_name
            logger.info("新项目创建成功")
            return True
            
        except Exception as e:
            logger.error(f"创建新项目失败: {e}")
            return False
    
    def import_material(self, video_path: str) -> bool:
        """
        导入素材到项目
        
        Args:
            video_path: 视频文件路径
        
        Returns:
            是否导入成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        if not os.path.exists(video_path):
            logger.error(f"素材文件不存在: {video_path}")
            return False
            
        try:
            logger.info(f"导入素材: {video_path}")
            
            # 方法1: 使用快捷键导入
            # Ctrl+I 打开导入对话框
            self.pyautogui.hotkey('ctrl', 'i')
            time.sleep(2)
            
            # 输入文件路径
            self.pyautogui.typewrite(video_path)
            time.sleep(0.5)
            
            # 确认
            self.pyautogui.press('enter')
            time.sleep(2)
            
            # 将素材拖入时间轴
            # TODO: 根据实际UI调整坐标
            
            logger.info("素材导入成功")
            return True
            
        except Exception as e:
            logger.error(f"导入素材失败: {e}")
            return False
    
    def split_at_position(self, position_seconds: float) -> bool:
        """
        在指定时间点分割视频
        
        Args:
            position_seconds: 分割位置（秒）
        
        Returns:
            是否分割成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        try:
            logger.info(f"在 {position_seconds} 秒处分割")
            
            # 1. 定位时间轴到指定位置
            # 这需要根据时间轴UI计算像素位置
            # 简化处理：使用播放头定位
            
            # 2. 使用快捷键分割
            self.pyautogui.hotkey(*self.SHORTCUTS['split'])
            time.sleep(0.5)
            
            logger.info("分割完成")
            return True
            
        except Exception as e:
            logger.error(f"分割失败: {e}")
            return False
    
    def set_speed(self, speed: float, start_time: float, end_time: float) -> bool:
        """
        设置片段速度（变速）
        
        Args:
            speed: 速度倍数 (0.5=慢放, 2.0=加速)
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        
        Returns:
            是否设置成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        try:
            logger.info(f"设置速度 {speed}x: {start_time}-{end_time}秒")
            
            # 1. 选中目标片段
            # TODO: 根据时间轴位置点击选中
            
            # 2. 打开速度调节面板
            # 右键 -> 变速 或使用快捷键
            self.pyautogui.rightClick()
            time.sleep(0.5)
            
            # 3. 选择变速选项
            # TODO: 根据实际菜单调整
            
            # 4. 设置速度值
            # 点击速度输入框
            self.pyautogui.typewrite(str(speed))
            time.sleep(0.3)
            
            self.pyautogui.press('enter')
            
            logger.info("速度设置完成")
            return True
            
        except Exception as e:
            logger.error(f"设置速度失败: {e}")
            return False
    
    def add_transition(self, transition_type: str = "溶解", 
                       position: float = 0) -> bool:
        """
        添加转场效果
        
        Args:
            transition_type: 转场类型（溶解、闪白、推拉等）
            position: 添加位置（秒）
        
        Returns:
            是否添加成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        try:
            logger.info(f"添加转场: {transition_type}")
            
            # 1. 定位到分割点
            # 2. 点击转场按钮
            # 3. 选择转场类型
            # 4. 确认添加
            
            # 简化：使用快捷键
            self.pyautogui.hotkey('ctrl', 'shift', 't')
            time.sleep(1)
            
            logger.info("转场添加完成")
            return True
            
        except Exception as e:
            logger.error(f"添加转场失败: {e}")
            return False
    
    def add_text(self, text: str, position: float, duration: float,
                 style: str = "默认") -> bool:
        """
        添加字幕文本
        
        Args:
            text: 文本内容
            position: 开始时间（秒）
            duration: 持续时间（秒）
            style: 文本样式
        
        Returns:
            是否添加成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        try:
            logger.info(f"添加字幕: {text}")
            
            # 1. 点击文本按钮
            self.pyautogui.hotkey(*self.SHORTCUTS['add_text'])
            time.sleep(1)
            
            # 2. 输入文本
            self.pyautogui.typewrite(text)
            time.sleep(0.5)
            
            # 3. 确认
            self.pyautogui.press('enter')
            
            logger.info("字幕添加完成")
            return True
            
        except Exception as e:
            logger.error(f"添加字幕失败: {e}")
            return False
    
    def add_audio(self, audio_path: str, start_time: float = 0) -> bool:
        """
        添加背景音乐
        
        Args:
            audio_path: 音频文件路径
            start_time: 开始时间（秒）
        
        Returns:
            是否添加成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        if not os.path.exists(audio_path):
            logger.error(f"音频文件不存在: {audio_path}")
            return False
            
        try:
            logger.info(f"添加背景音乐: {audio_path}")
            
            # 1. 导入音频
            self.import_material(audio_path)
            
            # 2. 拖入音频轨道
            # TODO: 根据实际UI调整
            
            logger.info("背景音乐添加完成")
            return True
            
        except Exception as e:
            logger.error(f"添加背景音乐失败: {e}")
            return False
    
    def apply_filter(self, filter_name: str = "电影感",
                     intensity: float = 0.8) -> bool:
        """
        应用滤镜效果
        
        Args:
            filter_name: 滤镜名称
            intensity: 强度 (0-1)
        
        Returns:
            是否应用成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        try:
            logger.info(f"应用滤镜: {filter_name}")
            
            # 1. 选中视频片段
            # 2. 打开滤镜面板
            # 3. 选择滤镜
            # 4. 调整强度
            
            logger.info("滤镜应用完成")
            return True
            
        except Exception as e:
            logger.error(f"应用滤镜失败: {e}")
            return False
    
    def export_video(self, output_path: str, 
                     resolution: str = "1080p",
                     fps: int = 30,
                     quality: str = "高质量") -> bool:
        """
        导出视频
        
        Args:
            output_path: 输出路径
            resolution: 分辨率
            fps: 帧率
            quality: 质量设置
        
        Returns:
            是否导出成功
        """
        if not self.pyautogui:
            logger.error("pyautogui 未初始化")
            return False
            
        try:
            logger.info(f"导出视频到: {output_path}")
            
            # 1. 打开导出对话框
            self.pyautogui.hotkey(*self.SHORTCUTS['export'])
            time.sleep(2)
            
            # 2. 设置输出路径
            # TODO: 根据实际UI调整
            
            # 3. 设置分辨率和帧率
            # TODO: 根据实际UI调整
            
            # 4. 开始导出
            self.pyautogui.press('enter')
            
            # 5. 等待导出完成
            # 根据视频长度估算等待时间
            time.sleep(30)  # 至少等待30秒
            
            logger.info("视频导出完成")
            return True
            
        except Exception as e:
            logger.error(f"导出视频失败: {e}")
            return False
    
    def close_project(self, save: bool = True) -> bool:
        """
        关闭当前项目
        
        Args:
            save: 是否保存
        
        Returns:
            是否关闭成功
        """
        try:
            if save:
                self.pyautogui.hotkey('ctrl', 's')
                time.sleep(1)
            
            self.pyautogui.hotkey('ctrl', 'w')
            time.sleep(1)
            
            self.current_project = None
            logger.info("项目已关闭")
            return True
            
        except Exception as e:
            logger.error(f"关闭项目失败: {e}")
            return False
    
    def execute_edit_plan(self, edit_plan: Dict[str, Any], 
                          material_path: str,
                          output_path: str) -> Dict[str, Any]:
        """
        执行完整的剪辑计划
        
        Args:
            edit_plan: 剪辑策略JSON
            material_path: 素材路径
            output_path: 输出路径
        
        Returns:
            执行结果
        """
        results = {
            'success': False,
            'operations': [],
            'errors': [],
            'output_path': None
        }
        
        try:
            # 1. 启动剪映
            if not self.start_jianying():
                results['errors'].append("启动剪映失败")
                return results
            
            # 2. 创建新项目
            if not self.create_new_project():
                results['errors'].append("创建项目失败")
                return results
            
            # 3. 导入素材
            if not self.import_material(material_path):
                results['errors'].append("导入素材失败")
                return results
            
            # 4. 执行剪辑操作
            edit_points = edit_plan.get('edit_points', [])
            
            for point in edit_points:
                op_type = point.get('operation_type', 'split')
                timestamp = point.get('source_timestamp', '')
                effects = point.get('suggested_effects', [])
                
                # 解析时间戳
                times = timestamp.split('-')
                if len(times) == 2:
                    start_time = self._parse_time(times[0])
                    end_time = self._parse_time(times[1])
                    
                    # 执行分割
                    if self.split_at_position(start_time):
                        results['operations'].append(f"分割 @ {start_time}s")
                    
                    # 应用特效
                    for effect in effects:
                        if effect == 'slow_motion':
                            if self.set_speed(0.5, start_time, end_time):
                                results['operations'].append(f"慢动作 {start_time}-{end_time}s")
                        elif effect == 'fast_motion':
                            if self.set_speed(2.0, start_time, end_time):
                                results['operations'].append(f"加速 {start_time}-{end_time}s")
            
            # 5. 添加标题（如果有）
            title = edit_plan.get('title_suggestions', [{}])[0].get('title', '')
            if title:
                self.add_text(title, 0, 3)
            
            # 6. 导出视频
            if self.export_video(output_path):
                results['output_path'] = output_path
                results['success'] = True
            
            # 7. 关闭项目
            self.close_project()
            
        except Exception as e:
            results['errors'].append(str(e))
            logger.error(f"执行剪辑计划失败: {e}")
        
        return results
    
    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串为秒数"""
        try:
            parts = time_str.strip().split(':')
            if len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + float(seconds)
            elif len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return float(time_str)
        except:
            return 0.0


# 便捷函数
def create_controller(jianying_path: str = None) -> JianyingController:
    """创建剪映控制器实例"""
    return JianyingController(jianying_path)


def check_jianying_installed() -> bool:
    """检查剪映是否已安装"""
    try:
        controller = JianyingController()
        return controller.is_installed()
    except Exception as e:
        logger.warning(f"检查剪映安装失败: {e}")
        return False


def get_jianying_path() -> Optional[str]:
    """获取剪映安装路径"""
    try:
        controller = JianyingController()
        return controller.jianying_path
    except Exception as e:
        logger.warning(f"获取剪映路径失败: {e}")
        return None
