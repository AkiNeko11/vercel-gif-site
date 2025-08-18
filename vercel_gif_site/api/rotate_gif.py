# api/rotate_gif.py
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs
from PIL import Image
import io
import math
import json

def rgba_to_p_with_transparency(image):
   
    # 将透明像素设为特定颜色，然后转换为P模式
    alpha = image.split()[-1]
    image = image.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
    
    # 设置透明色索引
    mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
    image.paste(255, mask)  # 将透明区域设为调色板中的最后一个颜色
    image.info['transparency'] = 255
    
    return image

def calculate_expanded_size(width, height):
     
     #计算能完全容纳旋转图片的画布尺寸
     #使用图片对角线长度作为新画布的边长
    diagonal = math.sqrt(width**2 + height**2)
    return int(math.ceil(diagonal))

def process_gif(file_data, step=10, size=512, delay=40, direction="right"):
    """处理 GIF 生成的核心逻辑"""
    try:
        # 参数验证与边界限制
        step = max(1, min(180, int(step)))
        size = max(64, min(1024, int(size)))
        delay = max(10, min(1000, int(delay)))
        direction = str(direction).lower()
        if direction not in ["left", "right"]:
            direction = "right"

        # 打开并转换图片
        img = Image.open(io.BytesIO(file_data)).convert("RGBA")

        # 计算扩展后的画布尺寸
        expanded_size = calculate_expanded_size(img.width, img.height)
        
        # 如果扩展后的尺寸超过用户设定的最大尺寸，进行等比缩放
        if expanded_size > size:
            scale = size / expanded_size
            new_w = max(1, int(img.width * scale))
            new_h = max(1, int(img.height * scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)
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
            
            # 旋转图片
            rotated = img.rotate(
                angle, 
                expand=True,
                center=None,
                fillcolor=(0, 0, 0, 0)
            )
            
            # 将旋转后的图片居中放置在画布上
            paste_x = (expanded_size - rotated.width) // 2
            paste_y = (expanded_size - rotated.height) // 2
            canvas.paste(rotated, (paste_x, paste_y), rotated)
            
            # 使用透明度处理函数
            p_frame = rgba_to_p_with_transparency(canvas)
            frames.append(p_frame)

        # 保存为 GIF
        buf = io.BytesIO()
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=delay,
            loop=0,
            transparency=255,
            disposal=2
        )
        
        return buf.getvalue()
    except Exception as e:
        raise Exception(f"处理图片失败: {str(e)}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 解析 multipart/form-data
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # 简单的 multipart 解析
            boundary = self.headers['Content-Type'].split('boundary=')[1]
            parts = post_data.split(f'--{boundary}'.encode())
            
            file_data = None
            params = {}
            
            for part in parts:
                if b'Content-Disposition' in part:
                    lines = part.split(b'\r\n')
                    headers = {}
                    data_start = 0
                    
                    for i, line in enumerate(lines):
                        if line == b'':
                            data_start = i + 1
                            break
                        if b':' in line:
                            key, value = line.decode().split(':', 1)
                            headers[key.strip()] = value.strip()
                    
                    if 'Content-Disposition' in headers:
                        disp = headers['Content-Disposition']
                        if 'name="file"' in disp:
                            file_data = b'\r\n'.join(lines[data_start:]).rstrip(b'\r\n')
                        else:
                            # 提取参数名
                            import re
                            name_match = re.search(r'name="([^"]+)"', disp)
                            if name_match:
                                param_name = name_match.group(1)
                                param_value = b'\r\n'.join(lines[data_start:]).rstrip(b'\r\n').decode()
                                params[param_name] = param_value
            
            if not file_data:
                self.send_error(400, "没有找到文件数据")
                return
            
            # 处理 GIF
            gif_data = process_gif(
                file_data,
                step=int(params.get('step', 10)),
                size=int(params.get('size', 512)),
                delay=int(params.get('delay', 40)),
                direction=params.get('direction', 'right')
            )
            
            # 返回 GIF
            self.send_response(200)
            self.send_header('Content-Type', 'image/gif')
            self.send_header('Content-Length', str(len(gif_data)))
            self.end_headers()
            self.wfile.write(gif_data)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({"error": str(e)}).encode()
            self.wfile.write(error_response)