import sys, types
for name in ['reikna','reikna.fft','reikna.cluda','skimage','skimage.morphology','skimage.segmentation',
             'skimage._shared','skimage._shared.coord','PIL','PIL.Image','PIL.ImageTk','PIL.ImageDraw',
             'PIL.ImageFont','tkinter']:
    m = types.ModuleType(name); m.__getattr__ = lambda k: None; sys.modules.setdefault(name, m)
src=open('/tmp/nca/chan_LeniaF.py').read().split('\n')
g={}
exec(compile('\n'.join(src[:119]+src[119:489]+src[489:676]),'lenia_head','exec'), g)
import inspect, pickle
print('World.__init__:', str(inspect.signature(g['World'].__init__))[:420]); print()
print('Automaton.__init__:', str(inspect.signature(g['Automaton'].__init__))[:420]); print()
print('SIZE',g.get('SIZE'),'MID',g.get('MID'),'DIM',g.get('DIM'),'CHANNEL',list(g.get('CHANNEL',[])),'KERNEL',list(g.get('KERNEL',[])))
pickle.dump(g, open('/tmp/nca/chan_g.pkl','wb'))
