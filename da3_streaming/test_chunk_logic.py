#!/usr/bin/env python3
# coding=utf-8
"""
测试chunk处理逻辑
"""

def test_chunk_logic():
    """测试chunk触发逻辑"""
    chunk_size = 120
    overlap = 60
    
    print("=" * 60)
    print("测试chunk处理逻辑")
    print(f"chunk_size = {chunk_size}, overlap = {overlap}")
    print("=" * 60)
    
    chunk_count = 0
    processed_frames = 0
    
    # 模拟接收帧的过程
    for total_frames in range(1, 301):
        # 检查是否应该处理chunk
        if chunk_count == 0:
            required_frames = chunk_size
        else:
            required_frames = processed_frames - overlap + chunk_size
        
        if total_frames >= required_frames:
            # 计算chunk范围
            if chunk_count == 0:
                start_idx = 0
                end_idx = chunk_size
            else:
                start_idx = processed_frames - overlap
                end_idx = start_idx + chunk_size
            
            # 检查是否有足够的帧
            if total_frames >= end_idx:
                print(f"\n[帧 {total_frames}] 触发处理 Chunk {chunk_count}")
                print(f"  - 范围: [{start_idx}:{end_idx}]")
                print(f"  - 需要帧数: {required_frames}")
                print(f"  - 当前总帧数: {total_frames}")
                
                # 更新状态
                processed_frames = end_idx
                chunk_count += 1
                
                # 计算下次触发时机
                if chunk_count > 0:
                    next_required = processed_frames - overlap + chunk_size
                    print(f"  - 下次将在第 {next_required} 帧时处理")
    
    print("\n" + "=" * 60)
    print(f"总共处理了 {chunk_count} 个chunk")
    print("=" * 60)


def test_chunk_logic_detailed():
    """详细测试每一帧的判断"""
    chunk_size = 120
    overlap = 60
    
    print("\n" + "=" * 60)
    print("详细测试: 显示关键帧的判断")
    print("=" * 60)
    
    chunk_count = 0
    processed_frames = 0
    
    # 只显示关键帧附近的情况
    key_frames = [118, 119, 120, 121, 178, 179, 180, 181, 238, 239, 240, 241]
    
    for total_frames in range(1, 301):
        # 检查是否应该处理chunk
        if chunk_count == 0:
            required_frames = chunk_size
        else:
            required_frames = processed_frames - overlap + chunk_size
        
        should_process = total_frames >= required_frames
        
        # 只显示关键帧
        if total_frames in key_frames:
            status = "✓ 可以处理" if should_process else "✗ 等待更多帧"
            print(f"帧 {total_frames:3d}: chunk={chunk_count}, processed={processed_frames:3d}, required={required_frames:3d} -> {status}")
        
        # 实际处理
        if should_process:
            if chunk_count == 0:
                start_idx = 0
                end_idx = chunk_size
            else:
                start_idx = processed_frames - overlap
                end_idx = start_idx + chunk_size
            
            if total_frames >= end_idx:
                if total_frames not in key_frames:
                    print(f"帧 {total_frames:3d}: 🎯 处理 Chunk {chunk_count} (范围: [{start_idx}:{end_idx}])")
                else:
                    print(f"    └─> 🎯 处理 Chunk {chunk_count} (范围: [{start_idx}:{end_idx}])")
                
                processed_frames = end_idx
                chunk_count += 1


if __name__ == '__main__':
    test_chunk_logic()
    test_chunk_logic_detailed()
    
    print("\n" + "=" * 60)
    print("预期结果:")
    print("  - Chunk 0 在第 120 帧处理 (范围: [0:120])")
    print("  - Chunk 1 在第 180 帧处理 (范围: [60:180])")
    print("  - Chunk 2 在第 240 帧处理 (范围: [120:240])")
    print("  - 依此类推...")
    print("=" * 60)

