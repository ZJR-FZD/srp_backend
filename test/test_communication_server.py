# test/test_communication_server.py
"""通信模块测试

测试 CommunicationServer、ConnectionManager、MessageRouter、TaskDispatcher 的基本功能
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from core.agent import RobotAgent
from core.server import CommunicationServer, TaskDispatcher, ConnectionManager, MessageRouter
from core.server.message_router import TaskRequest, UserInputRequest


class TestConnectionManager:
    """ConnectionManager 单元测试"""
    
    def test_initialization(self):
        """测试连接管理器初始化"""
        cm = ConnectionManager(max_connections=50)
        assert cm.max_connections == 50
        assert cm.get_connection_count() == 0
        assert cm.get_online_agents() == []
    
    def test_get_connection_count(self):
        """测试获取连接数"""
        cm = ConnectionManager()
        assert cm.get_connection_count() == 0


class TestMessageRouter:
    """MessageRouter 单元测试"""
    
    def test_initialization(self):
        """测试消息路由器初始化"""
        router = MessageRouter()
        assert router.message_count == 0
    
    def test_validate_task_request_success(self):
        """测试验证有效的任务请求"""
        router = MessageRouter()
        data = {
            "task_type": "execute_action",
            "task_name": "test_task",
            "parameters": {"key": "value"}
        }
        result = router.validate_task_request(data)
        assert result is not None
        assert result.task_type == "execute_action"
        assert result.task_name == "test_task"
        assert router.message_count == 1
    
    def test_validate_task_request_failure(self):
        """测试验证无效的任务请求"""
        router = MessageRouter()
        data = {"invalid": "data"}  # 缺少必需字段
        result = router.validate_task_request(data)
        assert result is None
    
    def test_validate_user_input_success(self):
        """测试验证有效的用户输入"""
        router = MessageRouter()
        data = {
            "input_type": "text",
            "content": "Hello, robot!"
        }
        result = router.validate_user_input(data)
        assert result is not None
        assert result.input_type == "text"
        assert result.content == "Hello, robot!"
    
    def test_convert_user_input_to_task(self):
        """测试将用户输入转换为任务请求"""
        router = MessageRouter()
        user_input = UserInputRequest(
            input_type="voice",
            content="Turn on the lights"
        )
        task = router.convert_user_input_to_task(user_input)
        assert task.task_type == "user_input"
        assert task.task_name == "user_input_voice"
        assert task.parameters["content"] == "Turn on the lights"


@pytest.mark.asyncio
class TestTaskDispatcher:
    """TaskDispatcher 单元测试"""
    
    async def test_initialization(self):
        """测试任务调度器初始化"""
        agent = RobotAgent()
        dispatcher = TaskDispatcher(agent=agent)
        assert dispatcher.agent == agent
        assert len(dispatcher.task_status_map) == 0
    
    async def test_dispatch_task(self):
        """测试任务分发"""
        agent = RobotAgent()
        dispatcher = TaskDispatcher(agent=agent)
        
        task_request = TaskRequest(
            task_type="custom",
            task_name="test_task",
            parameters={"test": "data"}
        )
        
        task_id = await dispatcher.dispatch_task(task_request)
        assert task_id is not None
        assert len(dispatcher.task_status_map) == 1
        assert task_id in dispatcher.task_status_map
        
        # 验证任务状态
        task_info = dispatcher.get_task_status(task_id)
        assert task_info is not None
        assert task_info.status == "pending"
    
    async def test_list_tasks(self):
        """测试获取任务列表"""
        agent = RobotAgent()
        dispatcher = TaskDispatcher(agent=agent)
        
        # 创建多个任务
        for i in range(3):
            task_request = TaskRequest(
                task_type="custom",
                task_name=f"task_{i}",
                parameters={}
            )
            await dispatcher.dispatch_task(task_request)
        
        tasks = dispatcher.list_tasks()
        assert len(tasks) == 3


class TestCommunicationServer:
    """CommunicationServer 单元测试"""
    
    def test_initialization(self):
        """测试通信服务器初始化"""
        server = CommunicationServer(
            host="127.0.0.1",
            port=8090,
            api_key="test-key",
            agent_id="test-agent"
        )
        assert server.host == "127.0.0.1"
        assert server.port == 8090
        assert server.api_key == "test-key"
        assert server.agent_id == "test-agent"
        assert server.app is not None
        assert server.connection_manager is not None
        assert server.message_router is not None


@pytest.mark.asyncio  
class TestIntegration:
    """集成测试"""
    
    async def test_full_initialization(self):
        """测试完整初始化流程"""
        # 创建 Agent
        agent = RobotAgent()
        
        # 创建 TaskDispatcher
        task_dispatcher = TaskDispatcher(agent=agent)
        
        # 创建 CommunicationServer
        comm_server = CommunicationServer(
            host="127.0.0.1",
            port=8091,
            api_key="test-key",
            agent_id="test-agent"
        )
        
        # 建立双向引用
        comm_server.set_task_dispatcher(task_dispatcher)
        task_dispatcher.set_communication_server(comm_server)
        
        # 验证引用
        assert comm_server.task_dispatcher == task_dispatcher
        assert task_dispatcher.communication_server == comm_server
        
        # 清理
        comm_server.stop()


@pytest.mark.asyncio
class TestAPIEndpoints:
    """API 接口测试"""
    
    async def test_create_task_success(self):
        """测试创建任务接口 - 成功场景"""
        # 初始化完整系统
        agent = RobotAgent()
        task_dispatcher = TaskDispatcher(agent=agent)
        comm_server = CommunicationServer(
            host="127.0.0.1",
            port=8092,
            api_key="test-api-key",
            agent_id="test-agent"
        )
        comm_server.set_task_dispatcher(task_dispatcher)
        task_dispatcher.set_communication_server(comm_server)
        
        # 使用 AsyncClient 测试接口
        transport = ASGITransport(app=comm_server.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 准备任务数据
            task_data = {
                "task_type": "execute_action",
                "task_name": "test_watch",
                "parameters": {
                    "action_name": "watch",
                    "input_data": {"duration": 5}
                }
            }
            
            # 发送请求（在请求头中添加 API Key）
            response = await client.post(
                "/api/tasks",
                json=task_data,
                headers={"X-API-Key": "test-api-key"}
            )
            
            # 验证响应
            assert response.status_code == 200
            result = response.json()
            assert "task_id" in result
            assert result["status"] == "pending"
            assert result["message"] == "Task created successfully"
            assert "created_at" in result
            
        # 清理
        comm_server.stop()
    
    async def test_create_task_invalid_api_key(self):
        """测试创建任务接口 - API Key 无效"""
        agent = RobotAgent()
        task_dispatcher = TaskDispatcher(agent=agent)
        comm_server = CommunicationServer(
            host="127.0.0.1",
            port=8093,
            api_key="correct-key",
            agent_id="test-agent"
        )
        comm_server.set_task_dispatcher(task_dispatcher)
        
        transport = ASGITransport(app=comm_server.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            task_data = {
                "task_type": "execute_action",
                "task_name": "test_task",
                "parameters": {}
            }
            
            # 使用错误的 API Key
            response = await client.post(
                "/api/tasks",
                json=task_data,
                headers={"X-API-Key": "wrong-key"}
            )
            
            # 验证返回 401 未授权
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid API key"
        
        comm_server.stop()
    
    async def test_create_task_invalid_format(self):
        """测试创建任务接口 - 数据格式无效"""
        agent = RobotAgent()
        task_dispatcher = TaskDispatcher(agent=agent)
        comm_server = CommunicationServer(
            host="127.0.0.1",
            port=8094,
            api_key="test-key",
            agent_id="test-agent"
        )
        comm_server.set_task_dispatcher(task_dispatcher)
        
        transport = ASGITransport(app=comm_server.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 缺少必需字段的数据
            invalid_data = {"invalid": "data"}
            
            response = await client.post(
                "/api/tasks",
                json=invalid_data,
                headers={"X-API-Key": "test-key"}
            )
            
            # 验证返回 400 错误
            assert response.status_code == 400
            assert response.json()["detail"] == "Invalid task request format"
        
        comm_server.stop()
    
    async def test_create_task_with_query_param_api_key(self):
        """测试创建任务接口 - 使用查询参数传递 API Key"""
        agent = RobotAgent()
        task_dispatcher = TaskDispatcher(agent=agent)
        comm_server = CommunicationServer(
            host="127.0.0.1",
            port=8095,
            api_key="query-key",
            agent_id="test-agent"
        )
        comm_server.set_task_dispatcher(task_dispatcher)
        
        transport = ASGITransport(app=comm_server.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            task_data = {
                "task_type": "custom",
                "task_name": "query_test",
                "parameters": {"test": "value"}
            }
            
            # 通过查询参数传递 API Key
            response = await client.post(
                "/api/tasks?api_key=query-key",
                json=task_data
            )
            
            # 验证成功
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "pending"
        
        comm_server.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
