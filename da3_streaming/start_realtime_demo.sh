#!/bin/bash
# DA3 实时streaming演示启动脚本

echo "=========================================="
echo "  DA3 实时点云重建演示系统"
echo "=========================================="
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
python3 -c "import flask, flask_socketio, zmq, cv2" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "警告: 缺少某些依赖包"
    echo "正在安装依赖..."
    pip3 install -r requirements_realtime.txt
fi

# 设置默认参数
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-5000}
CONFIG=${CONFIG:-"./configs/base_config.yaml"}

echo ""
echo "配置信息:"
echo "  服务地址: http://${HOST}:${PORT}"
echo "  配置文件: ${CONFIG}"
echo ""

# 启动服务
echo "启动服务..."
python3 da3_realtime_service.py \
    --host ${HOST} \
    --port ${PORT} \
    --debug

echo ""
echo "服务已停止"

