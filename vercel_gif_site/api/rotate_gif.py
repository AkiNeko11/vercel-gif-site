# api/rotate_gif.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from PIL import Image
import io
import math

app = FastAPI()

def rgba_to_p_with_transparency(image):
    
    # 将RGBA图像转换为P模式，保持透明度
   
    # 将透明像素设为特定颜色，然后转换为P模式
    alpha = image.split()[-1]
    image = image.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
    
    # 设置透明色索引
    mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
    image.paste(255, mask)  # 将透明区域设为调色板中的最后一个颜色
    image.info['transparency'] = 255
    
    return image

def calculate_expanded_size(width, height):
    
    # 计算能完全容纳旋转图片的画布尺寸
    
    # 使用图片对角线长度作为新画布的边长
    diagonal = math.sqrt(width**2 + height**2)
    return int(math.ceil(diagonal))

@app.post("/")
async def rotate_gif(
    file: UploadFile = File(...),
    step: int = Form(10),
    size: int = Form(512),
    delay: int = Form(40),
    direction: str = Form("right")  # 新增：旋转方向，"right"(顺时针) 或 "left"(逆时针)
):
    
    # 文件大小限制
    MAX_FILE_MB = 12
    data = await file.read()
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件过大，限制 {MAX_FILE_MB}MB")

    # 参数验证与边界限制
    step = max(1, min(180, int(step)))
    size = max(64, min(1024, int(size)))
    delay = max(10, min(1000, int(delay)))
    direction = direction.lower()
    if direction not in ["left", "right"]:
        direction = "right"  # 默认顺时针

    try:
        # 按照本地版本的方式打开并转换图片
        img = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        raise HTTPException(status_code=400, detail="无法读取图片文件")

    # 计算扩展后的画布尺寸，确保能完全容纳旋转的图片
    expanded_size = calculate_expanded_size(img.width, img.height)
    
    # 如果扩展后的尺寸超过用户设定的最大尺寸，进行等比缩放
    if expanded_size > size:
        scale = size / expanded_size
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # 重新计算扩展尺寸
        expanded_size = calculate_expanded_size(new_w, new_h)

    # 生成旋转帧
    frames = []
    
    # 根据旋转方向设置角度范围
    if direction == "left":  # 逆时针
        angle_range = range(0, 360, step)
    else:  # 顺时针 (right)
        angle_range = range(0, -360, -step)
    
    for angle in angle_range:
        # 创建扩展画布，以透明背景填充
        canvas = Image.new("RGBA", (expanded_size, expanded_size), (0, 0, 0, 0))
        
        # 旋转图片，expand=True 让PIL自动计算旋转后的尺寸
        rotated = img.rotate(
            angle, 
            expand=True,  # 扩展画布以包含完整旋转图片
            center=None,  # 使用图片中心作为旋转中心
            fillcolor=(0, 0, 0, 0)  # 透明填充
        )
        
        # 将旋转后的图片居中放置在画布上
        paste_x = (expanded_size - rotated.width) // 2
        paste_y = (expanded_size - rotated.height) // 2
        canvas.paste(rotated, (paste_x, paste_y), rotated)
        
        # 使用本地版本的透明度处理函数
        p_frame = rgba_to_p_with_transparency(canvas)
        frames.append(p_frame)

    # 保存为 GIF - 使用与本地版本相同的参数
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=delay,  # 使用前端传入的延时参数
        loop=0,
        transparency=255,  # 保持本地版本的透明度设置
        disposal=2
    )
    
    return Response(content=buf.getvalue(), media_type="image/gif")