"""Treina YOLO para detectar pads e exporta ONNX para o app (cv2.dnn).

Pré-requisitos:
  py -3.11 -m pip install -r requirements_treino.txt

Exemplo:
  py -3.11 tools/treinar_pads.py --dataset C:\\PCB_Painel\\dataset_album --epochs 100

Saída:
  runs/pads/weights/best.pt  e  models/pads.onnx (usado pelo app em Detector IA)
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True, help='Pasta com data.yaml')
    ap.add_argument('--modelo', default='yolo11n.pt', help='yolo11n/s/m ou caminho de .pt')
    ap.add_argument('--epochs', type=int, default=100)
    ap.add_argument('--imgsz', type=int, default=1024)
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--device', default='', help='0 para GPU CUDA, vazio = auto')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--nome', default='pads')
    args = ap.parse_args()

    yaml = os.path.join(args.dataset, 'data.yaml')
    if not os.path.exists(yaml):
        print('data.yaml não encontrado em', args.dataset)
        sys.exit(1)

    try:
        from ultralytics import YOLO
    except Exception:
        print('Ultralytics não instalado. Rode:')
        print('  py -3.11 -m pip install -r requirements_treino.txt')
        print('(CPU funciona, mas treino fica lento; use GPU/Colab para 500+ fotos)')
        sys.exit(2)

    modelo = YOLO(args.modelo)
    resultados = modelo.train(
        data=yaml, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        device=args.device or None, workers=args.workers, project=os.path.join(ROOT, 'runs'),
        name=args.nome, exist_ok=True, patience=30, cache='ram',
    )
    try:
        melhor = os.path.join(ROOT, 'runs', args.nome, 'weights', 'best.pt')
        print('Melhor modelo:', melhor)
        export_path = modelo.export(format='onnx', imgsz=args.imgsz, opset=12, simplify=True)
        os.makedirs(os.path.join(ROOT, 'models'), exist_ok=True)
        destino = os.path.join(ROOT, 'models', 'pads.onnx')
        if export_path and os.path.exists(str(export_path)):
            shutil.copyfile(str(export_path), destino)
            try:
                import json
                with open(os.path.splitext(destino)[0] + '.json', 'w', encoding='utf-8') as f:
                    json.dump({'imgsz': int(args.imgsz), 'modelo': args.modelo, 'epochs': int(args.epochs)}, f, indent=2)
            except Exception:
                pass
            print('ONNX pronto para o app:', destino)
            print('No app: Ctrl+K -> "Detector IA (ONNX)"')
    except Exception as e:
        print('Treino concluído, mas export ONNX falhou:', e)
        print('Rode manualmente: yolo export model=runs/%s/weights/best.pt format=onnx imgsz=%d' % (args.nome, args.imgsz))


if __name__ == '__main__':
    main()
