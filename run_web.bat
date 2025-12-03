@echo off
chcp 65001 > nul
set HTTP_PROXY=
set HTTPS_PROXY=

echo 正在安装基础依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo 正在尝试安装 Mobi 支持库 (可选)...
pip install mobi -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo.
    echo [注意] 自动安装 mobi 库失败。
    echo 这可能是由于网络原因导致的。
    echo 如果您需要转换 .mobi 文件，请尝试手动运行: pip install mobi
    echo 或者检查您的网络设置。
    echo.
    echo 目前 .epub 转换功能不受影响。
) else (
    echo Mobi 库安装成功！
)

echo.
echo 启动 Web 服务器...
echo 请在浏览器中访问: http://localhost:5000
python app.py
pause
