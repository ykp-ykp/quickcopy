# -*- coding: utf-8 -*-
"""生成应用图标：app.png（运行时托盘/窗口用）+ app.ico（exe 文件图标用）。

仅打包前需要运行一次：python make_icon.py
风格与旧版代码绘制图标一致：蓝色圆角方块 + 白色 QC 字样。
小尺寸（16/32）去掉文字，避免缩成一团看不清。
"""

import os

from PIL import Image, ImageDraw, ImageFont

BLUE = "#5b7fff"
FONT_PATH = r"C:\Windows\Fonts\arialbd.ttf"


def draw_icon(size, with_text=True):
    """4 倍超采样绘制后缩小，保证边缘平滑。"""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = int(s * 0.06)
    radius = int(s * 0.22)
    d.rounded_rectangle(
        [margin, margin, s - margin, s - margin], radius=radius, fill=BLUE)
    if with_text:
        try:
            font = ImageFont.truetype(FONT_PATH, int(s * 0.42))
        except OSError:
            font = ImageFont.load_default()
        d.text((s / 2, s / 2), "QC", font=font, fill="#ffffff", anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    img256 = draw_icon(256)
    img256.save(os.path.join(here, "app.png"))

    small_no_text = [32, 16]
    variants = [img256, draw_icon(48)]
    variants += [draw_icon(n, with_text=False) for n in small_no_text]
    variants[0].save(
        os.path.join(here, "app.ico"), format="ICO",
        append_images=variants[1:])

    # 回读验证 ico 内嵌尺寸
    ico = Image.open(os.path.join(here, "app.ico"))
    print("app.ico sizes:", sorted(ico.ico.sizes(), reverse=True))
    print("app.png:", img256.size)


if __name__ == "__main__":
    main()
