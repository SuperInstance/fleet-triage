"""Independent numpy port of Chakazul/Lenia 2-D dynamics, re-derived from LeniaF.py.

Verified against Chan's own Automaton class in e1d (kernel, potential, field).
"""
import numpy as np

# ---- Board.rle2cells / cells2rle (lenia lines 245-328) ------------------------
DIM = 2
DIM_DELIM = {0: '', 1: '$', 2: '%'}

def ch2val(c):
    if c in '.b': return 0
    elif c == 'o': return 255
    elif len(c) == 1: return ord(c) - ord('A') + 1
    else: return (ord(c[0]) - ord('p')) * 24 + (ord(c[1]) - ord('A') + 25)

def val2ch(v):
    if v == 0: return ' .'
    elif v < 25: return ' ' + chr(ord('A') + v - 1)
    else: return chr(ord('p') + (v - 25) // 24) + chr(ord('A') + (v - 25) % 24)

def _append_stack(list1, list2, count, is_repeat):
    list1.append(list2)
    if count != '':
        repeated = list2 if is_repeat else []
        list1.extend([repeated] * (int(count) - 1))

def _recur_cubify(dim, list1, max_lens):
    more = max_lens[dim] - len(list1)
    if dim < DIM - 1:
        list1.extend([[]] * more)
        for list2 in list1: _recur_cubify(dim + 1, list2, max_lens)
    else:
        list1.extend([0] * more)

def _recur_get_max_lens(dim, list1, max_lens):
    max_lens[dim] = max(max_lens[dim], len(list1))
    if dim < DIM - 1:
        for list2 in list1: _recur_get_max_lens(dim + 1, list2, max_lens)

def rle2cells(st):
    stacks = [[], []]; last, count = '', ''
    delims = list(DIM_DELIM.values())
    st = st.rstrip('!') + DIM_DELIM[DIM - 1]
    for ch in st:
        if ch.isdigit(): count += ch
        elif ch in 'pqrstuvwxy@': last = ch
        else:
            if last + ch not in delims:
                _append_stack(stacks[0], ch2val(last + ch) / 255, count, is_repeat=True)
            else:
                dim = delims.index(last + ch)
                for d in range(dim):
                    _append_stack(stacks[d + 1], stacks[d], count, is_repeat=False)
                    stacks[d] = []
            last, count = '', ''
    A = stacks[DIM - 1]
    max_lens = [0, 0]
    _recur_get_max_lens(0, A, max_lens)
    _recur_cubify(0, A, max_lens)
    return np.asarray(A, dtype=np.float64)

# ---- Automaton.kernel_core / growth_func (lenia lines 491-503) ----------------
def kernel_core1(r):
    return (r > 0) * (r < 1) * (4 * r * (1 - r)) ** 4

def growth_func1(n, m, s):
    return np.maximum(0, 1 - (n - m) ** 2 / (9 * s ** 2)) ** 4 * 2 - 1

# ---- Automaton.calc_kernel, DIM==2 (lenia lines 644-670) --------------------
def make_kernel(R, b=(1.0,), r=1.0, G=128, centred=True):
    idx = np.arange(G) - G // 2
    Y, Z = np.meshgrid(idx, idx, indexing='ij')
    D = np.sqrt(Y ** 2 + Z ** 2) / R          # lenia 647-650
    B = len(b)
    bs = np.asarray([float(x) for x in b], dtype=np.float64)
    Br = B * D / r                             # lenia 541
    ring = bs[np.minimum(np.floor(Br).astype(int), B - 1)]   # lenia 543
    K = (D < r) * kernel_core1(np.minimum(Br % 1, 1)) * ring  # lenia 544
    K = K / K.sum()                            # lenia 668-669
    return K if centred else np.fft.ifftshift(K)

# ---- Automaton.calc_once (lenia lines 597-643) ------------------------------
def simulate(A, R, b, m, s, T, steps, centred_kernel=True, record=None):
    Kg = make_kernel(R, b, G=A.shape[0], centred=centred_kernel)
    FK = np.fft.fftn(Kg)
    A = A.copy(); dt = 1.0 / T
    hist = [] if record is not None else None
    for t in range(steps + 1):
        if t:
            U = np.fft.fftshift(np.real(np.fft.ifftn(np.fft.fftn(A) * FK)))  # lenia 609
            A = np.clip(A + dt * growth_func1(U, m, s), 0.0, 1.0)          # lenia 615,631
        if record is not None: hist.append(record(t, A))
    return A, hist

# ---- analysis helpers --------------------------------------------------------
def mass(A): return float(A.sum())

def com(A, wrapped=None):
    n = A.shape[0]
    idx = np.arange(n, dtype=np.float64)
    w = A / max(A.sum(), 1e-12)
    x = float((w.sum(1) * idx).sum()); y = float((w.sum(0) * idx).sum())
    if wrapped is not None:
        x = x + n * round((wrapped[0] - x) / n); y = y + n * round((wrapped[1] - y) / n)
    return x, y

def support(A, thr=1 / 255): return int((A > thr).sum())

def gyradius(A, thr=1 / 255):
    B = np.where(A > thr, A, 0.0)
    x, y = com(B); n = A.shape[0]
    idx = np.arange(n, dtype=np.float64)
    return float(np.sqrt((B * ((idx[:, None] - x) ** 2 + (idx[None, :] - y) ** 2)).sum() / max(B.sum(), 1e-12)))
