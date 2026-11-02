"""Testes para Active Learning."""
import pytest
import tempfile
import shutil
from pathlib import Path
import numpy as np
import cv2

from core.active_learning import (
    ActiveLearningConfig,
    UncertaintyMethod,
    QueryStrategy,
    DetectionResult,
    LabeledSample,
    UncertaintyEstimator,
    QuerySelector,
    PseudoLabeler,
    create_active_learning_orchestrator,
)


def test_uncertainty_estimator():
    """Testa estimativa de incerteza."""
    estimator = UncertaintyEstimator(UncertaintyMethod.ENTROPY)
    
    # Probabilidades uniformes (alta entropia)
    probs_uniform = np.array([0.25, 0.25, 0.25, 0.25])
    result = estimator.estimate(probs_uniform)
    assert 'entropy' in result
    assert result['entropy'] > 0.9  # Alta entropia normalizada
    
    # Probabilidade concentrada (baixa entropia)
    probs_peaked = np.array([0.95, 0.03, 0.01, 0.01])
    result = estimator.estimate(probs_peaked)
    assert result['entropy'] < 0.3
    
    # Least confidence
    estimator_lc = UncertaintyEstimator(UncertaintyMethod.LEAST_CONFIDENCE)
    probs_peaked_lc = np.array([0.9, 0.04, 0.03, 0.03])
    result = estimator_lc.estimate(probs_peaked_lc)
    assert 'least_confidence' in result
    assert abs(result['least_confidence'] - 0.1) < 1e-10  # 1 - 0.9
    
    # Margin
    estimator_m = UncertaintyEstimator(UncertaintyMethod.MARGIN)
    probs_margin = np.array([0.9, 0.08, 0.01, 0.01])
    result = estimator_m.estimate(probs_margin)
    assert 'margin' in result
    assert 0.8 < result['margin'] < 0.9  # 0.9 - 0.08


def test_pseudo_labeler():
    """Testa geração de pseudo-labels."""
    config = ActiveLearningConfig(pseudo_label_confidence=0.8)
    labeler = PseudoLabeler(config)
    
    # Cria predições fictícias
    preds = [
        DetectionResult(
            bbox=(100, 100, 20, 20),
            confidence=0.9,
            class_id=0,
            uncertainty=0.1,
            uncertainties_per_class=np.array([]),
            entropy=0.1,
            margin=0.8,
            image_path="test.jpg",
            image_shape=(480, 640)
        ),
        DetectionResult(
            bbox=(200, 200, 20, 20),
            confidence=0.5,  # Baixa confiança
            class_id=1,
            uncertainty=0.5,
            uncertainties_per_class=np.array([]),
            entropy=0.5,
            margin=0.3,
            image_path="test.jpg",
            image_shape=(480, 640)
        ),
    ]
    
    labels = []
    pseudo = labeler.generate(preds, labels)
    
    # Apenas a primeira predição tem confiança > 0.8
    assert len(pseudo) == 1
    assert pseudo[0].is_pseudo
    assert pseudo[0].class_id == 0
    assert pseudo[0].confidence == 0.9


def test_query_selector():
    """Testa seleção de amostras para query."""
    config = ActiveLearningConfig(
        query_batch_size=2,
        uncertainty_method=UncertaintyMethod.ENTROPY
    )
    selector = QuerySelector(config)
    
    # Cria predições com diferentes incertezas
    preds = []
    for i in range(10):
        entropy = i / 10.0  # 0.0 a 0.9
        preds.append(DetectionResult(
            bbox=(100, 100, 20, 20),
            confidence=0.5,
            class_id=0,
            uncertainty=entropy,
            uncertainties_per_class=np.array([]),
            entropy=entropy,
            margin=0.5,
            image_path=f"test{i}.jpg",
            image_shape=(480, 640)
        ))
    
    selected = selector.select_samples(preds, set(), num_samples=3)
    
    # Deve selecionar as 3 com maior entropia (índices 7, 8, 9)
    assert len(selected) == 3
    assert 9 in selected  # Maior entropia
    assert 8 in selected
    assert 7 in selected


def test_labeled_sample_serialization():
    """Testa serialização de LabeledSample."""
    sample = LabeledSample(
        image_path="test.jpg",
        bbox=(0.5, 0.5, 0.1, 0.1),
        class_id=5,
        is_pseudo=True,
        confidence=0.95,
        annotator="pseudo",
        metadata={"uncertainty": 0.1}
    )
    
    # Serializa para dict
    data = {
        'image_path': sample.image_path,
        'bbox': sample.bbox,
        'class_id': sample.class_id,
        'is_pseudo': sample.is_pseudo,
        'confidence': sample.confidence,
        'annotator': sample.annotator,
        'metadata': sample.metadata
    }
    
    # Reconstrói
    restored = LabeledSample(**data)
    assert restored.image_path == sample.image_path
    assert restored.bbox == sample.bbox
    assert restored.class_id == sample.class_id
    assert restored.is_pseudo == sample.is_pseudo
    assert restored.confidence == sample.confidence
    assert restored.annotator == sample.annotator


def test_active_learning_config():
    """Testa configuração do Active Learning."""
    config = ActiveLearningConfig(
        model_path="models/test.onnx",
        dataset_dir="test_data",
        query_batch_size=10,
        pseudo_label_confidence=0.75,
    )
    
    assert config.model_path == "models/test.onnx"
    assert config.dataset_dir == "test_data"
    assert config.query_batch_size == 10
    assert config.pseudo_label_confidence == 0.75
    assert config.uncertainty_method == UncertaintyMethod.ENTROPY
    assert config.query_strategy == QueryStrategy.HYBRID


def test_detection_result():
    """Testa DetectionResult."""
    result = DetectionResult(
        bbox=(100, 100, 20, 20),
        confidence=0.85,
        class_id=3,
        uncertainty=0.2,
        uncertainties_per_class=np.array([0.1, 0.2, 0.3]),
        entropy=0.3,
        margin=0.6,
        image_path="test.jpg",
        image_shape=(480, 640)
    )
    
    assert result.confidence == 0.85
    assert result.class_id == 3
    assert result.entropy == 0.3
    assert result.margin == 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])