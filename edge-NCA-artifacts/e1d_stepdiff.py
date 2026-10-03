"""E1d -- step-by-step diff: Chan's Automaton vs the independent port, kernel included."""
import sys, types, json
import numpy as np
for name in ['reikna', 'reikna.fft', 'reikna.cluda', 'skimage', 'skimage.morphology',
             'skimage.segmentation', 'skimage._shared', 'skimage._shared.coord',
             'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw', 'PIL.ImageFont', 'tkinter']:
    m = types.ModuleType(name); m.__getattr__ = lambda k: None; sys.modules.setdefault(name, m)
sys.argv = ['lenia', '-d', '2', '-c', '1', '-k', '1', '-w', '9', '9', '-b', '2']
src = open('/tmp/nca/chan_LeniaF.py').read().split('\n')
G = {}
exec(compile('\n'.join(src[:119] + src[119:489] + src[489:676]), 'lenia_head', 'exec'), G)
Board, Automaton = G['Board'], G['Automaton']
S = G['SIZE'][0]
orb = [a for a in json.load(open('/tmp/nca/animals.json')) if a.get('name') == 'Orbium unicaudatus'][0]
field = Board.rle2cells(orb['cells'])
w = Board(size=[S, S]); w.model = {'R': 13, 'T': 10, 'P': 0, 'kn': 1, 'gn': 1}
w.params = [Board.data2params(orb['params'])]
w.cells = [np.zeros((S, S))]
o = S // 2 - field.shape[0] // 2
w.cells[0][o:o + 20, o:o + 20] = field
au = Automaton(w); au.calc_kernel()
Kc = np.real(au.kernel[0]) / au.kernel_sum[0]

sys.path.insert(0, '/tmp/nca/exp')
import chan_ref as C
Kp, _ = C.make_kernel2(13, S, (1.0,))
Kpc = np.fft.ifftshift(Kp)          # undo my roll -> both in Chan's centred convention
print('KERNEL  max|Chan - port| =', float(np.abs(Kc - Kpc).max()), ' sums', float(Kc.sum()), float(Kpc.sum()))

# potential comparison at t=0
au.calc_once(is_update=True)        # Chan stores potential[0] for the step just taken
Up_c = au.potential[0]
A = w.cells[0].copy()               # already stepped once
# recompute t=0 potential by hand with the port kernel
A0 = np.zeros((S, S)); A0[o:o + 20, o:o + 20] = field
FK = np.fft.rfftn(Kpc)
U0 = np.fft.fftshift(np.real(np.fft.ifftn(np.fft.fftn(A0) * FK)))
print('POTENTIAL t=0 max|d| =', float(np.abs(U0 - Up_c).max()))
print('   Chan U range', float(Up_c.min()), float(Up_c.max()), ' port U range', float(U0.min()), float(U0.max()))

# where do they differ?
d = np.abs(U0 - Up_c); print('   argmax diff at', np.unravel_index(d.argmax(), d.shape), 'value', float(d.max()))
print('   Chan U at that pt', float(Up_c[np.unravel_index(d.argmax(), d.shape)]))

# field after 1 step from both, from scratch
au2 = Automaton(w); au2.calc_kernel()
w.cells[0][:] = A0
au2.calc_once()
Cfield = w.cells[0].copy()
UP = np.fft.fftshift(np.real(np.fft.ifftn(np.fft.fftn(A0) * np.fft.rfftn(Kpc))))
FP = C.growth_func1(UP, 0.15, 0.015)
A1p = np.clip(A0 + 0.1 * FP, 0, 1)
print('FIELD after 1 step: max|d| =', float(np.abs(Cfield - A1p).max()), ' mass', Cfield.sum(), A1p.sum())
