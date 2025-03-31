"""
Auto sign - 智慧教室自动签到应用程序
"""

from datetime import datetime
import os
import json
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import logging
from .login import SSOLogin
from .signin import IClassSignIn
from .logger import setup_logger


class GUIHandler(logging.Handler):
    """自定义日志处理器，将日志输出到 GUI 的状态框"""
    def __init__(self, status_box):
        super().__init__()
        self.status_box = status_box

    def emit(self, record):
        log_entry = self.format(record)
        self.status_box.value += log_entry + "\n"
        self.status_box.scroll_to_bottom()


class AutoSignApp(toga.App):
    """智慧教室自动签到应用程序"""
    
    def startup(self):
        """构建并显示 Toga 应用程序"""
        self.setup_logger()
        
        self.sso_login = SSOLogin()
        self.sign_in = IClassSignIn()

        self.course_map = {}
        self.unsign_list = []

        autofill_username, autofill_password = self.load_saved_credentials()
        
        main_box = self.create_main_ui(autofill_username, autofill_password)
        
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()
        
        self.logger.info("请在课程开始10分钟前连接校园网使用。")

    def setup_logger(self):
        """设置应用程序日志器"""
        self.logger = setup_logger("AutoSignApp")

    def load_saved_credentials(self):
        """从配置文件加载已保存的凭据"""
        autofill_username = ""
        autofill_password = ""
        
        if os.path.exists(self.sso_login.config_file):
            try:
                with open(self.sso_login.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    autofill_username = data.get("username", "").strip()
                    autofill_password = data.get("password", "").strip()
                    self.logger.info("成功从配置文件中加载凭据")
            except Exception as e:
                self.logger.error(f"读取凭据失败: {e}")
                
        return autofill_username, autofill_password

    def create_main_ui(self, autofill_username, autofill_password):
        """创建主界面 UI 组件"""
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        main_box.add(self.create_login_section(autofill_username, autofill_password))
        main_box.add(self.create_course_section())
        main_box.add(self.create_makeup_section())
        main_box.add(self.create_status_section())
        return main_box
    
    def create_login_section(self, username, password):
        """创建登录区域 UI"""
        login_box = toga.Box(style=Pack(direction=COLUMN))
        
        username_row = toga.Box(style=Pack(direction=ROW))
        username_row.add(toga.Label("学号:", style=Pack(width=100)))
        self.username_input = toga.TextInput(
            value=username, 
            placeholder="请输入学号",
            style=Pack(flex=1, padding=(0, 5))
        )
        username_row.add(self.username_input)
        login_box.add(username_row)

        password_row = toga.Box(style=Pack(direction=ROW))
        password_row.add(toga.Label("密码:", style=Pack(width=100)))
        self.password_input = toga.PasswordInput(
            value=password,
            placeholder="请输入密码",
            style=Pack(flex=1, padding=(0, 5))
        )
        password_row.add(self.password_input)
        login_box.add(password_row)
        
        login_button = toga.Button(
            "登录", 
            on_press=self.handle_login, 
            style=Pack(padding=5)
        )
        login_box.add(login_button)
        
        return login_box
        
    def create_course_section(self):
        """创建课程选择区域 UI"""
        course_box = toga.Box(style=Pack(direction=COLUMN))
        
        course_row = toga.Box(style=Pack(direction=ROW))
        course_row.add(toga.Label("课程:", style=Pack(width=100)))
        self.course_select = toga.Selection(
            items=[], 
            on_change=self.handle_course_change,
            style=Pack(flex=1, padding=(0, 5))
        )
        self.course_select.enabled = False
        course_row.add(self.course_select)
        course_box.add(course_row)
        
        self.signin_button = toga.Button(
            "签到", 
            on_press=self.handle_signin, 
            style=Pack(padding=5)
        )
        self.signin_button.enabled = False
        course_box.add(self.signin_button)
        
        return course_box
        
    def create_makeup_section(self):
        """创建补签区域 UI - 在启动时就完全显示"""
        self.makeup_box = toga.Box(style=Pack(direction=COLUMN, padding=5))

        separator = toga.Divider(style=Pack(padding=(10, 0)))
        self.makeup_box.add(separator)

        warning_label = toga.Label(
            "补签功能有破绽慎用", 
            style=Pack(color="red", font_size=8, padding_top=5, padding_bottom=5, alignment="center", width=300)
        )
        self.makeup_box.add(warning_label)

        label = toga.Label("请选择要补签的课程时间", style=Pack(padding_bottom=10))
        self.makeup_box.add(label)

        self.makeup_selection = toga.Selection(items=[], style=Pack(padding_bottom=10))
        self.makeup_selection.enabled = False
        self.makeup_box.add(self.makeup_selection)

        btn_box = toga.Box(style=Pack(direction=ROW, padding_top=10))
        
        self.makeup_ok_button = toga.Button(
            "确定", 
            on_press=self.confirm_makeup_sign, 
            style=Pack(padding_right=5)
        )
        
        self.makeup_cancel_button = toga.Button(
            "取消", 
            on_press=self.cancel_makeup_sign, 
            style=Pack(padding_left=5)
        )
        
        self.makeup_ok_button.enabled = False
        self.makeup_cancel_button.enabled = False
        
        btn_box.add(self.makeup_ok_button)
        btn_box.add(self.makeup_cancel_button)
        self.makeup_box.add(btn_box)
        
        return self.makeup_box

    def create_status_section(self):
        """创建状态显示区域 UI"""
        self.status_box = toga.MultilineTextInput(
            readonly=True, 
            style=Pack(flex=1, padding=10, height=200)
        )
        self.status_box.caret = False
        
        self.setup_gui_logger()
        
        return self.status_box
    
    def setup_gui_logger(self):
        """设置 GUI 日志处理器"""
        gui_handler = GUIHandler(self.status_box)
        gui_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[%(asctime)s][%(levelname)s] %(message)s", 
            datefmt="%H:%M:%S"
        )
        gui_handler.setFormatter(formatter)
        
        logging.getLogger().addHandler(gui_handler)
        logging.getLogger().setLevel(logging.INFO)

    def handle_login(self, widget):
        """处理登录逻辑"""
        username = self.username_input.value.strip()
        password = self.password_input.value.strip()

        if not username or not password:
            self.logger.error("用户名或密码不能为空")
            return

        self.sso_login.username = username
        self.sso_login.password = password

        self.logger.info("正在登录...")
        if self.sso_login.login():
            self.logger.info("登录成功！")
            self.signin_button.enabled = True
            self.course_select.enabled = True

            try:
                self.initialize_signin_session()
                self.load_courses()
            except Exception as e:
                self.logger.error(f"获取课程信息失败: {e}")
        else:
            self.logger.error("登录失败，请检查报错信息，确认用户名和密码正确。")
            
    def initialize_signin_session(self):
        """初始化签到会话"""
        self.sign_in.sso_login = self.sso_login
        self.sign_in.session = self.sso_login.session
        self.sign_in.headers = self.sso_login.headers

        self.sign_in.get_user_info()
            
    def load_courses(self):
        """加载课程列表"""
        term_code = self.sign_in.get_term_code()
        courses = self.sign_in.get_course_list(term_code)

        self.course_select.items = [course.get("course_name") for course in courses]
        self.courses = courses

    def handle_course_change(self, widget):
        """处理课程选择变更"""
        if self.course_select.value:
            self.update_makeup_options()

    def handle_signin(self, widget):
        """处理签到逻辑"""
        selected_course_name = self.course_select.value
        if not selected_course_name:
            self.logger.error("请选择课程")
            return

        self.logger.info("正在签到...")
        try:
            selected_course = next(
                course for course in self.courses 
                if course.get("course_name") == selected_course_name
            )
            course_id = selected_course.get("course_id")

            course_sched_id = self.sign_in.get_course_sched_id(course_id)
            if course_sched_id:
                if self.sign_in.perform_sign(course_sched_id):
                    self.logger.info("签到成功！")
                else:
                    self.logger.error("签到失败！")
            else:
                self.logger.info("没有正在进行的课程，尝试查找今天的课程排课...")
                today_schedules = self.sign_in.get_course_sched_by_date()
                now = datetime.now()

                course_schedules = [
                    schedule for schedule in today_schedules
                    if schedule.get("courseId") == course_id
                ]
                
                if not course_schedules:
                    self.logger.warning("今天没有该课程的排课安排")
                    self.logger.warning("没有正在进行的课程，请选择要补签的课程时间")
                    self.update_makeup_options()
                    return
                    
                signed = False
                for schedule in course_schedules:
                    begin_time_str = schedule.get("classBeginTime")
                    if not begin_time_str:
                        continue
                        
                    begin_time = datetime.strptime(begin_time_str, "%Y-%m-%d %H:%M:%S")
                    time_diff = (begin_time - now).total_seconds() / 60
                    
                    if 0 <= time_diff <= 10:
                        course_sched_id = schedule.get("id")
                        self.logger.info(f"发现即将开始的课程，距离开课还有 {time_diff:.1f} 分钟")
                        
                        if self.sign_in.perform_sign(course_sched_id):
                            self.logger.info("提前签到成功！")
                            signed = True
                        else:
                            self.logger.error("提前签到失败！")
                        break
                
                if not signed:
                    self.logger.warning("没有找到可以提前签到的课程或尚未到签到时间（课前10分钟内）")
                    self.logger.warning("请选择要补签的课程时间")
                    self.update_makeup_options()
        except Exception as e:
            self.logger.error(f"签到失败: {e}")

    def update_makeup_options(self):
        """更新补签选择区域的选项"""
        try:
            unsign_list = [data for data in self.sign_in.result_list if data.get("signStatus") == "0"]
            if not unsign_list:
                self.logger.warning("没有可补签的课程")
                self.makeup_selection.items = []
                self.makeup_selection.enabled = False
                self.makeup_ok_button.enabled = False
                self.makeup_cancel_button.enabled = False
                return

            items = []
            self.course_map = {}
            
            for data in unsign_list:
                begin = data.get("classBeginTime")
                end = data.get("classEndTime")
                item_text = f"{begin} - {end}"
                items.append(item_text)
                self.course_map[item_text] = data.get("courseSchedId")
                
            self.makeup_selection.items = items
            self.makeup_selection.enabled = True
            
            self.makeup_ok_button.enabled = True
            self.makeup_cancel_button.enabled = True
            
            self.unsign_list = unsign_list
            
            self.logger.info("已更新可补签课程列表")
                
        except Exception as e:
            self.logger.error(f"更新补签选项失败: {e}")

    def confirm_makeup_sign(self, widget):
        """用户点击确定后进行补签操作"""
        selected_value = self.makeup_selection.value
        if not selected_value:
            self.logger.error("未选择任何课程")
            return

        try:
            course_sched_id = self.course_map.get(selected_value)
            if not course_sched_id:
                self.logger.error("选择的课程时间不在列表中")
                return
                
            if self.sign_in.perform_sign(course_sched_id):
                self.logger.info("补签成功！")
                self.update_makeup_options()
            else:
                self.logger.error("补签失败！")
        except Exception as e:
            self.logger.error(f"补签失败: {e}")

    def cancel_makeup_sign(self, widget):
        """用户取消补签"""
        self.logger.info("用户取消补签")
    
        self.makeup_selection.items = []
        self.makeup_selection.enabled = False
    
        self.makeup_ok_button.enabled = False
        self.makeup_cancel_button.enabled = False


def main():
    """应用入口函数"""
    return AutoSignApp()
