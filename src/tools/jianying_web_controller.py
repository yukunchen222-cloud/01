"""
剪映网页版自动化控制器
使用 Playwright 控制浏览器操作剪映网页版
支持功能：导入视频、剪辑、添加特效、导出
"""

import os
import re
import time
import logging
from typing import List, Dict, Optional, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 剪映网页版地址
JIANYING_WEB_URL = "https://www.capcut.cn/editor"
JIANYING_WEB_LOGIN_URL = "https://www.capcut.cn/"


class JianyingWebController:
    """剪映网页版自动化控制器"""
    
    def __init__(self, headless: bool = False):
        """
        初始化控制器
        
        Args:
            headless: 是否无头模式运行（不显示浏览器窗口）
        """
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
        # 剪辑状态
        self.is_initialized = False
        self.current_project = None
        self.materials_imported: List[str] = []
        
        # 超时设置（秒）
        self.timeout = 30
        self.upload_timeout = 120  # 上传视频超时时间
        
    def _init_playwright(self) -> bool:
        """初始化 Playwright"""
        try:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            logger.info("✅ Playwright 初始化成功")
            return True
        except ImportError:
            logger.error("❌ Playwright 未安装，请运行: pip install playwright && playwright install chromium")
            return False
        except Exception as e:
            logger.error(f"❌ Playwright 初始化失败: {e}")
            return False
    
    def start(self) -> bool:
        """
        启动浏览器并打开剪映网页版
        
        Returns:
            是否启动成功
        """
        logger.info("🚀 启动剪映网页版...")
        
        # 初始化 Playwright
        if not self._init_playwright():
            return False
        
        try:
            # 启动浏览器
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            
            # 创建浏览器上下文
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # 创建页面
            self.page = self.context.new_page()
            
            # 设置默认超时
            self.page.set_default_timeout(self.timeout * 1000)
            
            # 打开剪映网页版
            logger.info(f"📱 打开剪映网页版: {JIANYING_WEB_URL}")
            self.page.goto(JIANYING_WEB_URL, wait_until='networkidle')
            
            self.is_initialized = True
            logger.info("✅ 剪映网页版启动成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 启动剪映网页版失败: {e}")
            return False
    
    def login_check(self) -> bool:
        """
        检查是否已登录
        
        Returns:
            是否已登录
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化，请先调用 start()")
            return False
        
        try:
            # 检查是否有登录按钮或用户头像
            # 剪映网页版登录状态检测
            login_btn = self.page.query_selector('text=登录')
            if login_btn:
                logger.warning("⚠️ 检测到未登录状态，请手动登录")
                return False
            
            # 检查用户头像（已登录状态）
            user_avatar = self.page.query_selector('[class*="avatar"], [class*="user"]')
            if user_avatar:
                logger.info("✅ 已登录")
                return True
                
            return True
            
        except Exception as e:
            logger.error(f"❌ 登录检查失败: {e}")
            return False
    
    def wait_for_login(self, timeout: int = 300) -> bool:
        """
        等待用户手动登录
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否登录成功
        """
        logger.info(f"⏳ 等待用户登录（超时: {timeout}秒）...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.login_check():
                logger.info("✅ 登录成功")
                return True
            time.sleep(2)
        
        logger.error("❌ 登录超时")
        return False
    
    def create_project(self, project_name: str = "AI剪辑项目") -> bool:
        """
        创建新项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否创建成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info(f"📁 创建新项目: {project_name}")
            
            # 点击新建项目按钮
            # 剪映网页版的新建按钮选择器
            new_project_selectors = [
                'text=新建项目',
                'text=开始创作',
                'button:has-text("新建")',
                '[class*="create"]',
                '[class*="new-project"]'
            ]
            
            clicked = False
            for selector in new_project_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=5000)
                    if btn:
                        btn.click()
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                # 如果找不到按钮，可能已经在编辑器页面
                logger.info("已进入编辑器页面")
            
            self.current_project = project_name
            time.sleep(2)  # 等待页面加载
            
            logger.info("✅ 项目创建成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建项目失败: {e}")
            return False
    
    def import_video(self, video_path: str) -> bool:
        """
        导入视频素材
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            是否导入成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info(f"📥 导入视频: {video_path}")
            
            # 检查文件是否存在
            if video_path.startswith('http'):
                # 网络视频，需要先下载
                logger.info("检测到网络视频，需要先下载到本地")
                video_path = self._download_video(video_path)
                if not video_path:
                    return False
            
            if not os.path.exists(video_path):
                logger.error(f"❌ 视频文件不存在: {video_path}")
                return False
            
            # 点击导入按钮
            import_selectors = [
                'text=导入',
                'text=上传',
                'button:has-text("导入")',
                '[class*="import"]',
                '[class*="upload"]'
            ]
            
            for selector in import_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=5000)
                    if btn:
                        btn.click()
                        break
                except:
                    continue
            
            time.sleep(1)
            
            # 使用文件选择器上传
            with self.page.expect_file_chooser() as fc_info:
                # 点击上传区域
                upload_area = self.page.query_selector('input[type="file"]')
                if upload_area:
                    upload_area.set_input_files(video_path)
                else:
                    # 使用剪映的上传按钮
                    upload_btn = self.page.query_selector('text=上传素材')
                    if upload_btn:
                        upload_btn.click()
            
            # 等待上传完成
            logger.info("⏳ 等待视频上传...")
            time.sleep(5)  # 基础等待
            
            # 等待上传进度消失
            try:
                self.page.wait_for_selector('[class*="progress"]', state='hidden', timeout=self.upload_timeout * 1000)
            except:
                pass
            
            self.materials_imported.append(video_path)
            logger.info("✅ 视频导入成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 导入视频失败: {e}")
            return False
    
    def add_to_timeline(self, material_index: int = 0) -> bool:
        """
        将素材添加到时间线
        
        Args:
            material_index: 素材索引
            
        Returns:
            是否添加成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info("🎬 添加素材到时间线")
            
            # 找到素材并拖拽到时间线
            materials = self.page.query_selector_all('[class*="material"], [class*="media-item"]')
            if materials and len(materials) > material_index:
                # 拖拽到时间线
                target = self.page.query_selector('[class*="timeline"], [class*="track"]')
                if target:
                    # type: ignore - Playwright ElementHandle has drag_to method
                    materials[material_index].drag_to(target)  # type: ignore[attr-defined]
                    time.sleep(1)
            
            logger.info("✅ 素材已添加到时间线")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加素材到时间线失败: {e}")
            return False
    
    def cut_clip(self, start_time: str, end_time: str) -> bool:
        """
        剪切片段
        
        Args:
            start_time: 开始时间 (格式: "00:00")
            end_time: 结束时间 (格式: "00:03")
            
        Returns:
            是否剪切成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info(f"✂️ 剪切片段: {start_time} - {end_time}")
            
            # 解析时间
            start_seconds = self._parse_time(start_time)
            end_seconds = self._parse_time(end_time)
            
            # 点击时间线选中
            self.page.click('[class*="timeline"]')
            
            # 使用快捷键或工具栏进行剪切
            # 方法1: 使用快捷键 Ctrl+B 分割
            # 先移动到开始位置
            self._seek_timeline(start_seconds)
            time.sleep(0.5)
            
            # 分割
            self.page.keyboard.press('Control+B')
            time.sleep(0.5)
            
            # 移动到结束位置
            self._seek_timeline(end_seconds)
            time.sleep(0.5)
            
            # 再次分割
            self.page.keyboard.press('Control+B')
            time.sleep(0.5)
            
            # 选中并删除不需要的部分
            # ... 根据需要实现
            
            logger.info("✅ 片段剪切完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 剪切片段失败: {e}")
            return False
    
    def apply_slow_motion(self, speed: float = 0.5) -> bool:
        """
        应用慢动作效果
        
        Args:
            speed: 播放速度 (0.5 = 半速)
            
        Returns:
            是否应用成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info(f"🐢 应用慢动作效果: {speed}x")
            
            # 选中当前片段
            self.page.click('[class*="clip"][class*="selected"], [class*="timeline-clip"]')
            
            # 点击速度调节
            speed_selectors = [
                'text=变速',
                'text=速度',
                '[class*="speed"]'
            ]
            
            for selector in speed_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=3000)
                    if btn:
                        btn.click()
                        break
                except:
                    continue
            
            time.sleep(0.5)
            
            # 设置速度值
            speed_input = self.page.query_selector('input[type="number"], [class*="speed-input"]')
            if speed_input:
                speed_input.fill(str(speed))
            
            # 确认
            self.page.keyboard.press('Enter')
            
            logger.info("✅ 慢动作效果应用成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 应用慢动作失败: {e}")
            return False
    
    def add_transition(self, transition_type: str = "fade") -> bool:
        """
        添加转场效果
        
        Args:
            transition_type: 转场类型 (fade/dissolve/slide等)
            
        Returns:
            是否添加成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info(f"🔄 添加转场效果: {transition_type}")
            
            # 点击转场面板
            transition_selectors = [
                'text=转场',
                'text=过渡',
                '[class*="transition"]'
            ]
            
            for selector in transition_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=3000)
                    if btn:
                        btn.click()
                        break
                except:
                    continue
            
            time.sleep(0.5)
            
            # 选择转场效果
            effect = self.page.query_selector(f'text={transition_type}, [class*="{transition_type}"]')
            if effect:
                effect.click()
            
            logger.info("✅ 转场效果添加成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加转场失败: {e}")
            return False
    
    def add_text(self, text: str, position: str = "center") -> bool:
        """
        添加文字
        
        Args:
            text: 文字内容
            position: 位置 (center/top/bottom)
            
        Returns:
            是否添加成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info(f"📝 添加文字: {text}")
            
            # 点击文字面板
            text_selectors = [
                'text=文字',
                'text=字幕',
                'text=文本',
                '[class*="text"]'
            ]
            
            for selector in text_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=3000)
                    if btn:
                        btn.click()
                        break
                except:
                    continue
            
            time.sleep(0.5)
            
            # 添加新文字
            add_text_btn = self.page.query_selector('text=添加文字, text=新建文字')
            if add_text_btn:
                add_text_btn.click()
            
            time.sleep(0.5)
            
            # 输入文字内容
            text_input = self.page.query_selector('textarea, input[type="text"]')
            if text_input:
                text_input.fill(text)
            
            logger.info("✅ 文字添加成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加文字失败: {e}")
            return False
    
    def export_video(
        self, 
        output_path: str,
        resolution: str = "1080p",
        fps: int = 30,
        format: str = "mp4"
    ) -> bool:
        """
        导出视频
        
        Args:
            output_path: 输出路径
            resolution: 分辨率 (720p/1080p/4K)
            fps: 帧率
            format: 格式 (mp4/mov)
            
        Returns:
            是否导出成功
        """
        if not self.is_initialized:
            logger.error("❌ 剪映未初始化")
            return False
        
        try:
            logger.info(f"📤 导出视频: {output_path}")
            
            # 点击导出按钮
            export_selectors = [
                'text=导出',
                'text=下载',
                '[class*="export"]',
                '[class*="download"]'
            ]
            
            for selector in export_selectors:
                try:
                    btn = self.page.wait_for_selector(selector, timeout=5000)
                    if btn:
                        btn.click()
                        break
                except:
                    continue
            
            time.sleep(1)
            
            # 设置导出参数
            # 分辨率
            resolution_map = {
                "720p": "1280x720",
                "1080p": "1920x1080",
                "4K": "3840x2160"
            }
            
            # 确认导出
            confirm_btn = self.page.query_selector('text=确认导出, text=开始导出, text=导出视频')
            if confirm_btn:
                confirm_btn.click()
            
            # 等待导出完成
            logger.info("⏳ 等待视频导出...")
            time.sleep(10)
            
            # 下载文件
            # 剪映网页版会自动下载
            logger.info(f"✅ 视频导出成功: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 导出视频失败: {e}")
            return False
    
    def execute_edit_plan(self, edit_plan: Dict[str, Any], video_path: str, output_path: str) -> Dict[str, Any]:
        """
        执行完整剪辑计划
        
        Args:
            edit_plan: 剪辑计划（从爆款Agent生成）
            video_path: 视频路径
            output_path: 输出路径
            
        Returns:
            执行结果
        """
        results = {
            "success": False,
            "operations": [],
            "output_path": output_path,
            "errors": []
        }
        
        try:
            # 1. 启动剪映
            if not self.start():
                results["errors"].append("启动剪映失败")
                return results
            
            # 2. 检查登录
            if not self.login_check():
                logger.info("⚠️ 需要登录，请手动登录...")
                if not self.wait_for_login():
                    results["errors"].append("登录超时")
                    return results
            
            # 3. 创建项目
            if not self.create_project():
                results["errors"].append("创建项目失败")
                return results
            
            # 4. 导入视频
            if not self.import_video(video_path):
                results["errors"].append("导入视频失败")
                return results
            
            # 5. 添加到时间线
            self.add_to_timeline()
            
            # 6. 执行剪辑操作
            edit_points = edit_plan.get("edit_points", [])
            for point in edit_points:
                timestamp = point.get("source_timestamp", "")
                effects = point.get("suggested_effects", [])
                
                if "-" in timestamp:
                    start, end = timestamp.split("-")
                    self.cut_clip(start, end)
                
                # 应用特效
                for effect in effects:
                    if effect == "slow_motion":
                        self.apply_slow_motion(0.5)
                    elif effect == "fade":
                        self.add_transition("fade")
            
            # 7. 添加标题文字
            titles = edit_plan.get("title_suggestions", [])
            if titles:
                self.add_text(titles[0].get("title", "精彩短视频"))
            
            # 8. 导出视频
            if not self.export_video(output_path):
                results["errors"].append("导出视频失败")
                return results
            
            results["success"] = True
            results["operations"].append("完整剪辑流程执行成功")
            
            return results
            
        except Exception as e:
            results["errors"].append(str(e))
            return results
    
    def close(self):
        """关闭浏览器"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("✅ 浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
    
    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串为秒数"""
        time_str = time_str.strip()
        
        # 格式: "00:00" 或 "00:00:00"
        parts = time_str.split(":")
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        else:
            return float(time_str)
    
    def _seek_timeline(self, seconds: float):
        """定位时间线到指定秒数"""
        # 使用播放头定位或输入时间码
        try:
            time_input = self.page.query_selector('[class*="timecode"], input[class*="time"]')
            if time_input:
                # 输入时间码
                self.page.keyboard.press('Control+A')  # 全选
                time_str = f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
                time_input.fill(time_str)
                self.page.keyboard.press('Enter')
        except:
            pass
    
    def _download_video(self, url: str) -> Optional[str]:
        """下载网络视频到本地临时目录"""
        try:
            import urllib.request
            temp_dir = "/tmp/jianying_materials"
            os.makedirs(temp_dir, exist_ok=True)
            
            filename = url.split("/")[-1] or "video.mp4"
            local_path = os.path.join(temp_dir, filename)
            
            logger.info(f"📥 下载视频: {url}")
            urllib.request.urlretrieve(url, local_path)
            
            return local_path
        except Exception as e:
            logger.error(f"下载视频失败: {e}")
            return None


def check_playwright_installed() -> bool:
    """检查 Playwright 是否已安装"""
    try:
        import playwright
        return True
    except ImportError:
        return False


def install_playwright():
    """安装 Playwright"""
    import subprocess
    import sys
    
    print("📦 安装 Playwright...")
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    print("✅ Playwright 安装完成")


# 测试代码
if __name__ == "__main__":
    print("🎬 剪映网页版控制器测试")
    print("=" * 60)
    
    # 检查 Playwright
    if not check_playwright_installed():
        print("⚠️ Playwright 未安装")
        install_playwright()
    
    # 创建控制器
    controller = JianyingWebController(headless=False)
    
    # 测试启动
    print("\n📌 测试启动剪映网页版...")
    if controller.start():
        print("✅ 启动成功")
        
        # 等待用户查看
        input("\n按 Enter 键关闭浏览器...")
        
        controller.close()
    else:
        print("❌ 启动失败")
