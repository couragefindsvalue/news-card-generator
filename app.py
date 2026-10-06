from flask import Flask, request, render_template, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import io
import os
import re
import base64
import json
import cv2
import numpy as np
import feedparser
import requests
from bs4 import BeautifulSoup
from collections import Counter
import tempfile  # ★★★ 新增：用于跨平台临时目录

try:
    import jieba.analyse

    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

app = Flask(__name__)

# ★★★ 核心：自动识别本地和 Render 的临时目录 ★★★
TEMP_DIR = tempfile.gettempdir()

# ================= 字体配置区 =================
FONT_FAMILIES = {
    "Arial 常规 (Arial)": [
        "arial.ttf", "C:/Windows/Fonts/arial.ttf", "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ],
    "Arial 粗体 (Arial Bold)": [
        "arialbd.ttf", "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "Arial 黑体 (Arial Black)": [
        "ariblk.ttf", "C:/Windows/Fonts/ariblk.ttf", "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "Impact 粗体": [
        "impact.ttf", "C:/Windows/Fonts/impact.ttf", "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ],
    "微软雅黑常规 (Microsoft YaHei)": ["msyh.ttc", "C:/Windows/Fonts/msyh.ttc"],
    "微软雅黑粗体 (Microsoft YaHei Bold)": ["msyhbd.ttc", "C:/Windows/Fonts/msyhbd.ttc"],
    "黑体 (SimHei)": ["simhei.ttf", "C:/Windows/Fonts/simhei.ttf"],
    "苹方常规 (PingFang)": ["/System/Library/Fonts/PingFang.ttc"],
    "Noto Sans CJK 粗体": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"],

    "Times New Roman 常规": ["times.ttf", "C:/Windows/Fonts/times.ttf", "/Library/Fonts/Times New Roman.ttf"],
    "Times New Roman 粗体": ["timesbd.ttf", "C:/Windows/Fonts/timesbd.ttf", "/Library/Fonts/Times New Roman Bold.ttf"],
    "Georgia": ["georgia.ttf", "C:/Windows/Fonts/georgia.ttf", "/Library/Fonts/Georgia.ttf"],
    "宋体 (SimSun)": ["simsun.ttc", "C:/Windows/Fonts/simsun.ttc"],
    "楷体 (KaiTi)": ["simkai.ttf", "C:/Windows/Fonts/simkai.ttf"],

    "Comic Sans MS": ["comic.ttf", "C:/Windows/Fonts/comic.ttf", "/Library/Fonts/Comic Sans MS.ttf"],
    "Courier New": ["cour.ttf", "C:/Windows/Fonts/cour.ttf", "/Library/Fonts/Courier New.ttf"],
    "Verdana": ["verdana.ttf", "C:/Windows/Fonts/verdana.ttf", "/Library/Fonts/Verdana.ttf"],
}


def contains_chinese(text):
    if not text: return False
    return bool(re.search(r'[\u4e00-\u9fa5\u3040-\u30ff\uac00-\ud7af]', text))


def get_font_path(font_name, text_content=""):
    if contains_chinese(text_content):
        for cn_font in ["Noto Sans CJK 粗体", "微软雅黑粗体 (Microsoft YaHei Bold)", "苹方 (PingFang)",
                        "黑体 (SimHei)"]:
            if cn_font in FONT_FAMILIES:
                for path in FONT_FAMILIES[cn_font]:
                    if os.path.exists(path): return path

    if font_name in FONT_FAMILIES:
        for path in FONT_FAMILIES[font_name]:
            if os.path.exists(path): return path

    for fallback in ["Arial 粗体 (Arial Bold)", "微软雅黑粗体 (Microsoft YaHei Bold)", "Noto Sans CJK 粗体"]:
        if fallback in FONT_FAMILIES:
            for path in FONT_FAMILIES[fallback]:
                if os.path.exists(path): return path
    return "arialbd.ttf"


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


# ★★★ 新增：图片预处理函数（强制限制尺寸，节省内存） ★★★
def resize_image_if_needed(image_file, max_dim=1080):
    try:
        img = Image.open(image_file)
        if max(img.size) > max_dim:
            scale = max_dim / max(img.size)
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        print(f"图片缩放出错: {e}")
        return None


# ================= 文本分析：自动提取关键词 =================
def extract_keywords_from_text(text, top_k=8):
    if not text: return []
    keywords = []
    if HAS_JIEBA and contains_chinese(text):
        try:
            cn_tags = jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)
            for t in cn_tags:
                if 2 <= len(t) <= 10 and not t.isdigit(): keywords.append(t)
        except:
            pass

    english_words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    stop_words = {'The', 'A', 'An', 'And', 'Or', 'But', 'In', 'On', 'At', 'To', 'For', 'Of', 'With', 'By', 'Is', 'Are',
                  'Was', 'Were', 'Be', 'Been', 'Has', 'Have', 'Had', 'Do', 'Does', 'Did', 'Will', 'Would', 'Could',
                  'Should', 'May', 'Might', 'Must', 'Can', 'This', 'That', 'These', 'Those', 'It', 'Its', 'As', 'If',
                  'So', 'We', 'They', 'He', 'She', 'You', 'I'}
    word_counts = Counter(w.lower() for w in english_words if
                          w.capitalize() not in stop_words and w.lower() not in {sw.lower() for sw in stop_words})
    for word, count in word_counts.most_common(top_k):
        if count >= 1:
            original_word = next(w for w in english_words if w.lower() == word)
            keywords.append(original_word)

    english_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text)
    for phrase in english_phrases:
        if len(phrase) <= 30 and phrase not in keywords: keywords.insert(0, phrase)

    seen, result = set(), []
    for kw in keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            result.append(kw)
    return result[:top_k]


# ================= 人脸检测与头像处理 =================
def auto_detect_face_offset(image_path, target_size):
    try:
        img = cv2.imread(image_path)
        if img is None: return 0.5, 0.5, 1.0
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) == 0:
            return 0.5, 0.5, 1.0

        (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
        img_h, img_w = img.shape[:2]
        offset_x = (x + w / 2) / img_w
        offset_y = (y + h / 2) / img_h
        base_scale = target_size / min(img_w, img_h)
        face_h_scaled = h * base_scale
        zoom = (target_size * 0.55) / face_h_scaled
        zoom = max(1.0, min(zoom, 5.0))
        offset_y = max(0.1, min(offset_y - 0.05, 0.9))
        return offset_x, offset_y, zoom
    except Exception as e:
        print(f"检测出错: {e}")
        return 0.5, 0.5, 1.0


def make_circular_avatar(avatar_file, size, border_width=6, border_color="#FFD700", offset_x=0.5, offset_y=0.5,
                         zoom=1.0):
    try:
        avatar = Image.open(avatar_file).convert("RGBA")
        w, h = avatar.size
        base_scale = size / min(w, h)
        final_scale = base_scale * zoom
        new_w, new_h = int(w * final_scale), int(h * final_scale)
        avatar_resized = avatar.resize((new_w, new_h), Image.Resampling.LANCZOS)
        paste_x = int((size - new_w) * offset_x)
        paste_y = int((size - new_h) * offset_y)
        base_canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        base_canvas.paste(avatar_resized, (paste_x, paste_y))
        mask = Image.new("L", (size, size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, size, size), fill=255)
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(base_canvas, (0, 0), mask)
        scale = 4
        upscaled_size = size * scale
        final_output = Image.new("RGBA", (upscaled_size, upscaled_size), (0, 0, 0, 0))
        out_upscaled = output.resize((upscaled_size, upscaled_size), Image.Resampling.LANCZOS)
        final_output.paste(out_upscaled, (0, 0))
        draw_border = ImageDraw.Draw(final_output)
        scaled_border_width = border_width * scale
        draw_border.ellipse((0, 0, upscaled_size, upscaled_size), outline=border_color, width=scaled_border_width)
        inner_offset = scaled_border_width
        if upscaled_size - 2 * inner_offset > 0:
            draw_border.ellipse(
                (inner_offset, inner_offset, upscaled_size - inner_offset, upscaled_size - inner_offset),
                outline="#FFFFFF", width=scale)
        return final_output.resize((size, size), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"处理头像出错: {e}")
        return None


# ================= 核心图像合成 =================
def parse_keywords_json(keywords_json_str):
    color_map = {}
    if not keywords_json_str: return color_map
    try:
        for group in json.loads(keywords_json_str):
            for word in group.get('words', []):
                if word.strip(): color_map[word.strip().lower()] = group.get('color', '#FFD700')
    except:
        pass
    return color_map


def tokenize_and_highlight(text, color_map, default_color):
    sorted_keywords = sorted(color_map.keys(), key=len, reverse=True)
    tokens, i = [], 0
    while i < len(text):
        matched_kw = None
        for kw in sorted_keywords:
            if text[i:i + len(kw)].lower() == kw:
                matched_kw, matched_color = text[i:i + len(kw)], color_map[kw]
                break
        if matched_kw:
            tokens.append((matched_kw, matched_color))
            i += len(matched_kw)
        else:
            match = re.match(r'([a-zA-Z0-9]+|\s+|[\u4e00-\u9fa5]|[^\w\s\u4e00-\u9fa5]+)', text[i:])
            if match:
                tokens.append((match.group(1), default_color))
                i += len(match.group(1))
            else:
                i += 1
    return tokens


def wrap_and_highlight(text, font, max_width, draw, color_map, default_color, stroke_width, stroke_color):
    tokens = tokenize_and_highlight(text, color_map, default_color)
    lines, current_line_tokens, current_line_width = [], [], 0
    for token, color in tokens:
        if token == '\n':
            lines.append(current_line_tokens)
            current_line_tokens, current_line_width = [], 0
            continue
        bbox = draw.textbbox((0, 0), token, font=font)
        token_width = bbox[2] - bbox[0]
        if current_line_width + token_width > max_width:
            if current_line_tokens: lines.append(current_line_tokens)
            if token.isspace():
                current_line_tokens, current_line_width = [], 0
            else:
                current_line_tokens, current_line_width = [(token, color)], token_width
        else:
            current_line_tokens.append((token, color))
            current_line_width += token_width
    if current_line_tokens: lines.append(current_line_tokens)
    return lines


def generate_image(main_img_file, avatar1_file, avatar2_file, text_mid, text_bottom, keywords_json_str,
                   avatar1_size, avatar1_x, avatar1_y, avatar1_offset_x, avatar1_offset_y, avatar1_zoom,
                   avatar2_size, avatar2_x, avatar2_y, avatar2_offset_x, avatar2_offset_y, avatar2_zoom,
                   font_mid_name, font_mid_size, font_mid_color, font_mid_stroke_w, font_mid_stroke_c,
                   font_bottom_name, font_bottom_size_override, font_bottom_color, font_bottom_stroke_w,
                   font_bottom_stroke_c,
                   canvas_ratio, darken_opacity, blur_radius, avatar_border_color, avatar_border_width,
                   bg_zoom, bg_offset_x, bg_offset_y, auto_face_detect, show_mid_line, mid_line_margin,
                   badge_text, badge_size, badge_text_color, badge_bg_color, badge_x, badge_y, badge_font_name,
                   logo_text, logo_size, logo_color, logo_x, logo_y, logo_font_name,
                   cta_text, cta_font_size, cta_text_color, cta_bg_color, cta_x, cta_y, cta_font_name,
                   cta_radius, cta_shadow, gradient_height_ratio, gradient_end_y_ratio, gradient_start_color,
                   gradient_end_color):
    # ★★★ 优化：单次读取主图 + 强制缩放 ★★★
    try:
        img = resize_image_if_needed(main_img_file, max_dim=1080)  # 限制主图长边 1080px
        if not img:
            raise ValueError("图片处理失败")

        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            bg = Image.new("RGB", img.size, (0, 0, 0))
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        else:
            img = img.convert("RGB")
    except Exception as e:
        raise ValueError(f"无法处理主图片: {e}")

    original_w, original_h = img.size

    if canvas_ratio == 'original':
        W, H = original_w, original_h
        max_dim = 2000
        if max(W, H) > max_dim:
            scale = max_dim / max(W, H)
            W, H = int(W * scale), int(H * scale)
        top_h = H
    else:
        if canvas_ratio == '9:16':
            W, H = 1080, 1920
        elif canvas_ratio == '3:4':
            W, H = 1080, 1440
        elif canvas_ratio == '1:1':
            W, H = 1080, 1080
        else:
            W, H = 1080, 1350
        top_h = int(H * gradient_end_y_ratio)

    bottom_h = H - top_h

    if blur_radius > 0: img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    w, h = img.size
    base_scale = max(W / w, top_h / h)
    final_scale = base_scale * bg_zoom
    target_w, target_h = int(w * final_scale), int(h * final_scale)
    img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    paste_x, paste_y = int((W - target_w) * bg_offset_x), int((top_h - target_h) * bg_offset_y)
    top_area = Image.new("RGB", (W, top_h), (0, 0, 0))
    top_area.paste(img_resized, (paste_x, paste_y))

    if darken_opacity > 0:
        top_area = Image.blend(top_area, Image.new("RGB", (W, top_h), (0, 0, 0)), alpha=darken_opacity)

    canvas = Image.new("RGB", (W, H), "black")
    canvas.paste(top_area, (0, 0))

    gradient_h = int(top_h * gradient_height_ratio)
    if gradient_h > 0:
        start_rgb = hex_to_rgb(gradient_start_color)
        end_rgb = hex_to_rgb(gradient_end_color)

        gradient_mask = Image.new('L', (1, gradient_h), color=0)
        for y in range(gradient_h):
            gradient_mask.putpixel((0, y), int(255 * (y / gradient_h)))
        gradient_mask = gradient_mask.resize((W, gradient_h))

        gradient_color_img = Image.new('RGB', (W, gradient_h))
        draw_grad = ImageDraw.Draw(gradient_color_img)
        for y in range(gradient_h):
            ratio = y / gradient_h
            r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
            g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
            b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
            draw_grad.line([(0, y), (W, y)], fill=(r, g, b))

        canvas.paste(gradient_color_img, (0, top_h - gradient_h), gradient_mask)

    # ★★★ 优化：头像处理（强制缩放）+ 使用 TEMP_DIR ★★★
    if avatar1_file and avatar1_file.filename:
        avatar1_img = resize_image_if_needed(avatar1_file, max_dim=600)  # 限制头像长边 600px
        if avatar1_img:
            temp_path1 = os.path.join(TEMP_DIR, "temp_avatar1.jpg")
            avatar1_img.save(temp_path1)
            if auto_face_detect:
                offset_x, offset_y, zoom = auto_detect_face_offset(temp_path1, avatar1_size)
                av1 = make_circular_avatar(temp_path1, avatar1_size, avatar_border_width, avatar_border_color, offset_x,
                                           offset_y, zoom)
            else:
                av1 = make_circular_avatar(temp_path1, avatar1_size, avatar_border_width, avatar_border_color,
                                           avatar1_offset_x, avatar1_offset_y, avatar1_zoom)
            if av1: canvas.paste(av1, (avatar1_x, avatar1_y), av1)

    if avatar2_file and avatar2_file.filename:
        avatar2_img = resize_image_if_needed(avatar2_file, max_dim=600)
        if avatar2_img:
            temp_path2 = os.path.join(TEMP_DIR, "temp_avatar2.jpg")
            avatar2_img.save(temp_path2)
            if auto_face_detect:
                offset_x, offset_y, zoom = auto_detect_face_offset(temp_path2, avatar2_size)
                av2 = make_circular_avatar(temp_path2, avatar2_size, avatar_border_width, avatar_border_color, offset_x,
                                           offset_y, zoom)
            else:
                av2 = make_circular_avatar(temp_path2, avatar2_size, avatar_border_width, avatar_border_color,
                                           avatar2_offset_x, avatar2_offset_y, avatar2_zoom)
            if av2: canvas.paste(av2, (avatar2_x, avatar2_y), av2)

    draw = ImageDraw.Draw(canvas)
    font_mid_path = get_font_path(font_mid_name, text_mid)
    font_bottom_path = get_font_path(font_bottom_name, text_bottom)
    try:
        font_mid = ImageFont.truetype(font_mid_path, font_mid_size)
    except:
        font_mid = ImageFont.load_default()

    if badge_text:
        try:
            font_badge = ImageFont.truetype(get_font_path(badge_font_name, badge_text), badge_size)
        except:
            font_badge = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x = 25
        pad_y = 12

        rect_x0 = badge_x
        rect_y0 = badge_y
        rect_x1 = badge_x + text_w + pad_x * 2
        rect_y1 = badge_y + text_h + pad_y * 2

        if hasattr(draw, 'rounded_rectangle'):
            draw.rounded_rectangle([rect_x0, rect_y0, rect_x1, rect_y1], radius=8, fill=badge_bg_color)
        else:
            draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=badge_bg_color)

        center_x = (rect_x0 + rect_x1) / 2
        center_y = (rect_y0 + rect_y1) / 2
        draw.text((center_x, center_y), badge_text, font=font_badge, fill=badge_text_color, anchor="mm")

    if logo_text:
        try:
            font_logo = ImageFont.truetype(get_font_path(logo_font_name, logo_text), logo_size)
        except:
            font_logo = ImageFont.load_default()

        draw.text((W - logo_x, logo_y), logo_text, font=font_logo, fill=logo_color, anchor="rt")

    if show_mid_line:
        line_y = top_h
        if text_mid:
            bbox = draw.textbbox((0, 0), text_mid, font=font_mid, stroke_width=font_mid_stroke_w)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            center_x = W // 2

            left_line_end = center_x - text_w // 2 - 20
            right_line_start = center_x + text_w // 2 + 20

            if left_line_end > mid_line_margin:
                draw.line([(mid_line_margin, line_y), (left_line_end, line_y)], fill="white", width=4)
            if right_line_start < W - mid_line_margin:
                draw.line([(right_line_start, line_y), (W - mid_line_margin, line_y)], fill="white", width=4)

            draw.text((center_x - text_w // 2, line_y - text_h // 2 - bbox[1]), text_mid, font=font_mid,
                      fill=font_mid_color, stroke_width=font_mid_stroke_w, stroke_fill=font_mid_stroke_c)
        else:
            draw.line([(mid_line_margin, line_y), (W - mid_line_margin, line_y)], fill="white", width=4)
    elif text_mid:
        line_y = top_h
        bbox = draw.textbbox((0, 0), text_mid, font=font_mid, stroke_width=font_mid_stroke_w)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        center_x = W // 2
        draw.text((center_x - text_w // 2, line_y - text_h // 2 - bbox[1]), text_mid, font=font_mid,
                  fill=font_mid_color, stroke_width=font_mid_stroke_w, stroke_fill=font_mid_stroke_c)

    color_map = parse_keywords_json(keywords_json_str)
    if text_bottom:
        available_w, available_h = W - 160, bottom_h - 120
        if font_bottom_size_override > 0:
            current_font_size = font_bottom_size_override
            final_font = ImageFont.truetype(font_bottom_path, current_font_size)
            final_lines = wrap_and_highlight(text_bottom, final_font, available_w, draw, color_map, font_bottom_color,
                                             font_bottom_stroke_w, font_bottom_stroke_c)
            line_spacing_y = int(current_font_size * 0.4)
            total_text_h = len(final_lines) * (current_font_size + line_spacing_y)
        else:
            current_font_size = 100
            final_lines, final_font = [], None
            while current_font_size >= 30:
                test_font = ImageFont.truetype(font_bottom_path, current_font_size)
                lines = wrap_and_highlight(text_bottom, test_font, available_w, draw, color_map, font_bottom_color,
                                           font_bottom_stroke_w, font_bottom_stroke_c)
                line_spacing_y = int(current_font_size * 0.4)
                total_text_h = len(lines) * (current_font_size + line_spacing_y)
                if total_text_h <= available_h:
                    final_lines, final_font = lines, test_font
                    break
                current_font_size -= 2
            if not final_font:
                final_font = ImageFont.truetype(font_bottom_path, 30)
                final_lines = wrap_and_highlight(text_bottom, final_font, available_w, draw, color_map,
                                                 font_bottom_color, font_bottom_stroke_w, font_bottom_stroke_c)
                line_spacing_y = int(30 * 0.4)
                total_text_h = len(final_lines) * (30 + line_spacing_y)

        current_y = top_h + (bottom_h - total_text_h) // 2
        for line_tokens in final_lines:
            line_width = sum(draw.textbbox((0, 0), token, font=final_font, stroke_width=font_bottom_stroke_w)[2] -
                             draw.textbbox((0, 0), token, font=final_font, stroke_width=font_bottom_stroke_w)[0] for
                             token, _ in line_tokens)
            current_x = (W - line_width) // 2
            for token, color in line_tokens:
                draw.text((current_x, current_y), token, font=final_font, fill=color, stroke_width=font_bottom_stroke_w,
                          stroke_fill=font_bottom_stroke_c)
                current_x += draw.textbbox((0, 0), token, font=final_font, stroke_width=font_bottom_stroke_w)[2] - \
                             draw.textbbox((0, 0), token, font=final_font, stroke_width=font_bottom_stroke_w)[0]
            current_y += current_font_size + line_spacing_y

    if cta_text:
        try:
            font_cta = ImageFont.truetype(get_font_path(cta_font_name, cta_text), cta_font_size)
        except:
            font_cta = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x = 35
        pad_y = 15

        rect_x0 = cta_x
        rect_y0 = cta_y
        rect_x1 = cta_x + text_w + pad_x * 2
        rect_y1 = cta_y + text_h + pad_y * 2

        if cta_shadow:
            shadow_offset = 6
            draw.rounded_rectangle(
                [rect_x0 + shadow_offset, rect_y0 + shadow_offset, rect_x1 + shadow_offset, rect_y1 + shadow_offset],
                radius=cta_radius, fill="#333333")

        if hasattr(draw, 'rounded_rectangle'):
            draw.rounded_rectangle([rect_x0, rect_y0, rect_x1, rect_y1], radius=cta_radius, fill=cta_bg_color)
        else:
            draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=cta_bg_color)

        center_x = (rect_x0 + rect_x1) / 2
        center_y = (rect_y0 + rect_y1) / 2
        draw.text((center_x, center_y), cta_text, font=font_cta, fill=cta_text_color, anchor="mm")

    img_byte_arr = io.BytesIO()
    canvas.save(img_byte_arr, format='JPEG', quality=90)
    img_byte_arr.seek(0)
    return img_byte_arr


# ================= 新闻抓取辅助函数 =================
def fetch_image_as_base64(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except:
        pass
    return None


# ================= Web 路由 =================
@app.route('/', methods=['GET'])
def index(): return render_template('index.html')


@app.route('/fetch_news', methods=['POST'])
def fetch_news():
    try:
        data = request.json
        rss_url = data.get('rss_url')
        limit = max(1, min(int(data.get('limit', 10)), 100))

        if not rss_url: return jsonify({'error': 'Please provide an RSS URL'}), 400
        feed = feedparser.parse(rss_url)
        if not feed.entries: return jsonify({'error': 'No entries found'}), 400
        news_list = []
        for entry in feed.entries[:limit]:
            title = entry.get('title', 'No Title')
            description = entry.get('description', entry.get('summary', ''))
            link = entry.get('link', '')
            soup_desc = BeautifulSoup(description, 'html.parser')
            clean_description = soup_desc.get_text(strip=True)
            image_url = None
            if hasattr(entry, 'media_content') and entry.media_content: image_url = entry.media_content[0].get('url')
            if not image_url and hasattr(entry, 'enclosures') and entry.enclosures: image_url = entry.enclosures[0].get(
                'href')
            if not image_url:
                img_tag = soup_desc.find('img')
                if img_tag and img_tag.get('src'): image_url = img_tag['src']
            news_list.append({'title': title, 'description': clean_description, 'link': link, 'image_url': image_url,
                              'keywords': extract_keywords_from_text(title + " " + clean_description)})
        return jsonify({'news_list': news_list})
    except Exception as e:
        return jsonify({'error': f"Failed to fetch news: {str(e)}"}), 500


@app.route('/fetch_news_image', methods=['POST'])
def fetch_news_image():
    try:
        data = request.json
        image_url = data.get('image_url')
        link = data.get('link')
        final_image_url = image_url
        if not final_image_url and link:
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                page_response = requests.get(link, headers=headers, timeout=5)
                page_soup = BeautifulSoup(page_response.text, 'html.parser')
                og_image = page_soup.find('meta', property='og:image')
                if og_image and og_image.get('content'): final_image_url = og_image['content']
            except:
                pass
        image_base64 = fetch_image_as_base64(final_image_url) if final_image_url else None
        return jsonify({'image_base64': image_base64})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/search_avatar', methods=['POST'])
def search_avatar():
    try:
        name = request.json.get('name')
        if not name: return jsonify({'error': 'Please provide a name'}), 400
        headers = {'User-Agent': 'NewsCardGenerator/1.0 (test@example.com)'}
        image_url = None
        search_queries = [name, f"{name} logo", f"{name} company", f"{name} brand"]
        for query in search_queries:
            try:
                search_url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&generator=search&gsrsearch={query}&gsrlimit=1&prop=pageimages&piprop=thumbnail&pithumbsize=500"
                response = requests.get(search_url, headers=headers, timeout=5)
                data = response.json()
                pages = data.get('query', {}).get('pages', {})
                if pages:
                    page_id = list(pages.keys())[0]
                    thumbnail = pages[page_id].get('thumbnail')
                    if thumbnail and thumbnail.get('source'):
                        image_url = thumbnail['source']
                        break
            except Exception:
                continue
        if not image_url:
            return jsonify({'error': f'No image found for "{name}". Try adding "logo" or "company".'}), 404
        img_response = requests.get(image_url, headers=headers, timeout=5)
        if img_response.status_code != 200:
            return jsonify({'error': 'Failed to download the image'}), 500
        img = Image.open(io.BytesIO(img_response.content)).convert("RGB")

        # ★★★ 使用 TEMP_DIR ★★★
        temp_path = os.path.join(TEMP_DIR, "temp_avatar_search.jpg")
        img.save(temp_path)

        target_size = 220
        offset_x, offset_y, zoom = auto_detect_face_offset(temp_path, target_size)
        circular_avatar = make_circular_avatar(temp_path, target_size, border_width=6, border_color="#FFD700",
                                               offset_x=offset_x, offset_y=offset_y, zoom=zoom)
        if not circular_avatar: return jsonify({'error': 'Failed to process image'}), 500
        buffered = io.BytesIO()
        circular_avatar.save(buffered, format="PNG")
        return jsonify({'image_base64': f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"})
    except Exception as e:
        return jsonify({'error': f"Search failed: {str(e)}"}), 500


@app.route('/generate', methods=['POST'])
def generate():
    try:
        main_img = request.files.get('main_img')
        avatar1 = request.files.get('avatar1')
        avatar2 = request.files.get('avatar2')
        text_mid = request.form.get('text_mid', '')
        text_bottom = request.form.get('text_bottom', '')
        keywords_json = request.form.get('keywords_json', '[]')
        canvas_ratio = request.form.get('canvas_ratio', '4:5')
        darken_opacity = float(request.form.get('darken_opacity', 0)) / 100.0
        blur_radius = int(request.form.get('blur_radius', 0))
        avatar_border_color = request.form.get('avatar_border_color', '#FFD700')
        avatar_border_width = int(request.form.get('avatar_border_width', 6))
        bg_zoom = float(request.form.get('bg_zoom', 1.0))
        bg_offset_x = float(request.form.get('bg_offset_x', 0.5))
        bg_offset_y = float(request.form.get('bg_offset_y', 0.5))
        auto_face_detect = request.form.get('auto_face_detect', 'false') == 'true'
        avatar1_size = int(request.form.get('avatar1_size', 220))
        avatar1_x = int(request.form.get('avatar1_x', 50))
        avatar1_y = int(request.form.get('avatar1_y', 50))
        avatar1_offset_x = float(request.form.get('avatar1_offset_x', 0.5))
        avatar1_offset_y = float(request.form.get('avatar1_offset_y', 0.5))
        avatar1_zoom = float(request.form.get('avatar1_zoom', 1.0))
        avatar2_size = int(request.form.get('avatar2_size', 220))
        avatar2_x = int(request.form.get('avatar2_x', 1080 - 50 - avatar2_size))
        avatar2_y = int(request.form.get('avatar2_y', 50))
        avatar2_offset_x = float(request.form.get('avatar2_offset_x', 0.5))
        avatar2_offset_y = float(request.form.get('avatar2_offset_y', 0.5))
        avatar2_zoom = float(request.form.get('avatar2_zoom', 1.0))
        font_mid_name = request.form.get('font_mid_name', '微软雅黑粗体 (Microsoft YaHei Bold)')
        font_mid_size = int(request.form.get('font_mid_size', 55))
        font_mid_color = request.form.get('font_mid_color', '#FFFFFF')
        font_mid_stroke_w = int(request.form.get('font_mid_stroke_w', 0))
        font_mid_stroke_c = request.form.get('font_mid_stroke_c', '#000000')
        font_bottom_name = request.form.get('font_bottom_name', '微软雅黑粗体 (Microsoft YaHei Bold)')
        font_bottom_size_override = int(request.form.get('font_bottom_size_override', 0))
        font_bottom_color = request.form.get('font_bottom_color', '#FFFFFF')
        font_bottom_stroke_w = int(request.form.get('font_bottom_stroke_w', 0))
        font_bottom_stroke_c = request.form.get('font_bottom_stroke_c', '#000000')

        show_mid_line = request.form.get('show_mid_line', 'false') == 'true'
        mid_line_margin = int(request.form.get('mid_line_margin', 60))
        badge_text = request.form.get('badge_text', '')
        badge_size = int(request.form.get('badge_size', 30))
        badge_text_color = request.form.get('badge_text_color', '#000000')
        badge_bg_color = request.form.get('badge_bg_color', '#FFFFFF')
        badge_x = int(request.form.get('badge_x', 50))
        badge_y = int(request.form.get('badge_y', 50))
        badge_font_name = request.form.get('badge_font_name', '微软雅黑粗体 (Microsoft YaHei Bold)')

        logo_text = request.form.get('logo_text', '')
        logo_size = int(request.form.get('logo_size', 40))
        logo_color = request.form.get('logo_color', '#FFFFFF')
        logo_x = int(request.form.get('logo_x', 50))
        logo_y = int(request.form.get('logo_y', 50))
        logo_font_name = request.form.get('logo_font_name', '微软雅黑粗体 (Microsoft YaHei Bold)')

        cta_text = request.form.get('cta_text', '')
        cta_font_size = int(request.form.get('cta_font_size', 30))
        cta_text_color = request.form.get('cta_text_color', '#000000')
        cta_bg_color = request.form.get('cta_bg_color', '#FFFFFF')
        cta_x = int(request.form.get('cta_x', 350))
        cta_y = int(request.form.get('cta_y', 1100))
        cta_font_name = request.form.get('cta_font_name', '微软雅黑粗体 (Microsoft YaHei Bold)')
        cta_radius = int(request.form.get('cta_radius', 10))
        cta_shadow = request.form.get('cta_shadow', 'false') == 'true'

        gradient_height_ratio = float(request.form.get('gradient_height_ratio', 0.15))
        gradient_end_y_ratio = float(request.form.get('gradient_end_y_ratio', 0.66))
        gradient_start_color = request.form.get('gradient_start_color', '#000000')
        gradient_end_color = request.form.get('gradient_end_color', '#000000')

        if not main_img: return jsonify({'error': 'Please upload a main image'}), 400
        result_img_stream = generate_image(
            main_img, avatar1, avatar2, text_mid, text_bottom, keywords_json,
            avatar1_size, avatar1_x, avatar1_y, avatar1_offset_x, avatar1_offset_y, avatar1_zoom,
            avatar2_size, avatar2_x, avatar2_y, avatar2_offset_x, avatar2_offset_y, avatar2_zoom,
            font_mid_name, font_mid_size, font_mid_color, font_mid_stroke_w, font_mid_stroke_c,
            font_bottom_name, font_bottom_size_override, font_bottom_color, font_bottom_stroke_w, font_bottom_stroke_c,
            canvas_ratio, darken_opacity, blur_radius, avatar_border_color, avatar_border_width,
            bg_zoom, bg_offset_x, bg_offset_y, auto_face_detect, show_mid_line, mid_line_margin,
            badge_text, badge_size, badge_text_color, badge_bg_color, badge_x, badge_y, badge_font_name,
            logo_text, logo_size, logo_color, logo_x, logo_y, logo_font_name,
            cta_text, cta_font_size, cta_text_color, cta_bg_color, cta_x, cta_y, cta_font_name,
            cta_radius, cta_shadow, gradient_height_ratio, gradient_end_y_ratio, gradient_start_color,
            gradient_end_color
        )
        return jsonify({'image': f'data:image/jpeg;base64,{base64.b64encode(result_img_stream.getvalue()).decode()}'})
    except Exception as e:
        return jsonify({'error': f"Error: {str(e)}"}), 500


if __name__ == '__main__':
    # 确保本地运行时临时目录存在
    os.makedirs(TEMP_DIR, exist_ok=True)
    app.run(debug=True, port=5010)