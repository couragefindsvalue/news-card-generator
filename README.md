# 📰 News Card Generator / 新闻贴图生成器

A powerful, locally-run news card generator for content creators, media matrix accounts, and social media managers. Generate stunning news cards for TikTok, Instagram, and Xiaohongshu in seconds.

一款功能强大的本地新闻卡片生成工具，专为自媒体创作者、新闻矩阵号和社媒运营设计。支持一键抓取新闻、AI 人脸检测、多色高亮与实时预览，快速生成适配抖音、小红书、Instagram 的精美图卡。

---

## ✨ Features / 核心功能

*   **📡 RSS News Fetching / RSS新闻抓取**: Fetch the latest 5 news articles from dozens of built-in free RSS feeds (BBC, Guardian, AP News, 36Kr, etc.). Auto-fill title, description, and image.
    *   内置数十个免费新闻源（BBC、Guardian、36氪等），一键抓取最新 5 条新闻，自动填入标题与配图。
*   **🔍 Image Search / 联网图片搜索**: Search for people, companies, brands, and robots via Wikipedia API. Auto-crop to a circular avatar.
    *   集成 Wikipedia API，一键搜索人物、公司、品牌、机器人的高清图片，自动裁剪为圆形头像。
*   **🤖 Smart Face Detection / 智能人脸检测**: Uses OpenCV to automatically detect faces, adjusting the zoom and focus to perfectly center the subject.
    *   利用 OpenCV 自动识别人脸，自动调整缩放和焦点，让头部完美居中。
*   **✨ Multi-color Keyword Highlighting / 多色关键字高亮**: Auto-extract keywords using jieba and TF-IDF. Support multi-color highlighting with long-phrase priority.
    *   基于 jieba 和 TF-IDF 自动提取中英文关键词，支持多色高亮、长词组优先匹配。
*   **🎨 Canvas Ratio Adaptation / 画幅适配**: One-click switch between 4:5 (Instagram), 9:16 (TikTok/抖音), 3:4 (小红书), and 1:1 (Square).
    *   一键切换 4:5（Instagram）、9:16（抖音/TikTok）、3:4（小红书）和 1:1（方形）画幅。
*   **⚡ Real-time Preview / 实时预览**: All adjustments (fonts, colors, positions) are reflected in the preview pane instantly.
    *   所有调整（字体、颜色、位置）均实时反映在右侧预览区，无需反复点击生成。
*   **📋 One-click Copy & Download / 一键复制与下载**: Copy the image directly to your clipboard or download it as a file.
    *   支持直接复制到剪贴板（方便在聊天软件中直接粘贴），也支持下载为文件。
*   **📜 History / 历史记录**: Automatically saves thumbnails of the last 10 generations for easy backtracking.
    *   自动保存最近 10 次生成的缩略图，方便回溯。

---

## 🛠️ Tech Stack / 技术栈

- **Backend / 后端**: Python, Flask, Pillow (PIL), OpenCV, feedparser, BeautifulSoup4, jieba
- **Frontend / 前端**: HTML5, CSS3, Vanilla JavaScript

---

## 🚀 Quick Start / 快速开始

### 1. Clone the repository / 克隆项目

```bash
git clone https://github.com/your-username/news-card-generator.git
cd news-card-generator