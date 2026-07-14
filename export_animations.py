# -*- coding: utf-8 -*-
"""把 spritesheet.webp 按动作导出为独立动图（透明 WebP + GIF）。

用法:  python export_animations.py [--scale 2] [--fps 8]
输出:  exports/<动作名>.webp 和 exports/<动作名>.gif
"""
import argparse
import os
from PIL import Image

SHEET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spritesheet.webp")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
CELL_W, CELL_H = 192, 208

# 每个动作: (行号, 帧数)
ANIMATIONS = {
    "idle":       (0, 7),   # 待机
    "walk-right": (1, 8),   # 向右走
    "walk-left":  (2, 8),   # 向左走
    "wave":       (3, 4),   # 挥手
    "jump":       (4, 5),   # 跳跃
    "failed":     (5, 8),   # 失落
    "waiting":    (6, 6),   # 耸肩等待
    "working":    (7, 6),   # 思考工作
    "checking":   (8, 6),   # 疲惫检查
    "observe-a":  (9, 8),   # 张望（组1）
    "observe-b":  (10, 8),  # 张望（组2）
}


def extract_frames(sheet, row, count, scale):
    frames = []
    for i in range(count):
        cell = sheet.crop((i * CELL_W, row * CELL_H, (i + 1) * CELL_W, (row + 1) * CELL_H))
        if scale != 1:
            cell = cell.resize((int(CELL_W * scale), int(CELL_H * scale)), Image.NEAREST)
        frames.append(cell)
    return frames


def to_gif_frame(im):
    # GIF 只支持 1 位透明：alpha < 128 的像素置为透明索引 255
    alpha = im.getchannel("A")
    pal = im.convert("RGB").quantize(colors=255, method=Image.MEDIANCUT)
    mask = alpha.point(lambda a: 255 if a < 128 else 0)
    pal.paste(255, mask)
    return pal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0, help="放大倍数（像素风建议整数倍）")
    ap.add_argument("--fps", type=float, default=8.0, help="播放帧率")
    args = ap.parse_args()

    duration = int(round(1000 / args.fps))
    os.makedirs(OUT_DIR, exist_ok=True)
    sheet = Image.open(SHEET).convert("RGBA")

    for name, (row, count) in ANIMATIONS.items():
        frames = extract_frames(sheet, row, count, args.scale)

        webp_path = os.path.join(OUT_DIR, f"{name}.webp")
        frames[0].save(webp_path, save_all=True, append_images=frames[1:],
                       duration=duration, loop=0, lossless=True)

        gif_frames = [to_gif_frame(f) for f in frames]
        gif_path = os.path.join(OUT_DIR, f"{name}.gif")
        gif_frames[0].save(gif_path, save_all=True, append_images=gif_frames[1:],
                           duration=duration, loop=0, disposal=2, transparency=255)

        print(f"{name:12s} {count} 帧 -> {os.path.basename(webp_path)}, {os.path.basename(gif_path)}")

    print(f"\n完成，输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
