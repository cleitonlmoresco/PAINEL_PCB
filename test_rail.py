import sys, os, cv2, numpy as np
sys.path.insert(0, '.')
from core import prefs as prefs_lib
prefs_lib.ARQ='C:/Users/cleit/AppData/Local/Temp/opencode/test_al3/cfg.json'
prefs_lib.ARQ_AUTO='C:/Users/cleit/AppData/Local/Temp/opencode/test_al3/auto.json'
os.makedirs('C:/Users/cleit/AppData/Local/Temp/opencode/test_al3', exist_ok=True)
import core.imgio as imgio
from app.app import AppV101
img=np.full((800,1200,3),(52,82,58),np.uint8)
for i in range(40):
    cv2.circle(img,(80+(i%10)*110,100+(i//10)*110),8,(205,208,215),-1)
imgio.imwrite('placa.jpg',img)
app=AppV101('placa.jpg'); app._trocar_aba('anotar')
app.pads=[{'id':i,'cx':200+i*60,'cy':300,'x':200+i*60,'y':300,'w':14,'h':14,'area':196,'manual':False} for i in range(1,9)]
app.next_id=9
app.componentes=[{'id':1,'nome':'U7','tipo':'ci','simbolo':'U','forma':'retangulo_h','cor':[80,255,120],'pads':list(range(1,9)),'x1':280,'y1':270,'x2':780,'y2':330,'valor':'LM358','tensao':'','obs':'','marcacao':'LM358','datasheet':'','pino1':1}]
app.next_comp_id=2; app.comp_selected=1; app.selected=3
app._render()
app._layout_rail()
print('Rail btns:', len(app.rail_btns))
for b in app.rail_btns:
    print('  {} at y={} h={}'.format(b['label'], b['rect'][1], b['rect'][3]))
print('view_h:', app.view_h, 'toolbar_h:', app._toolbar_h(), 'rail_w:', app.rail_w)
cv2.imwrite('test_al_ui.png', app._render())
print('OK')