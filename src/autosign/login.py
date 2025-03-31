import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from platformdirs import user_data_dir
from .logger import setup_logger

# 获取日志器
logger = setup_logger("SSOLogin")


class SSOLogin:
    """SSO登录"""
    BASE_URL = 'https://d.buaa.edu.cn/https-8346/77726476706e69737468656265737421f9f44d9d342326526b0988e29d51367ba018/'
    LOGIN_URL = 'https://d.buaa.edu.cn/https/77726476706e69737468656265737421e3e44ed225256951300d8db9d6562d/login?service=https%3A%2F%2Ficlass.buaa.edu.cn%3A8346%2F'

    def __init__(self):
        """初始化登录系统"""
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        self.username = ""
        self.password = ""
        data_dir = user_data_dir("AutoSign", "AutoSign")
        os.makedirs(data_dir, exist_ok=True)
        self.config_file = os.path.join(data_dir, "config.json")

    def load_credentials(self):
        """
        从配置文件加载凭据
        
        Returns:
            bool: 是否成功加载凭据
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.username = data.get("username", "").strip()
                    self.password = data.get("password", "").strip()
                    if self.username and self.password:
                        logger.info("成功加载凭据")
                        return True
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"加载凭据时发生错误: {e}")
                # 如果配置文件损坏，尝试删除
                self.delete_config_file()
        logger.warning("未找到有效凭据，请手动输入")
        return False

    def save_credentials(self):
        """保存凭据到配置文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"username": self.username, "password": self.password},
                          f, indent=4, ensure_ascii=False)
            logger.info("凭据已保存")
        except IOError as e:
            logger.error(f"保存凭据时发生错误: {e}")

    def get_login_token(self):
        """
        获取SSO登录所需的token
        
        Returns:
            str: 登录令牌
            
        Raises:
            RuntimeError: 获取登录令牌失败
        """
        logger.info("正在获取登录令牌...")
        try:
            r = self.session.get(self.LOGIN_URL)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, 'html.parser')
            token_input = soup.find('input', {'name': 'execution'})
            
            if not token_input:
                logger.error("页面中未找到登录令牌")
                raise RuntimeError("页面结构可能已更改，未找到登录令牌")
                
            token = token_input['value']
            logger.info(f"成功获取登录令牌: {token[:3]}...{token[-3:]}")
            return token
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求错误: {e}")
            raise RuntimeError(f"获取登录令牌失败: 网络错误 - {str(e)}") from e
        except Exception as e:
            logger.error(f"获取登录令牌失败: {e}")
            raise RuntimeError(f"获取登录令牌失败: {str(e)}") from e

    def login(self):
        """
        登录SSO系统
        
        Returns:
            bool: 是否登录成功
        """
        logger.info("尝试登录SSO系统...")
        if not self.username or not self.password:
            logger.error("用户名或密码为空")
            return False

        try:
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

            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.find_all('div', class_='error_txt'):
                logger.info("登录成功")
                self.save_credentials()
                return True
            else:
                error_msgs = [error.text.strip() for error in soup.find_all('div', class_='error_txt')]
                error_str = "、".join(error_msgs) if error_msgs else "未知错误"
                logger.error(f"登录失败: {error_str}")
                self.delete_config_file()
                return False
        except Exception as e:
            logger.error(f"登录失败: {e}")
            self.delete_config_file()
            return False

    def delete_config_file(self):
        """删除配置文件"""
        if os.path.exists(self.config_file):
            try:
                os.remove(self.config_file)
                logger.info("已删除配置文件")
            except IOError as e:
                logger.error(f"删除配置文件时发生错误: {e}")
