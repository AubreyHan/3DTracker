---
name: 3d-track-animation
description: Generate 3D GPS trajectory flyover animation videos (both 9:16 vertical 720x1280 and 16:9 horizontal 1280x720 MP4s) from one or more GPX (.gpx) files, compressed archives (.zip, .tar.gz, .tgz, .tar.bz2, .tar.xz, .gz, .bz2, .xz, .7z, .rar), or the local ./GPX subdirectory across macOS and Linux. Activate this skill when the user issues a command like "3D轨迹： 行走｜骑行｜自驾（如没有说明，根据速度判断） 轨迹名称" (or asks to generate a 3D trajectory animation).
---

# 3D Track Flyover Animation Skill (`3d-track-animation`)

Generate smooth 60fps 3D satellite-terrain GPS flyover videos in both **16:9 horizontal (`1280x720`)** and **9:16 vertical (`720x1280`)** formats, compatible with both **macOS (`Darwin`)** and **Linux (`Linux`)**.

---

## 1. Command Trigger & Parsing Rules

### User Command Format
```text
3D轨迹： [行走|骑行|自驾] [轨迹名称]
```
Examples:
- `3D轨迹： 骑行 20261101奥森` → Mode = `骑行`, Title = `20261101奥森`
- `3D轨迹： 自驾 武汉到北京` → Mode = `自驾`, Title = `武汉到北京`
- `3D轨迹： 2026暑期西北自驾` → Mode = `auto` (inferred from average speed), Title = `2026暑期西北自驾`
- `3D轨迹：` → Mode = `auto`, Title = extracted from `<name>` tag in GPX

### Input GPX File & `./GPX` Subdirectory Auto-Discovery
1. **Uploaded or Specified Files / Archives**:
   - Supports **1 or multiple `.gpx` files** and **compressed archives** (`.zip`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.gz`, `.bz2`, `.xz`, `.7z`, `.rar`).
   - Note that Antigravity may save uploaded `.zip` or `.gz` files in `.user_uploaded/` with a `.gpx` extension or generic name; `prepare_and_download.py` inspects magic bytes automatically and unpacks them recursively.
2. **Automatic Fallback to `./GPX` Subdirectory (with Auto-Cleanup)**:
   - If the user issues a `3D轨迹：...` command **without uploading or specifying any GPX/archive files**, omit `--gpx` (or pass `--gpx-dir "<workspace_dir>/GPX"`).
   - `prepare_and_download.py` will automatically scan `<workspace_dir>/GPX` for all `.gpx` files and compressed archives.
   - Once both `16:9` and `9:16` MP4 videos have been generated and verified in `./output/`, `run_3d_track.sh` **automatically clears all files inside `<workspace_dir>/GPX`**.

### Output Subdirectory (`./output`)
- All generated MP4 videos MUST be saved into the `./output` subdirectory of the workspace (`<workspace_dir>/output/`), creating `./output` automatically if it does not exist:
  - `<workspace_dir>/output/<轨迹名称>_16x9.mp4` (`1280x720`, 60fps)
  - `<workspace_dir>/output/<轨迹名称>_9x16.mp4` (`720x1280`, 60fps)

### Progress Reporting Every 2 Minutes
- Whenever a task (such as downloading hundreds of map tiles or rendering long trajectories) runs in the background or takes longer than 2 minutes, use the `schedule` tool (`DurationSeconds: 120`, `TimerCondition: "any"`) to report concrete progress (e.g., tile download percentage or video rendering stage) to the user every 2 minutes until completion.

### 轨迹贴地与无投影规范 (Ground Clinging & Zero Shadow)
- **绝对贴地（严禁悬空）**：轨迹所有三维坐标必须紧贴 3D 地形表面（Cling tightly to the ground terrain surface），严禁出现轨迹浮空、悬空（Floating / Hovering）在半空中的情况。
- **杜绝投影（无额外阴影）**：严禁在轨迹下方绘制任何额外的地面投影、阴影线或投射倒影（No drop shadows or ground projections），确保画面纯净真实、轨迹如同直接印刻在遥感地表之上。

### 地图全屏覆盖与无空白规范 (Full Canvas Map Coverage & Zero Blank)
- **100% 全屏卫星贴图覆盖**：生成的视频画面（无论是 16:9 还是 9:16）必须自始至终被卫星遥感地表完全铺满，严禁在俯瞰全景、巡航跟飞、镜头起落时出现任何黑边、天际线虚空、天空暗色渐变或未加载空白边缘（No sky void, no dark borders, no unmapped holes）。
- **俯角与相机视锥几何约束**：俯瞰全景视角必须采用大俯角（70°~72°）直接投射于地表；飞行巡航跟飞保持 48°~52° 倾角，视锥上边缘严格受限于地表前方，彻底消除天空虚空。
- **无限地形延伸机制（Terrain Skirt）**：在核心地形网格边界外围自动生成 8 块外缘卫星地面裙面（Terrain Skirt），采用边界纹理坐标钳位延伸，即使极端转弯或超大视场也 100% 保持地表贴图覆盖。

### 真实路网清晰显示与纯净无歪斜字规范 (Road Network Overlay & Clean Base Map)
- **真实路网清晰呈现（Road Network Overlay）**：地图底图必须包含清晰可见的高速公路、国道、主干道等公路网络（Highways & Expressways），让观众清晰看清轨迹行经的真实道路脉络（如 G7 京新高速、G30 连霍高速等）。
- **底图对齐与无烘焙歪斜字**：路网图层采用 ArcGIS `World_Transportation` 矢量路网（与 ArcGIS 卫星图同为 WGS84 Web Mercator 严格空间对齐），底图严禁烘焙栅格化的地名汉字（杜绝文字随相机视角倒置或倾斜）；所有沿途城市地名与打卡点均采用独立的屏幕空间正向看板（Billboard Badges）竖立展示。

### 视网膜级地貌贴图与双线性滤波规范 (Retina Sub-Texel Bilinear Filtering)
- **高精度双线性插值（Bilinear Interpolation）**：3D 光栅化引擎严禁使用粗糙的最近邻点采样（Nearest-Neighbor），必须全面采用子纹素高精度双线性插值算法（Sub-texel Bilinear Filtering），消除低空跟飞时的马赛克方块、走样台阶与地表蠕动杂波，呈现细腻平滑的视网膜级遥感地貌与真实公路路面。
- **高分辨率瓦片金字塔（Zoom 14+ 优先）**：中短途自驾与运动轨迹自动分配高密度金字塔网格（Zoom 14+，地面分辨率 ~9.5m/px），清晰呈现道路分流、立体交叉与地貌细节。

### 地名标注稳定不晃动规范 (Stable Rock-Solid Billboard Badges)
- **镜头平稳如滑轨云台（严禁人工正弦摇摆）**：巡航相机严禁在偏航角（yaw）与俯仰角（pitch）上叠加周期性正弦摆动波（`orbit` / `wobble`），轨迹航向角经过高斯平滑滤波，视角稳定顺滑推进，保证地标绝对不随晃动而摆动。
- **全线精选无冲突空间间距（≥ 3.2km 间隔）**：自动排查沿途地标并剔除相邻 3.2km 内的重叠地标及冗余区域前缀，杜绝多个地标同屏紧邻导致的抢夺闪退。
- **时间轴指数透明度过渡（Exponential Alpha Smoothing）**：地标出入视野采用平滑指数透明度混合（`alpha = alpha * 0.85 + target * 0.15`），彻底消除地标因屏幕距离临界碰撞而产生的突兀闪烁、跳变与抖动。

### 地名等汉字竖立正向显示与字体醒目清晰规范 (Upright Billboard Labels & Prominent Typography)
- **屏幕空间正向看板（Billboard Screen-Aligned）**：视频中的地名、途经城市、关键打卡点等汉字必须全部设置为竖立正向显示（水平自左向右正常阅读方向），保持屏幕空间正向对齐，严禁随视频相机视角、偏航角或俯仰角发生倾斜、倒置或翻转。
- **底图纯净无地表歪斜字**：地表遥感卫星图层严禁烘焙栅格化倾斜/倒立地表地名词缀，地貌保持 100% 纯净高分辨率遥感卫星地球贴图（ArcGIS World Imagery）。
- **字体字号放大 1 倍（24px 矢量粗体）**：文字采用精选矢量开源 CJK 粗体（字号放大 1 倍至 **24px**），搭配双倍尺寸半透明深色圆角胶囊底板（`rgba(15, 23, 42, 220)`）、`2px` 半透明白边与 `1px` 文字立体阴影，无论手机竖屏还是宽屏均极其醒目清晰。
- **微型地标图钉与语义指示灯**：徽标配备微型图钉与类别指示灯（直辖市/省会为青色 `#38bdf8`，重点名胜为琥珀金 `#fbbf24`，普通县市为银灰），底部微型三角指针精准扎根于地表高程锚点。
- **基于轨迹与地标数量动态计算巡航节奏（非固定写死时长）**：巡航时长严禁采用硬编码固定常数，必须根据轨迹实际总里程 $D_{\text{km}}$ 以及途经城市地标数量 $N_{\text{labels}}$ 动态自适应调节（公式综合距离对数与地标充裕视窗）：短途运动（5~30km）巡航约 28~35 秒，中长途自驾（200~1000km）巡航约 50~70 秒，跨省超长途自驾（2000~8000+km）巡航约 75~100 秒（总时长相应为巡航加 14.5 秒），保证镜头前平均每个城市地标持续可见 4~7 秒，确保观众来得及清晰阅读沿途每一个地名与城市标注。
- **远距离提前迎面展现与屏幕碰撞避让**：标签前向可视距离扩展至 1750 米，城市地标更早平滑地从地平线浮现；内置屏幕碰撞规避检测（dx < 88px, dy < 36px），智能避免重叠。

### 多段 GPX 连续性检查与用户确认流程 (Multiple GPX Continuity Check)
- **自动间隙与时间校验**：当输入包含多个 GPX 文件时，脚本自动对相邻航段进行空间跳跃距离与时间顺序检验（默认阈值 `--max-gap-km 5.0`）。
- **断层预警与拦截**：若相邻轨迹终点与起点的距离超过阈值（如相隔 > 5.0 km）或时间倒流，脚本会输出断层明细并触发 `[CONTINUITY_CHECK_FAILED]`（退出码 3）。
- **必须先征询用户确认**：
  - 当检测到轨迹不连续时，Agent **必须暂停并向用户展示断层详情**（包含断层路段名称、相隔距离、时间差），并询问用户是否继续；
  - 经用户明确确认忽略断层后，方可追加 `--ignore-discontinuity` 参数继续合并与渲染；若用户选择取消，则中止等待用户补充文件。

---

## 2. Step-by-Step Execution Workflow

### Step 1: Prepare GPX Data & Download/Verify Cached Map Tiles

Run `scripts/prepare_and_download.py`.
- **Case A: User uploaded or specified file(s)**: pass them via `--gpx "<file1>" "<file2>" ...`
- **Case B: User did NOT upload or specify file(s)**: omit `--gpx` and pass `--gpx-dir "<workspace_dir>/GPX"` so it automatically scans `./GPX` and marks it for post-render cleanup.

```bash
python3 "<skill_dir>/scripts/prepare_and_download.py" \
  --gpx-dir "./GPX" \
  --name "<轨迹名称>" \
  --mode "<行走|骑行|自驾|auto>" \
  --work-dir "<scratch_or_tmp_dir>/track_work"
```
*(Note: `<skill_dir>` is the directory containing this `SKILL.md`. If the user uploaded files, add `--gpx "<path1>" "<path2>"` to the command above.)*

`prepare_and_download.py` automatically:
1. Unpacks any compressed archives or scans `./GPX` (relative to the current working directory, or the path passed to `--gpx-dir`) if `--gpx` is omitted.
2. Parses all GPX files, sorts them chronologically, merges points, and smooths elevation.
3. Determines the activity mode (`行走` / `骑行` / `自驾`) and selects optimal zoom level `z` (`8..17`).
4. Uses the persistent local cache directory (`<skill_dir>/cache/`) and verifies whether cached map tiles (`ETag` / `Last-Modified` / `SHA-256`) have remote updates.

### Step 2: Compile & Render Both 16:9 and 9:16 Videos into `./output`

Run `<skill_dir>/scripts/run_3d_track.sh`:

```bash
"<skill_dir>/scripts/run_3d_track.sh" \
  "<scratch_or_tmp_dir>/track_work/track_data.json" \
  "./output/<轨迹名称>"
```

What `run_3d_track.sh` does:
1. Detects the OS (`Darwin` vs `Linux`):
   - **macOS (`Darwin`)**: Compiles `scripts/render_3d_track.mm` (if updated) and renders via native `CoreGraphics` + `AVFoundation`.
   - **Linux (`Linux`)**: Compiles `scripts/render_3d_track_linux.cpp` (if updated), runs `scripts/prepare_linux_assets.py`, and renders via multi-threaded C++17 software rasterization piped into `ffmpeg`.
2. Creates `<workspace_dir>/output/` automatically if it does not exist, and outputs:
   - `<workspace_dir>/output/<轨迹名称>_16x9.mp4` (`1280x720`, 60fps)
   - `<workspace_dir>/output/<轨迹名称>_9x16.mp4` (`720x1280`, 60fps)
3. If the GPX files were loaded from `<workspace_dir>/GPX`, automatically empties `<workspace_dir>/GPX` once both videos are verified non-empty.

### Step 3: Verify & Present Results

Verify that both `<workspace_dir>/output/<轨迹名称>_16x9.mp4` and `<workspace_dir>/output/<轨迹名称>_9x16.mp4` exist and are non-empty, then report the summary metrics and clickable `file://` links to the user.
