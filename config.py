"""
需求：管理SmartVoyage项目的配置信息，包括大模型、数据库、日志等配置
思路步骤：
1. 定义项目根目录路径
2. 设置环境变量（生产/测试/开发/预生产）
3. 创建Config类管理所有配置项
4. 配置大模型参数（API地址、密钥、模型名称）
5. 配置数据库参数（主机、用户名、密码、数据库名）
6. 配置日志文件路径
7. 配置票务查询接口地址
8. 配置意图映射字典
9. 实现根据环境获取不同数据库配置的方法
"""

import os

from dotenv import load_dotenv

# 加载项目根目录下的 .env（已加入 .gitignore，不会提交）
# 注意：不覆盖已存在的系统环境变量，.env 仅作为兜底
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# 项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))

# 生产环境
# env = "prod"
# 测试环境
env = "test"
# 开发环境
# env = "dev"
# 预生产环境
# env = "pre_prod"


# 定义配置文件
class Config:
    def __init__(self):
        # 大模型配置
        # TODO: 需要修改成自己的API Key,此处是从环境变量中读取的，可以直接把KEY写成字符串
        # self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        # self.api_key = os.getenv("DASHSCOPE_API_KEY")
        # self.model_name = "qwen3.7-plus"
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

        # 数据库配置
        # TODO: 需要修改成自己的数据库配置
        self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD")
        self.database = os.getenv("MYSQL_DATABASE", "travel_rag")

        # 日志配置
        self.log_file = os.path.join(project_root, "logs", "logs/app.log")

        # # 票务查询的12306接口地址
        # self.url_123 = ""

        # 路由：意图和对应的Agent的对应关系
        self.intent = {
            "weather": "WeatherQueryAssistant",
            "flight": "TicketAssistant",
            "train": "TicketAssistant",
            "concert": "TicketAssistant",
            "order": "TicketAssistant",
            "car_rental": "TripAssistant",
            "tour_group": "TripAssistant",
            "insurance": "TripAssistant",
            "trip_order": "TripAssistant",
        }

        self.temperature = 0.1

        # 天气数据源配置
        # 默认："database"，手动启动爬虫
        # 可选值："database"（从数据库获取） / "api"（直接从和风API获取）
        self.weather_source = "api"

        # 和风天气 API 配置
        # TODO【需要配置你自己的 QWeather API Key 和专属域名】
        # 原代码里的 key 和专属域名属于他人账号，已移除
        self.weather_api_key = os.getenv("QWEATHER_API_KEY")
        self.weather_api_host = os.getenv("QWEATHER_API_HOST", "")
        self.weather_base_url = (
            f"https://{self.weather_api_host}" if self.weather_api_host else ""
        )
        self.weather_timezone = "Asia/Shanghai"

        # 天气监控城市列表（城市名 -> 城市代码）
        self.weather_city_codes = {"北京": "101010100", "成都": "101270101"}

        # 天气定时更新调度时间（北京时间）
        self.weather_schedule_time = "01:00"

        # Milvus 向量数据库配置
        self.milvus_host = os.getenv("MILVUS_HOST", "127.0.0.1")
        self.milvus_port = int(os.getenv("MILVUS_PORT", "19531"))
        self.tour_group_collection = os.getenv("MILVUS_COLLECTION", "tour_groups")

        # Qwen Embedding API 配置（DashScope，与 DeepSeek LLM 密钥分离）
        # TODO: 需要配置自己的 DashScope API Key
        self.embedding_url = (
            "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
        )
        self.embedding_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.embedding_dim = 1024

    # 预留：按环境切换数据库配置（当前默认使用上方单环境配置）
    # def get_mysql_config(self, env):
    #     """
    #     通过不同的环境获取不同的数据库配置
    #     :return:
    #     """
    #     if env == "prod":
    #         self.host = "localhost"
    #         self.user = "root"
    #         self.password = "root"
    #         self.database = "travel_rag"
    #     elif env == "dev":
    #         self.host = "localhost1"
    #         self.user = "root1"
    #         self.password = "root1"
    #         self.database = "travel_rag"
    #     elif env == "test":
    #         self.host = "localhost2"
    #         self.user = "root2"
    #         self.password = "root2"
    #         self.database = "travel_rag"
    #     else:
    #         self.host = "localhost3"
    #         self.user = "root3"
    #         self.password = "root3"
    #         self.database = "travel_rag"
    #     return self.host, self.user, self.password, self.database


if __name__ == "__main__":
    conf = Config()
    print(conf.log_file)
    print(conf.model_name, conf.base_url)
    print(conf.embedding_url, bool(conf.embedding_api_key))
