//
// render_3d_track_linux.cpp
// Portable, zero-external-header standard C++17 3D GPX Trajectory Renderer for Linux
// Compiles with: g++ -O3 -std=c++17 -pthread render_3d_track_linux.cpp -o render_3d_track_linux
//

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

struct TrackPt {
    double lat, lon, ele, dist, asc, desc, t;
    int hr;
    double px, py, pz;
    double pz_route;
};

struct ImageRGBA {
    int w = 0, h = 0;
    std::vector<uint8_t> data;

    bool load(const std::string& path) {
        std::ifstream f(path, std::ios::binary);
        if (!f) return false;
        uint32_t uw = 0, uh = 0;
        f.read(reinterpret_cast<char*>(&uw), 4);
        f.read(reinterpret_cast<char*>(&uh), 4);
        if (!f || uw == 0 || uh == 0 || uw > 32768 || uh > 32768) return false;
        w = static_cast<int>(uw);
        h = static_cast<int>(uh);
        data.resize(static_cast<size_t>(w) * h * 4);
        f.read(reinterpret_cast<char*>(data.data()), data.size());
        return f.good() || f.eof();
    }

    inline void sample_nearest(double u, double v, uint8_t& r, uint8_t& g, uint8_t& b) const {
        if (w <= 0 || h <= 0) { r = 20; g = 26; b = 33; return; }
        int ix = std::clamp(static_cast<int>(u), 0, w - 1);
        int iy = std::clamp(static_cast<int>(v), 0, h - 1);
        size_t idx = (static_cast<size_t>(iy) * w + ix) * 4;
        r = data[idx];
        g = data[idx + 1];
        b = data[idx + 2];
    }

    // High-precision bilinear interpolation for Retina-level crispness without texture crawling
    inline void sample_bilinear(double u, double v, uint8_t& r, uint8_t& g, uint8_t& b) const {
        if (w <= 0 || h <= 0) { r = 20; g = 26; b = 33; return; }
        double su = std::clamp(u - 0.5, 0.0, static_cast<double>(w - 1.0001));
        double sv = std::clamp(v - 0.5, 0.0, static_cast<double>(h - 1.0001));
        int x0 = static_cast<int>(su);
        int y0 = static_cast<int>(sv);
        int x1 = std::min(w - 1, x0 + 1);
        int y1 = std::min(h - 1, y0 + 1);
        int fx = static_cast<int>((su - x0) * 256.0);
        int fy = static_cast<int>((sv - y0) * 256.0);
        int ifx = 256 - fx;
        int ify = 256 - fy;

        size_t row0 = static_cast<size_t>(y0) * w * 4;
        size_t row1 = static_cast<size_t>(y1) * w * 4;
        const uint8_t* p00 = &data[row0 + x0 * 4];
        const uint8_t* p10 = &data[row0 + x1 * 4];
        const uint8_t* p01 = &data[row1 + x0 * 4];
        const uint8_t* p11 = &data[row1 + x1 * 4];

        int w00 = ifx * ify;
        int w10 = fx * ify;
        int w01 = ifx * fy;
        int w11 = fx * fy;

        r = static_cast<uint8_t>((p00[0] * w00 + p10[0] * w10 + p01[0] * w01 + p11[0] * w11 + 32768) >> 16);
        g = static_cast<uint8_t>((p00[1] * w00 + p10[1] * w10 + p01[1] * w01 + p11[1] * w11 + 32768) >> 16);
        b = static_cast<uint8_t>((p00[2] * w00 + p10[2] * w10 + p01[2] * w01 + p11[2] * w11 + 32768) >> 16);
    }
};

struct Canvas {
    int w, h;
    std::vector<uint8_t> rgb; // W * H * 3

    Canvas(int width, int height) : w(width), h(height), rgb(static_cast<size_t>(width) * height * 3, 0) {}

    uint8_t bg_r = 135, bg_g = 125, bg_b = 85;

    inline void blend_px(int x, int y, uint8_t r, uint8_t g, uint8_t b, float alpha) {
        if (x < 0 || x >= w || y < 0 || y >= h || alpha <= 0.0f) return;
        size_t idx = (static_cast<size_t>(y) * w + x) * 3;
        if (alpha >= 0.999f) {
            rgb[idx] = r; rgb[idx + 1] = g; rgb[idx + 2] = b;
        } else {
            float inv = 1.0f - alpha;
            rgb[idx]     = static_cast<uint8_t>(r * alpha + rgb[idx] * inv);
            rgb[idx + 1] = static_cast<uint8_t>(g * alpha + rgb[idx + 1] * inv);
            rgb[idx + 2] = static_cast<uint8_t>(b * alpha + rgb[idx + 2] * inv);
        }
    }

    void fill_solid(uint8_t r, uint8_t g, uint8_t b) {
        bg_r = r; bg_g = g; bg_b = b;
        for (int y = 0; y < h; ++y) {
            uint8_t* row = &rgb[static_cast<size_t>(y) * w * 3];
            for (int x = 0; x < w; ++x) {
                row[x * 3] = r; row[x * 3 + 1] = g; row[x * 3 + 2] = b;
            }
        }
    }

    void draw_rounded_rect(float rx, float ry, float rw, float rh, float rad,
                           uint8_t r, uint8_t g, uint8_t b, float alpha) {
        int x0 = std::max(0, static_cast<int>(std::floor(rx - 1)));
        int x1 = std::min(w - 1, static_cast<int>(std::ceil(rx + rw + 1)));
        int y0 = std::max(0, static_cast<int>(std::floor(ry - 1)));
        int y1 = std::min(h - 1, static_cast<int>(std::ceil(ry + rh + 1)));
        float cx0 = rx + rad, cx1 = rx + rw - rad;
        float cy0 = ry + rad, cy1 = ry + rh - rad;
        for (int y = y0; y <= y1; ++y) {
            for (int x = x0; x <= x1; ++x) {
                float px = x + 0.5f, py = y + 0.5f;
                float dx = std::max({cx0 - px, 0.0f, px - cx1});
                float dy = std::max({cy0 - py, 0.0f, py - cy1});
                float dist = std::sqrt(dx * dx + dy * dy) - rad;
                if (dist < 0.5f) {
                    float cov = std::clamp(0.5f - dist, 0.0f, 1.0f);
                    blend_px(x, y, r, g, b, alpha * cov);
                }
            }
        }
    }

    void draw_circle(float cx, float cy, float rad, uint8_t r, uint8_t g, uint8_t b, float alpha) {
        int x0 = std::max(0, static_cast<int>(std::floor(cx - rad - 1.5f)));
        int x1 = std::min(w - 1, static_cast<int>(std::ceil(cx + rad + 1.5f)));
        int y0 = std::max(0, static_cast<int>(std::floor(cy - rad - 1.5f)));
        int y1 = std::min(h - 1, static_cast<int>(std::ceil(cy + rad + 1.5f)));
        for (int y = y0; y <= y1; ++y) {
            for (int x = x0; x <= x1; ++x) {
                float dx = (x + 0.5f) - cx, dy = (y + 0.5f) - cy;
                float d = std::sqrt(dx * dx + dy * dy) - rad;
                if (d < 0.5f) {
                    float cov = std::clamp(0.5f - d, 0.0f, 1.0f);
                    blend_px(x, y, r, g, b, alpha * cov);
                }
            }
        }
    }

    void draw_segment(float x0, float y0, float x1, float y1, float radius,
                      uint8_t r, uint8_t g, uint8_t b, float alpha) {
        int ix0 = std::max(0, static_cast<int>(std::floor(std::min(x0, x1) - radius - 1.5f)));
        int ix1 = std::min(w - 1, static_cast<int>(std::ceil(std::max(x0, x1) + radius + 1.5f)));
        int iy0 = std::max(0, static_cast<int>(std::floor(std::min(y0, y1) - radius - 1.5f)));
        int iy1 = std::min(h - 1, static_cast<int>(std::ceil(std::max(y0, y1) + radius + 1.5f)));
        float vx = x1 - x0, vy = y1 - y0;
        float len2 = vx * vx + vy * vy;
        for (int y = iy0; y <= iy1; ++y) {
            for (int x = ix0; x <= ix1; ++x) {
                float px = x + 0.5f, py = y + 0.5f;
                float t = (len2 > 1e-6f) ? std::clamp(((px - x0) * vx + (py - y0) * vy) / len2, 0.0f, 1.0f) : 0.0f;
                float dx = px - (x0 + t * vx), dy = py - (y0 + t * vy);
                float d = std::sqrt(dx * dx + dy * dy) - radius;
                if (d < 0.5f) {
                    float cov = std::clamp(0.5f - d, 0.0f, 1.0f);
                    blend_px(x, y, r, g, b, alpha * cov);
                }
            }
        }
    }

    void draw_textured_triangle(
        float x0, float y0, float u0, float v0,
        float x1, float y1, float u1, float v1,
        float x2, float y2, float u2, float v2,
        const ImageRGBA& tex, float shade, float haze
    ) {
        int min_x = std::max(0, static_cast<int>(std::floor(std::min({x0, x1, x2}))));
        int max_x = std::min(w - 1, static_cast<int>(std::ceil(std::max({x0, x1, x2}))));
        int min_y = std::max(0, static_cast<int>(std::floor(std::min({y0, y1, y2}))));
        int max_y = std::min(h - 1, static_cast<int>(std::ceil(std::max({y0, y1, y2}))));
        if (min_x > max_x || min_y > max_y) return;

        float denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2);
        if (std::abs(denom) < 1e-5f) return;
        float inv_d = 1.0f / denom;

        for (int y = min_y; y <= max_y; ++y) {
            float py = y + 0.5f;
            uint8_t* row = &rgb[static_cast<size_t>(y) * w * 3];
            for (int x = min_x; x <= max_x; ++x) {
                float px = x + 0.5f;
                float w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) * inv_d;
                float w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) * inv_d;
                float w2 = 1.0f - w0 - w1;
                if (w0 >= -1e-4f && w1 >= -1e-4f && w2 >= -1e-4f) {
                    double u = w0 * u0 + w1 * u1 + w2 * u2;
                    double v = w0 * v0 + w1 * v1 + w2 * v2;
                    uint8_t tr, tg, tb;
                    tex.sample_bilinear(u, v, tr, tg, tb);
                    float fr = tr * shade * (1.0f - haze) + bg_r * haze;
                    float fg = tg * shade * (1.0f - haze) + bg_g * haze;
                    float fb = tb * shade * (1.0f - haze) + bg_b * haze;
                    row[x * 3]     = static_cast<uint8_t>(std::clamp(fr, 0.0f, 255.0f));
                    row[x * 3 + 1] = static_cast<uint8_t>(std::clamp(fg, 0.0f, 255.0f));
                    row[x * 3 + 2] = static_cast<uint8_t>(std::clamp(fb, 0.0f, 255.0f));
                }
            }
        }
    }
};

// Built-in clean 5x7 bitmap font for HUD ASCII labels & digits
static const uint8_t* get_glyph5x7(unsigned char ch) {
    static const uint8_t G_SPACE[7] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00};
    static const uint8_t G_DOT[7]   = {0x00,0x00,0x00,0x00,0x00,0x0C,0x0C};
    static const uint8_t G_0[7]     = {0x0E,0x11,0x13,0x15,0x19,0x11,0x0E};
    static const uint8_t G_1[7]     = {0x04,0x0C,0x04,0x04,0x04,0x04,0x0E};
    static const uint8_t G_2[7]     = {0x0E,0x11,0x01,0x06,0x08,0x10,0x1F};
    static const uint8_t G_3[7]     = {0x1F,0x02,0x04,0x06,0x01,0x11,0x0E};
    static const uint8_t G_4[7]     = {0x02,0x06,0x0A,0x12,0x1F,0x02,0x02};
    static const uint8_t G_5[7]     = {0x1F,0x10,0x1E,0x01,0x01,0x11,0x0E};
    static const uint8_t G_6[7]     = {0x06,0x08,0x10,0x1E,0x11,0x11,0x0E};
    static const uint8_t G_7[7]     = {0x1F,0x01,0x02,0x04,0x08,0x08,0x08};
    static const uint8_t G_8[7]     = {0x0E,0x11,0x11,0x0E,0x11,0x11,0x0E};
    static const uint8_t G_9[7]     = {0x0E,0x11,0x11,0x0F,0x01,0x02,0x0C};
    static const uint8_t G_A[7]     = {0x0E,0x11,0x11,0x1F,0x11,0x11,0x11};
    static const uint8_t G_D[7]     = {0x1E,0x11,0x11,0x11,0x11,0x11,0x1E};
    static const uint8_t G_H[7]     = {0x11,0x11,0x11,0x1F,0x11,0x11,0x11};
    static const uint8_t G_K[7]     = {0x11,0x12,0x14,0x18,0x14,0x12,0x11};
    static const uint8_t G_M[7]     = {0x11,0x1B,0x15,0x15,0x11,0x11,0x11};
    static const uint8_t G_R[7]     = {0x1E,0x11,0x11,0x1E,0x14,0x12,0x11};
    static const uint8_t G_a[7]     = {0x00,0x00,0x0E,0x01,0x0F,0x11,0x0F};
    static const uint8_t G_b[7]     = {0x10,0x10,0x1E,0x11,0x11,0x11,0x1E};
    static const uint8_t G_c[7]     = {0x00,0x00,0x0E,0x10,0x10,0x11,0x0E};
    static const uint8_t G_e[7]     = {0x00,0x00,0x0E,0x11,0x1F,0x10,0x0E};
    static const uint8_t G_g[7]     = {0x00,0x00,0x0F,0x11,0x0F,0x01,0x0E};
    static const uint8_t G_i[7]     = {0x04,0x00,0x0C,0x04,0x04,0x04,0x0E};
    static const uint8_t G_k[7]     = {0x10,0x10,0x12,0x14,0x18,0x14,0x12};
    static const uint8_t G_m[7]     = {0x00,0x00,0x1A,0x15,0x15,0x11,0x11};
    static const uint8_t G_n[7]     = {0x00,0x00,0x1E,0x11,0x11,0x11,0x11};
    static const uint8_t G_p[7]     = {0x00,0x00,0x1E,0x11,0x1E,0x10,0x10};
    static const uint8_t G_r[7]     = {0x00,0x00,0x16,0x19,0x10,0x10,0x10};
    static const uint8_t G_s[7]     = {0x00,0x00,0x0F,0x10,0x0E,0x01,0x1E};
    static const uint8_t G_t[7]     = {0x08,0x08,0x1C,0x08,0x08,0x09,0x06};
    static const uint8_t G_v[7]     = {0x00,0x00,0x11,0x11,0x11,0x0A,0x04};
    switch (ch) {
        case '.': return G_DOT;
        case '0': return G_0;
        case '1': return G_1;
        case '2': return G_2;
        case '3': return G_3;
        case '4': return G_4;
        case '5': return G_5;
        case '6': return G_6;
        case '7': return G_7;
        case '8': return G_8;
        case '9': return G_9;
        case 'A': return G_A;
        case 'D': return G_D;
        case 'H': return G_H;
        case 'K': return G_K;
        case 'M': return G_M;
        case 'R': return G_R;
        case 'a': return G_a;
        case 'b': return G_b;
        case 'c': return G_c;
        case 'e': return G_e;
        case 'g': return G_g;
        case 'i': return G_i;
        case 'k': return G_k;
        case 'm': return G_m;
        case 'n': return G_n;
        case 'p': return G_p;
        case 'r': return G_r;
        case 's': return G_s;
        case 't': return G_t;
        case 'v': return G_v;
        default:  return G_SPACE;
    }
}

static void draw_ascii_text(Canvas& c, const std::string& s, float x, float y, float scale,
                            uint8_t r, uint8_t g, uint8_t b, float alpha) {
    float cur_x = x;
    for (unsigned char ch : s) {
        if (ch < 128) {
            const uint8_t* glyph = get_glyph5x7(ch);
            for (int row = 0; row < 7; ++row) {
                uint8_t bits = glyph[row];
                for (int col = 0; col < 5; ++col) {
                    if (bits & (1 << (4 - col))) {
                        c.draw_rounded_rect(cur_x + col * scale, y + row * scale,
                                            scale * 1.05f, scale * 1.05f, scale * 0.25f, r, g, b, alpha);
                    }
                }
            }
        }
        cur_x += (ch == '.' ? 3.5f : 6.0f) * scale;
    }
}

static bool out_of_china(double lat, double lon) {
    return !(lon >= 73.66 && lon <= 135.05 && lat >= 3.86 && lat <= 53.55);
}
static double transform_lat(double x, double y) {
    double ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * std::sqrt(std::abs(x));
    ret += (20.0 * std::sin(6.0 * x * M_PI) + 20.0 * std::sin(2.0 * x * M_PI)) * 2.0 / 3.0;
    ret += (20.0 * std::sin(y * M_PI) + 40.0 * std::sin(y / 3.0 * M_PI)) * 2.0 / 3.0;
    ret += (160.0 * std::sin(y / 12.0 * M_PI) + 320.0 * std::sin(y * M_PI / 30.0)) * 2.0 / 3.0;
    return ret;
}
static double transform_lon(double x, double y) {
    double ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * std::sqrt(std::abs(x));
    ret += (20.0 * std::sin(6.0 * x * M_PI) + 20.0 * std::sin(2.0 * x * M_PI)) * 2.0 / 3.0;
    ret += (20.0 * std::sin(x * M_PI) + 40.0 * std::sin(x / 3.0 * M_PI)) * 2.0 / 3.0;
    ret += (150.0 * std::sin(x / 12.0 * M_PI) + 300.0 * std::sin(x / 30.0 * M_PI)) * 2.0 / 3.0;
    return ret;
}
static void wgs84_to_gcj02(double lat, double lon, double& mgLat, double& mgLon) {
    if (out_of_china(lat, lon)) { mgLat = lat; mgLon = lon; return; }
    const double a = 6378245.0, ee = 0.00669342162296594323;
    double dLat = transform_lat(lon - 105.0, lat - 35.0);
    double dLon = transform_lon(lon - 105.0, lat - 35.0);
    double radLat = lat / 180.0 * M_PI;
    double magic = std::sin(radLat);
    magic = 1.0 - ee * magic * magic;
    double sqrtMagic = std::sqrt(magic);
    dLat = (dLat * 180.0) / ((a * (1.0 - ee)) / (magic * sqrtMagic) * M_PI);
    dLon = (dLon * 180.0) / (a / sqrtMagic * std::cos(radLat) * M_PI);
    mgLat = lat + dLat;
    mgLon = lon + dLon;
}

static void latlon_to_mosaic_px(double lat, double lon, int z, int x_min, int y_min, bool use_gcj02, double& px, double& py) {
    double mlat = lat, mlon = lon;
    if (use_gcj02) wgs84_to_gcj02(lat, lon, mlat, mlon);
    double n = static_cast<double>(1 << z);
    double tx = (mlon + 180.0) / 360.0 * n;
    double lat_rad = mlat * M_PI / 180.0;
    double ty = (1.0 - std::log(std::tan(lat_rad) + 1.0 / std::cos(lat_rad)) / M_PI) / 2.0 * n;
    px = (tx - x_min) * 256.0;
    py = (ty - y_min) * 256.0;
}

static double smoothstep(double a, double b, double x) {
    double t = std::clamp((x - a) / (b - a), 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}

static double map_cruise_progress(double u) {
    u = std::clamp(u, 0.0, 1.0);
    const double a = 0.07;
    if (u < a) return (u * u) / (2.0 * a * (1.0 - a));
    if (u > 1.0 - a) {
        double d = 1.0 - u;
        return 1.0 - (d * d) / (2.0 * a * (1.0 - a));
    }
    return (u - 0.5 * a) / (1.0 - a);
}

struct Camera3D {
    double cx, cy, cz, focal, cx_scr, cy_scr;
    double rx, ry, rz, ux, uy, uz, fx, fy, fz;

    void setup(double cam_x, double cam_y, double cam_z, double yaw, double pitch, double fov_deg, int W, int H) {
        cx = cam_x; cy = cam_y; cz = cam_z;
        focal = (H * 0.5) / std::tan(fov_deg * 0.5 * M_PI / 180.0);
        cx_scr = W * 0.5; cy_scr = H * 0.5;
        double fx0 = std::sin(yaw), fy0 = -std::cos(yaw);
        rx = -fy0; ry = fx0; rz = 0.0;
        fx = fx0 * std::cos(pitch); fy = fy0 * std::cos(pitch); fz = -std::sin(pitch);
        ux = fx0 * std::sin(pitch); uy = fy0 * std::sin(pitch); uz = std::cos(pitch);
    }

    inline bool project(double wx, double wy, double wz, float& sx, float& sy, float& depth) const {
        double dx = wx - cx, dy = wy - cy, dz = wz - cz;
        double zc = dx * fx + dy * fy + dz * fz;
        if (zc < 10.0) return false;
        double xc = dx * rx + dy * ry + dz * rz;
        double yc = dx * ux + dy * uy + dz * uz;
        sx = static_cast<float>(cx_scr + (xc / zc) * focal);
        sy = static_cast<float>(cy_scr - (yc / zc) * focal);
        depth = static_cast<float>(zc);
        return true;
    }
};

// Minimal JSON number/string/boolean extractor for track_data.json
static double extract_json_num(const std::string& s, const std::string& key, double def = 0.0) {
    std::string pat = "\"" + key + "\":";
    size_t pos = s.find(pat);
    if (pos == std::string::npos) return def;
    pos += pat.size();
    while (pos < s.size() && (s[pos] == ' ' || s[pos] == '\t')) ++pos;
    return std::strtod(s.c_str() + pos, nullptr);
}

static bool extract_json_bool(const std::string& s, const std::string& key, bool def = false) {
    std::string pat = "\"" + key + "\":";
    size_t pos = s.find(pat);
    if (pos == std::string::npos) return def;
    pos += pat.size();
    while (pos < s.size() && (s[pos] == ' ' || s[pos] == '\t')) ++pos;
    return s.compare(pos, 4, "true") == 0 ? true : (s.compare(pos, 5, "false") == 0 ? false : def);
}

static std::vector<TrackPt> extract_points(const std::string& s) {
    std::vector<TrackPt> pts;
    size_t ppos = s.find("\"points\":");
    if (ppos == std::string::npos) return pts;
    size_t cur = s.find('[', ppos);
    while (cur != std::string::npos) {
        size_t ob = s.find('{', cur);
        if (ob == std::string::npos) break;
        size_t cb = s.find('}', ob);
        if (cb == std::string::npos) break;
        std::string obj = s.substr(ob, cb - ob + 1);
        TrackPt p{};
        p.lat = extract_json_num(obj, "lat");
        p.lon = extract_json_num(obj, "lon");
        p.ele = extract_json_num(obj, "ele");
        p.dist = extract_json_num(obj, "dist");
        p.asc = extract_json_num(obj, "asc");
        p.desc = extract_json_num(obj, "desc");
        p.t = extract_json_num(obj, "t");
        p.hr = static_cast<int>(extract_json_num(obj, "hr"));
        pts.push_back(p);
        cur = cb + 1;
    }
    return pts;
}

struct BillboardLabel {
    std::string name;
    double lat, lon;
    int tier;
    bool overview;
    int atlas_x, atlas_y, w, h, anchor_x, anchor_y;
    double px, py, pz;
};

static std::string extract_json_str(const std::string& s, const std::string& key) {
    std::string pat = "\"" + key + "\":\"";
    size_t pos = s.find(pat);
    if (pos == std::string::npos) return "";
    pos += pat.size();
    size_t end = s.find('"', pos);
    if (end == std::string::npos) return "";
    return s.substr(pos, end - pos);
}

static std::vector<BillboardLabel> load_labels_json(const std::string& path) {
    std::vector<BillboardLabel> list;
    std::ifstream f(path);
    if (!f.is_open()) return list;
    std::stringstream ss;
    ss << f.rdbuf();
    std::string s = ss.str();

    size_t cur = 0;
    while ((cur = s.find('{', cur)) != std::string::npos) {
        size_t end = s.find('}', cur);
        if (end == std::string::npos) break;
        std::string obj = s.substr(cur, end - cur + 1);
        BillboardLabel lbl{};
        lbl.name = extract_json_str(obj, "name");
        lbl.lat = extract_json_num(obj, "lat");
        lbl.lon = extract_json_num(obj, "lon");
        lbl.tier = static_cast<int>(extract_json_num(obj, "tier", 2));
        lbl.overview = extract_json_bool(obj, "overview", false);
        lbl.atlas_x = static_cast<int>(extract_json_num(obj, "atlas_x", 0));
        lbl.atlas_y = static_cast<int>(extract_json_num(obj, "atlas_y", 0));
        lbl.w = static_cast<int>(extract_json_num(obj, "w", 0));
        lbl.h = static_cast<int>(extract_json_num(obj, "h", 0));
        lbl.anchor_x = static_cast<int>(extract_json_num(obj, "anchor_x", 0));
        lbl.anchor_y = static_cast<int>(extract_json_num(obj, "anchor_y", 0));
        list.push_back(lbl);
        cur = end + 1;
    }
    return list;
}

int main(int argc, char* argv[]) {
    std::string json_path, assets_dir, out_mp4;
    int W = 1280, H = 720;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--json" && i + 1 < argc) json_path = argv[++i];
        else if (a == "--assets-dir" && i + 1 < argc) assets_dir = argv[++i];
        else if (a == "--out" && i + 1 < argc) out_mp4 = argv[++i];
        else if (a == "--9x16") { W = 720; H = 1280; }
        else if (a == "--16x9") { W = 1280; H = 720; }
    }
    if (json_path.empty() || assets_dir.empty() || out_mp4.empty()) {
        std::cerr << "Usage: render_3d_track_linux --json <track_data.json> --assets-dir <dir> --out <out.mp4> [--16x9|--9x16]\n";
        return 1;
    }

    std::ifstream jf(json_path);
    std::stringstream ss;
    ss << jf.rdbuf();
    std::string jstr = ss.str();

    int z = static_cast<int>(extract_json_num(jstr, "z", 12));
    int x_min = static_cast<int>(extract_json_num(jstr, "x_min", 0));
    int x_max = static_cast<int>(extract_json_num(jstr, "x_max", 10));
    int y_min = static_cast<int>(extract_json_num(jstr, "y_min", 0));
    int y_max = static_cast<int>(extract_json_num(jstr, "y_max", 10));
    bool use_gcj02 = extract_json_bool(jstr, "use_gcj02", false);
    double min_ele = extract_json_num(jstr, "min_ele", 0.0);
    double max_ele = extract_json_num(jstr, "max_ele", 100.0);
    double total_dist = extract_json_num(jstr, "total_dist", 1000.0);
    int avg_hr = static_cast<int>(extract_json_num(jstr, "avg_hr", 0));

    std::vector<TrackPt> pts = extract_points(jstr);
    if (pts.size() < 2) {
        std::cerr << "Error: Fewer than 2 track points.\n";
        return 1;
    }

    ImageRGBA mosaic_color, mosaic_gray, icon_img, banner_img, labels_atlas;
    if (!mosaic_color.load(assets_dir + "/mosaic_color.rgba")) {
        std::cerr << "Error: Failed to load mosaic_color.rgba\n";
        return 1;
    }
    mosaic_gray.load(assets_dir + "/mosaic_gray.rgba");
    icon_img.load(assets_dir + "/icon.rgba");
    banner_img.load(assets_dir + (H > W ? "/banner_9x16.rgba" : "/banner_16x9.rgba"));
    bool has_labels = labels_atlas.load(assets_dir + "/labels_atlas.rgba");
    std::vector<BillboardLabel> labels;
    if (has_labels) {
        labels = load_labels_json(assets_dir + "/labels.json");
    }

    uint8_t mean_r = 135, mean_g = 125, mean_b = 85;
    if (mosaic_color.w > 0 && mosaic_color.h > 0 && !mosaic_color.data.empty()) {
        size_t sample_cnt = 0, sum_r = 0, sum_g = 0, sum_b = 0;
        size_t total_px = mosaic_color.data.size() / 4;
        size_t step = std::max<size_t>(1, total_px / 10000);
        for (size_t p = 0; p < total_px; p += step) {
            sum_r += mosaic_color.data[p * 4];
            sum_g += mosaic_color.data[p * 4 + 1];
            sum_b += mosaic_color.data[p * 4 + 2];
            sample_cnt++;
        }
        if (sample_cnt > 0) {
            mean_r = static_cast<uint8_t>(sum_r / sample_cnt);
            mean_g = static_cast<uint8_t>(sum_g / sample_cnt);
            mean_b = static_cast<uint8_t>(sum_b / sample_cnt);
        }
    }

    int MW = (x_max - x_min + 1) * 256;
    int MH = (y_max - y_min + 1) * 256;

    double rx0 = 1e9, rx1 = -1e9, ry0 = 1e9, ry1 = -1e9;
    for (auto& p : pts) {
        latlon_to_mosaic_px(p.lat, p.lon, z, x_min, y_min, use_gcj02, p.px, p.py);
        rx0 = std::min(rx0, p.px); rx1 = std::max(rx1, p.px);
        ry0 = std::min(ry0, p.py); ry1 = std::max(ry1, p.py);
    }
    double route_span = std::max(300.0, std::max(rx1 - rx0, ry1 - ry0));
    double ele_span = std::max(8.0, max_ele - min_ele);
    double target_relief = std::clamp(route_span * 0.075, 45.0, 95.0);
    double z_scale = target_relief / ele_span;
    double route_z_scale = z_scale * 0.62;

    for (auto& p : pts) {
        p.pz = (p.ele - min_ele) * z_scale;
        p.pz_route = (p.ele - min_ele) * route_z_scale;
    }
    std::vector<double> smooth_pz(pts.size(), 0.0);
    for (size_t i = 0; i < pts.size(); ++i) {
        double wsum = 0.0, zsum = 0.0;
        for (int k = -25; k <= 25; ++k) {
            int j = std::clamp(static_cast<int>(i) + k, 0, static_cast<int>(pts.size()) - 1);
            double w = std::exp(-(k * k) / (2.0 * 10.0 * 10.0));
            zsum += pts[j].pz_route * w;
            wsum += w;
        }
        smooth_pz[i] = zsum / wsum;
    }
    for (size_t i = 0; i < pts.size(); ++i) pts[i].pz_route = smooth_pz[i];

    // Build 180x180 3D terrain mesh
    const int NX = 180, NY = 180;
    std::vector<float> hgrid((NX + 1) * (NY + 1), 0.0f);
    std::vector<float> sgrid((NX + 1) * (NY + 1), 1.0f);
    for (int j = 0; j <= NY; ++j) {
        double wy = static_cast<double>(j) * MH / NY;
        for (int i = 0; i <= NX; ++i) {
            double wx = static_cast<double>(i) * MW / NX;
            double sum_w = 0.0, sum_z = 0.0, min_d2 = 1e18;
            for (size_t k = 0; k < pts.size(); k += 6) {
                double dx = wx - pts[k].px, dy = wy - pts[k].py;
                double d2 = dx * dx + dy * dy;
                if (d2 < min_d2) min_d2 = d2;
                double w = 1.0 / (d2 + 8000.0);
                sum_w += w;
                sum_z += pts[k].pz_route * w;
            }
            double base_z = (sum_w > 0.0) ? (sum_z / sum_w) : 0.0;
            double dist_r = std::sqrt(min_d2);
            double corridor = smoothstep(35.0, 220.0, dist_r);
            double n1 = std::sin(wx * 0.0045 + 0.7) * std::cos(wy * 0.0045 - 0.4) * 52.0;
            double n2 = std::sin(wx * 0.011 - wy * 0.009) * 24.0;
            hgrid[j * (NX + 1) + i] = static_cast<float>( std::max(0.0, base_z + corridor * (n1 + n2 + 28.0)) );
        }
    }
    double cell_w = static_cast<double>(MW) / NX, cell_h = static_cast<double>(MH) / NY;
    auto sample_terrain_h = [&](double wx, double wy) -> double {
        double gx = wx / cell_w;
        double gy = wy / cell_h;
        int i0 = std::clamp(static_cast<int>(std::floor(gx)), 0, NX);
        int j0 = std::clamp(static_cast<int>(std::floor(gy)), 0, NY);
        int i1 = std::min(NX, i0 + 1);
        int j1 = std::min(NY, j0 + 1);
        double fx = std::clamp(gx - i0, 0.0, 1.0);
        double fy = std::clamp(gy - j0, 0.0, 1.0);
        double h00 = hgrid[j0 * (NX + 1) + i0];
        double h10 = hgrid[j0 * (NX + 1) + i1];
        double h01 = hgrid[j1 * (NX + 1) + i0];
        double h11 = hgrid[j1 * (NX + 1) + i1];
        return (h00 * (1.0 - fx) + h10 * fx) * (1.0 - fy) + (h01 * (1.0 - fx) + h11 * fx) * fy;
    };

    // Ensure all route points tightly cling to the ground mesh surface (zero floating, zero hover)
    for (size_t i = 0; i < pts.size(); ++i) {
        pts[i].pz_route = sample_terrain_h(pts[i].px, pts[i].py) + 0.25;
    }

    if (has_labels && !labels.empty()) {
        for (auto& lbl : labels) {
            latlon_to_mosaic_px(lbl.lat, lbl.lon, z, x_min, y_min, use_gcj02, lbl.px, lbl.py);
            lbl.pz = sample_terrain_h(lbl.px, lbl.py) + 0.35;
        }
    }

    for (int j = 0; j <= NY; ++j) {
        for (int i = 0; i <= NX; ++i) {
            int i0 = std::max(0, i - 1), i1 = std::min(NX, i + 1);
            int j0 = std::max(0, j - 1), j1 = std::min(NY, j + 1);
            double dzdx = (hgrid[j * (NX + 1) + i1] - hgrid[j * (NX + 1) + i0]) / ((i1 - i0) * cell_w);
            double dzdy = (hgrid[j1 * (NX + 1) + i] - hgrid[j0 * (NX + 1) + i]) / ((j1 - j0) * cell_h);
            double nx = -dzdx * 2.2, ny = -dzdy * 2.2, nz = 1.0;
            double inv = 1.0 / std::sqrt(nx * nx + ny * ny + nz * nz);
            double dot = (nx * -0.55 + ny * -0.45 + nz * 0.70) * inv;
            sgrid[j * (NX + 1) + i] = static_cast<float>(std::clamp(0.68 + 0.46 * dot, 0.50, 1.18));
        }
    }

    // Precompute headings
    int N = static_cast<int>(pts.size());
    std::vector<double> headings(N, 0.0), smooth_hdg(N, 0.0);
    for (int i = 0; i < N; ++i) {
        int i0 = std::max(0, i - 18), i1 = std::min(N - 1, i + 18);
        double dx = pts[i1].px - pts[i0].px, dy = pts[i1].py - pts[i0].py;
        headings[i] = (dx * dx + dy * dy < 1e-4 && i > 0) ? headings[i - 1] : std::atan2(dx, -dy);
    }
    for (int i = 1; i < N; ++i) {
        double d = headings[i] - headings[i - 1];
        while (d > M_PI) d -= 2.0 * M_PI;
        while (d < -M_PI) d += 2.0 * M_PI;
        headings[i] = headings[i - 1] + d;
    }
    for (int i = 0; i < N; ++i) {
        double ws = 0.0, hs = 0.0;
        for (int k = -45; k <= 45; ++k) {
            int j = std::clamp(i + k, 0, N - 1);
            double w = std::exp(-(k * k) / (2.0 * 20.0 * 20.0));
            hs += headings[j] * w; ws += w;
        }
        smooth_hdg[i] = hs / ws;
    }

    double cx_mid = 0.5 * (rx0 + rx1), cy_mid = 0.5 * (ry0 + ry1);
    double span_x = rx1 - rx0, span_y = ry1 - ry0;
    bool is_portrait = (H > W);

    // Overview Camera: 70°-72° steep tilt looking firmly downward at satellite earth
    // Centers the route on screen and ensures 100% full-screen satellite terrain coverage (0% void)
    double ov_pitch = (is_portrait ? 72.0 : 70.0) * M_PI / 180.0;
    double ov_yaw = 0.0; // Geographic North orientation
    double ov_alt = is_portrait
        ? std::clamp(std::max(span_x / 0.58, span_y / 1.05) * 1.08, 700.0, 2200.0)
        : std::clamp(std::max(span_x / 1.55, span_y / 0.85) * 1.12, 600.0, 1800.0);
    double ov_cx = cx_mid;
    double ov_cy = cy_mid + ov_alt / std::tan(ov_pitch);

    // Cruising (Follow) Camera: 48°-52° tilt to keep 100% terrain coverage from row 0 to row H-1
    double follow_pitch = (is_portrait ? 52.0 : 48.0) * M_PI / 180.0;
    double follow_alt   = is_portrait ? 160.0 : 130.0;
    double follow_dist  = is_portrait ? 110.0 : 100.0;

    // Open ffmpeg pipe
    std::ostringstream cmd;
    cmd << "ffmpeg -y -f rawvideo -pix_fmt rgb24 -s " << W << "x" << H
        << " -r 30 -i - -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \"" << out_mp4 << "\"";
    FILE* pipe = popen(cmd.str().c_str(), "w");
    if (!pipe) {
        std::cerr << "Error: Failed to open ffmpeg pipe.\n";
        return 1;
    }

    // Dynamic flight timing based on trajectory distance and city landmark density:
    // Ensures viewers have ample time to comfortably see and read every city landmark along the route.
    double d_km = total_dist / 1000.0;
    double t_dist = 26.0 + 8.5 * std::log(1.0 + std::max(0.0, d_km) / 10.0);
    size_t n_labels = labels.size();
    size_t n_overview = 0;
    for (const auto& l : labels) if (l.overview) n_overview++;
    double t_cities = std::max(25.0, static_cast<double>(n_labels) * 1.5 + static_cast<double>(n_overview) * 2.0);
    double cruise_sec = std::clamp(std::max(t_dist, t_cities), 28.0, 105.0);

    // If specified in track_data.json, respect explicit override:
    double json_cruise = extract_json_num(jstr, "cruise_sec", 0.0);
    if (json_cruise >= 15.0) cruise_sec = json_cruise;

    const double INTRO_SEC = 4.5;
    const double TRANS_SEC = 3.0;
    const double CRUISE_SEC = cruise_sec;
    const double OUTRO_TRANS_SEC = 3.0;
    const double OUTRO_HOLD_SEC = 4.0;

    const double T0 = INTRO_SEC;
    const double T1 = T0 + TRANS_SEC;
    const double T2 = T1 + CRUISE_SEC;
    const double T3 = T2 + OUTRO_TRANS_SEC;
    const double TOTAL_SEC = T3 + OUTRO_HOLD_SEC;
    const int FPS = 30;
    const int TOTAL_FRAMES = static_cast<int>(TOTAL_SEC * FPS);
    Canvas canvas(W, H);

    std::cout << "Dynamic Timing : Dist=" << d_km << " km, Labels=" << n_labels
              << " (" << n_overview << " overview) -> Cruise=" << CRUISE_SEC
              << "s, Total=" << TOTAL_SEC << "s (" << TOTAL_FRAMES << " frames @ " << FPS << "fps)\n";

    struct Quad { int i, j; float depth; };
    std::vector<Quad> quads;
    quads.reserve(NX * NY);

    std::vector<float> smooth_lbl_alpha(labels.size(), 0.0f);
    std::vector<float> smooth_lbl_sx(labels.size(), -9999.0f);
    std::vector<float> smooth_lbl_sy(labels.size(), -9999.0f);

    for (int f = 0; f < TOTAL_FRAMES; ++f) {
        double t_sec = static_cast<double>(f) / FPS;
        double cam_x, cam_y, cam_z, cam_yaw, cam_pitch;
        int cur_idx = 0;
        double hud_alpha = 0.0, banner_alpha = 0.0;

        if (t_sec < T0) {
            cur_idx = N - 1;
            banner_alpha = smoothstep(0.0, 0.8, t_sec) * (1.0 - smoothstep(T0 - 1.0, T0, t_sec));
            double drift = t_sec / T0;
            cam_yaw = ov_yaw + (drift - 0.5) * 0.05;
            cam_pitch = ov_pitch;
            cam_x = ov_cx;
            cam_y = ov_cy;
            cam_z = ov_alt;
        } else if (t_sec < T1) {
            double u = smoothstep(T0, T1, t_sec);
            cur_idx = 0;
            hud_alpha = smoothstep(T0 + 1.5, T1, t_sec);
            double sy = smooth_hdg[0];
            double sx = pts[0].px - std::sin(sy) * follow_dist;
            double sy_pos = pts[0].py + std::cos(sy) * follow_dist;
            double sz = pts[0].pz_route + follow_alt;
            cam_x = ov_cx * (1.0 - u) + sx * u;
            cam_y = ov_cy * (1.0 - u) + sy_pos * u;
            cam_z = ov_alt * (1.0 - u) + sz * u;
            cam_yaw = ov_yaw * (1.0 - u) + sy * u;
            cam_pitch = ov_pitch * (1.0 - u) + follow_pitch * u;
        } else if (t_sec < T2) {
            // Slower, graceful cruising dynamically scaled to trajectory distance and city count
            double u = (t_sec - T1) / CRUISE_SEC;
            double prog = map_cruise_progress(u);
            double idx_f = prog * (N - 1);
            cur_idx = std::clamp(static_cast<int>(idx_f), 0, N - 1);
            int nxt_idx = std::min(N - 1, cur_idx + 1);
            double frac = idx_f - cur_idx;
            hud_alpha = 1.0;
            double px = pts[cur_idx].px * (1.0 - frac) + pts[nxt_idx].px * frac;
            double py = pts[cur_idx].py * (1.0 - frac) + pts[nxt_idx].py * frac;
            double pz = pts[cur_idx].pz_route * (1.0 - frac) + pts[nxt_idx].pz_route * frac;
            double hdg = smooth_hdg[cur_idx] * (1.0 - frac) + smooth_hdg[nxt_idx] * frac;
            cam_yaw = hdg;
            cam_pitch = follow_pitch;
            cam_x = px - std::sin(cam_yaw) * follow_dist;
            cam_y = py + std::cos(cam_yaw) * follow_dist;
            cam_z = pz + follow_alt;
        } else {
            double u = smoothstep(T2, T3, t_sec);
            cur_idx = N - 1;
            hud_alpha = 1.0 - smoothstep(T2, T2 + 1.5, t_sec);
            banner_alpha = smoothstep(T2 + 1.5, T3, t_sec);
            double ey = smooth_hdg[N - 1];
            double ex = pts[N - 1].px - std::sin(ey) * follow_dist;
            double ey_pos = pts[N - 1].py + std::cos(ey) * follow_dist;
            double ez = pts[N - 1].pz_route + follow_alt;
            double d = ey - ov_yaw;
            while (d > M_PI) d -= 2.0 * M_PI;
            while (d < -M_PI) d += 2.0 * M_PI;
            double ov_end_yaw = ey - d;
            cam_x = ex * (1.0 - u) + ov_cx * u;
            cam_y = ey_pos * (1.0 - u) + ov_cy * u;
            cam_z = ez * (1.0 - u) + ov_alt * u;
            cam_yaw = ey * (1.0 - u) + ov_end_yaw * u;
            cam_pitch = follow_pitch * (1.0 - u) + ov_pitch * u;
        }

        Camera3D cam;
        cam.setup(cam_x, cam_y, cam_z, cam_yaw, cam_pitch, is_portrait ? 58.0 : 50.0, W, H);
        canvas.fill_solid(mean_r, mean_g, mean_b);

        // Project terrain vertices
        std::vector<float> vx((NX + 1) * (NY + 1)), vy((NX + 1) * (NY + 1)), vz((NX + 1) * (NY + 1));
        std::vector<uint8_t> v_ok((NX + 1) * (NY + 1), 0);
        for (int j = 0; j <= NY; ++j) {
            double wy = j * cell_h;
            for (int i = 0; i <= NX; ++i) {
                double wx = i * cell_w;
                int idx = j * (NX + 1) + i;
                float sx, sy, dp;
                if (cam.project(wx, wy, hgrid[idx], sx, sy, dp)) {
                    vx[idx] = sx; vy[idx] = sy; vz[idx] = dp; v_ok[idx] = 1;
                }
            }
        }

        quads.clear();
        for (int j = 0; j < NY; ++j) {
            for (int i = 0; i < NX; ++i) {
                int i00 = j * (NX + 1) + i, i10 = i00 + 1, i01 = (j + 1) * (NX + 1) + i, i11 = i01 + 1;
                if (!(v_ok[i00] && v_ok[i10] && v_ok[i01] && v_ok[i11])) continue;
                float minx = std::min({vx[i00], vx[i10], vx[i01], vx[i11]});
                float maxx = std::max({vx[i00], vx[i10], vx[i01], vx[i11]});
                float miny = std::min({vy[i00], vy[i10], vy[i01], vy[i11]});
                float maxy = std::max({vy[i00], vy[i10], vy[i01], vy[i11]});
                if (maxx < 0 || minx > W || maxy < 0 || miny > H) continue;
                float d = 0.25f * (vz[i00] + vz[i10] + vz[i01] + vz[i11]);
                quads.push_back({i, j, d});
            }
        }
        std::sort(quads.begin(), quads.end(), [](const Quad& a, const Quad& b) { return a.depth > b.depth; });

        for (const auto& q : quads) {
            int i = q.i, j = q.j;
            int i00 = j * (NX + 1) + i, i10 = i00 + 1, i01 = (j + 1) * (NX + 1) + i, i11 = i01 + 1;
            float u0 = static_cast<float>(i * cell_w), u1 = static_cast<float>((i + 1) * cell_w);
            float v0 = static_cast<float>(j * cell_h), v1 = static_cast<float>((j + 1) * cell_h);
            float sh = 0.25f * (sgrid[i00] + sgrid[i10] + sgrid[i01] + sgrid[i11]);
            float hz = static_cast<float>(std::clamp((q.depth - 900.0) / 3800.0, 0.0, 0.35));
            canvas.draw_textured_triangle(vx[i00], vy[i00], u0, v0, vx[i10], vy[i10], u1, v0, vx[i11], vy[i11], u1, v1, mosaic_color, sh, hz);
            canvas.draw_textured_triangle(vx[i00], vy[i00], u0, v0, vx[i11], vy[i11], u1, v1, vx[i01], vy[i01], u0, v1, mosaic_color, sh, hz);
        }

        // Draw 3D route clinging tightly to the ground (NO shadow, NO hover)
        if (cur_idx >= 1) {
            float psx = 0, psy = 0, pdp = 0;
            bool prev_ok = false;
            for (int k = 0; k <= cur_idx; ++k) {
                float sx, sy, dp;
                if (cam.project(pts[k].px, pts[k].py, pts[k].pz_route, sx, sy, dp)) {
                    if (prev_ok) {
                        canvas.draw_segment(psx, psy, sx, sy, 5.0f, 165, 255, 20, 0.35f);
                        canvas.draw_segment(psx, psy, sx, sy, 3.2f, 198, 255, 42, 0.98f);
                    }
                    psx = sx; psy = sy; prev_ok = true;
                } else prev_ok = false;
            }
        }

        // Start marker & current icon
        float st_x, st_y, st_d;
        if (cam.project(pts[0].px, pts[0].py, pts[0].pz_route, st_x, st_y, st_d)) {
            canvas.draw_circle(st_x, st_y, 7.0f, 255, 255, 255, 0.95f);
            canvas.draw_circle(st_x, st_y, 5.0f, 235, 52, 46, 0.98f);
        }
        float hd_x, hd_y, hd_d;
        if (cam.project(pts[cur_idx].px, pts[cur_idx].py, pts[cur_idx].pz_route, hd_x, hd_y, hd_d)) {
            canvas.draw_circle(hd_x, hd_y - 22.0f, 20.0f, 255, 255, 255, 0.92f);
            canvas.draw_circle(hd_x, hd_y, 7.5f, 255, 255, 255, 0.98f);
            canvas.draw_circle(hd_x, hd_y, 5.2f, 184, 255, 38, 1.0f);
        }

        // Draw 3D screen-aligned billboard place name labels with temporal stability (zero jitter, zero shaking)
        if (has_labels && !labels.empty()) {
            bool is_overview = (t_sec < T0 || t_sec > T3 - 0.5);

            for (size_t li = 0; li < labels.size(); ++li) {
                const auto& lbl = labels[li];
                float target_alpha = 0.0f;
                float sx = 0.0f, sy = 0.0f, dp = 0.0f;

                if (cam.project(lbl.px, lbl.py, lbl.pz, sx, sy, dp) && dp >= 20.0f) {
                    if (sx >= -60.0f && sx <= W + 60.0f && sy >= 35.0f && sy <= H + 25.0f) {
                        if (is_overview) {
                            if (lbl.overview) target_alpha = 0.95f;
                        } else {
                            if (dp <= 1650.0f && dp >= 25.0f) {
                                float fade = 1.0f;
                                if (dp > 1150.0f) {
                                    fade = std::clamp((1650.0f - dp) / 500.0f, 0.0f, 1.0f);
                                } else if (dp < 60.0f) {
                                    fade = std::clamp((dp - 25.0f) / 35.0f, 0.0f, 1.0f);
                                }
                                target_alpha = fade;
                            }
                        }
                    }
                }

                // Smooth exponential fade (eliminates sudden popping in / popping out and flickering)
                smooth_lbl_alpha[li] = smooth_lbl_alpha[li] * 0.85f + target_alpha * 0.15f;

                if (smooth_lbl_alpha[li] > 0.02f) {
                    // Smooth screen projection coordinates to dampen any sub-pixel raster wobble
                    if (smooth_lbl_sx[li] > -1000.0f && std::hypot(sx - smooth_lbl_sx[li], sy - smooth_lbl_sy[li]) < 40.0f) {
                        smooth_lbl_sx[li] = smooth_lbl_sx[li] * 0.35f + sx * 0.65f;
                        smooth_lbl_sy[li] = smooth_lbl_sy[li] * 0.35f + sy * 0.65f;
                    } else {
                        smooth_lbl_sx[li] = sx;
                        smooth_lbl_sy[li] = sy;
                    }

                    int dst_x = static_cast<int>(std::round(smooth_lbl_sx[li] - lbl.anchor_x));
                    int dst_y = static_cast<int>(std::round(smooth_lbl_sy[li] - lbl.anchor_y));

                    for (int ly = 0; ly < lbl.h; ++ly) {
                        int cy = dst_y + ly;
                        if (cy < 0 || cy >= H) continue;
                        for (int lx = 0; lx < lbl.w; ++lx) {
                            int cx = dst_x + lx;
                            if (cx < 0 || cx >= W) continue;
                            size_t src_idx = (static_cast<size_t>(lbl.atlas_y + ly) * labels_atlas.w + (lbl.atlas_x + lx)) * 4;
                            uint8_t a = labels_atlas.data[src_idx + 3];
                            if (a > 0) {
                                float fa = (a / 255.0f) * smooth_lbl_alpha[li];
                                canvas.blend_px(cx, cy, labels_atlas.data[src_idx], labels_atlas.data[src_idx + 1], labels_atlas.data[src_idx + 2], fa);
                            }
                        }
                    }
                } else {
                    smooth_lbl_sx[li] = -9999.0f;
                    smooth_lbl_sy[li] = -9999.0f;
                }
            }
        }

        // Blend top banner during intro/outro
        if (banner_alpha > 0.01 && banner_img.w > 0) {
            int by0 = is_portrait ? 54 : 28;
            for (int y = 0; y < banner_img.h && (by0 + y) < H; ++y) {
                for (int x = 0; x < banner_img.w && x < W; ++x) {
                    size_t bi = (static_cast<size_t>(y) * banner_img.w + x) * 4;
                    uint8_t ba = banner_img.data[bi + 3];
                    if (ba > 0) {
                        canvas.blend_px(x, by0 + y, banner_img.data[bi], banner_img.data[bi + 1], banner_img.data[bi + 2],
                                        (ba / 255.0f) * static_cast<float>(banner_alpha));
                    }
                }
            }
        }

        // HUD overlay during cruise
        if (hud_alpha > 0.01) {
            float ha = static_cast<float>(hud_alpha);
            float pad = is_portrait ? 20.0f : 26.0f;
            float mm_r = is_portrait ? 64.0f : 74.0f;
            float mm_cx = pad + mm_r, mm_cy = pad + mm_r;
            canvas.draw_circle(mm_cx, mm_cy, mm_r + 3.0f, 255, 255, 255, 0.85f * ha);
            canvas.draw_circle(mm_cx, mm_cy, mm_r, 32, 38, 46, 0.92f * ha);

            double sc = (mm_r * 1.55) / std::max(1.0, std::max(rx1 - rx0, ry1 - ry0));
            for (int k = 1; k <= cur_idx; k += 2) {
                float x0 = static_cast<float>(mm_cx + (pts[k - 1].px - cx_mid) * sc);
                float y0 = static_cast<float>(mm_cy + (pts[k - 1].py - cy_mid) * sc);
                float x1 = static_cast<float>(mm_cx + (pts[k].px - cx_mid) * sc);
                float y1 = static_cast<float>(mm_cy + (pts[k].py - cy_mid) * sc);
                canvas.draw_segment(x0, y0, x1, y1, 1.8f, 184, 255, 38, 0.95f * ha);
            }
            float cur_Y = mm_cy + mm_r + 16.0f;
            if (avg_hr > 0) {
                canvas.draw_rounded_rect(pad, cur_Y, 175.0f, 64.0f, 12.0f, 18, 22, 28, 0.65f * ha);
                draw_ascii_text(canvas, "Average Heart Rate", pad + 12, cur_Y + 10, 1.5f, 220, 225, 230, ha);
                draw_ascii_text(canvas, std::to_string(avg_hr) + " bpm", pad + 12, cur_Y + 30, 3.0f, 255, 255, 255, ha);
                cur_Y += 74.0f;
            }
            canvas.draw_rounded_rect(pad, cur_Y, 165.0f, 68.0f, 12.0f, 18, 22, 28, 0.65f * ha);
            draw_ascii_text(canvas, "Distance", pad + 12, cur_Y + 10, 1.6f, 220, 225, 230, ha);
            char d_buf[32];
            std::snprintf(d_buf, sizeof(d_buf), "%.1f km", pts[cur_idx].dist / 1000.0);
            draw_ascii_text(canvas, d_buf, pad + 12, cur_Y + 32, 3.0f, 255, 255, 255, ha);

            // Bottom elevation profile
            float prof_h = is_portrait ? 82.0f : 74.0f;
            float prof_y0 = H - prof_h - 14.0f;
            float asc_y = prof_y0 - 74.0f;
            canvas.draw_rounded_rect(pad, asc_y, 210.0f, 62.0f, 12.0f, 18, 22, 28, 0.65f * ha);
            char a_buf[32], de_buf[32];
            std::snprintf(a_buf, sizeof(a_buf), "%.0f m", pts[cur_idx].asc);
            std::snprintf(de_buf, sizeof(de_buf), "%.0f m", pts[cur_idx].desc);
            draw_ascii_text(canvas, "Ascent", pad + 12, asc_y + 10, 1.5f, 220, 225, 230, ha);
            draw_ascii_text(canvas, a_buf, pad + 12, asc_y + 30, 2.5f, 255, 255, 255, ha);
            draw_ascii_text(canvas, "Descent", pad + 112, asc_y + 10, 1.5f, 220, 225, 230, ha);
            draw_ascii_text(canvas, de_buf, pad + 112, asc_y + 30, 2.5f, 255, 255, 255, ha);

            float px0 = pad, px1 = W - pad, pw = px1 - px0;
            for (int k = 1; k < N; ++k) {
                float x0 = px0 + static_cast<float>(pts[k - 1].dist / total_dist) * pw;
                float x1 = px0 + static_cast<float>(pts[k].dist / total_dist) * pw;
                float y0 = prof_y0 + prof_h - static_cast<float>((pts[k - 1].ele - min_ele) / ele_span) * (prof_h - 14.0f);
                float y1 = prof_y0 + prof_h - static_cast<float>((pts[k].ele - min_ele) / ele_span) * (prof_h - 14.0f);
                if (k <= cur_idx) canvas.draw_segment(x0, y0, x1, y1, 2.0f, 184, 255, 38, 0.95f * ha);
                else canvas.draw_segment(x0, y0, x1, y1, 1.4f, 200, 210, 220, 0.45f * ha);
            }
        }

        std::fwrite(canvas.rgb.data(), 1, canvas.rgb.size(), pipe);
        if (f % 180 == 0 || f == TOTAL_FRAMES - 1) {
            std::cerr << "Progress: " << (f + 1) << " / " << TOTAL_FRAMES
                      << " (" << static_cast<int>(100.0 * (f + 1) / TOTAL_FRAMES) << "%)\n";
        }
    }

    pclose(pipe);
    std::cout << "Successfully wrote MP4 video to " << out_mp4 << "\n";
    return 0;
}
