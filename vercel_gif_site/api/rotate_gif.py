# api/rotate_gif.py
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs
from PIL import Image
import io
import math
import json
import re

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
        raise Exception(f"Image processing failed: {str(e)}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 解析 multipart/form-data
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No content")
                return
                
            post_data = self.rfile.read(content_length)
            
            # 解析 Content-Type 获取 boundary
            content_type = self.headers.get('Content-Type', '')
            if 'boundary=' not in content_type:
                self.send_error(400, "Invalid content type")
                return
                
            boundary = content_type.split('boundary=')[1].strip()
            
            # 分割数据
            boundary_bytes = f'--{boundary}'.encode()
            parts = post_data.split(boundary_bytes)
            
            file_data = None
            params = {}
            
            for part in parts:
                if len(part) < 10:  # 跳过太短的部分
                    continue
                    
                # 查找 Content-Disposition 头
                if b'Content-Disposition' not in part:
                    continue
                
                # 分离头部和数据
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                    
                headers_section = part[:header_end].decode('utf-8', errors='ignore')
                data_section = part[header_end + 4:]
                
                # 移除末尾的 \r\n
                if data_section.endswith(b'\r\n'):
                    data_section = data_section[:-2]
                
                # 解析 Content-Disposition
                disp_match = re.search(r'Content-Disposition: form-data; name="([^"]+)"', headers_section)
                if not disp_match:
                    continue
                    
                field_name = disp_match.group(1)
                
                if field_name == 'file':
                    file_data = data_section
                else:
                    params[field_name] = data_section.decode('utf-8', errors='ignore')
            
            if not file_data or len(file_data) == 0:
                self.send_error(400, "No file data found")
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
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(gif_data)
            
        except Exception as e:
            error_msg = str(e).encode('utf-8', errors='replace')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(error_msg)))
            self.end_headers()
            self.wfile.write(error_msg)