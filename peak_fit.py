# peak_fit.py
# ============================================================
# XPS 峰拟合后端
#   - 背景扣除：Linear / Shirley
#   - 峰型：伪 Voigt（Gaussian + Lorentzian 线性混合）
#   - 多峰拟合：scipy.optimize.curve_fit（含参数边界）
# ============================================================

import numpy as np
from scipy.optimize import curve_fit
from scipy.integrate import cumulative_trapezoid


# ------------------------------------------------------------------ #
#  Background subtraction                                              #
# ------------------------------------------------------------------ #

def linear_background(x, y):
    """
    两端点连线作为线性背景（x 可任意顺序）。
    返回与 x 等长的背景数组。
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    idx = np.argsort(x)
    xs, ys = x[idx], y[idx]
    # 在全程上线性插值
    bg = np.interp(x, [xs[0], xs[-1]], [ys[0], ys[-1]])
    return bg


def shirley_background(x, y, max_iter=50, tol=1e-6):
    """
    Shirley 迭代背景：阶梯形背景，用于 XPS 峰下方的非弹性散射贡献。

    算法：
        B[i] = y_lo + (y_hi - y_lo) * ∫[x[0]→x[i]] (y−B) dx
                                      ────────────────────────
                                      ∫[x[0]→x[-1]] (y−B) dx

    其中 x[0] = low BE 端，x[-1] = high BE 端。
    内部升序处理，完成后还原到原始顺序。
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    idx_sort = np.argsort(x)
    xs = x[idx_sort]
    ys = y[idx_sort]
    y_lo = ys[0]
    y_hi = ys[-1]

    # 初始猜测：线性
    bg = np.linspace(y_lo, y_hi, len(ys))

    for _ in range(max_iter):
        net = np.maximum(ys - bg, 0.0)
        total = np.trapz(net, xs)
        if total < 1e-30:
            break
        cum = cumulative_trapezoid(net, xs, initial=0.0)
        bg_new = y_lo + (y_hi - y_lo) * cum / total
        if np.max(np.abs(bg_new - bg)) < tol:
            bg = bg_new
            break
        bg = bg_new

    result = np.empty_like(x)
    result[idx_sort] = bg
    return result


# ------------------------------------------------------------------ #
#  Peak model                                                          #
# ------------------------------------------------------------------ #

def pseudo_voigt(x, center, amplitude, fwhm, eta):
    """
    伪 Voigt 峰型：Gaussian 与 Lorentzian 的线性混合。

    参数
    ----
    center    : 峰中心 (eV)
    amplitude : 峰高（背景扣除后）
    fwhm      : 半高全宽 (eV)
    eta       : Lorentzian 比例（0 = 纯 Gaussian，1 = 纯 Lorentzian）
    """
    fwhm = max(float(fwhm), 1e-6)
    eta = float(np.clip(eta, 0.0, 1.0))
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    gamma = fwhm / 2.0
    G = np.exp(-0.5 * ((x - center) / sigma) ** 2)
    L = 1.0 / (1.0 + ((x - center) / gamma) ** 2)
    return amplitude * (eta * L + (1.0 - eta) * G)


def _multi_peak_func(x, *params):
    """内部：n 个伪 Voigt 之和，参数依次为 [cen, amp, fwhm, eta, ...]。"""
    n = len(params) // 4
    y = np.zeros_like(x, dtype=float)
    for i in range(n):
        cen, amp, fwhm, eta = params[i * 4: (i + 1) * 4]
        y += pseudo_voigt(x, cen, amp, fwhm, eta)
    return y


# ------------------------------------------------------------------ #
#  Main fitting function                                               #
# ------------------------------------------------------------------ #

def fit_xps(x, y, peak_guesses, bg_type="shirley", fit_range=None):
    """
    XPS 多峰拟合主函数。

    参数
    ----
    x, y         : 原始谱（可任意顺序，使用 raw y，非归一化）
    peak_guesses : list[dict]，每项 {"center": float, "fwhm": float, "eta": float}
                   amplitude 自动从背景扣除后的谱中估算
    bg_type      : "none" | "linear" | "shirley"
    fit_range    : (lo, hi) eV 截取范围；None 则用全谱

    返回 dict
    ----------
    success       : bool
    message       : str（失败原因 或 "ok"）
    x_fit         : 升序 x 数组（裁剪后）
    y_raw         : 对应原始 y
    y_bg          : 背景
    y_corrected   : 背景扣除后
    y_total_fit   : 多峰模型拟合值（背景扣除空间）
    peaks_y       : list[ndarray]，每峰单独的 y（背景扣除空间）
    params        : list[dict]，拟合得到的峰参数 {center, amplitude, fwhm, eta}
    errors        : list[dict]，各参数 1σ 不确定度
    r_squared     : float
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    # 裁剪到拟合范围
    if fit_range is not None:
        lo, hi = min(fit_range), max(fit_range)
        mask = (x >= lo) & (x <= hi)
        if np.sum(mask) < 10:
            return {
                "success": False,
                "message": f"拟合范围 {lo:.2f}–{hi:.2f} eV 内仅有 {int(np.sum(mask))} 个点（至少需要 10 个）",
            }
        x = x[mask]
        y = y[mask]

    # 升序排列（拟合与背景算法均要求）
    idx = np.argsort(x)
    x = x[idx]
    y = y[idx]

    # 背景扣除
    if bg_type == "shirley":
        y_bg = shirley_background(x, y)
    elif bg_type == "linear":
        y_bg = linear_background(x, y)
    else:
        y_bg = np.zeros_like(y)

    y_corr = y - y_bg

    if not peak_guesses:
        return {"success": False, "message": "请至少添加一个峰"}

    # 初始参数与边界
    p0, lo_b, hi_b = [], [], []
    y_max = float(np.max(y_corr)) if np.max(y_corr) > 0 else 1.0
    for pg in peak_guesses:
        cen  = float(pg["center"])
        fwhm = float(pg.get("fwhm", 1.0))
        eta  = float(pg.get("eta", 0.3))
        # 在 cen 处插值估算初始幅度，至少为谱高的 1%
        amp = float(np.interp(cen, x, y_corr))
        amp = max(amp, 0.01 * y_max)
        p0  += [cen, amp, fwhm, eta]
        lo_b += [cen - 3.0,  0.0,  0.05, 0.0]
        hi_b += [cen + 3.0,  y_max * 3.0,  8.0, 1.0]

    try:
        popt, pcov = curve_fit(
            _multi_peak_func, x, y_corr,
            p0=p0, bounds=(lo_b, hi_b),
            maxfev=20000,
        )
    except Exception as e:
        return {"success": False, "message": f"scipy curve_fit 失败：{e}"}

    # 参数不确定度
    try:
        perr = np.sqrt(np.diag(pcov))
    except Exception:
        perr = np.zeros_like(popt)

    n = len(peak_guesses)
    fitted_params, fitted_errors, peaks_y = [], [], []
    for i in range(n):
        cen, amp, fwhm, eta = popt[i * 4: (i + 1) * 4]
        err = perr[i * 4: (i + 1) * 4]
        fitted_params.append({"center": float(cen), "amplitude": float(amp),
                               "fwhm": float(fwhm), "eta": float(eta)})
        fitted_errors.append({"center": float(err[0]), "amplitude": float(err[1]),
                               "fwhm": float(err[2]), "eta": float(err[3])})
        peaks_y.append(pseudo_voigt(x, cen, amp, fwhm, eta))

    y_total = _multi_peak_func(x, *popt)
    ss_res = float(np.sum((y_corr - y_total) ** 2))
    ss_tot = float(np.sum((y_corr - np.mean(y_corr)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {
        "success":     True,
        "message":     "ok",
        "x_fit":       x,
        "y_raw":       y,
        "y_bg":        y_bg,
        "y_corrected": y_corr,
        "y_total_fit": y_total,
        "peaks_y":     peaks_y,
        "params":      fitted_params,
        "errors":      fitted_errors,
        "r_squared":   r2,
    }
