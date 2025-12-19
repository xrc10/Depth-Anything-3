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
        self.status = "idle"  # idle, capturing, processing, finalizing, loop_closure, finished
        self.da3_processor = None
        self.zmq_thread = None
        self.processing_thread = None  # 添加处理线程引用
        self.frame_queue = Queue()
        self.output_dir = None
        self.config = None
        self.default_config_path = "./configs/realtime_config.yaml"  # 默认配置文件路径
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
    
    frame_skip = 0  # 用于控制视频流发送频率
    
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
                
                # 每5帧发送一次视频预览到前端（降低带宽消耗）
                if frame_skip % 5 == 0:
                    # 缩小图像用于预览
                    preview_img = cv2.resize(img, (320, 240))
                    _, buffer = cv2.imencode('.jpg', preview_img, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    preview_b64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # 发送视频预览帧
                    socketio.emit('video_frame', {
                        'frame': preview_b64,
                        'frame_count': state.frame_count,
                        'timestamp': timestamp
                    })
                
                frame_skip += 1
                
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
    
    while True:
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
        
        # 计算剩余待处理的chunk数量（估算）
        if state.chunk_count == 0 and current_total_frames > 0:
            # 第一个chunk还未处理
            estimated_remaining_chunks = max(0, int((current_total_frames - chunk_size) / (chunk_size - overlap)) + 1)
        elif state.chunk_count > 0 and hasattr(state.da3_processor, 'processed_frames'):
            # 已处理的帧数
            processed_frames = state.da3_processor.processed_frames
            remaining_frames = current_total_frames - processed_frames
            # 估算剩余chunk数（每个chunk处理 chunk_size - overlap 的新帧）
            estimated_remaining_chunks = max(0, int(remaining_frames / (chunk_size - overlap)))
        else:
            estimated_remaining_chunks = 0
        
        # 决定是否处理：
        # 1. 正常情况：有足够的帧来形成完整的chunk
        # 2. 停止捕获后：即使帧数不够，也要处理剩余的帧
        has_enough_frames = current_total_frames >= required_frames
        has_remaining_frames = (not state.is_running and 
                               state.chunk_count > 0 and 
                               hasattr(state.da3_processor, 'processed_frames') and
                               current_total_frames > state.da3_processor.processed_frames)
        
        should_process = (has_enough_frames or has_remaining_frames) and not state.is_processing
        
        if should_process:
            state.is_processing = True
            state.status = "processing"
            
            # 通知前端开始处理，包括剩余chunk数
            socketio.emit('processing_started', {
                'chunk_id': state.chunk_count,
                'frame_count': state.frame_count,
                'remaining_chunks': estimated_remaining_chunks
            })
            
            if has_remaining_frames and not has_enough_frames:
                print(f"Processing final partial chunk {state.chunk_count}... (total frames: {current_total_frames}, processed: {state.da3_processor.processed_frames})")
            else:
                print(f"Processing chunk {state.chunk_count}... (total frames: {current_total_frames}, required: {required_frames}, estimated remaining: {estimated_remaining_chunks})")
            
            # 调用DA3处理
            try:
                ply_path = state.da3_processor.process_next_chunk(force_process=has_remaining_frames)
                
                if ply_path and os.path.exists(ply_path):
                    # 读取PLY文件并发送到前端
                    socketio.emit('chunk_ready', {
                        'chunk_id': state.chunk_count,
                        'ply_path': ply_path,
                        'ply_url': f"/pointcloud/{state.chunk_count}"
                    })
                    print(f"Chunk {state.chunk_count} processed, PLY saved to {ply_path}")
                    
                    if state.is_running:
                        print(f"Next chunk will process at frame {state.da3_processor.processed_frames - overlap + chunk_size}")
                    else:
                        print(f"Processed frames: {state.da3_processor.processed_frames}/{state.frame_count}")
                    
                    state.chunk_count += 1
                    
                    # 检查是否所有帧都已处理完毕
                    if (not state.is_running and 
                        hasattr(state.da3_processor, 'processed_frames') and
                        state.da3_processor.processed_frames >= state.frame_count):
                        print(f"All frames processed ({state.da3_processor.processed_frames}/{state.frame_count}), exiting processing thread")
                        break
                        
                elif ply_path is None:
                    print(f"Not enough frames for chunk {state.chunk_count}, waiting...")
                
            except Exception as e:
                print(f"Error processing chunk: {e}")
                import traceback
                traceback.print_exc()
                socketio.emit('error', {'message': str(e)})
            
            state.is_processing = False
        else:
            # 如果不需要处理，等待一会
            time.sleep(0.1)
            
            # 检查退出条件：停止捕获且所有帧都已处理
            if (not state.is_running and 
                state.chunk_count > 0 and
                hasattr(state.da3_processor, 'processed_frames') and
                state.da3_processor.processed_frames >= state.frame_count):
                print(f"All frames processed ({state.da3_processor.processed_frames}/{state.frame_count}), exiting processing thread")
                break
    
    print("DA3 processing thread stopped")


@app.route('/api/start', methods=['POST'])
def start_streaming():
    """开始视频流捕获和处理"""
    if state.is_running:
        return jsonify({'error': 'Already running'}), 400
    
    # 如果之前有运行过，先清理旧状态（确保旧线程已停止）
    if state.status != "idle" and state.status != "finished":
        print("Cleaning up previous session before starting new one...")
        # 确保旧线程已停止
        if state.zmq_thread and state.zmq_thread.is_alive():
            print("Waiting for old capture thread to stop...")
            state.zmq_thread.join(timeout=2)
        if state.processing_thread and state.processing_thread.is_alive():
            print("Waiting for old processing thread to stop...")
            state.processing_thread.join(timeout=2)
        
        # 清空队列中的残留数据
        while not state.frame_queue.empty():
            try:
                state.frame_queue.get_nowait()
            except:
                break
    
    data = request.json or {}
    # 如果API请求中没有指定config，使用启动时传入的默认配置
    config_path = data.get('config', state.default_config_path)
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
    state.is_processing = False
    
    # 启动线程
    state.zmq_thread = threading.Thread(target=zmq_capture_thread, args=(zmq_host, zmq_port))
    state.zmq_thread.start()
    
    state.processing_thread = threading.Thread(target=da3_processing_thread)
    state.processing_thread.start()
    
    # 通知前端清空旧的点云（如果存在）
    socketio.emit('clear_pointclouds', {
        'message': 'Starting new scan, clearing old point clouds'
    })
    
    return jsonify({
        'status': 'started',
        'output_dir': state.output_dir,
        'config': config_path
    })


def finalize_and_loop_closure():
    """在后台线程中完成剩余处理和回环优化"""
    print("\n" + "=" * 80)
    print("FINALIZING REALTIME SESSION")
    print("=" * 80)
    
    # 等待处理线程完成所有未处理的chunk
    if state.processing_thread:
        print("\n[Step 1/3] Waiting for processing thread to finish remaining chunks...")
        
        # 计算估算的剩余chunk数
        chunk_size = state.config["Model"]["chunk_size"]
        overlap = state.config["Model"]["overlap"]
        
        if hasattr(state.da3_processor, 'processed_frames'):
            processed_frames = state.da3_processor.processed_frames
            remaining_frames = state.frame_count - processed_frames
            estimated_remaining = max(0, int(remaining_frames / (chunk_size - overlap)))
        else:
            estimated_remaining = 0
        
        print(f"  - Total frames captured: {state.frame_count}")
        print(f"  - Chunks processed: {state.chunk_count}")
        print(f"  - Estimated remaining chunks: {estimated_remaining}")
        
        socketio.emit('processing_remaining', {
            'total_frames': state.frame_count,
            'processed_chunks': state.chunk_count,
            'remaining_chunks': estimated_remaining
        })
        
        state.processing_thread.join()  # 等待所有chunk都处理完成
        print(f"[Step 1/3] All chunks processed! Total chunks: {state.chunk_count}")
    
    state.status = "loop_closure"
    
    # 通知前端开始回环
    print(f"\n[Step 2/3] Starting loop closure optimization...")
    print(f"  - Total chunks: {state.chunk_count}")
    print(f"  - Total frames: {state.frame_count}")
    print(f"  - Frame directory: {state.output_dir}/frames")
    
    socketio.emit('loop_closure_started', {
        'total_chunks': state.chunk_count,
        'total_frames': state.frame_count
    })
    
    # 执行回环优化
    try:
        state.da3_processor.finalize_with_loop_closure()
        
        # 合并所有点云
        print(f"\n[Step 3/3] Finalizing...")
        final_ply_path = os.path.join(state.output_dir, "pcd", "combined_pcd.ply")
        
        if os.path.exists(final_ply_path):
            print(f"  - Final pointcloud saved: {final_ply_path}")
        else:
            print(f"  - Warning: Final pointcloud not found at {final_ply_path}")
        
        socketio.emit('loop_closure_finished', {
            'final_ply_url': f"/pointcloud/final",
            'final_ply_path': final_ply_path
        })
        
        state.status = "finished"
        print("\n" + "=" * 80)
        print("REALTIME SESSION COMPLETED!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\nERROR in loop closure: {e}")
        import traceback
        traceback.print_exc()
        socketio.emit('error', {'message': f"Loop closure error: {str(e)}"})


@app.route('/api/stop', methods=['POST'])
def stop_streaming():
    """停止捕获并开始回环优化"""
    if not state.is_running:
        return jsonify({'error': 'Not running'}), 400
    
    state.is_running = False
    state.status = "finalizing"
    
    # 等待捕获线程结束（这个很快）
    if state.zmq_thread:
        print("Stopping capture thread...")
        state.zmq_thread.join(timeout=5)
        print("Capture thread stopped")
    
    # 在后台线程中完成剩余处理和回环优化，不阻塞API响应
    finalize_thread = threading.Thread(target=finalize_and_loop_closure)
    finalize_thread.start()
    
    # 立即返回响应
    return jsonify({
        'status': 'stopping',
        'message': 'Processing remaining chunks and will start loop closure',
        'total_frames': state.frame_count,
        'total_chunks': state.chunk_count
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取当前状态"""
    # 计算剩余chunk数（如果正在运行）
    remaining_chunks = 0
    if state.config and state.da3_processor:
        chunk_size = state.config["Model"]["chunk_size"]
        overlap = state.config["Model"]["overlap"]
        
        if state.chunk_count == 0 and state.frame_count > 0:
            # 第一个chunk还未处理
            remaining_chunks = max(0, int((state.frame_count - chunk_size) / (chunk_size - overlap)) + 1)
        elif state.chunk_count > 0 and hasattr(state.da3_processor, 'processed_frames'):
            # 已处理的帧数
            processed_frames = state.da3_processor.processed_frames
            remaining_frames = state.frame_count - processed_frames
            # 估算剩余chunk数
            remaining_chunks = max(0, int(remaining_frames / (chunk_size - overlap)))
    
    return jsonify({
        'is_running': state.is_running,
        'is_processing': state.is_processing,
        'status': state.status,
        'frame_count': state.frame_count,
        'chunk_count': state.chunk_count,
        'remaining_chunks': remaining_chunks,
        'output_dir': state.output_dir
    })


@app.route('/api/reset', methods=['POST'])
def reset_all():
    """清空所有状态，为下一次扫描做准备"""
    print("Resetting all state...")
    
    # 如果正在运行，先停止
    if state.is_running:
        state.is_running = False
        state.status = "finalizing"
        
        # 等待捕获线程结束
        if state.zmq_thread and state.zmq_thread.is_alive():
            print("Stopping capture thread...")
            state.zmq_thread.join(timeout=3)
        
        # 等待处理线程结束
        if state.processing_thread and state.processing_thread.is_alive():
            print("Stopping processing thread...")
            state.processing_thread.join(timeout=3)
    
    # 清空队列
    while not state.frame_queue.empty():
        try:
            state.frame_queue.get_nowait()
        except:
            break
    
    # 重置所有状态变量
    state.is_running = False
    state.is_processing = False
    state.frame_count = 0
    state.chunk_count = 0
    state.status = "idle"
    state.da3_processor = None
    state.zmq_thread = None
    state.processing_thread = None
    state.output_dir = None
    # 保留 config 和 zmq_host/zmq_port，方便下次使用
    
    # 通知前端已清空
    socketio.emit('reset_completed', {
        'message': 'All state cleared, ready for next scan'
    })
    
    print("Reset completed")
    
    return jsonify({
        'status': 'reset',
        'message': 'All state cleared successfully'
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
    parser.add_argument('--config', type=str, default='./configs/realtime_config.yaml', 
                       help='Default configuration file path')
    
    args = parser.parse_args()
    
    # 设置默认配置文件路径
    state.default_config_path = args.config
    
    print(f"Starting DA3 Realtime Service on {args.host}:{args.port}")
    print(f"Default config: {args.config}")
    socketio.run(app, host=args.host, port=args.port, debug=False)

