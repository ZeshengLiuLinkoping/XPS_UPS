# 发给别人后如何运行（Windows）

你现在有两种发法：

## 方式 A（推荐）：解压即用（对方无需安装 Python）

1. 在你电脑里双击运行 `制作解压即用包.bat`
2. 按提示下载并解压 **Python embeddable package (64-bit)** 到生成的 `XPS_UPS_便携\python\` 下
3. 脚本会自动复制程序文件并安装依赖
4. 把整个 `XPS_UPS_便携` 文件夹 **打包成 zip 发给别人**
5. 对方解压后，双击 `运行.bat` 即可

最终对方拿到的结构大概是：

```text
XPS_UPS_便携\
  python\
    python.exe
    ...
  XPS_UPS.py
  app.py
  reader.py
  plots.py
  export_csv.py
  requirements.txt
  运行.bat
  给她用-免安装说明.txt
```

## 方式 B：对方电脑已安装 Python（或 Anaconda）

1. 直接把整个 `XPS_UPS` 文件夹发给对方
2. 对方双击 `运行.bat`  
   或者在该文件夹打开终端执行：

```bash
python XPS_UPS.py
```

> 依赖库：`numpy / matplotlib / igor2 / pandas`  
> 你的 `XPS_UPS.py` 也会尝试自动安装缺少的依赖（需要对方环境允许 pip 安装）。

