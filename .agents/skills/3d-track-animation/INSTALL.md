# 3D 运动轨迹飞行动画 Skill (`3d-track-animation`) 安装与使用指南

本 Skill 支持将单个或多个 `.gpx` 轨迹文件（或包含 `.gpx` 的压缩包）一键渲染为 **16:9 横屏 (1280×720)** 与 **9:16 竖屏 (720×1280)** 两个 60fps 高清 3D 卫星地形飞行动画 MP4 视频，同时兼容 **macOS** 与 **Linux**。

---

## 一、目录结构说明

```text
3d-track-animation/
├── SKILL.md                        # Antigravity Skill 触发指令与工作流定义
├── INSTALL.md                      # 本安装与跨平台使用说明文档
├── resources/                      # 3D 运动图标透明贴图资源 (行走 / 骑行 / 自驾)
│   ├── icon_walk.png
│   ├── icon_bike.png
│   └── icon_car.png
├── scripts/
│   ├── prepare_and_download.py     # GPX/压缩包自动解包、多段合并、速度判定、瓦片缓存与更新校验
│   ├── run_3d_track.sh             # 跨平台 (macOS / Linux) 自动编译、渲染输出与 GPX 目录自动清理脚本
│   ├── render_3d_track.mm          # macOS 原生 3D 渲染器源码 (CoreGraphics + AVFoundation)
│   ├── render_3d_track_linux.cpp   # Linux 原生 C++17 多线程 3D 软光栅渲染器源码
│   └── prepare_linux_assets.py     # Linux 瓦片拼接与中文标题横幅预处理脚本
└── cache/                          # 本地持久化缓存目录 (运行时自动创建与维护)
    ├── tile_cache_meta.json        # 瓦片 ETag / Last-Modified / SHA-256 校验元数据
    ├── tiles_sat_z*/               # Esri World Imagery 卫星底图持久化缓存
    ├── tiles_road_z*/              # 高德路网 + 地名透明图层持久化缓存
    └── tracks/                     # 已解析的轨迹 JSON 缓存
```

---

## 二、安装到其他设备（macOS / Linux）

### 1. 选择安装位置

Antigravity 支持两种安装级别，任选其一即可：

- **方式 A：全局安装（推荐，该设备上所有项目均可直接调用）**
  将 `3d-track-animation` 文件夹放置到：
  ```bash
  ~/.gemini/antigravity/skills/3d-track-animation/
  ```
- **方式 B：项目级安装（仅在指定工程目录内生效）**
  将 `3d-track-animation` 文件夹放置到工程根目录下：
  ```bash
  <你的项目根目录>/.agents/skills/3d-track-animation/
  ```

### 2. 解压安装包命令

```bash
# 全局安装示例：
mkdir -p ~/.gemini/antigravity/skills
unzip -o 3d-track-animation-skill.zip -d ~/.gemini/antigravity/skills/

# 或者解压包含离线地图缓存的完整包：
unzip -o 3d-track-animation-skill-with-cache.zip -d ~/.gemini/antigravity/skills/

# 确保脚本具有可执行权限：
chmod +x ~/.gemini/antigravity/skills/3d-track-animation/scripts/run_3d_track.sh
```

---

## 三、系统环境依赖

### 1. macOS 设备 (`Darwin`)
- **Python 3**：系统自带或 Homebrew Python 3（仅使用标准库，无需额外 `pip` 包）。
- **Xcode Command Line Tools**：提供 `clang++` 及 macOS 原生 `CoreGraphics` / `AVFoundation` 框架。
  若新 Mac 尚未安装，执行以下命令即可：
  ```bash
  xcode-select --install
  ```
- **首次运行自检编译**：
  ```bash
  ~/.gemini/antigravity/skills/3d-track-animation/scripts/run_3d_track.sh --compile-only
  ```

### 2. Linux 设备 (`Linux`)
Linux 版本采用纯标准 C++17 多线程 3D 渲染器 (`render_3d_track_linux.cpp`) + `ffmpeg` H.264 管道编码，无需任何第三方 C++ 开发头文件：
- **Ubuntu / Debian 安装依赖**：
  ```bash
  sudo apt update && sudo apt install -y g++ python3 python3-pil ffmpeg fonts-noto-cjk p7zip-full
  ```
- **CentOS / RHEL / Rocky / Fedora 安装依赖**：
  ```bash
  sudo dnf install -y gcc-c++ python3 python3-pillow ffmpeg google-noto-sans-cjk-ttc-fonts p7zip
  ```
- **首次运行自检编译**：
  ```bash
  ~/.gemini/antigravity/skills/3d-track-animation/scripts/run_3d_track.sh --compile-only
  ```

---

## 四、使用方法与核心功能

### 1. 对话指令格式
在对话框中直接输入：
```text
3D轨迹： 行走｜骑行｜自驾（如没有说明，根据速度判断） 轨迹名称
```
**示例**：
- `3D轨迹： 2026暑期西北自驾`（省略运动方式时，自动根据平均移动速度判断：`< 8 km/h` 行走、`8~35 km/h` 骑行、`>= 35 km/h` 自驾）
- `3D轨迹： 骑行 环青海湖骑行`
- `3D轨迹： 行走 奥森健步走`

### 2. 两种提供 GPX 轨迹的方式
1. **直接上传文件或压缩包**：
   在发送指令时随消息上传 1 个或多个 `.gpx` 文件，或包含 `.gpx` 的压缩包（支持 `.zip`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.gz`, `.bz2`, `.xz`, `.7z`, `.rar`）。
2. **免上传自动扫描 `./GPX` 子目录（生成后自动清空）**：
   如果发送指令时**没有上传任何文件**，Skill 会自动在当前工作区子目录 `./GPX/` 下查找所有 `.gpx` 文件及压缩包；当横屏和竖屏视频全部生成完毕后，会**自动清空 `./GPX/` 目录内的文件**，方便下次直接放入新轨迹。

### 3. 视频输出目录 (`./output`)
所有生成的视频均自动保存在当前工作区的 `./output/` 子目录下（若不存在会自动创建）：
- `./output/<轨迹名称>_16x9.mp4`（16:9 横屏，`1280×720`，60fps）
- `./output/<轨迹名称>_9x16.mp4`（9:16 竖屏，`720×1280`，60fps）

### 4. 本地地图缓存与更新检查 (`cache/`)
- 已下载的卫星瓦片与路网标签图层持久化保存在 `3d-track-animation/cache/` 目录中。
- 再次渲染相同区域或修改参数时，自动通过 `ETag` / `Last-Modified` / `SHA-256` 校验缓存有效性，免去重复下载。

### 5. 轨迹贴地与无投影规范
- **紧贴地表（不悬空）**：轨迹的所有三维高程点均精确贴合 3D 地形曲面（Draped tightly on terrain），绝不产生脱离地面的浮空或悬空感。
- **无额外投影（不假投）**：渲染时不绘制任何轨迹的假阴影或地面落差投影线，保持纯净利落的实景画质。

### 6. 多段 GPX 连续性自动检查与用户确认
- 若输入包含多个 GPX 文件，脚本会自动按时间校验相邻路段之间的空间跳跃距离（默认阈值 5.0 km）与时间连续性。
- 若存在明显空间断层（相隔距离超限）或时间倒流，脚本将输出断层详细诊断信息并拦截退出；必须由用户确认是否忽略断层（追加 `--ignore-discontinuity` 参数）后方可继续。

### 7. 地图全屏覆盖与无空白规范
- **全屏覆盖（无任何虚空）**：视频全程无论横屏 16:9 还是竖屏 9:16，卫星地图纹理均 100% 充满全屏画布，消除原有的天际线黑边、空白漏洞或天空暗色虚空。
- **相机几何与边缘裙面**：通过相机大俯角视锥控制（俯瞰 70°~72°，跟飞 48°~52°）结合 8 方向无限地形裙面延伸（Terrain Skirt），确保视锥内任一像素永远由真实卫星遥感地表承接。

### 8. 地名等汉字竖立正向显示与字体醒目清晰规范
- **屏幕正向公告牌（Billboard Badges）**：所有地名、途经城市与打卡点均采用屏幕空间对齐的水平正向标注，自左向右自然阅读，严禁随视频相机旋转、俯仰或偏航发生倾斜、倒转或变形。
- **地表无贴图文字烘焙**：地表遥感卫星图层不烘焙任何不可控倾斜的栅格地名词缀，保持 100% 纯净自然地球质感。
- **字号放大 1 倍至 24px 矢量粗体**：使用矢量 CJK 粗体（字号放大 1 倍至 **24px**），搭配双倍尺寸半透明深色圆角胶囊底板（高约 44px）、`2px` 半透明白边与 `1px` 文字立体阴影，大幅提升在手机竖屏与宽屏大画面下的辨识度。
- **微型地标图钉与类别指示灯**：配备微型图钉与类别指示灯（直辖市/省会为青色 `#38bdf8`，重点名胜为琥珀金 `#fbbf24`，普通县市为银灰），底部微型三角指针精准扎根于地表实际地理高程点。
- **基于轨迹距离与地标数量动态调节巡航时间（非固定时长）**：飞行动画严禁采用写死的固定时长，而是综合轨迹总里程 $D_{\text{km}}$ 与地标数量 $N_{\text{labels}}$ 自适应调节巡航时长（短途 28~35 秒、中长途 50~70 秒、超长途 75~105 秒，总时长对应为巡航加 14.5 秒），确保观众在任何距离规模的线路上均拥有 4~7 秒的充裕辨识视窗，从容看清沿途城市地名。
- **超远视距提前展现与碰撞避让**：标签前向可视距离扩展至 1750 米，城市地标更早平滑地从地平线浮现；内置屏幕碰撞规避检测（dx < 88px, dy < 36px），智能避免重叠。

### 9. 命令行手动调用示例
```bash
# 1. 不指定 --gpx 时，自动从 ./GPX 目录读取轨迹或压缩包：
python3 ~/.gemini/antigravity/skills/3d-track-animation/scripts/prepare_and_download.py \
  --gpx-dir "./GPX" \
  --name "2026暑期西北自驾" \
  --mode "auto" \
  --work-dir "/tmp/track_work"

# 2. 渲染输出到 ./output 目录，并在完成后自动清空 ./GPX 目录内容：
~/.gemini/antigravity/skills/3d-track-animation/scripts/run_3d_track.sh \
  "/tmp/track_work/track_data.json" \
  "./output/2026暑期西北自驾"
```
