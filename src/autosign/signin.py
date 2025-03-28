import time
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from .login import SSOLogin
from .logger import setup_logger

logger = setup_logger("IClassSignIn")

class IClassSignIn:
    def __init__(self):
        """初始化签到系统"""
        self.sso_login = SSOLogin()
        self.session = self.sso_login.session
        self.headers = self.sso_login.headers
        self.user_id = None
        self.user_info = None
        self.result_list = []

    def get_user_info(self):
        """
        获取用户信息
        
        Returns:
            dict: 用户信息字典
        
        Raises:
            RuntimeError: 获取用户信息失败
        """
        logger.info("正在获取用户信息...")
        try:
            current_url = self.session.get(self.sso_login.BASE_URL).url
            parsed_url = urlparse(current_url)
            login_name = parse_qs(parsed_url.query).get('loginName', [None])[0]

            if not login_name:
                logger.error("无法从URL中提取应用令牌")
                raise RuntimeError("获取应用令牌失败")

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
                logger.info(f"成功获取用户信息: {self.user_id}")
                return result
            else:
                logger.error("响应中未包含用户信息")
                raise RuntimeError("获取用户信息失败: 返回数据中无用户信息")
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求错误: {e}")
            raise RuntimeError(f"获取用户信息失败: 网络错误 - {str(e)}") from e
        except Exception as e:
            logger.error(f"获取用户信息时发生错误: {e}")
            raise RuntimeError(f"获取用户信息失败: {str(e)}") from e

    def get_term_code(self):
        """获取当前学期代码"""
        logger.info("正在获取学期信息...")
        try:
            url = f"https://iclass.buaa.edu.cn:8346/app/course/get_base_school_year.action?userId={self.user_id}&type=2"
            r = self.session.get(url, headers=self.headers)
            r.raise_for_status()
            term_data = r.json()

            for data in term_data.get("result", []):
                if data.get("yearStatus") == "1":
                    term_code = data.get("code")
                    logger.info(f"成功获取学期代码: {term_code}")
                    return term_code

            logger.error("未找到当前学期信息")
            raise RuntimeError("未找到当前学期")
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
            logger.info(f"成功获取到 {len(courses)} 门课程")
            return courses
        except Exception as e:
            logger.error(f"获取课程列表失败: {e}")
            raise RuntimeError("获取课程列表失败") from e

    def get_course_sched_id(self, course_id):
        """
        获取课程排课ID
        
        Args:
            course_id (str): 课程ID
            
        Returns:
            str: 排课ID，如果没有进行中的课程则返回None
            
        Raises:
            RuntimeError: 获取排课信息失败
        """
        logger.info(f"正在获取课程 {course_id} 的排课信息...")
        try:
            url = f"https://iclass.buaa.edu.cn:8346/app/my/get_my_course_sign_detail.action?id={self.user_id}&courseId={course_id}"
            r = self.session.post(url, headers=self.headers)
            r.raise_for_status()
            course_data = r.json()
            self.result_list = course_data.get("result", [])

            if not self.result_list:
                logger.error("未获取到排课信息")
                raise RuntimeError("未找到排课信息")

            last_entry = self.result_list[-1]
            class_end_time_str = last_entry.get("classEndTime")
            class_end_time = datetime.strptime(class_end_time_str, "%Y-%m-%d %H:%M:%S")
            now_time = datetime.now()

            if class_end_time >= now_time:
                schedule_id = last_entry.get("courseSchedId")
                logger.info(f"成功获取当前课程排课ID: {schedule_id}")
                return schedule_id
            else:
                logger.info("当前没有正在进行的课程，但可能需要补签")
                return None
        except Exception as e:
            logger.error(f"获取排课ID时发生错误: {e}")
            raise RuntimeError(f"获取排课信息失败: {str(e)}") from e

    def perform_sign(self, course_sched_id):
        """
        执行签到操作
        
        Args:
            course_sched_id (str): 排课ID
            
        Returns:
            bool: 签到是否成功
        """
        logger.info(f"正在执行签到操作，排课ID: {course_sched_id}...")
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