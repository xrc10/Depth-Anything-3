#!/usr/bin/env python3
"""
基于 Viser 的高级点云可视化与目标标注工具
支持实时更新、交互式控制面板
"""

import viser
import numpy as np
import json
import os
from pathlib import Path
import open3d as o3d
import time
import threading

# 配置路径
PLY_PATH = "/home/lh/projects/Depth-Anything-3/da3_streaming/video_output/pcd/combined_pcd.ply"
JSON_PATH = ""

# 颜色映射（为不同的目标类型分配不同的颜色）
OBJECT_COLORS = {
    "Keyboard": (255, 0, 0),      # 红色
    "Bag": (0, 255, 0),           # 绿色
    "Chair": (0, 0, 255),         # 蓝色
    "Plant": (255, 255, 0),       # 黄色
    "Monitor": (255, 0, 255),     # 品红
    "Mouse": (0, 255, 255),       # 青色
    "Desk": (128, 128, 128),      # 灰色
    "default": (255, 128, 0)      # 橙色（默认）
}

class ViserPointCloudViewer:
    """Viser 点云查看器类"""
    
    def __init__(self, ply_path, json_path, port=8080):
        self.ply_path = ply_path
        self.json_path = json_path
        self.port = port
        
        # 创建 Viser 服务器
        self.server = viser.ViserServer(port=port)
        
        # 数据存储
        self.points = None
        self.colors = None
        self.objects = []
        self.last_json_mtime = 0
        
        # 控制参数
        self.show_point_cloud = True
        self.show_objects = True
        self.show_labels = True
        self.show_bbox = False  # 默认不显示边界框
        self.show_grid = True
        self.point_size = 0.002  # 从0.005改为0.002，更小
        self.auto_refresh = True
        
        # GUI 控件
        self.gui_elements = {}
        
    def load_point_cloud(self):
        """加载点云文件"""
        print(f"正在加载点云: {self.ply_path}")
        
        if not os.path.exists(self.ply_path):
            raise FileNotFoundError(f"点云文件不存在: {self.ply_path}")
        
        # 使用 Open3D 加载点云
        pcd = o3d.io.read_point_cloud(self.ply_path)
        
        # 获取点和颜色
        self.points = np.asarray(pcd.points)
        self.colors = np.asarray(pcd.colors) if pcd.has_colors() else None
        
        # 如果没有颜色信息，使用默认灰色
        if self.colors is None:
            self.colors = np.ones_like(self.points) * 0.5
        
        # 下采样点云（如果点太多）
        max_points = 500000
        if len(self.points) > max_points:
            print(f"点云过大，进行下采样: {len(self.points)} -> {max_points}")
            indices = np.random.choice(len(self.points), max_points, replace=False)
            self.points = self.points[indices]
            self.colors = self.colors[indices]
        
        print(f"点云加载完成: {len(self.points)} 个点")
        
    def load_objects_json(self):
        """加载目标信息 JSON"""
        if not os.path.exists(self.json_path):
            print(f"警告: JSON 文件不存在: {self.json_path}")
            return []
        
        try:
            # 检查文件修改时间
            current_mtime = os.path.getmtime(self.json_path)
            if current_mtime == self.last_json_mtime and self.objects:
                return self.objects
            
            self.last_json_mtime = current_mtime
            
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.objects = data.get('objects', [])
            print(f"加载了 {len(self.objects)} 个目标对象")
            return self.objects
        except Exception as e:
            print(f"加载 JSON 失败: {e}")
            return []
    
    def get_object_color(self, object_name):
        """获取目标对象的颜色"""
        return OBJECT_COLORS.get(object_name, OBJECT_COLORS["default"])
    
    def render_point_cloud(self):
        """渲染点云"""
        if self.points is None or not self.show_point_cloud:
            return
        
        try:
            self.server.scene.add_point_cloud(
                name="/point_cloud",
                points=self.points,
                colors=self.colors,
                point_size=self.point_size,
            )
        except Exception as e:
            print(f"渲染点云失败: {e}")
    
    def render_objects(self):
        """渲染目标对象标注"""
        if not self.show_objects:
            return
        
        # 清除旧的对象标注
        for idx in range(len(self.objects)):
            try:
                self.server.scene.remove(f"/object_{idx}/center")
                self.server.scene.remove(f"/object_{idx}/bbox")
                self.server.scene.remove(f"/object_{idx}/label")
            except:
                pass
        
        # 添加新的对象标注
        for idx, obj in enumerate(self.objects):
            object_name = obj.get('object_name', 'Unknown')
            center = obj.get('center', {})
            cx = center.get('x', 0)
            cy = center.get('y', 0)
            cz = center.get('z', 0)
            num_points = obj.get('num_points', 0)
            timestamp = obj.get('timestamp', 'N/A')
            
            # 获取颜色
            color = self.get_object_color(object_name)
            
            # 添加球体标记中心点（更小的标注点）
            self.server.scene.add_icosphere(
                name=f"/object_{idx}/center",
                radius=0.02,  # 从0.05改为0.02，更小
                color=color,
                position=(cx, cy, cz),
            )
            
            # 根据点数估算边界框大小
            box_size = (num_points / 10000) ** (1/3) * 0.3
            box_size = max(0.1, min(box_size, 0.5))
            
            # 添加边界框
            if self.show_bbox:
                self.server.scene.add_box(
                    name=f"/object_{idx}/bbox",
                    dimensions=(box_size, box_size, box_size),
                    color=color,
                    position=(cx, cy, cz),
                    wireframe=True,
                )
            
            # 添加文本标签（只显示目标名称）
            if self.show_labels:
                label_text = object_name  # 只显示名称
                self.server.scene.add_label(
                    name=f"/object_{idx}/label",
                    text=label_text,
                    position=(cx, cy, cz + 0.08),  # 调整标签位置
                )
    
    def setup_gui(self):
        """设置GUI控制面板"""
        with self.server.gui.add_folder("显示控制"):
            # 点云显示开关
            self.gui_elements['show_pcd'] = self.server.gui.add_checkbox(
                "显示点云",
                initial_value=self.show_point_cloud
            )
            
            # 点大小滑块
            self.gui_elements['point_size'] = self.server.gui.add_slider(
                "点大小",
                min=0.001,
                max=0.02,
                step=0.001,
                initial_value=self.point_size
            )
            
            # 对象显示开关
            self.gui_elements['show_objects'] = self.server.gui.add_checkbox(
                "显示目标对象",
                initial_value=self.show_objects
            )
            
            # 边界框显示开关
            self.gui_elements['show_bbox'] = self.server.gui.add_checkbox(
                "显示边界框",
                initial_value=self.show_bbox
            )
            
            # 标签显示开关
            self.gui_elements['show_labels'] = self.server.gui.add_checkbox(
                "显示标签",
                initial_value=self.show_labels
            )
            
            # 网格显示开关
            self.gui_elements['show_grid'] = self.server.gui.add_checkbox(
                "显示网格",
                initial_value=self.show_grid
            )
        
        with self.server.gui.add_folder("数据信息"):
            # 显示点云信息
            self.gui_elements['pcd_info'] = self.server.gui.add_text(
                "点云信息",
                initial_value=f"点数: {len(self.points) if self.points is not None else 0}",
                disabled=True
            )
            
            # 显示对象数量
            self.gui_elements['obj_count'] = self.server.gui.add_text(
                "目标数量",
                initial_value=f"对象: {len(self.objects)}",
                disabled=True
            )
        
        with self.server.gui.add_folder("操作"):
            # 刷新按钮
            self.gui_elements['refresh_btn'] = self.server.gui.add_button("刷新数据")
            
            # 自动刷新开关
            self.gui_elements['auto_refresh'] = self.server.gui.add_checkbox(
                "自动刷新 (5秒)",
                initial_value=self.auto_refresh
            )
        
        # 设置回调函数
        @self.gui_elements['show_pcd'].on_update
        def _(_):
            self.show_point_cloud = self.gui_elements['show_pcd'].value
            if self.show_point_cloud:
                self.render_point_cloud()
            else:
                try:
                    self.server.scene.remove("/point_cloud")
                except:
                    pass
        
        @self.gui_elements['point_size'].on_update
        def _(_):
            self.point_size = self.gui_elements['point_size'].value
            if self.show_point_cloud:
                self.render_point_cloud()
        
        @self.gui_elements['show_objects'].on_update
        def _(_):
            self.show_objects = self.gui_elements['show_objects'].value
            self.render_objects()
        
        @self.gui_elements['show_bbox'].on_update
        def _(_):
            self.show_bbox = self.gui_elements['show_bbox'].value
            self.render_objects()
        
        @self.gui_elements['show_labels'].on_update
        def _(_):
            self.show_labels = self.gui_elements['show_labels'].value
            self.render_objects()
        
        @self.gui_elements['show_grid'].on_update
        def _(_):
            self.show_grid = self.gui_elements['show_grid'].value
            if self.show_grid:
                self.render_grid()
            else:
                try:
                    self.server.scene.remove("/grid")
                except:
                    pass
        
        @self.gui_elements['refresh_btn'].on_click
        def _(_):
            print("手动刷新数据...")
            self.refresh_data()
        
        @self.gui_elements['auto_refresh'].on_update
        def _(_):
            self.auto_refresh = self.gui_elements['auto_refresh'].value
    
    def render_grid(self):
        """渲染网格"""
        if not self.show_grid:
            return
        
        self.server.scene.add_grid(
            name="/grid",
            width=10.0,
            height=10.0,
            width_segments=20,
            height_segments=20,
            plane="xz",
            cell_color=(200, 200, 200),
            cell_thickness=1.0,
            cell_size=0.5,
        )
    
    def render_coordinate_frame(self):
        """渲染坐标系"""
        self.server.scene.add_frame(
            name="/world",
            axes_length=0.5,
            axes_radius=0.01,
        )
    
    def refresh_data(self):
        """刷新数据"""
        # 重新加载对象
        self.load_objects_json()
        
        # 更新GUI信息
        if 'obj_count' in self.gui_elements:
            self.gui_elements['obj_count'].value = f"对象: {len(self.objects)}"
        
        # 重新渲染对象
        self.render_objects()
        
        print(f"数据已刷新 - 当前有 {len(self.objects)} 个目标对象")
    
    def auto_refresh_loop(self):
        """自动刷新循环"""
        while True:
            time.sleep(5)  # 每5秒检查一次
            if self.auto_refresh:
                try:
                    self.refresh_data()
                except Exception as e:
                    print(f"自动刷新失败: {e}")
    
    def run(self):
        """运行可视化"""
        print("=" * 60)
        print("Viser 高级点云可视化与目标标注工具")
        print("=" * 60)
        
        # 加载点云
        try:
            self.load_point_cloud()
        except Exception as e:
            print(f"❌ 加载点云失败: {e}")
            return
        
        # 加载目标对象
        self.load_objects_json()
        
        # 渲染场景
        print("\n正在渲染场景...")
        self.render_point_cloud()
        self.render_objects()
        self.render_grid()
        self.render_coordinate_frame()
        
        # 设置GUI
        print("正在设置控制面板...")
        self.setup_gui()
        
        # 启动自动刷新线程
        refresh_thread = threading.Thread(target=self.auto_refresh_loop, daemon=True)
        refresh_thread.start()
        
        print("\n" + "=" * 60)
        print("✅ 可视化准备完成！")
        print(f"📊 点云: {len(self.points)} 个点")
        print(f"🎯 目标: {len(self.objects)} 个对象")
        print(f"🌐 访问: http://localhost:{self.port}")
        print("=" * 60)
        print("\n功能说明:")
        print("  • 左侧面板可以控制显示选项")
        print("  • 支持自动刷新 object.json (每5秒)")
        print("  • 点击'刷新数据'按钮手动刷新")
        print("\n按 Ctrl+C 退出...")
        
        # 保持服务器运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 服务器已关闭")

def main():
    """主函数"""
    viewer = ViserPointCloudViewer(
        ply_path=PLY_PATH,
        json_path=JSON_PATH,
        port=8080
    )
    viewer.run()

if __name__ == "__main__":
    main()
