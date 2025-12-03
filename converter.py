import os
import threading
import time
from pathlib import Path

# 尝试导入库，优雅地处理缺失的情况
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    HAS_EPUB_LIB = True
except ImportError:
    HAS_EPUB_LIB = False
    print("警告: 未找到 ebooklib 或 beautifulsoup4。")

try:
    import mobi
    HAS_MOBI_LIB = True
except ImportError:
    HAS_MOBI_LIB = False
    # 尝试使用内置的简单 MobiReader
    try:
        from mobi_reader import MobiReader
        HAS_INTERNAL_MOBI = True
    except ImportError:
        HAS_INTERNAL_MOBI = False
    print("警告: 未找到 mobi 库，将尝试使用内置读取器。")

class Converter:
    def __init__(self):
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set() # 设置为 True 表示“未暂停”（运行中）

    def convert_file(self, input_path, output_path=None, update_callback=None):
        """
        转换单个文件。
        update_callback(progress, status_message)
        """
        if not os.path.exists(input_path):
            return False, "文件未找到"

        file_ext = os.path.splitext(input_path)[1].lower()
        if output_path is None:
            output_path = os.path.splitext(input_path)[0] + ".txt"
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            if file_ext == '.epub':
                return self._convert_epub(input_path, output_path, update_callback)
            elif file_ext == '.mobi':
                return self._convert_mobi(input_path, output_path, update_callback)
            else:
                return False, f"不支持的格式: {file_ext}"
        except Exception as e:
            return False, str(e)

    def _convert_epub(self, input_path, output_path, callback):
        if not HAS_EPUB_LIB:
            return False, "缺少库 'ebooklib' 或 'bs4'。"
            
        try:
            book = epub.read_epub(input_path)
            items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
            total_items = len(items)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, item in enumerate(items):
                    # 检查控制标志
                    if self.stop_event.is_set():
                        return False, "用户已停止"
                    
                    while not self.pause_event.is_set():
                        time.sleep(0.1)
                        if self.stop_event.is_set():
                             return False, "用户已停止"

                    # 提取文本
                    content = item.get_content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # 获取标题（如果可能）（有时标题在 h1/h2 中）
                    # 简单的文本提取，保留换行符
                    text = soup.get_text(separator='\n\n')
                    
                    f.write(text)
                    f.write('\n\n' + '-'*20 + '\n\n') # 章节分隔符
                    
                    if callback:
                        progress = (i + 1) / total_items * 100
                        callback(progress, f"正在处理章节 {i+1}/{total_items}")
            
            return True, "成功"
        except Exception as e:
            return False, f"EPUB 错误: {str(e)}"

    def _convert_mobi(self, input_path, output_path, callback):
        if not HAS_MOBI_LIB and not HAS_INTERNAL_MOBI:
             return False, "缺少库 'mobi' 且内置读取器不可用。"
        
        # 优先尝试标准库 mobi
        if HAS_MOBI_LIB:
            try:
                # 'mobi' 库通常会解压到一个临时目录
                # 但我们可以尝试用它来获取内容。
                # 实际上，'mobi' python 包 (pip install mobi) 是 KindleUnpack 的包装器
                # 或者类似的工具，或者一个纯 python 阅读器。
                # 假设标准用法: mobi.extract(path)
                
                if callback: callback(10, "正在提取 MOBI 内容...")
                
                temp_dir, filepath = mobi.extract(input_path)
                
                # 结果通常是一个 HTML 文件或 OPF
                if callback: callback(50, "正在解析提取的内容...")
                
                # 现在我们需要读取提取的 html 文件并转换为 txt
                # filepath 通常指向 html 文件
                
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as html_file:
                        content = html_file.read()
                        
                    if HAS_EPUB_LIB: # 使用 BS4
                        soup = BeautifulSoup(content, 'html.parser')
                        text = soup.get_text(separator='\n\n')
                    else:
                        # 如果缺少 bs4，则使用回退的粗略正则表达式（如果存在 mobi，则不太可能缺少）
                        import re
                        text = re.sub('<[^<]+?>', '', content)
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                        
                    return True, "成功"
                else:
                    return False, "MOBI 提取失败（无输出文件）"
                    
            except Exception as e:
                # 如果标准库失败，尝试使用内置读取器
                print(f"标准 mobi 库失败: {e}，尝试内置读取器...")
                pass

        # 使用内置读取器作为回退或首选
        if HAS_INTERNAL_MOBI:
            try:
                if callback: callback(10, "正在使用内置读取器解析...")
                reader = MobiReader(input_path)
                content = reader.extract_text()
                
                if not content:
                    return False, "提取内容为空 (可能是加密文件或不支持的压缩格式)"
                
                # Clean HTML tags
                if callback: callback(50, "正在清理 HTML 标签...")
                
                if HAS_EPUB_LIB:
                    try:
                        # Try to parse with BeautifulSoup
                        # Some MOBI content might be partial HTML, BS4 handles it well
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # Remove style and script tags
                        for script in soup(["script", "style"]):
                            script.decompose()
                            
                        text = soup.get_text(separator='\n\n')
                    except Exception as bs_e:
                         print(f"BS4 parsing failed: {bs_e}, falling back to regex")
                         import re
                         text = re.sub(r'<[^>]+>', '', content)
                else:
                    import re
                    # Basic regex to strip HTML tags
                    text = re.sub(r'<[^>]+>', '', content)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                return True, "成功 (内置模式)"
            except Exception as e:
                return False, f"MOBI 错误: {str(e)}"
        
        return False, "无法转换此 MOBI 文件"

    def stop(self):
        self.stop_event.set()

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()
