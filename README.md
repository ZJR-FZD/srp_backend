
# 前提
安装整个项目的依赖：uv sync --no-install-project
填写 .env 和 core\intelligent-qa-system\.env 中的 api-key

# 1. 启动 RAG 服务器
找到 robot-agent-main\core\intelligent-qa-system 下面的rag工具说明.md，照着文档部署启动服务器
需要定位到该目录下，然后conda安装环境并激活，例如
(intelligent-qa) E:\srp\robot-agent-main\core\intelligent-qa-system>uvicorn rag_http_api:app --host 127.0.0.1 --port 9000 --reload

# 2. 启动 WebSocket 服务器
（可以先后端测试一下）uv run --no-project python scripts/run_qa_bot.py

（前端连接好接口之后）
uv run --no-project python api/websocket_server.py
```

前端看到：
```
🦊 数字人对话 WebSocket 服务器
====================================
启动中...

🚀 初始化数字人对话系统...
✅ 系统初始化完成，等待前端连接...

INFO:     Uvicorn running on http://0.0.0.0:8000

# 前端集成示例（React）
// 前端 WebSocket 客户端
const ws = new WebSocket('ws://localhost:8000/ws/conversation');

ws.onopen = () => {
  console.log('✅ 已连接到数字人服务器');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'connected':
      console.log('欢迎消息:', data.message);
      // 显示待机状态
      setDigitalHumanState('idle');
      break;
    
    case 'state_change':
      handleStateChange(data.state, data.data);
      break;
  }
};

function handleStateChange(state: string, data: any) {
  switch (state) {
    case 'waiting_wake':
      // 数字人进入待机状态（呼吸动画）
      setAnimation('breathing');
      setStatusText(`等待唤醒: ${data.message}`);
      break;
    
    case 'awakened':
      // 唤醒成功（招手动画）
      setAnimation('waving');
      setStatusText('我在！');
      playSound('awakened.mp3');
      break;
    
    case 'conversing':
      // 对话中（说话动画）
      setAnimation('talking');
      if (data.bot_response) {
        setStatusText(data.bot_response);
      }
      break;
    
    case 'idle':
      // 闲置（等待用户说话）
      setAnimation('listening');
      setStatusText('在听...');
      break;
    
    case 'goodbye':
      // 再见（挥手告别）
      setAnimation('goodbye');
      setStatusText('再见！');
      playSound('goodbye.mp3');
      
      // 2秒后回到待机
      setTimeout(() => {
        setAnimation('breathing');
      }, 2000);
      break;
  }
}