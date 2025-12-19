# 🚀 DA3 实时点云重建 - 快速开始

## 立即开始 (3分钟)

### 1️⃣ 环境检查
```bash
cd /home/xu_ruochen/Depth-Anything-3/da3_streaming
python3 test_realtime_system.py
```

期望输出：
```
🎉 所有关键测试通过！系统已准备就绪。
```

如果有错误，安装依赖：
```bash
pip3 install -r requirements_realtime.txt
```

### 2️⃣ 启动视频流

**从视频文件：**
```bash
python3 rgb_zmq_publisher.py --source your_video.mp4 --port 5555
```

**从摄像头：**
```bash
python3 rgb_zmq_publisher.py --source 0 --port 5555
```

### 3️⃣ 启动DA3服务
```bash
bash start_realtime_demo.sh
```

### 4️⃣ 打开浏览器
```
http://localhost:5000
```

### 5️⃣ 开始扫描
1. 点击 "开始扫描"
2. 观察实时点云生成
3. 完成后点击 "停止并回环优化"
4. 查看最终结果！

---

## 📁 已创建的文件

```
da3_streaming/
├── 🔧 核心服务
│   ├── da3_realtime_service.py       (9.4KB)  ← Flask服务端
│   └── da3_streaming_realtime.py     (13KB)   ← 实时处理类
│
├── 🎨 前端界面  
│   └── templates/index.html          (23KB)   ← Three.js渲染
│
├── ⚙️ 配置和依赖
│   ├── configs/realtime_config.yaml  (1.3KB)  ← 配置文件
│   └── requirements_realtime.txt     (230B)   ← Python依赖
│
├── 🚀 脚本工具
│   ├── start_realtime_demo.sh        (982B)   ← 启动脚本
│   └── test_realtime_system.py       (6.7KB)  ← 测试工具
│
└── 📚 文档
    ├── README_REALTIME.md            (6.7KB)  ← API文档
    ├── USAGE_CN.md                   (9.9KB)  ← 使用指南
    ├── REALTIME_SYSTEM_SUMMARY.md    (11KB)   ← 系统总结
    └── QUICKSTART.md                          ← 本文件
```

---

## 🎯 系统功能

✅ **实时视频流处理** - 从ZMQ订阅视频流  
✅ **增量点云生成** - 每40帧自动处理  
✅ **实时3D渲染** - Three.js流畅渲染  
✅ **回环优化** - 自动全局一致性优化  
✅ **现代UI** - 美观的渐变色界面  

---

## 🖱️ 网页操作

### 鼠标控制
- **左键拖动** → 旋转视角
- **右键拖动** → 平移视角  
- **滚轮** → 缩放

### 按钮
- **开始扫描** → 启动视频流接收和处理
- **停止并回环优化** → 完成扫描并优化

---

## 📊 实时状态

网页左侧面板显示：
- 📍 **状态**: 空闲/捕获中/处理中/回环优化/完成
- 📸 **已捕获帧数**: 实时更新
- 📦 **已处理块**: chunk计数
- 🎨 **点云数量**: 当前显示的点数

---

## 📂 输出结果

结果保存在：
```
exps/realtime/YYYY-MM-DD-HH-MM-SS/
├── frames/          ← 捕获的所有帧
├── pcd/
│   ├── 0_pcd.ply   ← 第1个chunk的点云
│   ├── 1_pcd.ply   ← 第2个chunk的点云
│   ├── ...
│   └── combined_pcd.ply  ← 最终合并的点云
└── _tmp_*           ← 临时文件
```

使用CloudCompare或MeshLab查看点云：
```bash
# CloudCompare
cloudcompare.CloudCompare exps/realtime/*/pcd/combined_pcd.ply

# MeshLab
meshlab exps/realtime/*/pcd/combined_pcd.ply
```

---

## ⚡ 性能调优

### 快速响应模式
编辑 `configs/realtime_config.yaml`:
```yaml
chunk_size: 20      # 减小chunk
overlap: 5          # 减小重叠
sample_ratio: 0.01  # 稀疏点云
loop_enable: False  # 关闭回环
```

### 高质量模式
```yaml
chunk_size: 60      # 增大chunk
overlap: 20         # 增大重叠
sample_ratio: 0.1   # 密集点云
loop_enable: True   # 启用回环
```

---

## ❓ 常见问题

### Q: 无法接收视频流？
**A:** 检查ZMQ发布器是否运行，端口是否正确（默认5555）

### Q: 处理速度慢？
**A:** 确认GPU可用，减小chunk_size，关闭其他GPU程序

### Q: 点云渲染卡顿？
**A:** 降低sample_ratio，减小浏览器窗口

### Q: 网页空白？
**A:** 检查浏览器控制台(F12)，清除缓存，换浏览器

---

## 🔍 调试

### 查看日志
服务端输出会显示实时状态和错误信息

### 测试ZMQ连接
```bash
python3 capture_from_zmq.py --host 127.0.0.1 --port 5555 --output test.jpg
```

### 浏览器调试
按F12打开开发者工具，查看：
- Console → JavaScript错误
- Network → API请求
- WebSocket → 实时消息

---

## 📚 更多文档

- **详细使用**: `USAGE_CN.md`
- **API文档**: `README_REALTIME.md`
- **系统总结**: `REALTIME_SYSTEM_SUMMARY.md`

---

## 🎉 开始体验

```bash
# 一键启动！
bash start_realtime_demo.sh
```

然后打开浏览器访问 `http://localhost:5000`

**祝你玩得开心！** 🚀

---

<p align="center">
  <strong>DA3 实时点云重建系统</strong><br>
  实时 · 增量 · 交互式
</p>

