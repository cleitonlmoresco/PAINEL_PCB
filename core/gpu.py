"""Aceleração por GPU: NVIDIA/AMD/Intel/Apple/Qualcomm via OpenCL e CUDA.

- OpenCL (T-API/UMat) funciona nos wheels padrão do OpenCV e cobre AMD, Intel,
  NVIDIA e outros drivers que exponham OpenCL.
- CUDA é usado quando o build do OpenCV tem suporte e existe GPU NVIDIA.
- A VRAM é usada por padrão sempre que houver GPU; se o driver falhar, cai para CPU.
"""
from __future__ import annotations

import cv2


def _nome_dispositivo():
    try:
        dev = cv2.ocl.Device_getDefault()
        nome = dev.name()
        return nome if nome else "OpenCL"
    except Exception:
        return "OpenCL"


def _vendor_do_nome(nome):
    n = (nome or "").upper()
    if any(t in n for t in ("NVIDIA", "GEFORCE", "RTX", "QUADRO", "TESLA")):
        return "NVIDIA"
    if any(t in n for t in ("AMD", "RADEON", "ATI ", "FIREPRO", "ELLESMERE", "POLARIS", "VEGA",
                            "NAVI", "PITCAIRN", "TAHITI", "HAWAII", "BONAIRE", "CURACAO", "LEXA",
                            "BAFFIN", "RENOIR", "RAVEN", "PICASSO", "CEZANNE", "REMBRANDT",
                            "ALDEBARAN", "GFX")):
        return "AMD"
    if any(t in n for t in ("INTEL", "IRIS", "UHD", "ARC ", "GEN9", "GEN11", "GEN12")):
        return "Intel"
    if any(t in n for t in ("APPLE", "M1", "M2", "M3")):
        return "Apple"
    if any(t in n for t in ("QUALCOMM", "ADRENO")):
        return "Qualcomm"
    if any(t in n for t in ("LLVMPIPE", "SWIFTSHADER", "SOFTWARE", "CPU")):
        return "Software"
    return "Outra"


def _eh_software(nome):
    return any(t in (nome or "").upper() for t in ("LLVMPIPE", "SWIFTSHADER", "SOFTWARE RASTERIZER"))


def detectar():
    """Retorna o estado atual de aceleração (não altera nada)."""
    info = {
        "opencl_disponivel": False,
        "opencl_ativo": False,
        "cuda_disponivel": False,
        "cuda_dispositivos": 0,
        "modo": "CPU",
        "device": "CPU",
        "vendor": "",
        "gpu_nome": "",
        "erro": "",
    }
    try:
        info["opencl_disponivel"] = bool(cv2.ocl.haveOpenCL())
        info["opencl_ativo"] = bool(cv2.ocl.useOpenCL())
    except Exception as e:
        info["erro"] = str(e)
    try:
        info["cuda_dispositivos"] = int(cv2.cuda.getCudaEnabledDeviceCount())
    except Exception:
        info["cuda_dispositivos"] = 0
    info["cuda_disponivel"] = info["cuda_dispositivos"] > 0

    nome = _nome_dispositivo()
    info["device"] = nome
    info["gpu_nome"] = nome
    info["vendor"] = _vendor_do_nome(nome)
    info["software"] = _eh_software(nome)

    if info["cuda_disponivel"]:
        info["modo"] = "CUDA"
        info["device"] = f"CUDA x{info['cuda_dispositivos']}"
        info["vendor"] = "NVIDIA"
    elif info["opencl_disponivel"] and info["opencl_ativo"]:
        info["modo"] = "OpenCL"
    elif info["opencl_disponivel"]:
        info["modo"] = "OpenCL-DISPONIVEL"
        info["device"] = f"{nome} (OpenCL desligado)"
    else:
        info["modo"] = "CPU"
        info["device"] = "CPU"
    return info


def ativar(usar=True):
    """Liga/desliga OpenCL (VRAM) e devolve o estado atualizado."""
    try:
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(bool(usar))
    except Exception as e:
        try:
            info = detectar(); info["erro"] = str(e); return info
        except Exception:
            pass
    return detectar()


def ligar_por_padrao():
    """Ativa a GPU automaticamente quando existir (VRAM por padrão).

    Renderizadores OpenCL de software (llvmpipe/SwiftShader) não contam como GPU.
    """
    info = detectar()
    if info.get("software"):
        return info
    if info.get("opencl_disponivel") or info.get("cuda_disponivel"):
        return ativar(True)
    return info


def usando_gpu():
    try:
        return bool(cv2.ocl.haveOpenCL() and cv2.ocl.useOpenCL())
    except Exception:
        return False


def tem_cuda():
    try:
        return cv2.cuda.getCudaEnabledDeviceCount() > 0
    except Exception:
        return False


def descricao(info=None):
    """Texto curto para a interface: 'GPU NVIDIA' / 'GPU AMD' / 'CPU'."""
    info = info or detectar()
    if info.get("software"):
        return "OpenCL (CPU)"
    if info.get("modo") == "CUDA":
        return "GPU CUDA"
    if info.get("modo") == "OpenCL":
        v = info.get("vendor") or ""
        return f"GPU {v}" if v and v not in ("Outra", "Software") else "GPU OpenCL"
    if info.get("opencl_disponivel"):
        return "CPU (GPU off)"
    return "CPU"


def benchmark(img_amostra, repeticoes=2):
    """Compara CPU x OpenCL numa amostra e recomenda a opção mais rápida.

    Retorna {'suportado','usar_gpu','cpu_ms','gpu_ms'}.
    """
    from core.detector import detectar_pads_com_mascara_v84 as _det
    import time

    def medir(usar):
        tempos = []
        for _ in range(max(1, repeticoes)):
            t0 = time.perf_counter()
            _det(img_amostra, scale=0.8, usar_gpu=usar)
            tempos.append(time.perf_counter() - t0)
        return min(tempos) * 1000.0

    resultado = {'suportado': False, 'usar_gpu': False, 'cpu_ms': 0.0, 'gpu_ms': 0.0}
    try:
        if not cv2.ocl.haveOpenCL():
            return resultado
        estado_anterior = bool(cv2.ocl.useOpenCL())
    except Exception:
        return resultado
    try:
        cv2.ocl.setUseOpenCL(True)
        medir(True)  # aquecimento: compila os kernels OpenCL
        gpu_ms = medir(True)
        cv2.ocl.setUseOpenCL(False)
        medir(False)
        cpu_ms = medir(False)
        cv2.ocl.setUseOpenCL(True)
        resultado.update(suportado=True, cpu_ms=cpu_ms, gpu_ms=gpu_ms, usar_gpu=bool(gpu_ms < cpu_ms * 0.95))
    except Exception:
        pass
    finally:
        try:
            cv2.ocl.setUseOpenCL(estado_anterior)
        except Exception:
            pass
    return resultado
