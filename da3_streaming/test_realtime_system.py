#!/usr/bin/env python3
# coding=utf-8
"""
DA3实时系统测试脚本
用于测试各个组件是否正常工作
"""
import json
import os
import sys
import time

def check_dependencies():
    """检查依赖是否安装"""
    print("=" * 50)
    print("检查依赖...")
    print("=" * 50)
    
    required_packages = [
        ('flask', 'Flask'),
        ('flask_socketio', 'Flask-SocketIO'),
        ('zmq', 'PyZMQ'),
        ('cv2', 'OpenCV'),
        ('numpy', 'NumPy'),
        ('torch', 'PyTorch'),
    ]
    
    missing = []
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print(f"✓ {package_name} 已安装")
        except ImportError:
            print(f"✗ {package_name} 未安装")
            missing.append(package_name)
    
    if missing:
        print(f"\n缺少以下依赖: {', '.join(missing)}")
        print("请运行: pip install -r requirements_realtime.txt")
        return False
    
    print("\n所有依赖已安装 ✓")
    return True


def check_weights():
    """检查模型权重是否存在"""
    print("\n" + "=" * 50)
    print("检查模型权重...")
    print("=" * 50)
    
    weight_files = [
        './weights/model.safetensors',
        './weights/config.json',
    ]
    
    missing = []
    for weight_file in weight_files:
        if os.path.exists(weight_file):
            print(f"✓ {weight_file} 存在")
        else:
            print(f"✗ {weight_file} 不存在")
            missing.append(weight_file)
    
    if missing:
        print(f"\n缺少以下权重文件: {', '.join(missing)}")
        print("请确保已下载DA3模型权重")
        return False
    
    print("\n所有权重文件已就绪 ✓")
    return True


def check_config():
    """检查配置文件"""
    print("\n" + "=" * 50)
    print("检查配置文件...")
    print("=" * 50)
    
    config_file = './configs/realtime_config.yaml'
    
    if not os.path.exists(config_file):
        print(f"✗ 配置文件不存在: {config_file}")
        print("请确保配置文件存在")
        return False
    
    print(f"✓ 配置文件存在: {config_file}")
    
    try:
        from loop_utils.config_utils import load_config
        config = load_config(config_file)
        print("✓ 配置文件格式正确")
        print(f"  - chunk_size: {config['Model']['chunk_size']}")
        print(f"  - overlap: {config['Model']['overlap']}")
        print(f"  - loop_enable: {config['Model']['loop_enable']}")
    except Exception as e:
        print(f"✗ 配置文件加载失败: {e}")
        return False
    
    print("\n配置文件检查通过 ✓")
    return True


def check_cuda():
    """检查CUDA是否可用"""
    print("\n" + "=" * 50)
    print("检查CUDA...")
    print("=" * 50)
    
    try:
        import torch
        
        if torch.cuda.is_available():
            print(f"✓ CUDA 可用")
            print(f"  - 设备数量: {torch.cuda.device_count()}")
            print(f"  - 当前设备: {torch.cuda.get_device_name(0)}")
            print(f"  - CUDA 版本: {torch.version.cuda}")
        else:
            print("⚠ CUDA 不可用，将使用CPU（速度会很慢）")
            return False
    except Exception as e:
        print(f"✗ 检查CUDA时出错: {e}")
        return False
    
    print("\nCUDA 检查通过 ✓")
    return True


def check_templates():
    """检查模板文件"""
    print("\n" + "=" * 50)
    print("检查模板文件...")
    print("=" * 50)
    
    template_file = './templates/index.html'
    
    if not os.path.exists(template_file):
        print(f"✗ 模板文件不存在: {template_file}")
        return False
    
    print(f"✓ 模板文件存在: {template_file}")
    
    # 检查文件大小
    file_size = os.path.getsize(template_file)
    print(f"  - 文件大小: {file_size} bytes")
    
    if file_size < 1000:
        print("⚠ 模板文件可能不完整")
        return False
    
    print("\n模板文件检查通过 ✓")
    return True


def test_zmq_connection(host='127.0.0.1', port=5555, timeout=2):
    """测试ZMQ连接（可选）"""
    print("\n" + "=" * 50)
    print(f"测试ZMQ连接 ({host}:{port})...")
    print("=" * 50)
    
    try:
        import zmq
        
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(f"tcp://{host}:{port}")
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        socket.setsockopt(zmq.RCVTIMEO, timeout * 1000)
        
        print(f"正在等待消息 (超时 {timeout}s)...")
        
        try:
            msg = socket.recv_string()
            print("✓ 成功接收到ZMQ消息")
            print(f"  - 消息长度: {len(msg)} bytes")
            socket.close()
            context.term()
            return True
        except zmq.error.Again:
            print(f"⚠ 在 {timeout}s 内未收到消息")
            print("  这是正常的，如果ZMQ发布器未运行")
            socket.close()
            context.term()
            return None
            
    except Exception as e:
        print(f"✗ ZMQ连接测试失败: {e}")
        return False


def print_summary(results):
    """打印测试总结"""
    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    
    all_passed = all(v == True for v in results.values() if v is not None)
    
    for test_name, result in results.items():
        if result == True:
            status = "✓ 通过"
        elif result == False:
            status = "✗ 失败"
        else:
            status = "- 跳过"
        print(f"{status} - {test_name}")
    
    print("=" * 50)
    
    if all_passed:
        print("\n🎉 所有关键测试通过！系统已准备就绪。")
        print("\n启动服务:")
        print("  bash start_realtime_demo.sh")
        print("\n或手动启动:")
        print("  python3 da3_realtime_service.py")
        return 0
    else:
        print("\n⚠ 部分测试失败，请先修复上述问题。")
        return 1


def main():
    print("\n")
    print("╔" + "=" * 48 + "╗")
    print("║  DA3 实时点云重建系统 - 环境检查工具      ║")
    print("╚" + "=" * 48 + "╝")
    print()
    
    results = {}
    
    # 必须通过的测试
    results['依赖检查'] = check_dependencies()
    results['权重检查'] = check_weights()
    results['配置检查'] = check_config()
    results['CUDA检查'] = check_cuda()
    results['模板检查'] = check_templates()
    
    # 可选测试
    if '--test-zmq' in sys.argv:
        results['ZMQ连接'] = test_zmq_connection()
    
    # 打印总结
    exit_code = print_summary(results)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

