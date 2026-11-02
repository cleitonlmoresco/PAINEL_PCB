"""
=============================================================================
 SISTEMA DE DETECÇÃO DE ANOMALIAS EM PCB
 Comparação com "Padrão Ouro" (Golden Board)
=============================================================================
 Uso: Compare uma placa nova (suspeita) com uma placa de referência
      sabidamente boa, e destaque automaticamente todas as divergências.
=============================================================================
"""

import cv2
import numpy as np
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from enum import Enum


# =============================================================================
# 1. ESTRUTURAS DE DADOS
# =============================================================================

class TipoAnomalia(Enum):
    """Categorias de anomalias detectáveis."""
    COMPONENTE_FALTANTE = "COMPONENTE_FALTANTE"
    COMPONENTE_EXTRA = "COMPONENTE_EXTRA"
    COMPONENTE_DESLOCADO = "COMPONENTE_DESLOCADO"
    PAD_DANIFICADO = "PAD_DANIFICADO"
    TRILHA_ROMPIDA = "TRILHA_ROMPIDA"
    MANCHA_CORROSAO = "MANCHA_CORROSAO"
    DIFERENCA_GEOMETRICA = "DIFERENCA_GEOMETRICA"
    DIFERENCA_COR = "DIFERENCA_COR"


class Severidade(Enum):
    """Nível de criticidade da anomalia."""
    CRITICA = "CRITICA"      # Componente faltante, trilha rompida
    ALTA = "ALTA"            # Pad danificado, deslocamento grande
    MEDIA = "MEDIA"          # Deslocamento pequeno, mancha
    BAIXA = "BAIXA"          # Diferença de cor, ruído


@dataclass
class Anomalia:
    """Representa uma anomalia detectada."""
    id: int
    tipo: str
    severidade: str
    bbox: Tuple[int, int, int, int]      # (x, y, w, h)
    centro: Tuple[float, float]
    area: float
    score_diferenca: float               # 0.0 a 1.0 (1.0 = totalmente diferente)
    descricao: str = ""
    elemento_referencia: Optional[int] = None  # ID do componente na placa ouro


@dataclass
class ResultadoComparacao:
    """Resultado completo da comparação entre duas placas."""
    placa_ouro_path: str
    placa_teste_path: str
    timestamp: str
    total_anomalias: int
    anomalias_por_severidade: Dict[str, int] = field(default_factory=dict)
    anomalias: List[Anomalia] = field(default_factory=list)
    score_global_similaridade: float = 0.0
    matriz_alinhamento: Optional[np.ndarray] = None
    deslocamento_detectado: Tuple[float, float] = (0.0, 0.0)
    rotacao_detectada: float = 0.0
    escala_detectada: float = 1.0


@dataclass
class ConfigAnomalias:
    """Parâmetros ajustáveis do detector de anomalias."""
    
    # --- Alinhamento ---
    alinhamento: Dict = field(default_factory=lambda: {
        "metodo": "ORB",              # "ORB", "SIFT", "AKAZE", "EORB"
        "num_features": 5000,
        "match_ratio": 0.75,
        "min_matches": 20,
        "ransac_thresh": 5.0,
        "usar_homografia": True       # True = perspectiva, False = afim
    })
    
    # --- Normalização ---
    normalizacao: Dict = field(default_factory=lambda: {
        "aplicar_clahe": True,
        "clipLimit": 3.0,
        "aplicar_balanceamento_branco": False,
        "aplicar_correcao_gamma": False,
        "gamma": 1.0
    })
    
    # --- Comparação ---
    comparacao: Dict = field(default_factory=lambda: {
        "metodo": "COMBINADO",        # "ABSDIFF", "SSIM", "COMBINADO"
        "threshold_absdiff": 40,      # Diferença de pixel significativa
        "threshold_ssim": 0.65,       # SSIM abaixo disso = anomalia
        "peso_absdiff": 0.4,
        "peso_ssim": 0.6,
        "aplicar_blur_antes": True,
        "blur_kernel": 5
    })
    
    # --- Morfologia da máscara de diferença ---
    morfologia: Dict = field(default_factory=lambda: {
        "abertura_kernel": 3,
        "abertura_iter": 1,
        "fechamento_kernel": 7,
        "fechamento_iter": 2,
        "dilatacao_kernel": 3,
        "dilatacao_iter": 1
    })
    
    # --- Classificação de anomalias ---
    classificacao: Dict = field(default_factory=lambda: {
        "area_min_anomalia": 50,
        "area_max_anomalia": 100000,
        "deslocamento_min_px": 3,
        "considerar_cor": True,
        "sensibilidade_cor": 30,
        "ignorar_bordas": True,
        "margem_borda": 15           # Pixels a ignorar nas bordas
    })
    
    # --- Visualização ---
    visualizacao: Dict = field(default_factory=lambda: {
        "desenhar_bbox": True,
        "desenhar_centro": True,
        "desenhar_rotulo": True,
        "espessura_bbox": 2,
        "raio_centro": 4,
        "alpha_overlay": 0.5,
        "cor_anomalia": (0, 0, 255),
        "cor_heatmap": True
    })


# =============================================================================
# 2. MÓDULO DE ALINHAMENTO
# =============================================================================

class AlinhadorPlacas:
    """
    Alinha geometricamente duas imagens da mesma placa usando
    pontos-chave (features) e homografia.
    """
    
    def __init__(self, config: Dict):
        self.config = config
    
    def _criar_detector(self):
        """Cria o detector de features conforme configuração."""
        metodo = self.config.get("metodo", "ORB")
        
        if metodo == "ORB":
            return cv2.ORB_create(nfeatures=self.config["num_features"])
        elif metodo == "SIFT":
            return cv2.SIFT_create(nfeatures=self.config["num_features"])
        elif metodo == "AKAZE":
            return cv2.AKAZE_create()
        else:
            return cv2.ORB_create(nfeatures=self.config["num_features"])
    
    def _criar_matcher(self):
        """Cria o matcher conforme o detector."""
        metodo = self.config.get("metodo", "ORB")
        if metodo in ["SIFT", "AKAZE"]:
            # Matcher para descritores float
            return cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
        else:
            # Matcher para descritores binários (ORB)
            return cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    
    def alinhar(self, img_ouro: np.ndarray,
                img_teste: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict]:
        """
        Alinha a placa de teste à placa ouro.
        
        Returns:
            img_ouro_alinhada, img_teste_alinhada, info_alinhamento
        """
        # Converter para tons de cinza
        gray_ouro = cv2.cvtColor(img_ouro, cv2.COLOR_BGR2GRAY)
        gray_teste = cv2.cvtColor(img_teste, cv2.COLOR_BGR2GRAY)
        
        # Detectar features
        detector = self._criar_detector()
        kp_ouro, des_ouro = detector.detectAndCompute(gray_ouro, None)
        kp_teste, des_teste = detector.detectAndCompute(gray_teste, None)
        
        info = {
            "kp_ouro": len(kp_ouro) if kp_ouro else 0,
            "kp_teste": len(kp_teste) if kp_teste else 0,
            "matches_brutos": 0,
            "matches_bons": 0,
            "metodo": self.config["metodo"],
            "sucesso": False
        }
        
        if des_ouro is None or des_teste is None:
            print("[Alinhamento] Falha: sem descritores detectados.")
            return img_ouro, img_teste, info
        
        # Matching
        matcher = self._criar_matcher()
        matches = matcher.knnMatch(des_teste, des_ouro, k=2)
        info["matches_brutos"] = len(matches)
        
        # Ratio test de Lowe
        ratio = self.config.get("match_ratio", 0.75)
        bons_matches = []
        for m_n in matches:
            if len(m_n) == 2:
                m, n = m_n
                if m.distance < ratio * n.distance:
                    bons_matches.append(m)
        
        info["matches_bons"] = len(bons_matches)
        
        if len(bons_matches) < self.config.get("min_matches", 20):
            print(f"[Alinhamento] Falha: apenas {len(bons_matches)} matches bons.")
            return img_ouro, img_teste, info
        
        # Extrair pontos correspondentes
        pts_teste = np.float32([kp_teste[m.queryIdx].pt for m in bons_matches]).reshape(-1, 1, 2)
        pts_ouro = np.float32([kp_ouro[m.trainIdx].pt for m in bons_matches]).reshape(-1, 1, 2)
        
        # Calcular transformação
        if self.config.get("usar_homografia", True):
            H, mask = cv2.findHomography(
                pts_teste, pts_ouro, cv2.RANSAC,
                ransacReprojThreshold=self.config.get("ransac_thresh", 5.0)
            )
        else:
            # Transformação afim (mais estável se só houver rotação/translação)
            H, mask = cv2.estimateAffinePartial2D(
                pts_teste, pts_ouro,
                method=cv2.RANSAC,
                ransacReprojThreshold=self.config.get("ransac_thresh", 5.0)
            )
            # Converter para homografia 3x3
            if H is not None:
                H_full = np.eye(3)
                H_full[:2, :] = H
                H = H_full
        
        if H is None:
            print("[Alinhamento] Falha: não foi possível calcular homografia.")
            return img_ouro, img_teste, info
        
        # Aplicar transformação à placa de teste
        h, w = img_ouro.shape[:2]
        img_teste_alinhada = cv2.warpPerspective(img_teste, H, (w, h))
        
        # Extrair parâmetros da transformação para o relatório
        # Deslocamento aproximado (translação)
        tx, ty = H[0, 2], H[1, 2]
        
        # Escala aproximada
        escala = np.sqrt(H[0, 0]**2 + H[0, 1]**2)
        
        # Rotação aproximada
        rotacao_rad = np.arctan2(H[1, 0], H[0, 0])
        rotacao_deg = np.degrees(rotacao_rad)
        
        info.update({
            "sucesso": True,
            "deslocamento_x": float(tx),
            "deslocamento_y": float(ty),
            "escala": float(escala),
            "rotacao_graus": float(rotacao_deg),
            "matriz_H": H.tolist()
        })
        
        print(f"[Alinhamento] Sucesso: {len(bons_matches)} matches, "
              f"desloc=({tx:.1f},{ty:.1f})px, escala={escala:.3f}, rot={rotacao_deg:.2f}°")
        
        return img_ouro, img_teste_alinhada, info


# =============================================================================
# 3. MÓDULO DE NORMALIZAÇÃO
# =============================================================================

class NormalizadorIluminacao:
    """Normaliza iluminação e cor entre as duas placas."""
    
    def __init__(self, config: Dict):
        self.config = config
    
    def normalizar(self, img: np.ndarray) -> np.ndarray:
        """Aplica normalização de iluminação."""
        resultado = img.copy()
        
        if self.config.get("aplicar_clahe", True):
            lab = cv2.cvtColor(resultado, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            clahe = cv2.createCLAHE(
                clipLimit=self.config.get("clipLimit", 3.0),
                tileGridSize=(8, 8)
            )
            l = clahe.apply(l)
            
            lab = cv2.merge([l, a, b])
            resultado = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        if self.config.get("aplicar_correcao_gamma", False):
            gamma = self.config.get("gamma", 1.0)
            if gamma != 1.0:
                inv_gamma = 1.0 / gamma
                table = np.array([
                    ((i / 255.0) ** inv_gamma) * 255
                    for i in np.arange(0, 256)
                ]).astype("uint8")
                resultado = cv2.LUT(resultado, table)
        
        if self.config.get("aplicar_balanceamento_branco", False):
            resultado = self._balanceamento_branco_simples(resultado)
        
        return resultado
    
    def _balanceamento_branco_simples(self, img: np.ndarray) -> np.ndarray:
        """Balanceamento de branco por Gray World."""
        resultado = img.astype(np.float32)
        medias = resultado.reshape(-1, 3).mean(axis=0)
        media_global = medias.mean()
        
        for c in range(3):
            if medias[c] > 0:
                resultado[:, :, c] *= (media_global / medias[c])
        
        return np.clip(resultado, 0, 255).astype(np.uint8)


# =============================================================================
# 4. MÓDULO DE COMPARAÇÃO
# =============================================================================

class ComparadorPlacas:
    """
    Compara duas placas alinhadas e gera máscara de diferenças
    combinando AbsDiff e SSIM.
    """
    
    def __init__(self, config: Dict):
        self.config = config
    
    def comparar(self, img_ouro: np.ndarray,
                 img_teste: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compara as duas imagens e retorna:
        - mascara_diferenca (binária)
        - mapa_absdiff (grayscale)
        - mapa_ssim (grayscale)
        """
        # Suavização para reduzir ruído de sensores diferentes
        if self.config.get("aplicar_blur_antes", True):
            k = self.config.get("blur_kernel", 5)
            if k % 2 == 0:
                k += 1
            img_ouro_b = cv2.GaussianBlur(img_ouro, (k, k), 0)
            img_teste_b = cv2.GaussianBlur(img_teste, (k, k), 0)
        else:
            img_ouro_b = img_ouro
            img_teste_b = img_teste
        
        # --- Mapa AbsDiff ---
        diff = cv2.absdiff(img_ouro_b, img_teste_b)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        
        _, mask_absdiff = cv2.threshold(
            gray_diff,
            self.config.get("threshold_absdiff", 40),
            255,
            cv2.THRESH_BINARY
        )
        
        # --- Mapa SSIM ---
        ssim_map = self._calcular_ssim_map(img_ouro_b, img_teste_b)
        
        # SSIM: 1.0 = idêntico, -1.0 = totalmente diferente
        # Anomalia onde SSIM < threshold
        mask_ssim = (ssim_map < self.config.get("threshold_ssim", 0.65)).astype(np.uint8) * 255
        
        # --- Combinar (por padrão) ---
        metodo = self.config.get("metodo", "COMBINADO")
        
        if metodo == "ABSDIFF":
            mascara_final = mask_absdiff
        elif metodo == "SSIM":
            mascara_final = mask_ssim
        else:  # COMBINADO
            peso_a = self.config.get("peso_absdiff", 0.4)
            peso_s = self.config.get("peso_ssim", 0.6)
            
            # Combinar ponderadamente
            abs_norm = mask_absdiff.astype(np.float32) / 255.0
            ssim_norm = mask_ssim.astype(np.float32) / 255.0
            combinada = peso_a * abs_norm + peso_s * ssim_norm
            
            mascara_final = (combinada > 0.5).astype(np.uint8) * 255
        
        # --- Morfologia para limpar a máscara ---
        mascara_final = self._aplicar_morfologia(mascara_final)
        
        # Converter SSIM map para uint8 para visualização
        ssim_vis = ((ssim_map + 1) / 2 * 255).astype(np.uint8)
        
        return mascara_final, gray_diff, ssim_vis
    
    def _calcular_ssim_map(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        """
        Calcula o mapa SSIM usando a fórmula clássica de Wang et al.
        (implementação sem skimage para evitar dependência externa)
        """
        # Constantes SSIM
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2
        
        # Converter para float
        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)
        
        # Converter para tons de cinza se necessário
        if img1.ndim == 3:
            img1 = cv2.cvtColor(img1.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float64)
            img2 = cv2.cvtColor(img2.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float64)
        
        # Janela gaussiana
        kernel_size = 11
        sigma = 1.5
        
        # Médias locais
        mu1 = cv2.GaussianBlur(img1, (kernel_size, kernel_size), sigma)
        mu2 = cv2.GaussianBlur(img2, (kernel_size, kernel_size), sigma)
        
        mu1_sq = mu1 ** 2
        mu2_sq = mu2 ** 2
        mu1_mu2 = mu1 * mu2
        
        # Variâncias e covariância
        sigma1_sq = cv2.GaussianBlur(img1 ** 2, (kernel_size, kernel_size), sigma) - mu1_sq
        sigma2_sq = cv2.GaussianBlur(img2 ** 2, (kernel_size, kernel_size), sigma) - mu2_sq
        sigma12 = cv2.GaussianBlur(img1 * img2, (kernel_size, kernel_size), sigma) - mu1_mu2
        
        # Fórmula SSIM
        ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / \
                   ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
        
        return ssim_map
    
    def _aplicar_morfologia(self, mask: np.ndarray) -> np.ndarray:
        """Limpa a máscara de diferenças com operações morfológicas."""
        cfg = self.config
        
        # Abertura: remove ruído pontual
        k_ab = cfg.get("abertura_kernel", 3)
        if k_ab > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_ab, k_ab))
            mask = cv2.morphologyEx(
                mask, cv2.MORPH_OPEN, kernel,
                iterations=cfg.get("abertura_iter", 1)
            )
        
        # Fechamento: une regiões próximas
        k_fc = cfg.get("fechamento_kernel", 7)
        if k_fc > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_fc, k_fc))
            mask = cv2.morphologyEx(
                mask, cv2.MORPH_CLOSE, kernel,
                iterations=cfg.get("fechamento_iter", 2)
            )
        
        # Dilatação: aumenta margem de segurança
        k_dil = cfg.get("dilatacao_kernel", 3)
        if k_dil > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_dil, k_dil))
            mask = cv2.dilate(mask, kernel, iterations=cfg.get("dilatacao_iter", 1))
        
        return mask


# =============================================================================
# 5. CLASSIFICADOR DE ANOMALIAS
# =============================================================================

class ClassificadorAnomalias:
    """
    Analisa os contornos da máscara de diferenças e classifica
    cada anomalia em categorias semânticas.
    """
    
    def __init__(self, config: Dict):
        self.config = config
    
    def classificar(self, mascara_diferenca: np.ndarray,
                    img_ouro: np.ndarray,
                    img_teste: np.ndarray,
                    mascara_corpo_ouro: Optional[np.ndarray] = None,
                    mascara_pads_ouro: Optional[np.ndarray] = None
                    ) -> List[Anomalia]:
        """
        Classifica cada região de diferença em um tipo de anomalia.
        """
        anomalias = []
        id_atual = 1
        
        # Ignorar bordas (evita falsos positivos da moldura)
        if self.config.get("ignorar_bordas", True):
            margem = self.config.get("margem_borda", 15)
            h, w = mascara_diferenca.shape[:2]
            mascara_borda = np.zeros_like(mascara_diferenca)
            mascara_borda[margem:h-margem, margem:w-margem] = 255
            mascara_diferenca = cv2.bitwise_and(mascara_diferenca, mascara_borda)
        
        # Encontrar contornos das diferenças
        contours, _ = cv2.findContours(
            mascara_diferenca, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        area_min = self.config.get("area_min_anomalia", 50)
        area_max = self.config.get("area_max_anomalia", 100000)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (area_min < area < area_max):
                continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            centro_x = x + w / 2.0
            centro_y = y + h / 2.0
            
            # Extrair patches das duas imagens
            patch_ouro = img_ouro[y:y+h, x:x+w]
            patch_teste = img_teste[y:y+h, x:x+w]
            
            if patch_ouro.size == 0 or patch_teste.size == 0:
                continue
            
            # Calcular score de diferença
            diff_local = cv2.absdiff(patch_ouro, patch_teste)
            score = float(np.mean(diff_local)) / 255.0
            
            # Classificar tipo
            tipo, severidade, descricao = self._classificar_tipo(
                area, w, h, score,
                patch_ouro, patch_teste,
                (x, y, w, h),
                mascara_corpo_ouro, mascara_pads_ouro,
                img_ouro.shape
            )
            
            anomalias.append(Anomalia(
                id=id_atual,
                tipo=tipo,
                severidade=severidade,
                bbox=(x, y, w, h),
                centro=(round(centro_x, 1), round(centro_y, 1)),
                area=round(area, 1),
                score_diferenca=round(score, 3),
                descricao=descricao
            ))
            id_atual += 1
        
        # Ordenar por severidade e área
        ordem_sev = {"CRITICA": 0, "ALTA": 1, "MEDIA": 2, "BAIXA": 3}
        anomalias.sort(key=lambda a: (ordem_sev.get(a.severidade, 4), -a.area))
        
        return anomalias
    
    def _classificar_tipo(self, area: float, w: int, h: int, score: float,
                          patch_ouro: np.ndarray, patch_teste: np.ndarray,
                          bbox: Tuple, mask_corpo: Optional[np.ndarray],
                          mask_pads: Optional[np.ndarray],
                          shape_global: Tuple) -> Tuple[str, str, str]:
        """
        Lógica de classificação baseada em heurísticas.
        """
        x, y, w_g, h_g = bbox
        
        # Análise de cor média dos patches
        media_ouro = patch_ouro.reshape(-1, 3).mean(axis=0)
        media_teste = patch_teste.reshape(-1, 3).mean(axis=0)
        delta_cor = np.linalg.norm(media_ouro - media_teste)
        
        # Aspect ratio da anomalia
        aspect = max(w, h) / max(min(w, h), 1)
        
        # Verificar presença na máscara de corpo (componente existia na ouro?)
        corpo_ouro_presente = False
        pads_ouro_presente = False
        
        if mask_corpo is not None:
            regiao_corpo = mask_corpo[y:y+h, x:x+w]
            if regiao_corpo.size > 0:
                corpo_ouro_presente = (regiao_corpo > 0).mean() > 0.3
        
        if mask_pads is not None:
            regiao_pads = mask_pads[y:y+h, x:x+w]
            if regiao_pads.size > 0:
                pads_ouro_presente = (regiao_pads > 0).mean() > 0.3
        
        # --- REGRAS DE CLASSIFICAÇÃO ---
        
        # 1. Componente faltante: corpo/pads existiam na ouro mas sumiram
        #    na teste → área bem preenchida em ambas, mas a teste tem "buraco"
        if corpo_ouro_presente and score > 0.35 and area > 100:
            if aspect < 3 and area > 200:
                return (
                    TipoAnomalia.COMPONENTE_FALTANTE.value,
                    Severidade.CRITICA.value,
                    "Componente presente na placa de referência mas ausente/alterado na teste"
                )
        
        # 2. Componente extra: área nova sem correspondência na ouro
        if not corpo_ouro_presente and area > 150 and score > 0.3:
            if aspect < 2.5:
                return (
                    TipoAnomalia.COMPONENTE_EXTRA.value,
                    Severidade.ALTA.value,
                    "Elemento presente apenas na placa de teste"
                )
        
        # 3. Pad danificado
        if pads_ouro_presente and area < 500 and score > 0.4:
            return (
                TipoAnomalia.PAD_DANIFICADO.value,
                Severidade.ALTA.value,
                "Pad de solda com diferença significativa"
            )
        
        # 4. Trilha rompida: forma alongada, área média
        if aspect > 4 and area < 2000 and score > 0.25:
            return (
                TipoAnomalia.TRILHA_ROMPIDA.value,
                Severidade.CRITICA.value,
                "Possível rompimento ou alteração em trilha de cobre"
            )
        
        # 5. Mancha / corrosão: diferença de cor sem forma definida
        if delta_cor > self.config.get("sensibilidade_cor", 30) and aspect < 3:
            return (
                TipoAnomalia.MANCHA_CORROSAO.value,
                Severidade.MEDIA.value,
                f"Mancha ou corrosão (Δcor={delta_cor:.0f})"
            )
        
        # 6. Diferença geométrica (deslocamento)
        if 50 < area < 500 and score < 0.5:
            return (
                TipoAnomalia.DIFERENCA_GEOMETRICA.value,
                Severidade.MEDIA.value,
                "Possível deslocamento de componente"
            )
        
        # 7. Diferença genérica
        return (
            TipoAnomalia.DIFERENCA_COR.value,
            Severidade.BAIXA.value,
            f"Diferença pixel-a-pixel (score={score:.2f})"
        )


# =============================================================================
# 6. VISUALIZADOR DE ANOMALIAS
# =============================================================================

class VisualizadorAnomalias:
    """Gera visualizações das anomalias para relatório."""
    
    CORES_SEVERIDADE = {
        "CRITICA": (0, 0, 255),      # Vermelho
        "ALTA": (0, 100, 255),       # Laranja
        "MEDIA": (0, 200, 255),      # Amarelo
        "BAIXA": (0, 255, 0)         # Verde
    }
    
    def __init__(self, config: Dict):
        self.config = config
    
    def gerar_overlay(self, img_ouro: np.ndarray, img_teste: np.ndarray,
                      mascara: np.ndarray,
                      anomalias: List[Anomalia]) -> np.ndarray:
        """
        Gera imagem lado-a-lado com overlay das anomalias.
        """
        # Redimensionar se necessário
        h, w = img_ouro.shape[:2]
        canvas = np.zeros((h, w * 2 + 10, 3), dtype=np.uint8)
        canvas[:, :w] = img_ouro
        canvas[:, w+10:] = img_teste
        
        # Aplicar heatmap onde há diferença
        if self.config.get("cor_heatmap", True):
            heatmap = cv2.applyColorMap(mascara, cv2.COLORMAP_JET)
            alpha = self.config.get("alpha_overlay", 0.5)
            img_teste_overlay = cv2.addWeighted(
                img_teste, 1 - alpha, heatmap, alpha, 0
            )
            canvas[:, w+10:] = img_teste_overlay
        
        # Desenhar contornos das anomalias na imagem de teste
        for anom in anomalias:
            x, y, bw, bh = anom.bbox
            x_offset = w + 10 + x
            
            cor = self.CORES_SEVERIDADE.get(anom.severidade, (255, 255, 255))
            
            if self.config.get("desenhar_bbox", True):
                cv2.rectangle(
                    canvas,
                    (x_offset, y),
                    (x_offset + bw, y + bh),
                    cor,
                    self.config.get("espessura_bbox", 2)
                )
            
            if self.config.get("desenhar_centro", True):
                cv2.circle(
                    canvas,
                    (x_offset + bw // 2, y + bh // 2),
                    self.config.get("raio_centro", 4),
                    cor, -1
                )
            
            if self.config.get("desenhar_rotulo", True):
                rotulo = f"#{anom.id} {anom.tipo[:15]}"
                cv2.putText(
                    canvas, rotulo,
                    (x_offset, max(y - 5, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1
                )
        
        # Título
        cv2.putText(canvas, "PLACA OURO (referencia)", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(canvas, f"PLACA TESTE ({len(anomalias)} anomalias)",
                    (w + 20, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return canvas
    
    def gerar_mapa_calor(self, mascara: np.ndarray) -> np.ndarray:
        """Gera heatmap colorido da máscara de diferenças."""
        heatmap = cv2.applyColorMap(mascara, cv2.COLORMAP_JET)
        return heatmap
    
    def gerar_zoom_anomalias(self, img_ouro: np.ndarray, img_teste: np.ndarray,
                              anomalias: List[Anomalia],
                              max_zooms: int = 12) -> np.ndarray:
        """
        Gera grade de zooms individuais das anomalias mais severas.
        """
        if not anomalias:
            return np.zeros((100, 500, 3), dtype=np.uint8)
        
        # Selecionar as mais severas
        top = anomalias[:max_zooms]
        
        # Tamanho de cada célula
        cell_w, cell_h = 200, 200
        
        # Grid 4x3
        cols = 4
        rows = (len(top) + cols - 1) // cols
        
        grid = np.zeros((rows * cell_h, cols * cell_w, 3), dtype=np.uint8)
        
        for idx, anom in enumerate(top):
            row = idx // cols
            col = idx % cols
            
            x, y, w, h = anom.bbox
            
            # Patch ouro
            patch_ouro = img_ouro[y:y+h, x:x+w]
            patch_teste = img_teste[y:y+h, x:x+w]
            
            if patch_ouro.size == 0 or patch_teste.size == 0:
                continue
            
            # Redimensionar ambos para caber na célula
            patch_ouro_r = cv2.resize(patch_ouro, (cell_w // 2 - 5, cell_h - 30))
            patch_teste_r = cv2.resize(patch_teste, (cell_w // 2 - 5, cell_h - 30))
            
            # Colocar na célula
            y0 = row * cell_h
            x0 = col * cell_w
            
            grid[y0+25:y0+cell_h, x0:x0+cell_w//2-5] = patch_ouro_r
            grid[y0+25:y0+cell_h, x0+cell_w//2:x0+cell_w-5] = patch_teste_r
            
            # Rótulo
            cor = self.CORES_SEVERIDADE.get(anom.severidade, (255, 255, 255))
            texto = f"#{anom.id} {anom.tipo[:12]}"
            cv2.putText(grid, texto, (x0 + 5, y0 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1)
        
        return grid


# =============================================================================
# 7. EXPORTADOR DE RELATÓRIOS
# =============================================================================

class ExportadorRelatorio:
    """Gera relatórios em JSON, TXT e visual."""
    
    @staticmethod
    def para_json(resultado: ResultadoComparacao, caminho: str):
        """Exporta resultado completo em JSON."""
        dados = {
            "metadata": {
                "placa_ouro": resultado.placa_ouro_path,
                "placa_teste": resultado.placa_teste_path,
                "timestamp": resultado.timestamp,
                "score_similaridade": resultado.score_global_similaridade
            },
            "alinhamento": {
                "deslocamento": list(resultado.deslocamento_detectado),
                "rotacao_graus": resultado.rotacao_detectada,
                "escala": resultado.escala_detectada
            },
            "resumo": {
                "total_anomalias": resultado.total_anomalias,
                "por_severidade": resultado.anomalias_por_severidade
            },
            "anomalias": [
                {
                    "id": a.id,
                    "tipo": a.tipo,
                    "severidade": a.severidade,
                    "bbox": list(a.bbox),
                    "centro": list(a.centro),
                    "area": a.area,
                    "score_diferenca": a.score_diferenca,
                    "descricao": a.descricao
                }
                for a in resultado.anomalias
            ]
        }
        
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        print(f"[JSON] Relatório salvo: {caminho}")
    
    @staticmethod
    def para_txt(resultado: ResultadoComparacao, caminho: str):
        """Exporta relatório legível em texto."""
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("=" * 75 + "\n")
            f.write(" RELATÓRIO DE INSPEÇÃO - DETECÇÃO DE ANOMALIAS\n")
            f.write("=" * 75 + "\n\n")
            
            f.write(f"Placa de referência: {resultado.placa_ouro_path}\n")
            f.write(f"Placa testada:       {resultado.placa_teste_path}\n")
            f.write(f"Data/hora:           {resultado.timestamp}\n")
            f.write(f"Score de similaridade: {resultado.score_global_similaridade:.2%}\n\n")
            
            f.write("-" * 75 + "\n")
            f.write(" ALINHAMENTO GEOMÉTRICO\n")
            f.write("-" * 75 + "\n")
            f.write(f"  Deslocamento: ({resultado.deslocamento_detectado[0]:.1f}, "
                    f"{resultado.deslocamento_detectado[1]:.1f}) px\n")
            f.write(f"  Rotação:      {resultado.rotacao_detectada:.2f}°\n")
            f.write(f"  Escala:       {resultado.escala_detectada:.4f}\n\n")
            
            f.write("-" * 75 + "\n")
            f.write(" RESUMO DE ANOMALIAS\n")
            f.write("-" * 75 + "\n")
            f.write(f"  Total detectado: {resultado.total_anomalias}\n")
            for sev, qtd in resultado.anomalias_por_severidade.items():
                f.write(f"  {sev:<10}: {qtd}\n")
            f.write("\n")
            
            f.write("-" * 75 + "\n")
            f.write(" DETALHAMENTO\n")
            f.write("-" * 75 + "\n")
            f.write(f"{'ID':<5} {'SEVERIDADE':<12} {'TIPO':<25} "
                    f"{'CENTRO':<18} {'AREA':<10} {'SCORE':<8}\n")
            f.write("-" * 75 + "\n")
            
            for a in resultado.anomalias:
                centro_str = f"({a.centro[0]:.0f},{a.centro[1]:.0f})"
                f.write(f"{a.id:<5} {a.severidade:<12} {a.tipo:<25} "
                        f"{centro_str:<18} {a.area:<10.0f} {a.score_diferenca:<8.3f}\n")
                f.write(f"      └─ {a.descricao}\n")
        
        print(f"[TXT] Relatório salvo: {caminho}")


# =============================================================================
# 8. PIPELINE PRINCIPAL DE DETECÇÃO DE ANOMALIAS
# =============================================================================

class DetectorAnomaliasPCB:
    """
    Orquestra todo o pipeline de detecção de anomalias.
    """
    
    def __init__(self, config: Optional[ConfigAnomalias] = None):
        self.config = config or ConfigAnomalias()
        
        self.alinhador = AlinhadorPlacas(self.config.alinhamento)
        self.normalizador = NormalizadorIluminacao(self.config.normalizacao)
        self.comparador = ComparadorPlacas(
            {**self.config.comparacao, **self.config.morfologia}
        )
        self.classificador = ClassificadorAnomalias(self.config.classificacao)
        self.visualizador = VisualizadorAnomalias(self.config.visualizacao)
    
    def detectar(self, caminho_ouro: str, caminho_teste: str,
                 dir_saida: str = "saida_anomalias") -> ResultadoComparacao:
        """
        Executa o pipeline completo de comparação.
        """
        os.makedirs(dir_saida, exist_ok=True)
        
        print("=" * 75)
        print(" DETECÇÃO DE ANOMALIAS EM PCB")
        print("=" * 75)
        
        # --- 1. CARREGAR IMAGENS ---
        print("\n[1/7] Carregando imagens...")
        img_ouro = cv2.imread(caminho_ouro)
        img_teste = cv2.imread(caminho_teste)
        
        if img_ouro is None:
            raise FileNotFoundError(f"Placa ouro não encontrada: {caminho_ouro}")
        if img_teste is None:
            raise FileNotFoundError(f"Placa teste não encontrada: {caminho_teste}")
        
        print(f"  Placa ouro: {img_ouro.shape}")
        print(f"  Placa teste: {img_teste.shape}")
        
        # --- 2. ALINHAMENTO ---
        print("\n[2/7] Alinhando placas...")
        img_ouro, img_teste, info_alinhamento = self.alinhador.alinhar(
            img_ouro, img_teste
        )
        
        if not info_alinhamento.get("sucesso", False):
            print("  AVISO: Alinhamento falhou. Prosseguindo com imagens originais.")
        
        cv2.imwrite(f"{dir_saida}/01_ouro_alinhada.png", img_ouro)
        cv2.imwrite(f"{dir_saida}/02_teste_alinhada.png", img_teste)
        
        # --- 3. NORMALIZAÇÃO ---
        print("\n[3/7] Normalizando iluminação...")
        img_ouro = self.normalizador.normalizar(img_ouro)
        img_teste = self.normalizador.normalizar(img_teste)
        
        cv2.imwrite(f"{dir_saida}/03_ouro_normalizada.png", img_ouro)
        cv2.imwrite(f"{dir_saida}/04_teste_normalizada.png", img_teste)
        
        # --- 4. COMPARAÇÃO ---
        print("\n[4/7] Comparando placas...")
        mascara_diff, mapa_absdiff, mapa_ssim = self.comparador.comparar(
            img_ouro, img_teste
        )
        
        cv2.imwrite(f"{dir_saida}/05_mapa_absdiff.png", mapa_absdiff)
        cv2.imwrite(f"{dir_saida}/06_mapa_ssim.png", mapa_ssim)
        cv2.imwrite(f"{dir_saida}/07_mascara_diferenca.png", mascara_diff)
        
        # --- 5. CLASSIFICAÇÃO ---
        print("\n[5/7] Classificando anomalias...")
        
        # (Opcional) Extrair máscaras de referência da ouro
        # para auxiliar na classificação
        mask_corpo_ouro = None
        mask_pads_ouro = None
        try:
            from filtros_pcb import FiltrosPCB
            filtros = FiltrosPCB()
            mask_corpo_ouro = filtros.filtro_threshold_corpo(img_ouro, 80)
            mask_pads_ouro = filtros.filtro_adaptativo_pads(img_ouro)
        except ImportError:
            print("  (FiltrosPCB não disponível — classificação heurística básica)")
        
        anomalias = self.classificador.classificar(
            mascara_diff, img_ouro, img_teste,
            mask_corpo_ouro, mask_pads_ouro
        )
        
        print(f"  Total de anomalias: {len(anomalias)}")
        
        # --- 6. VISUALIZAÇÃO ---
        print("\n[6/7] Gerando visualizações...")
        
        img_overlay = self.visualizador.gerar_overlay(
            img_ouro, img_teste, mascara_diff, anomalias
        )
        cv2.imwrite(f"{dir_saida}/08_overlay_anomalias.png", img_overlay)
        
        img_heatmap = self.visualizador.gerar_mapa_calor(mascara_diff)
        cv2.imwrite(f"{dir_saida}/09_heatmap.png", img_heatmap)
        
        img_zooms = self.visualizador.gerar_zoom_anomalias(
            img_ouro, img_teste, anomalias
        )
        cv2.imwrite(f"{dir_saida}/10_zooms_anomalias.png", img_zooms)
        
        # --- 7. RELATÓRIO ---
        print("\n[7/7] Gerando relatório...")
        
        # Contar por severidade
        por_sev = {}
        for a in anomalias:
            por_sev[a.severidade] = por_sev.get(a.severidade, 0) + 1
        
        # Score global de similaridade
        pixels_total = mascara_diff.size
        pixels_diff = int(np.sum(mascara_diff > 0))
        score = 1.0 - (pixels_diff / pixels_total) if pixels_total > 0 else 1.0
        
        resultado = ResultadoComparacao(
            placa_ouro_path=caminho_ouro,
            placa_teste_path=caminho_teste,
            timestamp=datetime.now().isoformat(),
            total_anomalias=len(anomalias),
            anomalias_por_severidade=por_sev,
            anomalias=anomalias,
            score_global_similaridade=round(score, 4),
            deslocamento_detectado=(
                info_alinhamento.get("deslocamento_x", 0.0),
                info_alinhamento.get("deslocamento_y", 0.0)
            ),
            rotacao_detectada=info_alinhamento.get("rotacao_graus", 0.0),
            escala_detectada=info_alinhamento.get("escala", 1.0)
        )
        
        # Exportar
        ExportadorRelatorio.para_json(resultado, f"{dir_saida}/relatorio.json")
        ExportadorRelatorio.para_txt(resultado, f"{dir_saida}/relatorio.txt")
        
        # Imprimir resumo
        self._imprimir_resumo(resultado)
        
        print("\n" + "=" * 75)
        print(f" CONCLUÍDO! Resultados em: {dir_saida}/")
        print("=" * 75)
        
        return resultado
    
    def _imprimir_resumo(self, resultado: ResultadoComparacao):
        """Imprime resumo executivo no console."""
        print("\n" + "-" * 75)
        print(" RESUMO EXECUTIVO")
        print("-" * 75)
        print(f"  Score de similaridade: {resultado.score_global_similaridade:.2%}")
        print(f"  Total de anomalias:    {resultado.total_anomalias}")
        
        for sev in ["CRITICA", "ALTA", "MEDIA", "BAIXA"]:
            qtd = resultado.anomalias_por_severidade.get(sev, 0)
            if qtd > 0:
                icone = {"CRITICA": "🔴", "ALTA": "🟠",
                         "MEDIA": "🟡", "BAIXA": "🟢"}[sev]
                print(f"    {icone} {sev:<10}: {qtd}")
        
        if resultado.anomalias:
            print("\n  TOP 5 anomalias mais severas:")
            for a in resultado.anomalias[:5]:
                print(f"    #{a.id} [{a.severidade}] {a.tipo} "
                      f"em {a.centro} — {a.descricao}")


# =============================================================================
# 9. PONTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    
    # --- Configuração ---
    config = ConfigAnomalias()
    
    # Ajustes customizados (opcional):
    # config.comparacao["metodo"] = "SSIM"        # Apenas SSIM
    # config.comparacao["threshold_absdiff"] = 30 # Mais sensível
    # config.comparacao["threshold_ssim"] = 0.70  # Mais sensível
    # config.classificacao["area_min_anomalia"] = 30
    
    # --- Executar detector ---
    detector = DetectorAnomaliasPCB(config)
    
    resultado = detector.detectar(
        caminho_ouro="placa_ouro.jpg",
        caminho_teste="placa_teste.jpg",
        dir_saida="saida_anomalias"
    )
    
    # --- Análise automática ---
    if resultado.total_anomalias == 0:
        print("\n✓ PLACA APROVADA — Nenhuma anomalia detectada.")
    elif resultado.score_global_similaridade > 0.95:
        print(f"\n✓ PLACA APROVADA COM RESSALVAS — Similaridade "
              f"{resultado.score_global_similaridade:.1%}")
    elif resultado.score_global_similaridade > 0.85:
        print(f"\n⚠ PLACA SUSPEITA — Similaridade "
              f"{resultado.score_global_similaridade:.1%}")
    else:
        print(f"\n✗ PLACA REPROVADA — Similaridade "
              f"{resultado.score_global_similaridade:.1%}")