from PIL import Image
import math
import os

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 设置输入输出路径为相对路径
img_path = os.path.join(current_dir, "sample.jpg")
output_path = os.path.join(current_dir, "sample_rotate.gif")

# 打开图片
img = Image.open(img_path).convert("RGBA")

# 将RGBA转换为支持透明的P模式
def rgba_to_p_with_transparency(image):
    # 将RGBA图像转换为P模式，保持透明度
    # 将透明像素设为特定颜色（如品红色），然后转换为P模式
    alpha = image.split()[-1]
    image = image.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
    
    # 设置透明色索引
    mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
    image.paste(255, mask)  # 将透明区域设为调色板中的最后一个颜色
    image.info['transparency'] = 255
    
    return image

# 生成旋转帧
frames = []
for angle in range(0, 360, 10):  # 每次旋转 10°，一共 36 帧
    # 以图片中心旋转，不扩展画布
    rotated = img.rotate(angle, expand=False, center=None, fillcolor=(0, 0, 0, 0))
    # 转换为P模式并保持透明度
    p_frame = rgba_to_p_with_transparency(rotated)
    frames.append(p_frame)

# 保存为 GIF
frames[0].save(
    output_path, 
    save_all=True, 
    append_images=frames[1:], 
    duration=100, 
    loop=0,
    transparency=255,
    disposal=2
)

print(f"以中心旋转的透明背景GIF已成功保存到: {output_path}")