import sys, os, cv2, numpy as np
sys.path.insert(0, '.')
from core import prefs as prefs_lib
prefs_lib.ARQ='C:/Users/cleit/AppData/Local/Temp/opencode/test_al6/cfg.json'
prefs_lib.ARQ_AUTO='C:/Users/cleit/AppData/Local/Temp/opencode/test_al6/auto.json'
os.makedirs('C:/Users/cleit/AppData/Local/Temp/opencode/test_al6', exist_ok=True)
import core.imgio as imgio
from app.app import AppV101

img=np.full((800,1200,3),(52,82,58),np.uint8)
rng=np.random.default_rng(5)
for _ in range(180):
    x=int(rng.integers(30,1170)); y=int(rng.integers(30,770))
    cv2.circle(img,(x,y),int(rng.integers(4,8)),(195,198,205),-1)
for i in range(8):
    cv2.circle(img,(300+i*60,300),9,(210,215,220),-1)
imgio.imwrite('placa.jpg',img)

app=AppV101('placa.jpg'); app._trocar_aba('anotar')
app.pads=[{'id':i,'cx':300+i*60,'cy':300,'x':300+i*60,'y':300,'w':14,'h':14,'area':196,'manual':False,'score':0.8} for i in range(1,17)]
app.next_id=17
app.componentes=[{'id':1,'nome':'U7','tipo':'ci','simbolo':'U','forma':'retangulo_h','cor':[80,255,120],'pads':list(range(1,9)),'x1':280,'y1':270,'x2':780,'y2':330,'valor':'LM358','tensao':'','obs':'','marcacao':'LM358','datasheet':'','pino1':1}]
app.next_comp_id=2; app.comp_selected=1; app.selected=3

# Ensure rail is laid out
app._render()
app._layout_rail()
print('Rail btns:', len(app.rail_btns), 'labels=[', ', '.join([b['label'] for b in app.rail_btns]), ']')

# Test 1: Rail button click - Validar AL
print("Test 1: Rail click on 'Validar AL'")
rb=next(b for b in app.rail_btns if b['label']=='Validar AL')
rx,ry,rw,rh=rb['rect']
app.mode='navegar'
app._on_mouse(cv2.EVENT_LBUTTONDOWN, rx+rw//2, ry+rh//2, 0, None)
print('  Mode after click:', app.mode)
assert app.mode == 'validar_al', 'Expected validar_al, got %s' % app.mode
print('  PASS: Mode changed to validar_al')

# Test 2: Click on rail button - Pino
print("\nTest 2: Rail click on 'Pino'")
rb=next(b for b in app.rail_btns if b['label']=='Pino')
rx,ry,rw,rh=rb['rect']
app.mode='navegar'
app._on_mouse(cv2.EVENT_LBUTTONDOWN, rx+rw//2, ry+rh//2, 0, None)
print('  Mode after click:', app.mode)
assert app.mode == 'pino', 'Expected pino, got %s' % app.mode
print('  PASS: Mode changed to pino')

# Test 3: Toolbar button - Active Learning group
print("\nTest 3: Toolbar Active Learning group")
app.right_mode='calib'; app.tab='anotar'; app._rebuild_toolbar()
al_btns = [b for b in app.botoes_toolbar if b.key in ('modo_al_validar','al_pseudo','al_train')]
print('  Active Learning toolbar buttons:', [b.label for b in al_btns])
assert len(al_btns) == 3, 'Expected 3 AL buttons, got %d' % len(al_btns)
print('  PASS: Active Learning toolbar buttons present')

# Test 4: Click on Validar AL toolbar button
print("\nTest 4: Click on 'Validar AL' toolbar button")
btn = next(b for b in app.botoes_toolbar if b.key == 'modo_al_validar')
bx,by,bw,bh = btn.rect
app.mode='navegar'; app._on_mouse(cv2.EVENT_LBUTTONDOWN, bx+bw//2, by+bh//2, 0, None)
print('  Mode after click:', app.mode)
assert app.mode == 'validar_al', 'Expected validar_al, got %s' % app.mode
print('  PASS: Toolbar button works')

# Test 5: Click on Pseudo-Label toolbar button
print("\nTest 5: Click on 'Pseudo-Label' toolbar button")
btn = next(b for b in app.botoes_toolbar if b.key == 'al_pseudo')
bx,by,bw,bh = btn.rect
app.mode='navegar'; app._on_mouse(cv2.EVENT_LBUTTONDOWN, bx+bw//2, by+bh//2, 0, None)
print('  Pseudo-labels generated:', len(app.anotacoes), 'anotacoes')
assert len(app.anotacoes) > 0, 'Expected pseudo-labels to be generated'
print('  PASS: %d pseudo-labels generated' % len(app.anotacoes))

# Test 6: Click on Treinar LoRA toolbar button (should handle gracefully)
print("\nTest 6: Click on 'Treinar LoRA' toolbar button")
btn = next(b for b in app.botoes_toolbar if b.key == 'al_train')
bx,by,bw,bh = btn.rect
app._on_mouse(cv2.EVENT_LBUTTONDOWN, bx+bw//2, by+bh//2, 0, None)
print('  Flash message:', app._flash_msg)
assert any(kw in app._flash_msg for kw in ['Poucos dados', 'Fine-tuning', 'modelo', 'erro', 'does not exist', 'doesnt exist', 'not found'])
print('  PASS: LoRA training handled gracefully')

print("\n=== ALL GUI TESTS PASSED ===")