# DA3 实时点云重建系统 - 使用指南

## 📋 目录

1. [系统简介](#系统简介)
2. [环境准备](#环境准备)
3. [快速开始](#快速开始)
4. [详细使用流程](#详细使用流程)
5. [配置说明](#配置说明)
6. [常见问题](#常见问题)
7. [性能优化](#性能优化)

## 🎯 系统简介

这是一个完整的**实时3D点云重建演示系统**，具有以下特点：

- ✅ **实时处理**: 从视频流实时捕获并处理
- ✅ **增量渲染**: 处理完成的chunk立即显示
- ✅ **交互式3D视图**: 使用Three.js实现流畅的3D交互
- ✅ **回环优化**: 自动进行全局一致性优化
- ✅ **现代UI**: 美观的渐变色界面设计

## 🔧 环境准备

### 1. 系统要求

- **操作系统**: Linux / macOS / Windows (WSL)
- **Python**: 3.8+
- **GPU**: NVIDIA GPU (推荐，CUDA 11.0+)
- **内存**: 8GB+ (推荐16GB+)
- **浏览器**: Chrome / Firefox / Edge (支持WebGL)

### 2. 安装依赖

```bash
cd /home/xu_ruochen/Depth-Anything-3/da3_streaming

# 安装Python依赖
pip3 install -r requirements_realtime.txt

# 或使用conda
conda install --file requirements_realtime.txt
```

### 3. 下载模型权重

确保以下文件存在：

```
weights/
├── model.safetensors        # DA3模型权重
├── config.json              # DA3配置
└── dino_salad.ckpt         # SALAD回环检测权重（如果启用loop）
```

如果使用软链接：

```bash
ln -s ~/projects/Depth-Anything-3/da3_streaming/da3_small_weights weights
```

### 4. 环境检查

运行测试脚本检查环境：

```bash
python3 test_realtime_system.py
```

如果所有检查都通过，你会看到：

```
🎉 所有关键测试通过！系统已准备就绪。
```

## 🚀 快速开始

### 方法一：使用启动脚本（推荐）

```bash
bash start_realtime_demo.sh
```

### 方法二：手动启动

```bash
python3 da3_realtime_service.py --host 0.0.0.0 --port 5000
```

### 访问网页

在浏览器中打开：

```
http://localhost:5000
```

## 📖 详细使用流程

### 步骤1: 启动视频流发布器

首先需要运行一个ZMQ视频流发布器。你可以使用 `rgb_zmq_publisher.py`：

```bash
# 从视频文件发布
python3 rgb_zmq_publisher.py --source video.mp4 --port 5555

# 从摄像头发布
python3 rgb_zmq_publisher.py --source 0 --port 5555

# 从图片序列发布
python3 rgb_zmq_publisher.py --source ./images/ --port 5555
```

### 步骤2: 启动DA3服务

```bash
bash start_realtime_demo.sh
```

服务启动后会显示：

```
========================================
  DA3 实时点云重建演示系统
========================================

配置信息:
  服务地址: http://0.0.0.0:5000
  配置文件: ./configs/realtime_config.yaml

启动服务...
```

### 步骤3: 打开网页界面

在浏览器中访问 `http://localhost:5000`，你会看到：

- **左侧控制面板**: 显示状态和控制按钮
- **中央3D视图**: 实时渲染的点云
- **底部提示**: 操作说明

### 步骤4: 配置和启动

1. **配置ZMQ连接**:
   - ZMQ主机: 默认 `127.0.0.1`（本地）
   - ZMQ端口: 默认 `5555`（需与发布器一致）

2. **点击"开始扫描"**:
   - 系统开始接收视频流
   - 状态变为"捕获中"
   - 帧计数实时更新

3. **观察处理过程**:
   - 每达到`chunk_size`（默认40帧）后自动处理
   - 处理完成后，点云增量显示在3D视图中
   - 可以使用鼠标交互：
     - **左键拖动**: 旋转视角
     - **右键拖动**: 平移视角
     - **滚轮**: 缩放

### 步骤5: 完成扫描

当扫描完成后：

1. **点击"停止并回环优化"**
2. 系统停止捕获视频流
3. 自动执行回环检测和优化（如果启用）
4. 优化完成后，显示最终修正的点云

### 步骤6: 查看结果

结果保存在 `exps/realtime/YYYY-MM-DD-HH-MM-SS/` 目录下：

```
exps/realtime/2025-12-18-16-30-00/
├── frames/                    # 捕获的所有帧
│   ├── frame_000000.jpg
│   ├── frame_000001.jpg
│   └── ...
├── pcd/                       # 生成的点云
│   ├── 0_pcd.ply
│   ├── 1_pcd.ply
│   ├── ...
│   └── combined_pcd.ply      # 最终合并的点云
└── _tmp_*/                    # 临时文件
```

你可以使用CloudCompare、MeshLab等工具查看点云文件。

## ⚙️ 配置说明

配置文件位于 `configs/realtime_config.yaml`。

### 关键配置项

#### 处理参数

```yaml
Model:
  chunk_size: 40        # 每个chunk的帧数
                        # 越大：内存占用越高，处理间隔越长
                        # 越小：更快看到结果，但对齐次数更多
  
  overlap: 10           # chunk间重叠帧数
                        # 用于相邻chunk的对齐
                        # 建议: chunk_size的20-30%
  
  loop_enable: True     # 是否启用回环检测
                        # True: 更好的全局一致性，但耗时更长
                        # False: 更快完成，但可能有累积误差
```

#### 点云保存

```yaml
Pointcloud_Save:
  sample_ratio: 0.05           # 点云采样率（0.01-1.0）
                               # 越大：点云越密集，文件越大
                               # 越小：点云越稀疏，文件越小
  
  conf_threshold_coef: 0.6     # 置信度阈值系数
                               # 只保留高置信度的点
                               # 建议: 0.5-0.8
```

#### 对齐方法

```yaml
Model:
  align_lib: 'torch'           # 对齐库
                               # 'torch': GPU加速，兼容性好
                               # 'triton': 最快，需要支持
                               # 'numba': CPU，较慢
  
  align_method: 'scale+se3'    # 对齐方法
                               # 'sim3': 7自由度
                               # 'se3': 6自由度（无尺度）
                               # 'scale+se3': 分离尺度和SE3
```

### 针对不同场景的配置建议

#### 小型室内场景

```yaml
chunk_size: 30
overlap: 10
sample_ratio: 0.1      # 密集点云
```

#### 大型室外场景

```yaml
chunk_size: 60
overlap: 20
sample_ratio: 0.02     # 稀疏点云
loop_enable: True      # 必须启用
```

#### 快速预览模式

```yaml
chunk_size: 20
overlap: 5
sample_ratio: 0.01
loop_enable: False
```

## ❓ 常见问题

### Q1: 无法接收ZMQ视频流

**症状**: 帧计数一直是0

**解决方案**:
1. 确认ZMQ发布器正在运行
2. 检查主机地址和端口是否正确
3. 测试ZMQ连接：
   ```bash
   python3 capture_from_zmq.py --host 127.0.0.1 --port 5555
   ```
4. 检查防火墙设置

### Q2: 处理速度很慢

**症状**: 每个chunk处理时间超过30秒

**解决方案**:
1. 确认GPU可用：
   ```python
   import torch
   print(torch.cuda.is_available())  # 应该是True
   ```
2. 减小`chunk_size`（例如改为20）
3. 检查GPU显存是否充足
4. 关闭其他占用GPU的程序

### Q3: 点云渲染卡顿

**症状**: 浏览器中3D视图不流畅

**解决方案**:
1. 降低`sample_ratio`（例如改为0.01）
2. 减小浏览器窗口大小
3. 使用更快的GPU或减少点数
4. 关闭浏览器的其他标签页

### Q4: 回环优化失败

**症状**: 停止后一直处于"回环优化"状态

**解决方案**:
1. 检查是否有足够的重叠区域
2. 查看服务端日志中的错误信息
3. 如果场景没有回环，设置`loop_enable: False`
4. 确认SALAD权重文件存在

### Q5: 内存不足

**症状**: 程序崩溃或系统卡顿

**解决方案**:
1. 减小`chunk_size`
2. 降低`sample_ratio`
3. 增加系统swap空间
4. 升级内存

### Q6: 网页显示空白

**症状**: 打开网页后是空白的

**解决方案**:
1. 检查浏览器控制台的错误信息（F12）
2. 确认模板文件存在：`templates/index.html`
3. 清除浏览器缓存
4. 尝试其他浏览器

## 🚀 性能优化

### GPU优化

```yaml
# 使用Triton（如果支持）
align_lib: 'triton'

# 使用bfloat16（需要GPU支持）
# 在da3_streaming_realtime.py中会自动检测
```

### 内存优化

```yaml
# 减小chunk大小
chunk_size: 30

# 降低采样率
sample_ratio: 0.02

# 减小batch size
batch_size: 8
```

### 实时性优化

```yaml
# 小chunk快速响应
chunk_size: 20
overlap: 5

# 使用较快的对齐方法
align_method: 'se3'  # 比sim3快

# 关闭回环（如果不需要）
loop_enable: False
```

### 质量优化

```yaml
# 大chunk更好的对齐
chunk_size: 60
overlap: 20

# 高密度点云
sample_ratio: 0.1

# 启用回环
loop_enable: True
```

## 📊 性能基准

以下是在不同配置下的性能参考（NVIDIA RTX 3090）：

| 配置 | Chunk Size | 处理时间/Chunk | 内存占用 | 适用场景 |
|------|-----------|---------------|---------|---------|
| 快速 | 20 | ~5s | ~4GB | 快速预览 |
| 标准 | 40 | ~10s | ~6GB | 一般场景 |
| 高质量 | 60 | ~15s | ~8GB | 精细重建 |

## 🎓 进阶使用

### 编程接口

你可以通过Python代码直接调用DA3处理：

```python
from da3_streaming_realtime import DA3_Streaming_Realtime
from loop_utils.config_utils import load_config

config = load_config('./configs/realtime_config.yaml')

processor = DA3_Streaming_Realtime(
    frame_dir='./frames',
    save_dir='./output',
    config=config
)

# 处理下一个chunk
ply_path = processor.process_next_chunk()

# 完成并执行回环
processor.finalize_with_loop_closure()
```

### REST API

你也可以通过HTTP API控制系统：

```bash
# 开始
curl -X POST http://localhost:5000/api/start \
  -H "Content-Type: application/json" \
  -d '{"zmq_host": "127.0.0.1", "zmq_port": 5555}'

# 查询状态
curl http://localhost:5000/api/status

# 停止
curl -X POST http://localhost:5000/api/stop
```

## 📞 支持

如果遇到问题：

1. 运行环境检查：`python3 test_realtime_system.py`
2. 查看服务端日志输出
3. 查看浏览器控制台（F12）
4. 参考 [README_REALTIME.md](README_REALTIME.md)

## 📄 许可证

Apache License 2.0

---

**祝你使用愉快！🎉**

