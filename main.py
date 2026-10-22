"""项目入口：启动 FastAPI Web 服务"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000)