# Robot Agent

本项目是机器人的Agent，这是 [PRD](https://k1ntis7zj04.feishu.cn/docx/GKw1dr5bHoqx8KxAAMzcmBMBnDc?from=from_copylink) 链接

## 启动项目
1. 安装 [uv]()
2. 使用`uv run main.py`启动项目

## 运行测试

本项目使用 pytest 进行单元测试，可以使用下面的命令运行所有单测:
```bash
uv run pytest
```
如果需要更详细的信息，可以增加 -v 参数:
```bash
uv run pytest -v
```
如果只需要运行特定测试，可以使用下面的命令（自行替换文件名和测试函数名）:
```bash
uv run pytest test/test_camera.py::test_camera_initialization -s
```
如果需要运行集成测试，可以使用下面的命令:
```bash
# 先设置环境变量
export RUN_INTEGRATION=1
# 然后运行测试
uv run pytest test/test_camera_integration.py -v -s
```

## Todo

- 机器人本地能力
    - [x] 语音能力 SpeakAction
    - [x] 告警能力 AlertAction（不直接用 AI 决策调用 mcp 接口是为了摔倒检测等功能的可靠性）
    - [x] 视觉能力 WatchAction
    - [ ] 巡逻能力
- Agent 任务管理器
    - [x] 任务循环
    - [x] 任务决策
    - [x] 支持多轮任务
- MCP 控制模块
    - [x] MCP 连接管理
    - [x] MCP 工具管理、缓存处理
    - [x] MCP 调用参数生成
- [ ] 引入[A2A protocol](https://github.com/a2aproject/A2A)辅助智能体通信
- [ ] 日志管理

## 一些碎碎念

1. 友善的24.04镜像好像有奇怪的原因导致apt install没办法认zst格式的包，选型的时候需要注意一下。
2. 阿里云百炼的Qwen3-tts-flash-realtime接口有点问题，大陆的base_url用不了，要用那个国际的。国际的和大陆的API_Key是不一样的
3. 友善的这个板子声卡只支持双声道，TTS 生成的单声道音频不能直接播放




