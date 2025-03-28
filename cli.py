import os
import time
import requests
import json
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse, parse_qs
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s]%(message)s",
)
logger = logging.getLogger("iClass签到")


class SSOLogin:
    """SSO登录"""
    BASE_URL = 'https://iclass.buaa.edu.cn:8346/'
    LOGIN_URL = 'https://sso.buaa.edu.cn/login?service=' + quote(BASE_URL, 'utf-8')
    
    def __init__(self):
        """初始化签到系统"""
        self.session = requests.Session()
        self.session.proxies = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        self.username = ""
        self.password = ""
        self.user_info = None
        self.user_id = None

    def load_credentials(self):
        """从配置文件加载或用户输入获取凭据"""
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.username = data.get("username", "").strip()
                    self.password = data.get("password", "").strip()
                    if self.username and self.password:
                        logger.info("已成功从配置文件加载凭据")
                        return True
            except Exception as e:
                logger.error(f"读取配置文件时出错: {e}")
        
        # 如果没有配置文件或配置无效，则要求用户输入
        logger.info("请输入登录凭据")
        self.username = input("请输入学号: ")
        self.password = input("请输入密码: ")
        
        # 保存凭据到配置文件
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({"username": self.username, "password": self.password}, 
                          f, indent=4, ensure_ascii=False)
            logger.info("凭据已保存到配置文件")
        except Exception as e:
            logger.error(f"写入配置文件时出错: {e}")
        
        return bool(self.username and self.password)

    def get_login_token(self):
        """获取SSO登录所需的token"""
        logger.info("正在获取登录令牌...")
        try:
            r = self.session.get(self.LOGIN_URL)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, 'html.parser')
            token = soup.find('input', {'name': 'execution'})['value']
            token_display = f"{token[:3]}...{token[-3:]}"
            logger.info(f"获取到登录令牌: {token_display}")
            return token
        except Exception as e:
            logger.error(f"获取登录令牌失败: {e}")
            raise RuntimeError("获取登录令牌失败") from e

    def login(self):
        """登录SSO系统"""
        logger.info("正在尝试登录北航SSO系统...")
        try:
            # 验证凭据是否存在
            if not self.username or not self.password:
                logger.error("登录失败：用户名或密码为空")
                return False
                
            # 发送登录请求
            formdata = {
                'username': self.username,
                'password': self.password,
                'submit': '登录',
                'type': 'username_password',
                'execution': self.get_login_token(),
                '_eventId': 'submit'
            }
            r = self.session.post(self.LOGIN_URL, data=formdata, allow_redirects=True)
            r.raise_for_status()
            
            # 检查登录结果
            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.find_all('div', class_='error_txt'):
                logger.info("SSO登录成功")
                return True
            else:
                logger.error("登录失败，可能是用户名或密码错误")
                self.delete_config_file()
                return False
        except Exception as e:
            logger.error(f"登录过程中发生错误: {e}")
            self.delete_config_file()
            return False

    def delete_config_file(self):
        """删除配置文件"""
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                os.remove(config_file)
                logger.info("登录失败，已删除配置文件")
            except Exception as e:
                logger.error(f"删除配置文件时出错: {e}")
        
class IClassSignIn:
    def __init__(self):
        """初始化签到系统"""
        self.sso_login = SSOLogin()
        self.session = self.sso_login.session
        self.headers = self.sso_login.headers
        self.user_id = None

    def get_user_info(self):
        """获取用户信息"""
        logger.info("正在获取用户信息...")
        try:
            # 获取当前会话的URL
            current_url = self.session.get(self.sso_login.BASE_URL).url
            parsed_url = urlparse(current_url)
            query_params = parse_qs(parsed_url.query)
            login_name = query_params.get('loginName', [None])[0]
            
            if not login_name:
                logger.error("无法从URL中提取应用令牌")
                raise RuntimeError("获取应用令牌失败")
                
            login_name_display = f"{login_name[:3]}...{login_name[-3:]}"
            logger.info(f"获取到应用令牌: {login_name_display}")
            
            # 构造GET请求的URL
            user_info_url = (
                f"https://iclass.buaa.edu.cn:8346/app/user/login.action?"
                f"phone={login_name}&password=&verificationType=2&"
                f"verificationUrl=&userLevel=1"
            )
            response = self.session.get(user_info_url)
            response.raise_for_status()
            response_json = response.json()
            result = response_json.get('result', None)
            
            if result:
                self.user_info = result
                self.user_id = result.get('id')
                logger.info("成功获取用户信息")
                real_name = result.get('realName', '未知')
                user_uuid = result.get('userUUID', '未知')
                logger.info(f"姓名: {real_name}")
                logger.info(f"学号: {user_uuid}")
                return result
            else:
                logger.error("响应中未包含用户信息")
                raise RuntimeError("获取用户信息失败")
        except Exception as e:
            logger.error(f"获取用户信息时发生错误: {e}")
            raise RuntimeError("获取用户信息失败") from e

    def get_term_code(self):
        """获取当前学期代码"""
        logger.info("正在获取学期信息...")
        try:
            url = f"https://iclass.buaa.edu.cn:8346/app/course/get_base_school_year.action?userId={self.user_id}&type=2"
            r = self.session.get(url, headers=self.headers)
            r.raise_for_status()
            term_data = r.json()
            
            # 寻找当前学期
            term_code = -1
            term_name = ""
            for data in term_data.get("result", []):
                if data.get("yearStatus") == "1":
                    term_code = data.get("code")
                    term_name = data.get("name")
                    break
                    
            if term_code == -1:
                logger.error("未找到当前学期信息")
                raise RuntimeError("未找到当前学期")
            else:
                logger.info(f"当前学期：{term_name}")
                
            return term_code
        except Exception as e:
            logger.error(f"获取学期代码失败: {e}")
            raise RuntimeError("获取学期信息失败") from e

    def get_course_list(self, term_code):
        """获取课程列表"""
        logger.info("正在获取课程列表...")
        try:
            url = (f"https://iclass.buaa.edu.cn:8346/app/choosecourse/get_myall_course.action?"
                  f"user_type=1&id={self.user_id}&xq_code={term_code}")
            r = self.session.get(url, headers=self.headers)
            r.raise_for_status()
            course_data = r.json()
            courses = course_data.get("result", [])
            
            if not courses:
                logger.error("未获取到任何课程信息")
                raise RuntimeError("未找到课程信息")
                
            return courses
        except Exception as e:
            logger.error(f"获取课程列表失败: {e}")
            raise RuntimeError("获取课程列表失败") from e

    def select_course(self, courses):
        """让用户选择要签到的课程"""
        logger.info("请选择需要签到的课程：")
        for idx, data in enumerate(courses, start=1):
            print(f"{idx}. {data.get('course_name')}")
            
        while True:
            try:
                choice = int(input("请输入课程序号: "))
                if 1 <= choice <= len(courses):
                    selected = courses[choice - 1]
                    logger.info(f"选择课程：{selected.get('course_name')}")
                    return selected.get("course_id")
                else:
                    logger.error(f"序号必须在1-{len(courses)}之间")
            except ValueError:
                logger.error("请输入有效的数字")

    def get_course_sched_id(self, course_id):
        """获取排课ID"""
        logger.info("正在获取排课信息...")
        try:
            url = f"https://iclass.buaa.edu.cn:8346/app/my/get_my_course_sign_detail.action?id={self.user_id}&courseId={course_id}"
            r = self.session.post(url, headers=self.headers)
            r.raise_for_status()
            course_data = r.json()
            
            # 检查课程状态
            course_status = course_data.get("STATUS")
            if course_status == "2":
                logger.error("课程目前未开始")
                raise RuntimeError("课程未开始")
            elif course_status == "1":
                logger.warning("未知课程状态，请联系开发者")
                raise RuntimeError("未知课程状态")
                
            # 获取排课信息
            result_list = course_data.get("result", [])
            if not result_list:
                logger.error("未获取到排课信息")
                raise RuntimeError("未找到排课信息")
            
            # 检查是否有正在进行的课程
            last_entry = result_list[-1]
            class_end_time_str = last_entry.get("classEndTime")
            class_end_time = datetime.strptime(class_end_time_str, "%Y-%m-%d %H:%M:%S")
            now_time = datetime.now()
            
            if class_end_time >= now_time:
                # 当前正在上课
                return last_entry.get("courseSchedId")
            else:
                # 询问是否补签
                return self.handle_makeup_sign(result_list)
                
        except Exception as e:
            logger.error(f"获取排课ID时发生错误: {e}")
            raise RuntimeError("获取排课信息失败") from e
            
    def handle_makeup_sign(self, result_list):
        """处理补签逻辑"""
        make_up_sign = input("您是否想补签以前的课？(y/n): ")
        if make_up_sign.lower() != 'y':
            logger.info("用户选择不补签")
            raise RuntimeError("没有正在进行的课程")
            
        # 获取未签到的课程列表
        unsign_list = [data for data in result_list if data.get("signStatus") == "0"]
        if not unsign_list:
            logger.warning("没有未签到的课程")
            raise RuntimeError("没有可补签的课程")
            
        # 显示可补签课程
        logger.info("可补签的课程列表：")
        for idx, data in enumerate(unsign_list, start=1):
            begin = data.get("classBeginTime")
            end = data.get("classEndTime")
            print(f"{idx}. {begin} - {end}")
            
        # 用户选择补签课程
        while True:
            try:
                choice = int(input("请选择要补签的课程序号: "))
                if 1 <= choice <= len(unsign_list):
                    return unsign_list[choice - 1].get("courseSchedId")
                else:
                    logger.error(f"序号必须在1-{len(unsign_list)}之间")
            except ValueError:
                logger.error("请输入有效的数字")

    def perform_sign(self, course_sched_id):
        """执行签到操作"""
        logger.info("正在执行签到操作...")
        try:
            timestamp = int((time.time() + 5) * 1000)
            sign_url = (f"http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action?"
                       f"courseSchedId={course_sched_id}&timestamp={timestamp}")
            params = {"id": self.user_id}
            r = self.session.post(sign_url, data=params, headers=self.headers)
            r.raise_for_status()
            
            response_dict = r.json()
            if response_dict["STATUS"] == "0":
                logger.info("签到成功！")
                return True
            else:
                error_code = response_dict.get("ERRCODE", "未知")
                error_msg = response_dict.get("ERRMSG", "未知错误")
                logger.error(f"签到失败：错误码 {error_code}, 错误信息: {error_msg}")
                return False
        except Exception as e:
            logger.error(f"签到操作发生错误: {e}")
            return False

    def run(self):
        """运行签到流程"""
        try:
            logger.info("签到系统启动")
            
            # 1. 加载用户凭据
            if not self.sso_login.load_credentials():
                logger.error("获取用户凭据失败")
                return False
                
            # 2. 登录SSO系统
            if not self.sso_login.login():
                logger.error("登录失败，请检查凭据或网络连接")
                return False
                
            # 3. 获取用户信息
            self.get_user_info()
            
            # 4. 签到流程
            term_code = self.get_term_code()
            courses = self.get_course_list(term_code)
            course_id = self.select_course(courses)
            course_sched_id = self.get_course_sched_id(course_id)
            
            # 5. 执行签到
            return self.perform_sign(course_sched_id)
            
        except Exception as e:
            logger.error(f"签到过程中发生错误: {e}")
            return False


def main():
    """主函数"""
    try:
        sign_system = IClassSignIn()
        success = sign_system.run()
        
        if success:
            logger.info("签到流程成功完成")
        else:
            logger.error("签到流程未能完成")
            
    except KeyboardInterrupt:
        logger.info("用户中断了程序")
    except Exception as e:
        logger.critical(f"程序出现严重错误: {e}")
    finally:
        logger.info("程序结束运行,按回车键退出")
        input()
        

if __name__ == "__main__":
    main()