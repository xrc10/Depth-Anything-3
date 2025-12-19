# coding=utf-8
import argparse
import base64
import json

import cv2
import numpy as np
import zmq


def main():
    parser = argparse.ArgumentParser(
        description="Capture a single image from rgb_zmq_publisher.py stream"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="发布端所在主机 IP（默认 127.0.0.1）"
    )
    parser.add_argument(
        "--port", type=int, default=5555,
        help="发布端使用的端口（需与 rgb_zmq_publisher.py 一致）"
    )
    parser.add_argument(
        "--output", type=str, default="capture.jpg",
        help="保存图片的路径"
    )
    parser.add_argument(
        "--timeout", type=int, default=5000,
        help="接收超时时间（毫秒），默认 5000ms"
    )
    args = parser.parse_args()

    # --- ZeroMQ SUB 端初始化 ---
    context = zmq.Context()
    socket = context.socket(zmq.SUB)

    addr = f"tcp://{args.host}:{args.port}"
    print(f"Connecting to publisher at {addr} ...")
    socket.connect(addr)

    # 订阅所有消息（空字符串）
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    # 设置接收超时（毫秒）
    socket.setsockopt(zmq.RCVTIMEO, args.timeout)

    try:
        # 接收一条消息（字符串）
        msg_str = socket.recv_string()
        print("Message received from publisher.")

        # 解析 JSON
        data = json.loads(msg_str)
        timestamp = data.get("timestamp", None)
        img_b64 = data["image"]

        # base64 -> bytes
        img_bytes = base64.b64decode(img_b64)

        # bytes -> numpy 数组 -> OpenCV 图像
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is None:
            print("解码 JPEG 失败，未能获得有效图像。")
            return

        # 保存到文件
        cv2.imwrite(args.output, img)
        print(f"保存成功: {args.output}")
        if timestamp is not None:
            print(f"图像时间戳: {timestamp}")

    except zmq.error.Again:
        print(f"在 {args.timeout} ms 内未收到任何图像。")
    finally:
        socket.close()
        context.term()


if __name__ == "__main__":
    main()