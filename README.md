### 数字人对话系统部署指南
#### 一、前置准备
1. **安装项目依赖**
   ```bash
   # 安装项目所有依赖（不安装当前项目本身）
   uv sync --no-install-project
   ```
2. **配置密钥**
   - 填写项目根目录下 `.env` 文件中的 API Key
   - 填写 `core\intelligent-qa-system\.env` 文件中的 API Key

#### 二、服务启动步骤
##### 步骤1：启动 RAG 服务器（知识库服务）
1. 参考文档：`robot-agent-main\core\intelligent-qa-system\rag工具说明.md`
2. 环境准备 & 启动命令：
   ```bash
   # 1. 进入 RAG 服务目录
   cd E:\srp\robot-agent-main\core\intelligent-qa-system
   
   # 2. 激活 conda 环境（根据实际环境名调整）
   conda activate intelligent-qa
   
   # 3. 启动 RAG HTTP 服务（热重载模式）
   uvicorn rag_http_api:app --host 127.0.0.1 --port 9000 --reload
   ```
   ✅ 启动成功标志：终端显示 `Uvicorn running on http://127.0.0.1:9000`

##### 步骤2：启动 WebSocket 服务器（数字人对话服务）
###### 阶段1：后端自测（可选）
```bash
# 仅后端测试，验证服务基础功能
uv run --no-project python scripts/run_qa_bot.py
```

###### 阶段2：前端对接（正式启动）
```bash
# 前端已配置好接口后，启动 WebSocket 服务
uv run --no-project python api/websocket_server.py
```


✅ 启动成功标志（终端输出）：
```
🦊 数字人对话 WebSocket 服务器
====================================
启动中...

🚀 初始化数字人对话系统...
✅ 系统初始化完成，等待前端连接...

INFO:     Uvicorn running on http://0.0.0.0:8000
```

###### 阶段3：简单前端测试
浏览器打开 api/test_frontend.html

#### 三、前端集成示例（React 版）
```tsx
// WebSocket 客户端封装（React 组件示例）
import { useState, useEffect } from 'react';

const DigitalHumanClient = () => {
  // 数字人状态管理
  const [animation, setAnimation] = useState('breathing'); // 呼吸/招手/说话/监听/告别
  const [statusText, setStatusText] = useState('等待唤醒...');
  const [ws, setWs] = useState<WebSocket | null>(null);

  // 初始化 WebSocket 连接
  useEffect(() => {
    // 创建连接（注意：生产环境需替换为实际服务器地址）
    const socket = new WebSocket('ws://localhost:8000/ws/conversation');
    
    // 连接成功回调
    socket.onopen = () => {
      console.log('✅ 已连接到数字人服务器');
    };

    // 接收消息回调
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.type) {
        case 'connected':
          console.log('欢迎消息:', data.message);
          setAnimation('breathing'); // 初始待机状态
          break;
        
        case 'state_change':
          handleStateChange(data.state, data.data);
          break;
      }
    };

    // 连接关闭/错误处理
    socket.onclose = () => {
      console.log('❌ 与数字人服务器断开连接，正在重连...');
      setStatusText('连接已断开');
      setAnimation('breathing');
    };

    socket.onerror = (error) => {
      console.error('WebSocket 错误:', error);
    };

    setWs(socket);

    // 组件卸载时关闭连接
    return () => {
      socket.close();
    };
  }, []);

  // 状态变更处理（核心逻辑）
  const handleStateChange = (state: string, data: any) => {
    switch (state) {
      case 'waiting_wake':
        // 待机状态：呼吸动画 + 唤醒提示
        setAnimation('breathing');
        setStatusText(`等待唤醒: ${data.message}`);
        break;
      
      case 'awakened':
        // 唤醒成功：招手动画 + 提示音
        setAnimation('waving');
        setStatusText('我在！');
        // playSound('awakened.mp3'); // 唤醒提示音（需实现音频播放函数）
        break;
      
      case 'conversing':
        // 对话中：说话动画 + 机器人回复
        setAnimation('talking');
        setStatusText(data.bot_response || '正在思考...');
        break;
      
      case 'idle':
        // 闲置状态：监听动画 + 等待提示
        setAnimation('listening');
        setStatusText('在听...');
        break;
      
      case 'goodbye':
        // 告别状态：挥手动画 + 提示音，2秒后回到待机
        setAnimation('goodbye');
        setStatusText('再见！');
        // playSound('goodbye.mp3'); // 告别提示音
        setTimeout(() => {
          setAnimation('breathing');
          setStatusText('等待唤醒...');
        }, 2000);
        break;
    }
  };

  // 渲染数字人组件（示例）
  return (
    <div className="digital-human-container">
      {/* 数字人动画容器（根据 animation 切换样式） */}
      <div className={`digital-human-animation ${animation}`}></div>
      {/* 状态文本显示 */}
      <div className="status-text">{statusText}</div>
    </div>
  );
};

export default DigitalHumanClient;
```

