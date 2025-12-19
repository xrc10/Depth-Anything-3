# coding=utf-8
"""
DA3 实时处理服务
提供REST API和WebSocket接口，支持实时视频流处理和点云渲染
"""
import argparse
import base64
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue

import cv2
import numpy as np
import zmq
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from loop_utils.config_utils import load_config
from da3_streaming_realtime import DA3_Streaming_Realtime

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局状态
class StreamingState:
    def __init__(self):
        self.is_running = False
        self.is_processing = False
        self.frame_count = 0
        self.chunk_count = 0
        self.status = "idle"  # idle, capturing, processing, loop_closure, finished
        self.da3_processor = None
        self.zmq_thread = None
        self.frame_queue = Queue()
        self.output_dir = None
        self.config = None
        self.zmq_host = "127.0.0.1"
        self.zmq_port = 5555
        
state = StreamingState()


def zmq_capture_thread(host, port):
    """ZMQ视频流接收线程"""
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    
    addr = f"tcp://{host}:{port}"
    print(f"Connecting to ZMQ publisher at {addr}...")
    socket.connect(addr)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1秒超时
    
    while state.is_running:
        try:
            msg_str = socket.recv_string()
            data = json.loads(msg_str)
            timestamp = data.get("timestamp", time.time())
            img_b64 = data["image"]
            
            # 解码图像
            img_bytes = base64.b64decode(img_b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if img is not None:
                # 保存到临时目录
                frame_path = os.path.join(
                    state.output_dir, "frames", f"frame_{state.frame_count:06d}.jpg"
                )
                cv2.imwrite(frame_path, img)
                
                state.frame_count += 1
                state.frame_queue.put(frame_path)
                
                # 发送状态更新到前端
                socketio.emit('frame_captured', {
                    'frame_count': state.frame_count,
                    'timestamp': timestamp
                })
                
                print(f"Captured frame {state.frame_count}")
                
        except zmq.error.Again:
            continue
        except Exception as e:
            print(f"Error in ZMQ capture: {e}")
            continue
    
    socket.close()
    context.term()
    print("ZMQ capture thread stopped")


def da3_processing_thread():
    """DA3处理线程"""
    chunk_size = state.config["Model"]["chunk_size"]
    overlap = state.config["Model"]["overlap"]
    
    while state.is_running or not state.frame_queue.empty():
        # 检查是否有足够的帧来处理下一个chunk
        # 第一个chunk: 需要 chunk_size 帧
        # 后续chunk: 需要 (上次处理的帧数 - overlap + chunk_size) 帧
        if state.chunk_count == 0:
            required_frames = chunk_size
        else:
            # 已经处理的帧数存储在 da3_processor.processed_frames
            required_frames = state.da3_processor.processed_frames - overlap + chunk_size
        
        # 当前已捕获的总帧数
        current_total_frames = state.frame_count
        
        # 只有当有足够的新帧时才处理
        if current_total_frames >= required_frames and not state.is_processing:
            state.is_processing = True
            state.status = "processing"
            
            # 通知前端开始处理
            socketio.emit('processing_started', {
                'chunk_id': state.chunk_count,
                'frame_count': state.frame_count
            })
            
            print(f"Processing chunk {state.chunk_count}... (total frames: {current_total_frames}, required: {required_frames})")
            
            # 调用DA3处理
            try:
                ply_path = state.da3_processor.process_next_chunk()
                
                if ply_path and os.path.exists(ply_path):
                    # 读取PLY文件并发送到前端
                    socketio.emit('chunk_ready', {
                        'chunk_id': state.chunk_count,
                        'ply_path': ply_path,
                        'ply_url': f"/pointcloud/{state.chunk_count}"
                    })
                    print(f"Chunk {state.chunk_count} processed, PLY saved to {ply_path}")
                    print(f"Next chunk will process at frame {state.da3_processor.processed_frames - overlap + chunk_size}")
                    
                    state.chunk_count += 1
                elif ply_path is None:
                    print(f"Not enough frames for chunk {state.chunk_count}, waiting...")
                
            except Exception as e:
                print(f"Error processing chunk: {e}")
                socketio.emit('error', {'message': str(e)})
            
            state.is_processing = False
            
        time.sleep(0.1)
    
    print("DA3 processing thread stopped")


@app.route('/api/start', methods=['POST'])
def start_streaming():
    """开始视频流捕获和处理"""
    if state.is_running:
        return jsonify({'error': 'Already running'}), 400
    
    data = request.json or {}
    config_path = data.get('config', './configs/base_config.yaml')
    zmq_host = data.get('zmq_host', '127.0.0.1')
    zmq_port = data.get('zmq_port', 5555)
    
    # 加载配置
    state.config = load_config(config_path)
    state.zmq_host = zmq_host
    state.zmq_port = zmq_port
    
    # 创建输出目录
    current_datetime = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    state.output_dir = os.path.join("./exps/realtime", current_datetime)
    os.makedirs(os.path.join(state.output_dir, "frames"), exist_ok=True)
    
    # 初始化DA3处理器
    state.da3_processor = DA3_Streaming_Realtime(
        frame_dir=os.path.join(state.output_dir, "frames"),
        save_dir=state.output_dir,
        config=state.config
    )
    
    # 重置状态
    state.is_running = True
    state.frame_count = 0
    state.chunk_count = 0
    state.status = "capturing"
    
    # 启动线程
    state.zmq_thread = threading.Thread(target=zmq_capture_thread, args=(zmq_host, zmq_port))
    state.zmq_thread.start()
    
    processing_thread = threading.Thread(target=da3_processing_thread)
    processing_thread.start()
    
    return jsonify({
        'status': 'started',
        'output_dir': state.output_dir,
        'config': config_path
    })


@app.route('/api/stop', methods=['POST'])
def stop_streaming():
    """停止捕获并开始回环优化"""
    if not state.is_running:
        return jsonify({'error': 'Not running'}), 400
    
    state.is_running = False
    state.status = "loop_closure"
    
    # 等待线程结束
    if state.zmq_thread:
        state.zmq_thread.join(timeout=5)
    
    # 通知前端开始回环
    socketio.emit('loop_closure_started', {
        'total_chunks': state.chunk_count,
        'total_frames': state.frame_count
    })
    
    # 执行回环优化
    try:
        print("Starting loop closure optimization...")
        state.da3_processor.finalize_with_loop_closure()
        
        # 合并所有点云
        final_ply_path = os.path.join(state.output_dir, "pcd", "final_combined.ply")
        
        socketio.emit('loop_closure_finished', {
            'final_ply_url': f"/pointcloud/final",
            'final_ply_path': final_ply_path
        })
        
        state.status = "finished"
        print("Loop closure completed!")
        
    except Exception as e:
        print(f"Error in loop closure: {e}")
        socketio.emit('error', {'message': f"Loop closure error: {str(e)}"})
    
    return jsonify({
        'status': 'stopped',
        'total_frames': state.frame_count,
        'total_chunks': state.chunk_count
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取当前状态"""
    return jsonify({
        'is_running': state.is_running,
        'is_processing': state.is_processing,
        'status': state.status,
        'frame_count': state.frame_count,
        'chunk_count': state.chunk_count,
        'output_dir': state.output_dir
    })


@app.route('/pointcloud/<int:chunk_id>', methods=['GET'])
def get_pointcloud(chunk_id):
    """获取指定chunk的点云文件"""
    if state.output_dir is None:
        return jsonify({'error': 'No active session'}), 404
    
    ply_path = os.path.join(state.output_dir, "pcd", f"{chunk_id}_pcd.ply")
    
    if not os.path.exists(ply_path):
        return jsonify({'error': 'Pointcloud not found'}), 404
    
    return send_file(ply_path, mimetype='application/octet-stream')


@app.route('/pointcloud/final', methods=['GET'])
def get_final_pointcloud():
    """获取最终合并的点云文件"""
    if state.output_dir is None:
        return jsonify({'error': 'No active session'}), 404
    
    ply_path = os.path.join(state.output_dir, "pcd", "combined_pcd.ply")
    
    if not os.path.exists(ply_path):
        return jsonify({'error': 'Final pointcloud not found'}), 404
    
    return send_file(ply_path, mimetype='application/octet-stream')


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connection_established', {'status': 'connected'})


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="DA3 Realtime Streaming Service")
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=5000, help='Server port')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting DA3 Realtime Service on {args.host}:{args.port}")
    socketio.run(app, host=args.host, port=args.port, debug=args.debug)

