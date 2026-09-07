#!/usr/bin/env python3
"""
image_compress.py - Pillow 压缩图片到目标 KB。

# 使用示例

  python3 image_compress.py \\
    /tmp/in.png /tmp/out.jpg \\
    --target-kb 200

# 策略

  1. 若传 target_width/target_height，先按 cover 居中裁切到目标尺寸
  2. 再转 JPG（去 alpha），初始 quality=85
  3. 若 >= target_kb，逐步降 quality 步长 5，直到达标 / quality 降到 60
  4. 指定目标尺寸时保持像素不变，quality=60 仍超限则报错
  5. 未指定尺寸时允许等比缩小 0.9 倍，最多 10 轮；仍超限则报错
  6. 按 1KB = 1024 字节计算，严格小于上限；仅达标后原子写入输出

# 退出码

  0: 成功
  1: 输入文件不存在 / 不可读
  2: 压缩失败（尺寸非法或最终仍超上限）
"""

import argparse
import io
import os
import sys
import tempfile
from typing import Optional

try:
    from PIL import Image
except ImportError:
    print("❌ 需要安装 Pillow：pip install Pillow", file=sys.stderr)
    sys.exit(1)


def resize_cover(img: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """Resize to cover target dimensions, then center-crop exactly."""
    if target_width <= 0 or target_height <= 0:
        raise ValueError("target width/height must be positive")
    scale = max(target_width / img.width, target_height / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def compress(
    input_path: str,
    output_path: str,
    target_kb: int = 200,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
) -> str:
    """压缩到目标 KB。返回最终输出路径。"""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    if target_kb <= 0:
        raise ValueError("target KB must be positive")
    if (target_width is None) != (target_height is None):
        raise ValueError("target width and height must be provided together")
    fixed_size = target_width is not None
    with Image.open(input_path) as source:
        img = source.convert("RGB")
    if fixed_size:
        img = resize_cover(img, target_width, target_height)

    for round_no in range(1 if fixed_size else 10):
        scale = 0.9 ** round_no
        scaled = img if round_no == 0 else img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS
        )
        for quality in range(85, 59, -5):
            buffer = io.BytesIO()
            scaled.save(buffer, "JPEG", quality=quality, optimize=True)
            payload = buffer.getvalue()
            if len(payload) < target_kb * 1024:
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        dir=os.path.dirname(os.path.abspath(output_path)), delete=False
                    ) as temp:
                        temp_path = temp.name
                        temp.write(payload)
                    os.replace(temp_path, output_path)
                finally:
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                print(f"✅ {input_path} → {output_path} ({scaled.width}x{scaled.height}, {len(payload) / 1024:.1f} KB, q={quality})")
                return output_path

    raise ValueError(
        f"Cannot compress image below {target_kb} KB at quality >= 60"
        + (f" while preserving {target_width}x{target_height}" if fixed_size else " after 10 rounds")
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="输入图片路径")
    parser.add_argument("output", help="输出图片路径（.jpg）")
    parser.add_argument("--target-kb", type=int, default=200, help="目标大小（KB）")
    parser.add_argument("--target-width", type=int, help="导出目标宽度")
    parser.add_argument("--target-height", type=int, help="导出目标高度")
    args = parser.parse_args()

    try:
        compress(args.input, args.output, args.target_kb, args.target_width, args.target_height)
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"🔴 {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"🔴 压缩失败：{e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
