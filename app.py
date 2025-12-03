import os
import sys
import logging
import tempfile

# Determine base directory for file storage and logging
if getattr(sys, 'frozen', False):
    # Running as compiled EXE
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup logging IMMEDIATELY
log_file = os.path.join(BASE_DIR, 'app_startup.log')
try:
    logging.basicConfig(filename=log_file, level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        force=True)
except Exception:
    # Fallback to temp directory if we can't write to the app directory
    log_file = os.path.join(tempfile.gettempdir(), 'EbookConverterWeb_startup.log')
    try:
        logging.basicConfig(filename=log_file, level=logging.INFO, 
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            force=True)
    except:
        pass # Give up on logging

# Redirect stdout/stderr to logging
class StreamToLogger(object):
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level

    def write(self, buf):
        if buf and buf.strip():
            self.logger.log(self.log_level, buf.strip())

    def flush(self):
        pass

sys.stdout = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
sys.stderr = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)

logging.info("Initializing application...")

try:
    import time
    import zipfile
    import io
    import webbrowser
    import socket
    from threading import Timer
    
    logging.info("Standard libraries imported.")
    
    from flask import Flask, render_template, request, send_from_directory, jsonify, send_file
    from werkzeug.utils import secure_filename
    
    logging.info("Flask and Werkzeug imported.")
    
    from converter import Converter
    logging.info("Converter module imported.")

except Exception as e:
    logging.critical(f"Failed to import dependencies: {e}", exc_info=True)
    # Keep the process alive for a moment to ensure log is written
    import time
    time.sleep(2)
    sys.exit(1)

def log_msg(msg):
    logging.info(msg)

def log_err(msg):
    logging.error(msg)

try:
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        static_folder = os.path.join(sys._MEIPASS, 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
        log_msg(f"Running in frozen mode. Base dir: {BASE_DIR}")
    else:
        app = Flask(__name__)
        log_msg(f"Running in script mode. Base dir: {BASE_DIR}")


    # Configure storage paths
    # For cloud deployments (Render, Vercel), we must use /tmp as other directories are read-only
    # For local EXE/Script, we use the app directory
    if os.environ.get('VERCEL') or os.environ.get('RENDER'):
        STORAGE_DIR = tempfile.gettempdir()
    else:
        STORAGE_DIR = BASE_DIR

    app.config['UPLOAD_FOLDER'] = os.path.join(STORAGE_DIR, 'uploads')
    app.config['DOWNLOAD_FOLDER'] = os.path.join(STORAGE_DIR, 'downloads')
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
    log_msg("Directories ensured.")

    ALLOWED_EXTENSIONS = {'epub', 'mobi'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @app.route('/')
    def index():
        return render_template('index.html', version=time.time())

    @app.route('/upload', methods=['POST'])
    def upload_file():
        if 'file' not in request.files:
            return jsonify({'error': '没有文件被上传'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400
            
        if file and allowed_file(file.filename):
            # 使用原始文件名，但要注意安全（这是一个本地工具，所以相对安全）
            # 替换掉路径分隔符以防止目录遍历
            filename = file.filename.replace('/', '_').replace('\\', '_')
            
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)
            
            # Start conversion immediately
            converter = Converter()
            output_filename = os.path.splitext(filename)[0] + ".txt"
            output_path = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
            
            success, msg = converter.convert_file(upload_path, output_path)
            
            if success:
                return jsonify({
                    'success': True,
                    'filename': output_filename,
                    'download_url': f'/download/{output_filename}'
                })
            else:
                return jsonify({'error': f'转换失败: {msg}'}), 500
        else:
            return jsonify({'error': '不支持的文件格式'}), 400

    @app.route('/download/<filename>')
    def download_file(filename):
        return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)

    @app.route('/download_batch', methods=['POST'])
    def download_batch():
        data = request.get_json()
        if not data or 'filenames' not in data:
            return jsonify({'error': '没有提供文件名'}), 400
        
        filenames = data['filenames']
        if not filenames:
             return jsonify({'error': '文件名列表为空'}), 400

        # Create in-memory zip
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fname in filenames:
                file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], fname)
                if os.path.exists(file_path):
                    zf.write(file_path, fname)
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            attachment_filename='converted_ebooks.zip' # Flask 1.1.x use attachment_filename
        )

    def find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def open_browser(port):
        url = f'http://localhost:{port}/'
        log_msg(f"Opening browser at {url}")
        webbrowser.open_new(url)

    if __name__ == '__main__':
        try:
            port = 5000
            # Try to use port 5000, if occupied, find a free one
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 5000))
            if result == 0:
                log_msg("Port 5000 is in use, finding a free port...")
                port = find_free_port()
            sock.close()
            
            log_msg(f"Starting server on port {port}")
            
            # 如果是打包后的 exe，自动打开浏览器
            if getattr(sys, 'frozen', False):
                Timer(1.5, open_browser, args=[port]).start()
                app.run(host='0.0.0.0', port=port, debug=False)
            else:
                app.run(host='0.0.0.0', port=port, debug=True)
        except Exception as e:
            log_err(f"Server startup failed: {e}")
            raise

except Exception as e:
    log_err(f"Critical error during initialization: {e}")
    # Keep process alive briefly to ensure log is written
    time.sleep(2)
